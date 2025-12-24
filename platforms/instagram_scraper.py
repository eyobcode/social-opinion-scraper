# platforms/instagram_scraper.py
from core.browser import BrowserEngine
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from platforms.base import ScraperBase
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
import json
import os
import re
import time
from datetime import datetime

# Import ScraperUtils
from core.utils import ScraperUtils

class InstagramScraper(ScraperBase):
    def __init__(self, headless: bool = True, user_data_dir: str = None):
        super().__init__(headless=headless, user_data_dir=user_data_dir)
        self.browser_engine = BrowserEngine(headless=headless, user_data_dir=user_data_dir)
        self.page = self.browser_engine.create_driver()
        self.context = self.browser_engine.context
        self.driver = self.page

    def _find_element_with_selectors(self, selectors, timeout=10):
        """
        Try multiple selectors using Playwright.
        """
        for sel in selectors:
            try:
                locator = self.page.locator(sel)
                # Playwright wait is in ms, input is seconds.
                locator.wait_for(state='visible', timeout=timeout * 1000)
                return locator
            except PlaywrightTimeoutError:
                continue
            except Exception:
                continue
        return None

    def _find_elements_with_selectors(self, selectors):
        """
        Find elements using Playwright.
        """
        for sel in selectors:
            try:
                locator = self.page.locator(sel)
                # Playwright locator.all() returns array of ElementHandles
                elements = locator.all()
                if elements:
                    # Return raw handles for compatibility with existing utility code if needed
                    # Note: Playwright ElementHandles are raw, not Locators like in Selenium
                    return elements
            except Exception:
                continue
        return []

    def login(self, username: str = None, password: str = None, cookie_path="cookies/instagram_cookies.json"):
        if not os.path.exists(cookie_path):
            ScraperUtils.log_info(f"Cookie file not found at {cookie_path}. Will attempt manual login.")

        self.browser_engine.get_driver()
        self.wait = self.page

        try:
            self.page.goto("https://www.instagram.com/")
            # Instagram often has loading spins, wait for network idle or specific elements
            try:
                self.page.wait_for_load_state('domcontentloaded', timeout=60000)
                self.page.wait_for_timeout(2000)
            except Exception:
                pass
        except Exception as e:
            ScraperUtils.log_error(f"Could not open instagram.com: {e}")
            return False

        # Try cookie login
        if ScraperUtils.load_cookies(self.page):
            self.page.reload()
            self.page.wait_for_timeout(5000)
            if "instagram.com" in self.page.url and "/accounts/login" not in self.page.url:
                ScraperUtils.log_success("Logged in with cookies.")
                return True

        # Fallback to credentials
        if not username or not password:
            ScraperUtils.log_error("No valid session cookies and no credentials provided.")
            return False

        try:
            self.page.goto("https://www.instagram.com/accounts/login/")
            # Wait for login form
            self.page.wait_for_timeout(5000)

            username_selectors = [
                "input[name='username']",
                "input[name='email']"
            ]
            password_selectors = [
                "input[name='password']",
                "input[name='pass']"
            ]

            # Wait for username input
            username_input = self._find_element_with_selectors(username_selectors, timeout=15000)
            if not username_input:
                raise PlaywrightTimeoutError("Login inputs not found.")

            username_input.fill(username)
            ScraperUtils.random_delay(0.5, 1.0)

            password_input = self._find_element_with_selectors(password_selectors, timeout=5000)
            if not password_input:
                raise PlaywrightTimeoutError("Password input not found.")

            password_input.fill(password)
            password_input.press("Enter")

            # Wait for login result
            ScraperUtils.random_delay(5.0, 8.0)

        except Exception as e:
            ScraperUtils.log_error(f"Login failed: {e}")
            return False

        # Handle post-login popup
        popup_selectors = ["//main//section/following::div[1]//div[@role='button']"]
        try:
            btn = self._find_element_with_selectors(popup_selectors)
            if btn:
                btn.click()
                ScraperUtils.log_info("Successfully clicked popup button.")
        except Exception as e:
            ScraperUtils.log_info(f"Popup click attempt failed: {e}")

        # Verify login
        try:
            self.page.reload()
            self.page.wait_for_timeout(3000)
            home_selectors = ["//main[@aria-label='Home']"]
            if self._find_element_with_selectors(home_selectors) or "login" not in self.page.url:
                ScraperUtils.log_success("Login verified.")
                return True
            else:
                ScraperUtils.log_error(f"Login failed or challenge required. URL: {self.page.url}")
                return False
        except Exception as e:
            ScraperUtils.log_error(f"Post-login verification error: {e}")
            return False

    @staticmethod
    def prepare_target(text: str = None):
        if not text:
            return None
        text = text.strip()
        if text.startswith("#"):
            tag = text[1:]
            return f"https://www.instagram.com/explore/tags/{tag}/"
        if " " in text:
            return f"https://www.instagram.com/explore/tags/{text.replace(' ', '%20')}/"
        return f"https://www.instagram.com/{text}"

    def blind_scrape(self, url: str = None, max_posts=10):
        if url:
            self.page.goto(url, wait_until="domcontentloaded")
            self.page.wait_for_timeout(2000)
        return self.search(text=None, max_posts=max_posts)

    def search(self, text: str = None, start_time: str = None, end_time: str = None, max_posts=5, current_url: str = None):
        if text:
            target = self.prepare_target(text)
            if not target:
                ScraperUtils.log_error("Could not build target URL from text.")
                return []
            self.page.goto(target, wait_until="domcontentloaded")
            self.page.wait_for_timeout(2000)
            current_url = self.page.url
        elif not current_url:
            current_url = self.page.url

        ScraperUtils.log_info(f"Starting scrape on: {current_url}")

        # PHASE 1: Collect URLs
        post_hrefs = []
        seen = set()

        # Instagram specific pattern for posts (reels, single photos)
        url_pattern = re.compile(r'^https?://(www\.)?instagram\.com/(p|reel)/[A-Za-z0-9_-]+/?$')

        print(f"--- Phase 1: Collecting URLs (Need {max_posts}) ---")

        scroll_rounds = 0
        max_scrolls = 50

        while len(post_hrefs) < max_posts and scroll_rounds < max_scrolls:
            scroll_rounds += 1
            print(f"[DEBUG] Scroll Round {scroll_rounds}/{max_scrolls} | Current Posts: {len(post_hrefs)}")

            # Playwright JS scroll
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            self.page.wait_for_timeout(1500)

            try:
                # Use Playwright querySelectorAll equivalent
                anchors = self.page.locator('//a').all()

                for a in anchors:
                    try:
                        href = a.get_attribute('href')
                        if href and href not in seen:
                            if url_pattern.match(href):
                                seen.add(href)
                                post_hrefs.append(href)
                    except Exception:
                        pass
            except Exception as e:
                print(f"[DEBUG] Anchor extraction failed: {e}")

            # Check for immediate stop condition
            if len(post_hrefs) >= max_posts:
                print(f"[DEBUG] Target reached ({len(post_hrefs)}). Breaking scroll loop immediately.")
                break

            if len(post_hrefs) > 0:
                print(f"[SUCCESS] Found new posts. Total: {len(post_hrefs)}")

        print(f"--- Collection Complete. Total: {len(post_hrefs)} ---")

        # PHASE 2: Visit and Extract
        results = []
        print(f"--- Phase 2: Visiting posts ---")

        target_posts = post_hrefs[:max_posts]

        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(), TextColumn("[progress.percentage]{task.percentage:>3.0f}%")) as progress:
            task_scrape = progress.add_task("[cyan]Scraping posts...", total=len(target_posts))

            for i, href in enumerate(target_posts):
                print(f"[{i+1}/{len(target_posts)}] Visiting: {href}")
                try:
                    post = self._scrape_single_post(href)

                    if post:
                        # Date filtering
                        if post_time := post.get("timestamp"):
                            if start_time or end_time:
                                post_time_dt = ScraperUtils.convert_date(post_time)
                                keep = True
                                if start_time:
                                    st = ScraperUtils.convert_date(start_time)
                                    if st and post_time_dt < st: keep = False
                                if end_time:
                                    et = ScraperUtils.convert_date(end_time)
                                    if et and post_time_dt > et: keep = False
                                if not keep:
                                    print("Skipping post due to date filter.")
                                    continue
                        results.append(post)
                    else:
                        print(f"Failed to extract data for {href}")

                    if self.page.url != current_url:
                        print(f"Returning to base: {current_url}")
                        self.page.goto(current_url, timeout=60000)
                        self.page.wait_for_timeout(1000)

                except Exception as e:
                    ScraperUtils.log_error(f"Error scraping post {href}: {e}")
                    self.page.goto(current_url, timeout=60000)

                ScraperUtils.random_delay(2.0, 4.0)
                progress.update(task_scrape, advance=1)

        return results

    def _parse_comment_node(self, node: dict):
        """Helper to parse a single comment node from JSON."""
        user_obj = node.get('user', {})
        username = user_obj.get('username')
        user_url = f"https://www.instagram.com/{username}" if username else None

        comment = {
            "user": user_url,
            "text": node.get('text'),
            "timestamp": node.get('created_at'),
            "likes": str(node.get('like_count', 0))
        }

        # Handle profile pic
        profile_pic = user_obj.get('profile_pic_url')
        if profile_pic:
            comment["avatar_url"] = profile_pic

        return comment

    @staticmethod
    def parse_comments_from_json(data: dict | str):
        """
        Parses comments from the specific JSON structure provided.
        Structure: data['data']['xdt_api__v1__media__media_id__comments__connection']['edges']
        """
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except:
                return []

        comments = []

        # Navigate to the comments connection
        try:
            xdt_data = data.get('data', {})
            connection = xdt_data.get('xdt_api__v1__media__media_id__comments__connection', {})
            edges = connection.get('edges', [])

            for edge in edges:
                node = edge.get('node', {})
                if not node:
                    continue

                # Map fields to standard format
                comment = {
                    "user": None,
                    "text": None,
                    "timestamp": None,
                    "likes": "0",
                    "avatar_url": None
                }

                # User
                user_obj = node.get('user', {})
                username = user_obj.get('username')
                comment["user"] = f"https://www.instagram.com/{username}" if username else None

                # Profile Pic
                comment["avatar_url"] = user_obj.get('profile_pic_url')

                # Text
                comment["text"] = node.get('text')

                # Timestamp
                comment["timestamp"] = node.get('created_at')

                # Likes
                comment["likes"] = str(node.get('like_count', 0))

                comments.append(comment)

        except Exception as e:
            ScraperUtils.log_error(f"Error parsing comments JSON: {e}")

        return comments

    def _scrape_single_post(self, href: str) -> dict | None:
        data = {
            "url": href,
            "likes": "0",
            "timestamp": None,
            "author": None,
            "caption": None,
            "mentions": [],
            "hashtags": [],
            "media": [],
            "comments": []
        }

        all_comments = []

        # --- INTERCEPT REQUESTS ---
        # Define the pattern for the XDT comment API endpoint
        # This allows us to capture the JSON without scrolling specifically
        def handle_response(response):
            # The URL pattern for comments is quite specific
            if 'xdt_api__v1__media__media_id__comments__connection' in response.url and response.status == 200:
                try:
                    body = response.body()
                    body_str = body.decode('utf-8') if isinstance(body, bytes) else body
                    json_body = json.loads(body_str)

                    # Parse the JSON directly
                    new_comments = self.parse_comments_from_json(json_body)

                    if new_comments:
                        all_comments.extend(new_comments)

                except Exception as e:
                    ScraperUtils.log_error(f"Failed to parse comment JSON: {e}")

        self.page.on("response", handle_response)

        # --- MAIN POST EXTRACTION (DOM based for Media/Caption) ---
        try:
            self.page.goto(href, wait_until="domcontentloaded")
            self.page.wait_for_timeout(3000)
        except Exception as e:
            ScraperUtils.log_error(f"Navigation failed: {e}")
            return None

        # Extract basic info from DOM
        try:
            main_selectors = ["//main[1]//hr[1]/following::div[1]", "//main[@aria-label='Home']//hr[1]/following-sibling::div[1]"]
            main = self._find_element_with_selectors(main_selectors)

            if main:
                # Author, Timestamp, Caption
                # Note: DOM selectors for Instagram are brittle.
                top_block_selectors = ["//main[1]//hr[1]/following::div[1]/div[1]"]
                top_blocks = self._find_elements_with_selectors(top_block_selectors)

                if len(top_blocks) >= 2:
                    top = top_blocks[0]
                    target_selectors = ["./div[1]/div[1]/div[2]/div[1]/span[1]/div[1]"]
                    target = self._find_child_element(top, target_selectors)

                    if not target:
                        raise Exception("Target element not found.")

                    # Author
                    author_fallback_selectors = [".//a[1]//span[1]"]
                    author_el = self._find_child_element(target, author_fallback_selectors)
                    if author_el:
                        data["author"] = author_el.text.strip()

                    # Timestamp
                    time_fallback_selectors = ["//main//section[1]/following::div[1]//time"]
                    time_tag = self._find_child_element(target, time_fallback_selectors)
                    if time_tag:
                        data["timestamp"] = time_tag.get_attribute('datetime') or time_tag.get_attribute('title')

                    # Caption
                    caption_fallback_selectors = ["./span[1]"]
                    caption_el = self._find_child_element(target, caption_fallback_selectors)
                    if caption_el:
                        text = caption_el.text.strip()
                        data["caption"] = text

                        if text:
                            data["mentions"] = re.findall(r'@\w+', text)
                            data["hashtags"] = re.findall(r'#\w+', text)

                    # Likes
                    likes_selectors = [
                        "//main[1]//section[1]/div[1]/span[2]",
                        "//main[1]//section[2]/div[1]/div[1]/span[1]/a[1]/span[1]"
                    ]
                    likes_el = self._find_element_with_selectors(likes_selectors, timeout=5)
                    data["likes"] = likes_el.text.strip() if likes_el else "0"

            # Media Extraction (Simple DOM check)
            media_urls = []
            # Look for images in the main block
            # Instagram uses complex lazy loading for media.
            # We will do a basic extraction.
            img_selectors = ["//main[1]//div//ul//img", "//main[1]//div[1]/div[1]/div[1]/img"]
            imgs = self._find_elements_with_selectors(img_selectors)
            for im in imgs:
                try:
                    src = im.get_attribute('src')
                    if src and src.startswith('https://') and src not in media_urls:
                        media_urls.append(src)
                except Exception:
                    pass

            data["media"] = media_urls

            # Assign JSON captured comments
            # We filter duplicates based on user+text
            seen_comments = {}
            final_comments = []

            for c in all_comments:
                key = f"{c.get('user', '')}||{c.get('text', '')[:200]}"
                if key not in seen_comments:
                    seen_comments[key] = c
                    final_comments.append(c)

            data["comments"] = final_comments

            return data

        except Exception as e:
            ScraperUtils.log_error(f"Scraping failed for {href}: {e}")
            return None

    def close(self):
        self.browser_engine.quit_driver()