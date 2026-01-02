import time
import re
from tqdm import tqdm
from urllib.parse import urlparse
from playwright.sync_api import TimeoutError, ElementHandle
from platforms.base import ScraperBase
from core.browser import BrowserEngine
from core.insta_utils import InstaUtils

class InstagramScraper(ScraperBase):
    def __init__(self, headless: bool = True, user_data_dir: str = None):
        super().__init__(headless=headless, user_data_dir=user_data_dir)
        self.insta_utils = InstaUtils()
        self.browser = BrowserEngine(headless=headless, user_data_dir=user_data_dir)

        self.page = None

    def setup_page(self):

        if not self.page:

            self.page = self.browser.get_driver()

            self.driver = self.page

    def close(self):

        self.browser.quit_driver()


    def _get_full_sel(self, by: str, sel: str):
        if by == 'xpath':
            return f"xpath={sel}"
        elif by == 'css':
            return f"css={sel}"
        elif by == 'tag':
            return sel
        else:
            return sel

    def _find_element_with_selectors(self, selectors, by='xpath', timeout=10, wait=True, retries=3, retry_delay=0.2):
        if wait:
            timeout_ms = timeout * 1000
            for sel in selectors:
                full_sel = self._get_full_sel(by, sel)

                try:
                    self.page.wait_for_selector(full_sel, timeout=timeout_ms)
                    elem = self.page.query_selector(full_sel)
                    return elem
                except TimeoutError:
                    continue
            return None

        # FAST mode: no long blocking waits — quick retries only

        for sel in selectors:

            full_sel = self._get_full_sel(by, sel)


            for attempt in range(retries):
                elem = self.page.query_selector(full_sel)
                if elem:

                    return elem
                # small sleep between retries (non-blocking for long periods)
                if attempt < retries - 1:
                    self.page.wait_for_timeout(int(retry_delay * 1000))


        return None


    def _find_elements_with_selectors(self, selectors, by='xpath', timeout=10, wait=True, retries=3, retry_delay=0.2):
        if wait:
            timeout_ms = timeout * 1000

            for sel in selectors:

                full_sel = self._get_full_sel(by, sel)

                try:

                    self.page.wait_for_selector(full_sel, timeout=timeout_ms)

                    elements = self.page.query_selector_all(full_sel)

                    if elements:

                        return elements
                except TimeoutError:

                    continue

            return []

        # FAST mode

        for sel in selectors:

            full_sel = self._get_full_sel(by, sel)


            for attempt in range(retries):
                elements = self.page.query_selector_all(full_sel)
                if elements:

                    return elements
                if attempt < retries - 1:
                    self.page.wait_for_timeout(int(retry_delay * 1000))


        return []


    def _find_child_element(self, parent: ElementHandle, selectors, by='xpath', wait=False, retries=3, retry_delay=0.1):
        for sel in selectors:

            full_sel = self._get_full_sel(by, sel)


            if wait:
                for attempt in range(retries):
                    try:
                        elem = parent.query_selector(full_sel)
                        if elem:

                            return elem
                    except Exception:
                        self.insta_utils.log_info("exception for selector on attempt {}: {}".format(attempt + 1, sel))
                    if attempt < retries - 1:
                        self.page.wait_for_timeout(int(retry_delay * 1000))
            else:
                try:
                    elem = parent.query_selector(full_sel)
                    if elem:

                        return elem
                except Exception:

                    continue

        return None


    def _find_child_elements(self, parent: ElementHandle, selectors, by='xpath', wait=False, retries=3, retry_delay=0.1):
        for sel in selectors:

            full_sel = self._get_full_sel(by, sel)


            if wait:
                for attempt in range(retries):
                    try:
                        elements = parent.query_selector_all(full_sel)

                        if elements:

                            return elements
                    except Exception:
                        self.insta_utils.log_info("exception for selector on attempt {}: {}".format(attempt + 1, sel))
                    if attempt < retries - 1:
                        self.page.wait_for_timeout(int(retry_delay * 1000))
            else:
                try:
                    elements = parent.query_selector_all(full_sel)

                    if elements:

                        return elements
                except Exception:

                    continue

        return []

    def login(self, username: str = None, password: str = None, manual_login_timeout: int = 60):

        self.setup_page()
        self.page.goto("https://www.instagram.com/accounts/login/")

        def retry_goto(url, max_retries=3, timeout=5000):
            for attempt in range(1, max_retries + 1):
                try:

                    # Use 'commit' to minimize waiting - just wait for navigation to commit, not full load
                    self.page.goto(url, timeout=timeout, wait_until='commit')
                    # No additional wait_for_load_state - check URL immediately after commit
                    current_url = self.page.url

                    return True
                except Exception as e:
                    self.insta_utils.log_error(f"Attempt {attempt} failed: {e}")
                    time.sleep(2 * attempt)
            return False

        login_url = "https://www.instagram.com/accounts/login/"
        if not retry_goto(login_url, max_retries=3, timeout=10000):
            self.insta_utils.log_error("Cannot reach login page")
            return False

        # Immediately check if redirected (logged in) without waiting for load
        current_path = urlparse(self.page.url).path
        if "/accounts/login" not in current_path:
            self.insta_utils.log_success("Already logged in (redirect detected after commit)")
            # Optional: Brief wait for page to settle if needed, but avoid long waits
            time.sleep(2)  # Short sleep to let redirect settle
            return True
        else:
            self.insta_utils.log_info("On login page (no redirect), proceeding with login")

        if username and password:
            try:
                # Wait briefly for inputs to appear (since we didn't wait for full load)
                time.sleep(2)  # Adjust as needed
                user_input = self._find_element_with_selectors(["input[name='username']", "input[name='email']"], by='css', timeout=20)
                pwd_input = self._find_element_with_selectors(["input[name='password']", "input[name='pass']"], by='css', timeout=20)
                submit_btn = self._find_element_with_selectors(["button[type='submit']", "button[data-testid='login-button']"], by='css', timeout=10)
                user_input.fill(username)
                pwd_input.fill(password)
                if submit_btn:
                    submit_btn.click()
                else:
                    pwd_input.press("Enter")
                # After submit, wait for network idle with longer timeout
                self.page.wait_for_load_state("networkidle", timeout=60000)
            except Exception as e:
                self.insta_utils.log_error(f"Login failed: {e}")
                return False
        else:

            # For manual, go to home and wait for selector or URL change
            retry_goto("https://www.instagram.com/accounts/login/", max_retries=2, timeout=10000)
            try:
                self.page.wait_for_selector("svg[aria-label='Home']", timeout=manual_login_timeout * 1000)

            except Exception:
                # Fallback to URL check
                if "/accounts/login" not in urlparse(self.page.url).path:
                    self.insta_utils.log_info("Manual login: Home selector timeout, but URL indicates success")
                else:
                    self.insta_utils.log_error("Manual login timeout")
                    return False

        # Verify login via URL (no long waits)
        for _ in range(5):
            url_path = urlparse(self.page.url).path
            if "/accounts/login" not in url_path:
                self.insta_utils.log_success("Login successful")
                return True
            time.sleep(3)
            try:
                self.page.reload(timeout=30000)
                # Short wait after reload
                time.sleep(2)
            except:
                pass

        self.insta_utils.log_error("Login failed after verification")
        return False

    def blind_scrape(self, url: str = None, max_posts=10):

        self.setup_page()

        self.page.goto(url)

        result = self.search(text=None, max_posts=max_posts)


        return result

    def extract_posts(self):

        result = self.search(text=None)


        return result

    def search(self, text: str = None, start_time: str = None, end_time: str = None, max_posts=5):

        self.setup_page()

        if text:

            target = self.insta_utils.prepare_target(text)

            if not target:
                self.insta_utils.log_error("Could not build target URL from text.")
                return []
            self.page.goto(target)

            time.sleep(3)

        try:

            _ = self.page.url

        except Exception:
            self.insta_utils.log_error("No target and page not initialized.")
            return []
        try:

            article_selectors = ["article"]
            self._find_element_with_selectors(article_selectors, by='tag')

        except Exception:

            pass
        post_hrefs = []
        seen = set()
        scroll_rounds = 0
        current_url = self.page.url

        post_anchor_selectors = ["//a[contains(@href, '/p/') or contains(@href, '/reel/')]"]

        while len(post_hrefs) < max_posts and scroll_rounds < 30:

            anchors = self._find_elements_with_selectors(post_anchor_selectors, by='xpath')

            for a in anchors:
                try:

                    href = a.get_attribute("href")

                    if href.startswith('/'):

                        href = 'https://www.instagram.com' + href

                    if href and re.match(r'^https?://www\.instagram\.com/(p|reel)/[A-Za-z0-9_-]+/?$', href) and href not in seen:

                        seen.add(href)
                        post_hrefs.append(href)
                except:

                    continue
            self.insta_utils.random_delay(1.0, 2.0)

            self.insta_utils.scroll_page(self.page, pause=1.5, max_scrolls=2)

            scroll_rounds += 1

        results = []

        for href in post_hrefs[:max_posts]:

            try:
                post = self._scrape_single_post(href)

                if post is None:
                    self.insta_utils.log_error(f"Failed to scrape post {href}, saving scraped posts so far.")
                    return results
                post_time = post.get("timestamp")

                if post_time and (start_time or end_time):

                    keep = True
                    if start_time:

                        st = self.insta_utils.convert_date(start_time)

                        if st and post_time < st:
                            keep = False
                    if end_time:

                        et = self.insta_utils.convert_date(end_time)

                        if et and post_time > et:
                            keep = False
                    if not keep:

                        continue
                results.append(post)

                self.insta_utils.random_delay(2.0, 4.0)

            except Exception as e:
                self.insta_utils.log_error(f"Error scraping post {href}: {e}")
                return results

        self.page.goto(current_url)

        self.insta_utils.random_delay(1.0, 2.0)


        return results

    def _scrape_single_post(self, href: str) -> dict | None:

        data = {
            "url": href,
            "likes": None,
            "timestamp": None,
            "author": None,
            "caption": None,
            "mentions": [],
            "hashtags": [],
            "media": [],
            "comments": []
        }

        try:
            self.page.goto(href)

            self.insta_utils.random_delay(2.0, 4.0)

            main_selectors = ["//main[1]//hr[1]/following::div[1]"]

            main = self._find_element_with_selectors(main_selectors, by='xpath')

            if not main:
                raise TimeoutError("Main container not found.")
            # Author, timestamp, caption
            top_block_selectors = ["//main[1]//hr[1]/following::div[1]/div[1]"]

            top_blocks = self._find_elements_with_selectors(top_block_selectors, by='xpath')

            if len(top_blocks) >= 2:

                top = top_blocks[0]
                target_selectors = ["./div[1]/div[1]/div[2]/div[1]/span[1]/div[1]"]

                target = self._find_child_element(top, target_selectors, by='xpath')

                if not target:
                    raise ValueError("Target element not found.")
                author_selectors = [".//a[1]//span[1]"]

                author_el = self._find_child_element(target, author_selectors, by='xpath')
                data["author"] = author_el.text_content().strip() if author_el else None

                time_selectors = ["time"]

                time_tag = self._find_child_element(target, time_selectors, by='tag')
                data["timestamp"] = time_tag.get_attribute("datetime") if time_tag else None

                caption_selectors = ["./span[1]"]

                caption_el = self._find_child_element(target, caption_selectors, by='xpath')
                text = caption_el.text_content().strip() if caption_el else None
                data["caption"] = text

                if text:

                    data["mentions"] = re.findall(r'@\w+', text)
                    data["hashtags"] = re.findall(r'#\w+', text)

            else:

                # Fallback
                author_fallback_selectors = ["//main//hr[1]/preceding-sibling::div[1]/div[1]//div[2]//span[1]/div[1]"]

                author_el = self._find_element_with_selectors(author_fallback_selectors, by='xpath')
                if author_el:
                    data["author"] = author_el.text_content().strip() or None

                time_fallback_selectors = ["//main//section[1]/following::div[1]//time"]

                time_tag = self._find_element_with_selectors(time_fallback_selectors, by='xpath')
                if time_tag:
                    data["timestamp"] = time_tag.get_attribute("datetime") or None

            # Likes
            likes_selectors = ["//main[1]//section[1]/div[1]/span[2]", "//main[1]//section[2]/div[1]/div[1]/span[1]/a[1]/span[1]/span[1]"]

            likes_el = self._find_element_with_selectors(likes_selectors, by='xpath', timeout=5)
            data["likes"] = likes_el.text_content().strip() if likes_el else "0"

            # Media
            media_urls = []
            media_set = set()
            max_steps = 50
            steps = 0

            while steps < max_steps:

                steps += 1
                img_selectors = ["//main//div//ul//img","//main/div[1]/div[1]/div[1]/div[1]/div[1]//img","//main/div[1]/div[1]//div[@role='button']/div//img[1]"]

                imgs = self._find_elements_with_selectors(img_selectors, by='xpath',retries=1, wait=False)

                for im in imgs:
                    try:

                        src = im.get_attribute("src")

                        if src and src.startswith("https://") and src not in media_set:

                            media_set.add(src)
                            media_urls.append(src)
                    except:

                        continue
                vid_selectors = ["//video"]

                vids = self._find_elements_with_selectors(vid_selectors, by='xpath',retries=1, wait=False)

                for v in vids:
                    try:

                        src = v.get_attribute("src")

                        if src and src.startswith("https://") and src not in media_set:

                            media_set.add(src)
                            media_urls.append(src)
                    except:

                        continue
                    source_selectors = ["source"]

                    sources = self._find_child_elements(v, source_selectors, by='tag')

                    for s in sources:
                        try:

                            ssrc = s.get_attribute("src")

                            if ssrc and ssrc.startswith("https://") and ssrc not in media_set:

                                media_set.add(ssrc)
                                media_urls.append(ssrc)
                        except:

                            continue
                # Next button
                next_selectors = ["//button[@aria-label='Next' and ancestor::main]"]

                next_btn = self._find_element_with_selectors(next_selectors, by='xpath', wait=False,retries=1)

                if not next_btn:

                    break
                try:

                    next_btn.click()
                except Exception:

                    self.page.evaluate("btn => btn.click()", next_btn)
                self.insta_utils.random_delay(1.0, 2.0)

            data["media"] = media_urls

            # Comments

            data["comments"] = self._extract_comments(href)


            return data
        except Exception as e:
            self.insta_utils.log_error(f"_scrape_single_post failed for {href}: {e}")
            return None

    def _extract_comments(self, href: str):

        comments = []
        seen = set()
        # Scroll to load comments (try multiple selectors until success)
        comment_scroll_selectors = ["//main//hr[1]/following-sibling::div[1]", "//div[contains(@class, 'comments')]"]
        scrolled = False

        for sel in comment_scroll_selectors:

            locator = self.page.locator(f"xpath={sel}")  # Create Locator here
            if self.insta_utils.scroll_until_end(self.page, locator):

                scrolled = True
                break
        if not scrolled:
            self.insta_utils.log_info("Could not scroll comments section with any selector.")
        main_selectors = ["//main//hr[1]/following::div[1]/div[1]", "//article//section/following-sibling::div[1]/div[1]", "//div[contains(@class, 'comments')]/div[1]"]

        main = self._find_element_with_selectors(main_selectors, by='xpath')

        if not main:

            return comments
        block_selectors = ["./div", "./section", "./ul"]

        blocks = self._find_child_elements(main, block_selectors, by='xpath')

        if not blocks:

            return comments
        target_block = blocks[-1]

        try:
            h2_selectors = [".//h2", ".//div[contains(text(), 'No comments')]", ".//span[contains(@class, 'no-comments')]"]

            h2 = self._find_child_element(target_block, h2_selectors, by='xpath')

            if h2 and "No comments yet." in h2.text_content().strip():

                return []
        except:

            pass
        container_selectors = ["./div", "./ul/li", "./div[contains(@role, 'presentation')]/div"]

        containers = self._find_child_elements(target_block, container_selectors, by='xpath')

        for container in tqdm(containers, desc="Processing comments"):
            try:
                parsed = self.insta_utils.parse_instagram_comment(container)
                comments.append(parsed)
            except Exception as e:
                self.insta_utils.log_error(f"Error processing comment container: {e}")
                continue
        return comments