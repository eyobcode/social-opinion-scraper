# platforms/x_scraper.py
from core.browser import BrowserEngine
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from platforms.base import ScraperBase
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
import json
import time
import re
from pprint import pprint

class XScraper(ScraperBase):
    def __init__(self, headless: bool = True, user_data_dir: str = None):
        super().__init__(headless=headless, user_data_dir=user_data_dir)
        self.browser_engine = BrowserEngine(headless=headless, user_data_dir=user_data_dir)
        self.page = self.browser_engine.create_driver()
        self.context = self.browser_engine.context
        self.driver = self.page

    def _find_element_with_selectors(self, selectors, timeout=10):
        for sel in selectors:
            try:
                elem = self.page.locator(sel)
                if elem.count() > 0:
                    elem.wait_for(state='visible', timeout=timeout * 1000)
                    return elem
            except PlaywrightTimeoutError:
                continue
            except Exception:
                continue
        return None

    def _find_elements_with_selectors(self, selectors):
        for sel in selectors:
            try:
                elements = self.page.locator(sel).all()
                if elements:
                    return elements
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
                    self.utils.log_error(f"Attempt {attempt+1} failed for {url}: {e}")
                    if attempt == max_retries - 1:
                        return False
                    time.sleep(5)
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
                self.utils.log_success("Already logged in via persistent session.")
                return True
            else:
                self.utils.log_info("Home URL but content not fully loaded; attempting reload.")
                self.page.reload()
                self.page.wait_for_load_state('domcontentloaded', timeout=60000)
                if self._find_element_with_selectors(home_selectors, timeout=15000):
                    self.utils.log_success("Logged in after reload.")
                    return True

        self.utils.log_info(f"Not logged in; at {current_url}. Proceeding to login.")

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
                    self.utils.log_info("URL check timeout, but proceeding...")

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
                self.utils.log_error(f"Auto login failed: {e}")
                return False
        else:
            if self.headless:
                self.utils.log_error("No credentials provided and headless mode enabled; cannot perform manual login.")
                return False
            try:
                print("Please complete the login manually in the opened browser window.")
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
                self.utils.log_error(f"Manual login setup failed: {e}")
                return False

        try:
            if not retry_goto("https://x.com/home"):
                return False
            home_selectors = ['div[data-testid="primaryColumn"]', 'div[data-testid="HomeTimeline"]']
            if self._find_element_with_selectors(home_selectors, timeout=15000):
                self.utils.log_success("Login verified.")
                return True
            else:
                self.utils.log_error(f"Login verification failed. Current URL: {self.page.url}")
                return False
        except Exception as e:
            self.utils.log_error(f"Post-login verification error: {e}")
            return False

    def prepare_target(self, text: str = None):
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
                self.utils.log_error("Could not build target URL from text.")
                return []
            self.page.goto(target, wait_until="domcontentloaded")
            self.page.wait_for_timeout(2000)
            current_url = self.page.url
        elif not current_url:
            current_url = self.page.url

        self.utils.log_info(f"Starting scrape on: {current_url}")

        # PHASE 1: Collect URLs
        post_hrefs = []
        seen = set()
        scroll_rounds = 0
        url_pattern = re.compile(r'^https?://(www\.)?x\.com/.+/status/[0-9]+(?:\?.*)?$')

        print(f"--- Phase 1: Collecting URLs (Need {max_posts}) ---")

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

            # Check for immediate stop condition INSIDE the loop processing anchors
            # This prevents the "Found 17/2" issue
            found_new_this_round = 0
            for i, href in enumerate(anchors_hrefs):
                if href in seen:
                    continue

                if url_pattern.match(href):
                    seen.add(href)
                    post_hrefs.append(href)
                    found_new_this_round += 1

            # FIX: Break immediately if we hit max_posts, even if we found many in one scroll
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
                                post_time_dt = self.utils.convert_date(post_time)
                                keep = True
                                if start_time:
                                    st = self.utils.convert_date(start_time)
                                    if st and post_time_dt < st: keep = False
                                if end_time:
                                    et = self.utils.convert_date(end_time)
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
                    self.utils.log_error(f"Error scraping post {href}: {e}")
                    self.page.goto(current_url, timeout=60000)

                self.utils.random_delay(1.5, 3.0)
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
                except: return "0"

            data["likes"] = get_metric("like")
            data["retweets"] = get_metric("retweet")
            data["replies"] = get_metric("reply")
            data["views"] = get_metric("views")
            return data
        except Exception as e:
            self.utils.log_error(f"DOM Fallback failed: {e}")
            return None

    def _extract_main_post(self, data):
        """
        Extracts the main post and optional repost from given JSON data.
        Uses the reference logic provided to handle nested structures.
        """
        post = {
            "id": None,
            "created_at": None,
            "text": None,
            "author": {
                "name": None,
                "screen_name": None,
                "rest_id": None,
                "avatar_url": None
            },
            "metrics": {
                "favorite_count": None,
                "reply_count": None,
                "retweet_count": None,
                "quote_count": None,
                "views_count": None
            },
            "entities": {
                "hashtags": [],
                "urls": [],
                "user_mentions": []
            },
            "media": []
        }

        repost = None

        # Find the main tweet result
        main_tweet_result = None
        instructions = data.get('data', {}).get('threaded_conversation_with_injections_v2', {}).get('instructions', [])
        for instr in instructions:
            entries = instr.get('entries', [])
            for entry in entries:
                content = entry.get('content', {})
                item_content = content.get('itemContent', {})
                # Check for main tweet type (TimelineTweet or entryId starting with tweet-)
                if item_content.get('itemType') == 'TimelineTweet' or entry.get('entryId', '').startswith('tweet-'):
                    main_tweet_result = item_content.get('tweet_results', {}).get('result', {})
                    break
            if main_tweet_result:
                break

        if not main_tweet_result:
            return {"post": post}  # Return default if not found

        # Handle visibility wrapper
        if main_tweet_result.get('__typename') == 'TweetWithVisibilityResults':
            main_tweet_result = main_tweet_result.get('tweet', {})

        legacy = main_tweet_result.get('legacy', {})

        # Extract post fields
        post["id"] = main_tweet_result.get('rest_id') or legacy.get('id_str')
        post["created_at"] = legacy.get('created_at') or main_tweet_result.get('created_at')
        post["text"] = legacy.get('full_text') or main_tweet_result.get('text')

        if not post["text"]:
            note_tweet = main_tweet_result.get('note_tweet', {})
            note_result = note_tweet.get('note_tweet_results', {}).get('result', {})
            post["text"] = note_result.get('text') or note_result.get('full_text')

        # Author
        user_results = main_tweet_result.get('core', {}).get('user_results', {})
        user_result = user_results.get('result', {})
        if user_result.get('__typename') == 'UserWithVisibilityResults':
            user_result = user_result.get('user', {})

        user_legacy = user_result.get('legacy', {})
        user_core = user_result.get('core', {})

        post["author"]["name"] = user_core.get('name') or user_result.get('name') or user_legacy.get('name')
        post["author"]["screen_name"] = user_core.get('screen_name') or user_result.get('username') or user_legacy.get('screen_name')
        post["author"]["rest_id"] = user_result.get('rest_id')
        post["author"]["avatar_url"] = user_result.get('profile_image_url') or user_result.get('avatar', {}).get('image_url') or user_legacy.get('profile_image_url_https')

        # Metrics
        post["metrics"]["favorite_count"] = legacy.get('favorite_count') or main_tweet_result.get('favorite_count')
        post["metrics"]["reply_count"] = legacy.get('reply_count') or main_tweet_result.get('reply_count')
        post["metrics"]["retweet_count"] = legacy.get('retweet_count') or main_tweet_result.get('retweet_count')
        post["metrics"]["quote_count"] = legacy.get('quote_count') or main_tweet_result.get('quote_count')
        post["metrics"]["views_count"] = main_tweet_result.get('views', {}).get('count')

        # Entities
        entities = legacy.get('entities', {}) or main_tweet_result.get('entities', {})
        post["entities"]["hashtags"] = entities.get('hashtags', [])
        post["entities"]["urls"] = entities.get('urls', [])
        post["entities"]["user_mentions"] = entities.get('user_mentions', [])

        # Media
        extended_entities = legacy.get('extended_entities') or main_tweet_result.get('extended_entities') or {}
        media_items = extended_entities.get('media', [])
        for m in media_items:
            media_obj = {
                "media_key": m.get('media_key') or m.get('id_str'),
                "type": m.get('type'),
                "media_url": m.get('media_url_https') or m.get('media_url'),
                "thumbnail": None,
                "variants": []
            }
            if media_obj["type"] in ['video', 'animated_gif']:
                video_info = m.get('video_info', {})
                media_obj["thumbnail"] = m.get('media_url_https') or video_info.get('poster')
                variants = video_info.get('variants', [])
                media_obj["variants"] = [
                    {"content_type": v.get('content_type'), "url": v.get('url')}
                    for v in variants
                ]
            post["media"].append(media_obj)

        # Check for repost/quote
        quoted_status_result = main_tweet_result.get('quoted_status_result')
        quoted_status = legacy.get('quoted_status')
        quoted_status_id_str = legacy.get('quoted_status_id_str')

        if quoted_status_result or quoted_status or quoted_status_id_str:
            quoted = quoted_status_result.get('result') if quoted_status_result else quoted_status
            if quoted and quoted.get('__typename') == 'TweetWithVisibilityResults':
                quoted = quoted.get('tweet', {})

            quoted_legacy = quoted.get('legacy', {}) if quoted else {}

            repost_post = {
                "id": quoted.get('rest_id') or quoted_legacy.get('id_str'),
                "created_at": quoted_legacy.get('created_at') or quoted.get('created_at'),
                "text": quoted_legacy.get('full_text') or quoted.get('full_text') or quoted.get('text'),
                "author": {
                    "name": None,
                    "screen_name": None,
                    "rest_id": None,
                    "avatar_url": None
                },
                "metrics": {
                    "favorite_count": quoted_legacy.get('favorite_count') or quoted.get('favorite_count'),
                    "reply_count": quoted_legacy.get('reply_count') or quoted.get('reply_count'),
                    "retweet_count": quoted_legacy.get('retweet_count') or quoted.get('retweet_count'),
                    "quote_count": quoted_legacy.get('quote_count') or quoted.get('quote_count'),
                    "views_count": quoted.get('views', {}).get('count')
                },
                "entities": {
                    "hashtags": [],
                    "urls": [],
                    "user_mentions": []
                },
                "media": []
            }

            # Entities for repost
            entities = quoted_legacy.get('entities', {}) or quoted.get('entities', {})
            repost_post["entities"]["hashtags"] = entities.get('hashtags', [])
            repost_post["entities"]["urls"] = entities.get('urls', [])
            repost_post["entities"]["user_mentions"] = entities.get('user_mentions', [])

            # Note tweet fallback for text
            if not repost_post["text"]:
                note_tweet = quoted.get('note_tweet', {})
                note_result = note_tweet.get('note_tweet_results', {}).get('result', {})
                repost_post["text"] = note_result.get('text') or note_result.get('full_text')

            # Quoted author
            quoted_core = quoted.get('core', {})
            quoted_user_results = quoted_core.get('user_results', {})
            quoted_user_result = quoted_user_results.get('result', {})
            if quoted_user_result.get('__typename') == 'UserWithVisibilityResults':
                quoted_user_result = quoted_user_result.get('user', {})

            quoted_user_legacy = quoted_user_result.get('legacy', {})
            quoted_user_core = quoted_user_result.get('core', {})

            repost_post["author"]["name"] = quoted_user_core.get('name') or quoted_user_result.get('name') or quoted_user_legacy.get('name')
            repost_post["author"]["screen_name"] = quoted_user_core.get('screen_name') or quoted_user_result.get('username') or quoted_user_legacy.get('screen_name')
            repost_post["author"]["rest_id"] = quoted_user_result.get('rest_id')
            repost_post["author"]["avatar_url"] = quoted_user_result.get('profile_image_url') or quoted_user_result.get('avatar', {}).get('image_url') or quoted_user_legacy.get('profile_image_url_https')

            # Quoted media
            quoted_extended_entities = quoted_legacy.get('extended_entities') or quoted.get('extended_entities') or {}
            quoted_media_items = quoted_extended_entities.get('media', [])
            for m in quoted_media_items:
                media_obj = {
                    "media_key": m.get('media_key') or m.get('id_str'),
                    "type": m.get('type'),
                    "media_url": m.get('media_url_https') or m.get('media_url'),
                    "thumbnail": None,
                    "variants": []
                }
                if media_obj["type"] in ['video', 'animated_gif']:
                    video_info = m.get('video_info', {})
                    media_obj["thumbnail"] = m.get('media_url_https') or video_info.get('poster')
                    variants = video_info.get('variants', [])
                    media_obj["variants"] = [
                        {"content_type": v.get('content_type'), "url": v.get('url')}
                        for v in variants
                    ]
                repost_post["media"].append(media_obj)

            # Repost URL
            repost_url = main_tweet_result.get('quoted_status_permalink', {}).get('expanded') or legacy.get('quoted_status_permalink', {}).get('expanded') or quoted.get('quoted_status_permalink', {}).get('expanded') or quoted_legacy.get('quoted_status_permalink', {}).get('expanded')
            if repost_url and 'twitter.com' in repost_url:
                repost_url = repost_url.replace('twitter.com', 'x.com')

            repost = {
                "url": repost_url,
                "post": repost_post
            }

        result = {"post": post}
        if repost:
            result["repost"] = repost

        return result

    def _scrape_single_post(self, href: str) -> dict | None:
        data = {
            "url": href, "likes": "0", "retweets": "0", "replies": "0",
            "timestamp": None, "author": None, "text": None,
            "mentions": [], "hashtags": [], "media": [], "comments": []
        }

        captured = []

        def handle_response(response):
            if response.status == 200 and 'graphql' in response.url and 'TweetDetail' in response.url:
                try:
                    body = response.body()
                    body_str = body.decode('utf-8') if isinstance(body, bytes) else body
                    json_body = json.loads(body_str)
                    captured.append(json_body)
                except Exception as e:
                    print(f"[ERROR] Failed to parse response: {e}")

        self.page.on("response", handle_response)

        try:
            self.page.goto(href, wait_until="domcontentloaded")
            # CRITICAL FIX: Wait for network idle to ensure requests finish
            try:
                self.page.wait_for_load_state('networkidle', timeout=15000)
            except:
                self.page.wait_for_timeout(2000)
        except Exception as e:
            self.utils.log_error(f"Navigation failed: {e}")
            return None
        finally:
            self.page.remove_listener("response", handle_response)

        # Parse main tweet using the reference logic
        extracted = None
        for body in captured:
            extracted = self._extract_main_post(body)
            if extracted.get("post", {}).get("id"):
                print("[SUCCESS] Main tweet extracted successfully.")
                break

        if extracted and extracted.get("post"):
            post_data = extracted["post"]

            # Map structured data to the flat 'data' dict expected by the rest of the script
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

            # Comments
            print("[INFO] Starting comment extraction...")
            data["comments"] = self._extract_comments()
            return data
        else:
            print("GraphQL data missing, attempting DOM extraction...")
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

                # Note: DOM extraction doesn't support comments or metrics reliably in this scope
                data["comments"] = []
                return data
            except Exception as e:
                self.utils.log_error(f"DOM Fallback failed: {e}")
                return None

    def _extract_comments(self):
        """Extract comments by capturing GraphQL responses after scrolling to load all comments."""
        comments = []
        seen = set()
        captured = []

        def handle_response(response):
            if response.status == 200 and 'graphql' in response.url and 'TweetDetail' in response.url:
                try:
                    body = response.body()
                    body_str = body.decode('utf-8') if isinstance(body, bytes) else body
                    json_body = json.loads(body_str)
                    captured.append(json_body)
                except Exception:
                    pass

        self.page.on("response", handle_response)

        # Scroll whole page logic as requested
        # We are already on the page, but scrolling triggers new requests

        last_height = self.page.evaluate("document.body.scrollHeight")
        scrolls = 0
        max_scrolls = 30 # Reduced slightly as 50 is a lot
        no_change_count = 0
        max_no_change = 3

        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(), TextColumn("[progress.percentage]{task.percentage:>3.0f}%")) as progress:
            task_load = progress.add_task("[magenta]Loading comments...", total=max_scrolls)

            while scrolls < max_scrolls and no_change_count < max_no_change:
                # Scroll to bottom of page (whole page)
                self.page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                self.page.wait_for_timeout(2000) # Wait for content to load

                # Handle "Show" buttons (replies/spam)

                button_selectors = [
                    "//button[contains(., 'Show probable spam')]",
                ]
                for selector in button_selectors:
                    try:
                        buttons = self.page.locator(f"xpath={selector}").all()
                        for button in buttons:
                            try:
                                if button.is_visible():
                                    button.click()
                                    self.page.wait_for_timeout(500)
                                    no_change_count = 0
                            except:
                                pass
                    except:
                        pass

                new_height = self.page.evaluate("document.body.scrollHeight")
                if new_height == last_height:
                    no_change_count += 1
                else:
                    no_change_count = 0
                    last_height = new_height

                scrolls += 1
                progress.update(task_load, advance=1)

        self.page.remove_listener("response", handle_response)
        print(f"[INFO] Scroll finished. Parsing {len(captured)} responses.")

        # DEBUG: Print captured JSON structure for comments to help user debug
        if len(captured) > 0:
            print("\n[DEBUG] --- Captured Comment JSON Structure (First Response) ---")
            pprint(captured[0])
            print("[DEBUG] ------------------------------\n")
        else:
            print("[DEBUG] No comment responses captured during scroll.")

        # Parse captured GraphQL JSONs for comments using robust logic
        for data in captured:
            try:
                instructions = data.get('data', {}).get('threaded_conversation_with_injections_v2', {}).get('instructions', [])
                for instr in instructions:
                    if instr.get('type') == 'TimelineAddEntries':
                        entries = instr.get('entries', [])
                        for entry in entries:
                            entry_id = entry.get('entryId', '')
                            if entry_id.startswith('conversationthread-'):
                                items = entry.get('content', {}).get('items', [])
                                for item in items:
                                    tweet_result = item.get('item', {}).get('itemContent', {}).get('tweet_results', {}).get('result', {})

                                    if tweet_result.get('__typename') == 'TweetWithVisibilityResults':
                                        tweet_result = tweet_result.get('tweet', {})

                                    # Handle if repost or quote in comment
                                    inner_result = None
                                    inner_type = None
                                    if 'retweeted_status_result' in tweet_result:
                                        inner_result = tweet_result['retweeted_status_result'].get('result', {})
                                        inner_type = 'repost'
                                    elif 'quoted_status_result' in tweet_result:
                                        inner_result = tweet_result['quoted_status_result'].get('result', {})
                                        inner_type = 'quote'
                                    elif 'legacy' in tweet_result:
                                        legacy = tweet_result['legacy']
                                        if 'retweeted_status' in legacy:
                                            inner_result = legacy['retweeted_status']
                                            inner_type = 'repost'
                                        elif 'quoted_status' in legacy:
                                            inner_result = legacy['quoted_status']
                                            inner_type = 'quote'

                                    core = tweet_result.get('core', {})
                                    user_results = core.get('user_results', {}).get('result', {})

                                    if user_results.get('__typename') == 'UserWithVisibilityResults':
                                        user_result = user_results.get('user', {})
                                    else:
                                        user_result = user_results

                                    user_core = user_result.get('core', {})
                                    user_result_legacy = user_result.get('legacy', {})
                                    legacy = tweet_result.get('legacy', {})

                                    # Robust fallback for text
                                    text_dicts = [legacy, tweet_result]
                                    text_keys = ['full_text', 'text']
                                    text = None
                                    for d in text_dicts:
                                        for k in text_keys:
                                            if k in d:
                                                text = d[k]
                                                break
                                        if text:
                                            break
                                    if not text:
                                        note_tweet = tweet_result.get('note_tweet', {})
                                        note_result = note_tweet.get('note_tweet_results', {}).get('result', {})
                                        text = note_result.get('text') or note_result.get('full_text')

                                    # Robust fallback for user_handle
                                    handle_dicts = [user_core, user_result_legacy, user_result]
                                    handle_keys = ['screen_name', 'username', 'handle', 'user_name', 'user_commenter']
                                    user_handle = None
                                    for d in handle_dicts:
                                        for k in handle_keys:
                                            if k in d:
                                                user_handle = d[k]
                                                break
                                        if user_handle:
                                            break
                                    user = f"https://x.com/{user_handle}" if user_handle else None

                                    # Robust fallback for timestamp
                                    timestamp_dicts = [legacy, tweet_result]
                                    timestamp_keys = ['created_at']
                                    timestamp = None
                                    for d in timestamp_dicts:
                                        for k in timestamp_keys:
                                            if k in d:
                                                timestamp = d[k]
                                                break
                                        if timestamp:
                                            break

                                    # Robust fallback for likes
                                    likes_dicts = [legacy, tweet_result]
                                    likes_keys = ['favorite_count', 'like_count']
                                    likes = 0
                                    for d in likes_dicts:
                                        for k in likes_keys:
                                            if k in d:
                                                likes = d[k]
                                                break
                                        if likes != 0:
                                            break
                                    likes = str(likes)

                                    # Robust fallback for reposts
                                    reposts_dicts = [legacy, tweet_result]
                                    reposts_keys = ['retweet_count', 'repost_count']
                                    reposts = 0
                                    for d in reposts_dicts:
                                        for k in reposts_keys:
                                            if k in d:
                                                reposts = d[k]
                                                break
                                        if reposts != 0:
                                            break
                                    reposts = str(reposts)

                                    # Robust fallback for views
                                    views_obj = tweet_result.get('views', {}) or tweet_result.get('view_count', {})
                                    views = str(views_obj.get('count') or views_obj.get('value') or tweet_result.get('view_count') or '')

                                    if user and text:
                                        key = f"{user}||{text[:200]}"
                                        if key in seen:
                                            continue
                                        seen.add(key)

                                        comment = {
                                            "user": user,
                                            "text": text,
                                            "timestamp": timestamp,
                                            "likes": likes,
                                            "reposts": reposts,
                                            "views": views,
                                        }

                                        # Media extraction
                                        media = legacy.get('extended_entities', {}).get('media', [])
                                        img = next((m['media_url_https'] for m in media if m['type'] == 'photo'), None)
                                        video = None
                                        for m in media:
                                            if m['type'] in ['video', 'animated_gif']:
                                                variants = m.get('video_info', {}).get('variants', [])
                                                if variants:
                                                    video = max(variants, key=lambda v: v.get('bitrate', 0))['url']
                                                break
                                        if img:
                                            comment["img"] = img
                                        if video:
                                            comment["video"] = video

                                        # Handle inner post if repost or quote
                                        if inner_result:
                                            inner_legacy = inner_result.get('legacy', {}) if 'legacy' in inner_result else inner_result
                                            inner_core = inner_result.get('core', {})
                                            inner_user_result = inner_core.get('user_results', {}).get('result', {})

                                            if inner_user_result.get('__typename') == 'UserWithVisibilityResults':
                                                inner_user_result = inner_user_result.get('user', {})
                                            else:
                                                inner_user_result = inner_user_result

                                            inner_user_core = inner_user_result.get('core', {})
                                            inner_user_legacy = inner_user_result.get('legacy', {})

                                            inner_text = inner_legacy.get('full_text') or inner_result.get('full_text') or inner_result.get('text')
                                            inner_user_handle = None
                                            for d in [inner_user_core, inner_user_legacy, inner_user_result]:
                                                for k in handle_keys:
                                                    inner_user_handle = d.get(k)
                                                    if inner_user_handle:
                                                        break
                                                if inner_user_handle:
                                                    break
                                            inner_user = f"https://x.com/{inner_user_handle}" if inner_user_handle else None

                                            comment["type"] = inner_type
                                            comment["original_user"] = inner_user
                                            comment["original_text"] = inner_text

                                            # Add inner media if not already
                                            inner_media = inner_legacy.get('extended_entities', {}).get('media', [])
                                            inner_img = next((m['media_url_https'] for m in inner_media if m['type'] == 'photo'), None)
                                            inner_video = None
                                            for m in inner_media:
                                                if m['type'] in ['video', 'animated_gif']:
                                                    variants = m.get('video_info', {}).get('variants', [])
                                                    if variants:
                                                        inner_video = max(variants, key=lambda v: v.get('bitrate', 0))['url']
                                                    break
                                            if inner_img and "img" not in comment:
                                                comment["img"] = inner_img
                                            if inner_video and "video" not in comment:
                                                comment["video"] = inner_video

                                        comments.append(comment)
            except Exception:
                pass
        print(f"[INFO] Extracted {len(comments)} comments.")
        return comments

    def close(self):
        self.browser_engine.quit_driver()