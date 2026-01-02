# platforms/x_scraper.py
from core.browser import BrowserEngine
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from platforms.base import ScraperBase
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
import json
import re

from core.utils import ScraperUtils


class XScraper(ScraperBase):
    def __init__(self, headless: bool = True, user_data_dir: str = None):
        super().__init__(headless=headless, user_data_dir=user_data_dir)
        self.browser_engine = BrowserEngine(headless=headless, user_data_dir=user_data_dir)
        self.page = self.browser_engine.create_driver()
        self.context = self.browser_engine.context
        self.driver = self.page

    def _find_element_with_selectors(self, selectors, timeout=10):
        """
        Try multiple selectors. Waits for the first visible one to appear and returns its locator.
        """
        for sel in selectors:
            try:
                locator = self.page.locator(sel)
                # wait_for will raise TimeoutError if not visible within timeout
                locator.wait_for(state='visible', timeout=timeout * 1000)
                return locator
            except PlaywrightTimeoutError:
                continue
            except Exception:
                continue
        return None

    def _find_elements_with_selectors(self, selectors):
        """
        Return a list of element locators (actual elements) for the first selector that has matches.
        """
        for sel in selectors:
            try:
                locator = self.page.locator(sel)
                count = locator.count()
                if count > 0:
                    # return actual element handles (static list) to mimic previous behavior
                    return [locator.nth(i) for i in range(count)]
            except Exception:
                continue
        return []

    def login(self, username: str = None, password: str = None):
        def retry_goto(url, max_retries=3, timeout=120000):
            for attempt in range(max_retries):
                try:
                    self.page.goto(url, timeout=timeout, wait_until="domcontentloaded")
                    self.page.wait_for_timeout(2000)
                    return True
                except Exception as e:
                    ScraperUtils.log_error(f"Attempt {attempt+1} failed for {url}: {e}")
                    if attempt == max_retries - 1:
                        return False
                    ScraperUtils.random_delay(5.0)
            return False

        if not retry_goto("https://x.com/home"):
            return False

        current_url = self.page.url
        if "/home" in current_url:
            home_selectors = [
                'div[data-testid="primaryColumn"]',
                'div[data-testid="HomeTimeline"]',
                'div[data-testid="Home"]'
            ]
            if self._find_element_with_selectors(home_selectors, timeout=15000):
                ScraperUtils.log_success("Already logged in via persistent session.")
                return True
            else:
                ScraperUtils.log_info("Home URL but content not fully loaded; attempting reload.")
                try:
                    self.page.reload()
                    self.page.wait_for_load_state('domcontentloaded', timeout=60000)
                    if self._find_element_with_selectors(home_selectors, timeout=15000):
                        ScraperUtils.log_success("Logged in after reload.")
                        return True
                except Exception:
                    pass

        ScraperUtils.log_info(f"Not logged in; at {current_url}. Proceeding to login.")

        if "/login" not in current_url and "/i/flow/login" not in current_url:
            if not retry_goto("https://x.com/i/flow/login"):
                return False

        if username and password:
            try:
                username_selectors = [
                    'input[name="text"][autocomplete="username"]',
                    'input[name="text"]'
                ]
                username_input = self._find_element_with_selectors(username_selectors, timeout=30000)
                if not username_input:
                    raise PlaywrightTimeoutError("Username input not found.")
                username_input.click()
                username_input.fill(username)

                next_button_selectors = [
                    'div[role="button"]:has-text("Next")',
                    'xpath=//div[@role="button"]//span[contains(text(), "Next")]/ancestor::div[@role="button"]',
                    'xpath=//button[.//span[contains(text(), "Next")]]'
                ]
                next_btn = self._find_element_with_selectors(next_button_selectors, timeout=10000)
                if next_btn:
                    next_btn.click()
                    self.page.wait_for_timeout(3000)
                else:
                    raise PlaywrightTimeoutError("Next button not found.")

                unusual_input = self._find_element_with_selectors(username_selectors, timeout=5000)
                if unusual_input:
                    handle = username.split('@')[0] if '@' in username else username
                    unusual_input.fill(handle)
                    confirm_btn = self._find_element_with_selectors(next_button_selectors, timeout=10000)
                    if confirm_btn:
                        confirm_btn.click()
                        self.page.wait_for_timeout(3000)

                password_selectors = [
                    'input[name="password"][autocomplete="current-password"]',
                    'input[name="password"]'
                ]
                password_input = self._find_element_with_selectors(password_selectors, timeout=30000)
                if not password_input:
                    raise PlaywrightTimeoutError("Password input not found.")
                password_input.click()
                password_input.fill(password)

                login_button_selectors = [
                    'div[role="button"]:has-text("Log in")',
                    'xpath=//div[@role="button"]//span[contains(text(), "Log in")]/ancestor::div[@role="button"]',
                    'xpath=//button[.//span[contains(text(), "Log in")]]'
                ]
                login_btn = self._find_element_with_selectors(login_button_selectors, timeout=10000)
                if login_btn:
                    login_btn.click()
                    self.page.wait_for_timeout(5000)
                else:
                    raise PlaywrightTimeoutError("Login button not found.")

                try:
                    self.page.wait_for_url(lambda url: "/login" not in url and "/i/flow" not in url, timeout=15000)
                except PlaywrightTimeoutError:
                    ScraperUtils.log_info("URL check timeout, but proceeding...")

                popup_selectors = [
                    'div[role="button"]:has-text("Skip")',
                    'div[role="button"]:has-text("Not now")'
                ]
                try:
                    for _ in range(2):
                        popup_btn = self._find_element_with_selectors(popup_selectors, timeout=5000)
                        if popup_btn:
                            popup_btn.click()
                            self.page.wait_for_timeout(1000)
                except PlaywrightTimeoutError:
                    pass

            except Exception as e:
                ScraperUtils.log_error(f"Auto login failed: {e}")
                return False
        else:
            if self.headless:
                ScraperUtils.log_error("No credentials provided and headless mode enabled; cannot perform manual login.")
                return False
            try:
                print("Please complete login manually in the opened browser window.")
                input("Press Enter when login is complete and you are on the home page...")
                popup_selectors = [
                    'div[role="button"]:has-text("Skip")',
                    'div[role="button"]:has-text("Not now")'
                ]
                try:
                    popup_btn = self._find_element_with_selectors(popup_selectors, timeout=5000)
                    if popup_btn:
                        popup_btn.click()
                except PlaywrightTimeoutError:
                    pass
            except Exception as e:
                ScraperUtils.log_error(f"Manual login setup failed: {e}")
                return False

        try:
            if not retry_goto("https://x.com/home"):
                return False
            home_selectors = ['div[data-testid="primaryColumn"]', 'div[data-testid="HomeTimeline"]']
            if self._find_element_with_selectors(home_selectors, timeout=15000):
                ScraperUtils.log_success("Login verified.")
                return True
            else:
                ScraperUtils.log_error(f"Login verification failed. Current URL: {self.page.url}")
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
            return f"https://x.com/hashtag/{tag}"
        if " " in text:
            return f"https://x.com/search?q={text.replace(' ', '%20')}"
        return f"https://x.com/{text}"

    def blind_scrape(self, url: str = None, max_posts=10):
        if url:
            self.page.goto(url, wait_until="domcontentloaded")
            self.page.wait_for_timeout(2000)
        return self.search(text=None, max_posts=max_posts, current_url=self.page.url)

    def search(self, text: str = None, start_time: str = None, end_time: str = None, max_posts=5, current_url: str = None):
        if text and re.match(r'^https?://x\.com/.+/status/[0-9]+$', text):
            post = self._scrape_single_post(text)
            return [post] if post else []

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
        scroll_rounds = 0
        url_pattern = re.compile(r'^https?://(www\.)?x\.com/.+/status/[0-9]+(?:\?.*)?$')
        max_scrolls = 50

        while len(post_hrefs) < max_posts and scroll_rounds < max_scrolls:
            scroll_rounds += 1
            print(f"[DEBUG] Scroll Round {scroll_rounds}/{max_scrolls} | Current Posts: {len(post_hrefs)}")

            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            self.page.wait_for_timeout(1500)

            try:
                anchors_hrefs = self.page.evaluate("""
                    () => Array.from(document.querySelectorAll('a[href*="/status/"]')).map(a => a.href)
                """)
            except Exception as e:
                print(f"[DEBUG] JS Evaluation failed: {e}")
                anchors_hrefs = []

            # Check for immediate stop condition INSIDE loop processing anchors
            found_new_this_round = 0
            for i, href in enumerate(anchors_hrefs):
                if href in seen:
                    continue

                if url_pattern.match(href):
                    seen.add(href)
                    post_hrefs.append(href)
                    found_new_this_round += 1

            # FIX: Break immediately if we hit max_posts
            if len(post_hrefs) >= max_posts:
                print(f"[DEBUG] Target reached ({len(post_hrefs)}). Breaking scroll loop immediately.")
                break

            if found_new_this_round > 0:
                print(f"[SUCCESS] Found {found_new_this_round} new posts. Total: {len(post_hrefs)}")

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
                        try:
                            self.page.goto(current_url, timeout=60000)
                            self.page.wait_for_timeout(1000)
                        except Exception:
                            pass

                except Exception as e:
                    ScraperUtils.log_error(f"Error scraping post {href}: {e}")
                    try:
                        self.page.goto(current_url, timeout=60000)
                    except Exception:
                        pass

                ScraperUtils.random_delay(1.5, 3.0)
                progress.update(task_scrape, advance=1)

        return results

    def _extract_main_post_from_dom(self):
        try:
            data = {}
            text_el = self.page.locator('div[data-testid="tweetText"]').first
            if text_el.count() > 0:
                data["text"] = text_el.inner_text()

            user_el = self.page.locator('div[data-testid="User-Name"] a').first
            if user_el.count() > 0:
                handle = user_el.get_attribute('href').replace('/', '')
                data["author"] = f"https://x.com/{handle}"

            time_el = self.page.locator('time').first
            if time_el.count() > 0:
                data["timestamp"] = time_el.get_attribute('datetime')

            def get_metric(testid):
                try:
                    el = self.page.locator(f'div[data-testid="{testid}"]').first
                    if el.count() > 0:
                        val = el.locator('span').all()[-1].inner_text()
                        return val
                except Exception:
                    return "0"

            data["likes"] = get_metric("like")
            data["retweets"] = get_metric("retweet")
            data["replies"] = get_metric("reply")
            data["views"] = get_metric("views")
            return data
        except Exception as e:
            ScraperUtils.log_error(f"DOM Fallback failed: {e}")
            return None

    def _scrape_single_post(self, href: str) -> dict | None:
        data = {
            "url": href, "likes": "0", "retweets": "0", "replies": "0",
            "timestamp": None, "author": None, "text": None,
            "mentions": [], "hashtags": [], "media": [], "comments": []
        }

        captured = []

        def handle_response(response):
            # Intercept all TweetDetail responses
            try:
                if response.status == 200 and 'graphql' in response.url and 'TweetDetail' in response.url:
                    body = response.body()
                    body_str = body.decode('utf-8') if isinstance(body, bytes) else body
                    json_body = json.loads(body_str)
                    captured.append(json_body)
            except Exception as e:
                print(f"[ERROR] Failed to parse response: {e}")

        # Register listener
        self.page.on("response", handle_response)

        try:
            try:
                self.page.goto(href, wait_until="domcontentloaded")
                # Wait for network idle to ensure all initial requests (including comments) finish
                try:
                    self.page.wait_for_load_state('networkidle', timeout=15000)
                except Exception:
                    self.page.wait_for_timeout(2000)
            except Exception as e:
                ScraperUtils.log_error(f"Navigation failed: {e}")
                return None
        finally:
            # Always remove the listener
            try:
                self.page.off("response", handle_response)
            except Exception:
                try:
                    # older fallback name if present
                    self.page.remove_listener("response", handle_response)
                except Exception:
                    pass

        ScraperUtils.log_info(f"Parsing {len(captured)} captured responses.")

        # --- NEW LOGIC: EXTRACT INITIAL COMMENTS ---
        initial_comments = []

        for body in captured:
            try:
                batch_comments = ScraperUtils.parse_comments_from_json(body)
                for c in batch_comments:
                    if c not in initial_comments:
                        initial_comments.append(c)
            except Exception as e:
                ScraperUtils.log_error(f"Error parsing initial comments from JSON: {e}")

        ScraperUtils.log_info(f"Found {len(initial_comments)} initial comments in page load.")

        # --- MAIN POST EXTRACTION ---
        extracted = None
        for body in captured:
            try:
                extracted = ScraperUtils.parse_tweet_json(body)
                if extracted.get("post", {}).get("id"):
                    ScraperUtils.log_success("Main tweet extracted successfully.")
                    break
            except Exception as e:
                # skip malformed capture
                continue

        if extracted and extracted.get("post"):
            post_data = extracted["post"]

            # Map structured data to flat 'data' dict
            data["id"] = post_data["id"]
            data["timestamp"] = post_data["created_at"]
            data["text"] = post_data["text"]

            if data["text"]:
                data["mentions"] = re.findall(r'@\w+', data["text"])
                data["hashtags"] = re.findall(r'#\w+', data["text"])

            # Author mapping
            author = post_data.get("author", {})
            screen_name = author.get("screen_name")
            data["author"] = f"https://x.com/{screen_name}" if screen_name else None

            # Metrics mapping
            metrics = post_data.get("metrics", {})
            data["likes"] = str(metrics.get("favorite_count") or 0)
            data["replies"] = str(metrics.get("reply_count") or 0)
            data["retweets"] = str(metrics.get("retweet_count") or 0)
            data["quote_count"] = str(metrics.get("quote_count") or 0)
            data["views"] = str(metrics.get("views_count") or 0)

            # Media mapping (already a list)
            data["media"] = post_data.get("media", [])

            # Entities
            data["entities"] = post_data.get("entities", {})

            if "repost" in extracted:
                data["repost"] = extracted["repost"]

            # --- COMMENTS EXTRACTION ---
            ScraperUtils.log_info("Starting additional comment extraction via scroll...")
            additional_comments = ScraperUtils.extract_comments(self.page)

            # Merge initial and additional comments
            final_comments_list = []
            seen_comments = set()

            for c in initial_comments + additional_comments:
                key = f"{c.get('user', '')}||{c.get('text', '')[:200]}"
                if key not in seen_comments:
                    seen_comments.add(key)
                    final_comments_list.append(c)

            ScraperUtils.log_info(f"Total comments extracted: {len(final_comments_list)}.")
            data["comments"] = final_comments_list

            return data
        else:
            ScraperUtils.log_info("GraphQL data missing, attempting DOM extraction...")
            # DOM Fallback
            try:
                text_el = self.page.locator('div[data-testid="tweetText"]').first
                if text_el.count() > 0:
                    data["text"] = text_el.inner_text()

                user_el = self.page.locator('div[data-testid="User-Name"] a').first
                if user_el.count() > 0:
                    handle = user_el.get_attribute('href').replace('/', '')
                    data["author"] = f"https://x.com/{handle}"

                time_el = self.page.locator('time').first
                if time_el.count() > 0:
                    data["timestamp"] = time_el.get_attribute('datetime')

                if data["text"]:
                    data["mentions"] = re.findall(r'@\w+', data["text"])
                    data["hashtags"] = re.findall(r'#\w+', data["text"])

                data["comments"] = []
                return data
            except Exception as e:
                ScraperUtils.log_error(f"DOM Fallback failed: {e}")
                return None

    def close(self):
        self.browser_engine.quit_driver()