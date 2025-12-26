# platforms/instagram_scraper.py
import os
import time
import re
from tqdm import tqdm
from playwright.sync_api import TimeoutError, ElementHandle
# Assuming imports for base and utils
from platforms.base import ScraperBase
from core.browser import BrowserEngine
from core.insta_utils import InstaUtils

class InstagramScraper(ScraperBase):
    def __init__(self, headless: bool = True, user_data_dir: str = None):
        super().__init__(headless=headless, user_data_dir=user_data_dir)
        # Override self.insta_utils with the Playwright-adapted version
        self.insta_utils = InstaUtils()
        self.insta_utils.log_info("insta_utils overridden")
        self.browser = BrowserEngine(headless=headless, user_data_dir=user_data_dir)
        self.insta_utils.log_info("browser initialized")
        self.page = None
        self.insta_utils.log_info("__init__ finished")

    def setup_page(self):
        self.insta_utils.log_info("setup_page started")
        if not self.page:
            self.insta_utils.log_info("page is None, creating")
            self.page = self.browser.get_driver()
            self.insta_utils.log_info("page created")
            self.driver = self.page  # for compatibility with universal_scraper
            self.insta_utils.log_info("driver alias set to page")
        self.insta_utils.log_info("setup_page finished")

    def close(self):
        self.insta_utils.log_info("close started")
        self.browser.quit_driver()
        self.insta_utils.log_info("close finished")

    def _get_full_sel(self, by: str, sel: str):
        self.insta_utils.log_info("_get_full_sel started with by={} sel={}".format(by, sel))
        if by == 'xpath':
            self.insta_utils.log_info("returning xpath selector")
            return f"xpath={sel}"
        elif by == 'css':
            self.insta_utils.log_info("returning css selector")
            return f"css={sel}"
        elif by == 'tag':
            self.insta_utils.log_info("returning tag selector")
            return sel
        else:
            self.insta_utils.log_info("returning default selector")
            return sel
        self.insta_utils.log_info("_get_full_sel finished")

    def _find_element_with_selectors(self, selectors, by='xpath', timeout=10, wait=True, retries=3, retry_delay=0.2):
        """
        Backwards-compatible finder:
          - Default: wait=True -> original behavior (wait_for_selector per selector, same API)
          - wait=False -> fast mode: immediate query with small retry loop (no long timeouts)
        """
        self.insta_utils.log_info(
            "_find_element_with_selectors started with selectors={}, by={}, timeout={}, wait={}"
            .format(selectors, by, timeout, wait)
        )

        if wait:
            timeout_ms = timeout * 1000
            self.insta_utils.log_info("timeout_ms calculated: {}".format(timeout_ms))
            for sel in selectors:
                self.insta_utils.log_info("trying selector (wait mode): {}".format(sel))
                full_sel = self._get_full_sel(by, sel)
                self.insta_utils.log_info("full_sel: {}".format(full_sel))
                try:
                    self.insta_utils.log_info("waiting for selector")
                    self.page.wait_for_selector(full_sel, timeout=timeout_ms)
                    self.insta_utils.log_info("selector found")
                    elem = self.page.query_selector(full_sel)
                    self.insta_utils.log_info("element queried")
                    return elem
                except TimeoutError:
                    self.insta_utils.log_info("timeout for selector: {}".format(sel))
                    continue
            self.insta_utils.log_info("no element found")
            return None

        # FAST mode: no long blocking waits — quick retries only
        self.insta_utils.log_info("running in FAST mode (no long waits)")
        for sel in selectors:
            self.insta_utils.log_info("trying selector (fast mode): {}".format(sel))
            full_sel = self._get_full_sel(by, sel)
            self.insta_utils.log_info("full_sel: {}".format(full_sel))

            for attempt in range(retries):
                elem = self.page.query_selector(full_sel)
                if elem:
                    self.insta_utils.log_info("element found on attempt {}".format(attempt + 1))
                    return elem
                # small sleep between retries (non-blocking for long periods)
                if attempt < retries - 1:
                    self.page.wait_for_timeout(int(retry_delay * 1000))
            self.insta_utils.log_info("selector not found after {} retries: {}".format(retries, sel))

        self.insta_utils.log_info("no element found (fast mode)")
        return None


    def _find_elements_with_selectors(self, selectors, by='xpath', timeout=10, wait=True, retries=3, retry_delay=0.2):
        """
        Similar to _find_element_with_selectors:
          - wait=True  -> original behavior (per-selector wait_for_selector then query_selector_all)
          - wait=False -> fast mode: immediate query_selector_all with small retry loop
        """
        self.insta_utils.log_info(
            "_find_elements_with_selectors started with selectors={}, by={}, timeout={}, wait={}"
            .format(selectors, by, timeout, wait)
        )

        if wait:
            timeout_ms = timeout * 1000
            self.insta_utils.log_info("timeout_ms calculated: {}".format(timeout_ms))
            for sel in selectors:
                self.insta_utils.log_info("trying selector (wait mode): {}".format(sel))
                full_sel = self._get_full_sel(by, sel)
                self.insta_utils.log_info("full_sel: {}".format(full_sel))
                try:
                    self.insta_utils.log_info("waiting for selector")
                    self.page.wait_for_selector(full_sel, timeout=timeout_ms)
                    self.insta_utils.log_info("selector found")
                    elements = self.page.query_selector_all(full_sel)
                    self.insta_utils.log_info("elements queried, count: {}".format(len(elements)))
                    if elements:
                        self.insta_utils.log_info("returning elements")
                        return elements
                except TimeoutError:
                    self.insta_utils.log_info("timeout for selector: {}".format(sel))
                    continue
            self.insta_utils.log_info("no elements found")
            return []

        # FAST mode
        self.insta_utils.log_info("running in FAST mode (no long waits)")
        for sel in selectors:
            self.insta_utils.log_info("trying selector (fast mode): {}".format(sel))
            full_sel = self._get_full_sel(by, sel)
            self.insta_utils.log_info("full_sel: {}".format(full_sel))

            for attempt in range(retries):
                elements = self.page.query_selector_all(full_sel)
                if elements:
                    self.insta_utils.log_info("elements found on attempt {}, count: {}".format(attempt + 1, len(elements)))
                    return elements
                if attempt < retries - 1:
                    self.page.wait_for_timeout(int(retry_delay * 1000))
            self.insta_utils.log_info("selector not found after {} retries: {}".format(retries, sel))

        self.insta_utils.log_info("no elements found (fast mode)")
        return []


    def _find_child_element(self, parent: ElementHandle, selectors, by='xpath', wait=False, retries=3, retry_delay=0.1):
        """
        Child finders were already non-blocking. Default behavior preserved (wait=False).
        If wait=True, it will retry a few times (useful when children render slightly later).
        """
        self.insta_utils.log_info(
            "_find_child_element started with parent={}, selectors={}, by={}, wait={}"
            .format(parent, selectors, by, wait)
        )
        for sel in selectors:
            self.insta_utils.log_info("trying selector: {}".format(sel))
            full_sel = self._get_full_sel(by, sel)
            self.insta_utils.log_info("full_sel: {}".format(full_sel))

            if wait:
                for attempt in range(retries):
                    try:
                        elem = parent.query_selector(full_sel)
                        if elem:
                            self.insta_utils.log_info("child element found on attempt {}".format(attempt + 1))
                            return elem
                    except Exception:
                        self.insta_utils.log_info("exception for selector on attempt {}: {}".format(attempt + 1, sel))
                    if attempt < retries - 1:
                        self.page.wait_for_timeout(int(retry_delay * 1000))
            else:
                try:
                    elem = parent.query_selector(full_sel)
                    if elem:
                        self.insta_utils.log_info("child element found")
                        return elem
                except Exception:
                    self.insta_utils.log_info("exception for selector: {}".format(sel))
                    continue

        self.insta_utils.log_info("no child element found")
        return None


    def _find_child_elements(self, parent: ElementHandle, selectors, by='xpath', wait=False, retries=3, retry_delay=0.1):
        """
        Same idea as _find_child_element but returns list.
        Default: wait=False (same as before).
        """
        self.insta_utils.log_info(
            "_find_child_elements started with parent={}, selectors={}, by={}, wait={}"
            .format(parent, selectors, by, wait)
        )
        for sel in selectors:
            self.insta_utils.log_info("trying selector: {}".format(sel))
            full_sel = self._get_full_sel(by, sel)
            self.insta_utils.log_info("full_sel: {}".format(full_sel))

            if wait:
                for attempt in range(retries):
                    try:
                        elements = parent.query_selector_all(full_sel)
                        self.insta_utils.log_info("child elements found, count: {}".format(len(elements)))
                        if elements:
                            self.insta_utils.log_info("returning child elements on attempt {}".format(attempt + 1))
                            return elements
                    except Exception:
                        self.insta_utils.log_info("exception for selector on attempt {}: {}".format(attempt + 1, sel))
                    if attempt < retries - 1:
                        self.page.wait_for_timeout(int(retry_delay * 1000))
            else:
                try:
                    elements = parent.query_selector_all(full_sel)
                    self.insta_utils.log_info("child elements found, count: {}".format(len(elements)))
                    if elements:
                        self.insta_utils.log_info("returning child elements")
                        return elements
                except Exception:
                    self.insta_utils.log_info("exception for selector: {}".format(sel))
                    continue

        self.insta_utils.log_info("no child elements found")
        return []


    def login(self, username: str = None, password: str = None, cookie_path="cookies/instagram_cookies.json"):
        self.insta_utils.log_info("login started with username={}, password={}, cookie_path={}".format(username, password, cookie_path))
        self.setup_page()
        self.insta_utils.log_info("setup_page called in login")
        self.page.goto("https://www.instagram.com/")
        self.insta_utils.log_info("goto home page")
        self.insta_utils.log_info("login finished")
        return True

    def blind_scrape(self, url: str = None, max_posts=10):
        self.insta_utils.log_info("blind_scrape started with url={}, max_posts={}".format(url, max_posts))
        self.setup_page()
        self.insta_utils.log_info("setup_page called")
        self.page.goto(url)
        self.insta_utils.log_info("goto url: {}".format(url))
        result = self.search(text=None, max_posts=max_posts)
        self.insta_utils.log_info("search called, result length: {}".format(len(result)))
        self.insta_utils.log_info("blind_scrape finished")
        return result

    def extract_posts(self):
        self.insta_utils.log_info("extract_posts started")
        result = self.search(text=None)
        self.insta_utils.log_info("search called, result length: {}".format(len(result)))
        self.insta_utils.log_info("extract_posts finished")
        return result

    def search(self, text: str = None, start_time: str = None, end_time: str = None, max_posts=5):
        self.insta_utils.log_info("search started with text={}, start_time={}, end_time={}, max_posts={}".format(text, start_time, end_time, max_posts))
        self.setup_page()
        self.insta_utils.log_info("setup_page called")
        if text:
            self.insta_utils.log_info("text provided")
            target = self.insta_utils.prepare_target(text)
            self.insta_utils.log_info("target prepared: {}".format(target))
            if not target:
                self.insta_utils.log_error("Could not build target URL from text.")
                return []
            self.page.goto(target)
            self.insta_utils.log_info("goto target: {}".format(target))
            time.sleep(3)
            self.insta_utils.log_info("sleep 3")
        try:
            self.insta_utils.log_info("getting page url")
            _ = self.page.url
            self.insta_utils.log_info("page url got")
        except Exception:
            self.insta_utils.log_error("No target and page not initialized.")
            return []
        try:
            self.insta_utils.log_info("trying to find article")
            article_selectors = ["article"]
            self._find_element_with_selectors(article_selectors, by='tag')
            self.insta_utils.log_info("article found")
        except Exception:
            self.insta_utils.log_info("article not found")
            pass
        post_hrefs = []
        seen = set()
        scroll_rounds = 0
        current_url = self.page.url
        self.insta_utils.log_info("current_url: {}".format(current_url))
        post_anchor_selectors = ["//a[contains(@href, '/p/') or contains(@href, '/reel/')]"]
        self.insta_utils.log_info("starting scroll loop")
        while len(post_hrefs) < max_posts and scroll_rounds < 30:
            self.insta_utils.log_info("scroll round: {}, post_hrefs len: {}".format(scroll_rounds, len(post_hrefs)))
            anchors = self._find_elements_with_selectors(post_anchor_selectors, by='xpath')
            self.insta_utils.log_info("anchors found: {}".format(len(anchors)))
            for a in anchors:
                try:
                    self.insta_utils.log_info("getting href")
                    href = a.get_attribute("href")
                    self.insta_utils.log_info("href: {}".format(href))
                    if href.startswith('/'):
                        self.insta_utils.log_info("relative href, prepending")
                        href = 'https://www.instagram.com' + href
                        self.insta_utils.log_info("full href: {}".format(href))
                    if href and re.match(r'^https?://www\.instagram\.com/(p|reel)/[A-Za-z0-9_-]+/?$', href) and href not in seen:
                        self.insta_utils.log_info("valid href, adding")
                        seen.add(href)
                        post_hrefs.append(href)
                except:
                    self.insta_utils.log_info("exception in anchor processing")
                    continue
            self.insta_utils.random_delay(1.0, 2.0)
            self.insta_utils.log_info("random delay done")
            self.insta_utils.scroll_page(self.page, pause=1.5, max_scrolls=2)
            self.insta_utils.log_info("scroll_page done")
            scroll_rounds += 1
            self.insta_utils.log_info("scroll_rounds incremented")
        results = []
        self.insta_utils.log_info("starting post scraping loop")
        for href in post_hrefs[:max_posts]:
            self.insta_utils.log_info("scraping href: {}".format(href))
            try:
                post = self._scrape_single_post(href)
                self.insta_utils.log_info("post scraped")
                if post is None:
                    self.insta_utils.log_error(f"Failed to scrape post {href}, saving scraped posts so far.")
                    return results
                post_time = post.get("timestamp")
                self.insta_utils.log_info("post_time: {}".format(post_time))
                if post_time and (start_time or end_time):
                    self.insta_utils.log_info("checking time filters")
                    keep = True
                    if start_time:
                        self.insta_utils.log_info("start_time provided")
                        st = self.insta_utils.convert_date(start_time)
                        self.insta_utils.log_info("st: {}".format(st))
                        if st and post_time < st:
                            keep = False
                    if end_time:
                        self.insta_utils.log_info("end_time provided")
                        et = self.insta_utils.convert_date(end_time)
                        self.insta_utils.log_info("et: {}".format(et))
                        if et and post_time > et:
                            keep = False
                    if not keep:
                        self.insta_utils.log_info("post not kept")
                        continue
                results.append(post)
                self.insta_utils.log_info("post appended")
                self.insta_utils.random_delay(2.0, 4.0)
                self.insta_utils.log_info("random delay done")
            except Exception as e:
                self.insta_utils.log_error(f"Error scraping post {href}: {e}")
                return results
        self.insta_utils.log_info("finally block")
        self.page.goto(current_url)
        self.insta_utils.log_info("goto current_url")
        self.insta_utils.random_delay(1.0, 2.0)
        self.insta_utils.log_info("random delay done")
        self.insta_utils.log_info("search finished, results len: {}".format(len(results)))
        return results

    def _scrape_single_post(self, href: str) -> dict | None:
        self.insta_utils.log_info("_scrape_single_post started with href={}".format(href))
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
        self.insta_utils.log_info("data dict initialized")
        try:
            self.page.goto(href)
            self.insta_utils.log_info("goto href")
            self.insta_utils.random_delay(2.0, 4.0)
            self.insta_utils.log_info("random delay done")
            main_selectors = ["//main[1]//hr[1]/following::div[1]"]
            self.insta_utils.log_info("finding main")
            main = self._find_element_with_selectors(main_selectors, by='xpath')
            self.insta_utils.log_info("main found: {}".format(main is not None))
            if not main:
                raise TimeoutError("Main container not found.")
            # Author, timestamp, caption
            top_block_selectors = ["//main[1]//hr[1]/following::div[1]/div[1]"]
            self.insta_utils.log_info("finding top_blocks")
            top_blocks = self._find_elements_with_selectors(top_block_selectors, by='xpath')
            self.insta_utils.log_info("top_blocks len: {}".format(len(top_blocks)))
            if len(top_blocks) >= 2:
                self.insta_utils.log_info("using top block")
                top = top_blocks[0]
                target_selectors = ["./div[1]/div[1]/div[2]/div[1]/span[1]/div[1]"]
                self.insta_utils.log_info("finding target")
                target = self._find_child_element(top, target_selectors, by='xpath')
                self.insta_utils.log_info("target found: {}".format(target is not None))
                if not target:
                    raise ValueError("Target element not found.")
                author_selectors = [".//a[1]//span[1]"]
                self.insta_utils.log_info("finding author_el")
                author_el = self._find_child_element(target, author_selectors, by='xpath')
                data["author"] = author_el.text_content().strip() if author_el else None
                self.insta_utils.log_info("author: {}".format(data["author"]))
                time_selectors = ["time"]
                self.insta_utils.log_info("finding time_tag")
                time_tag = self._find_child_element(target, time_selectors, by='tag')
                data["timestamp"] = time_tag.get_attribute("datetime") if time_tag else None
                self.insta_utils.log_info("timestamp: {}".format(data["timestamp"]))
                caption_selectors = ["./span[1]"]
                self.insta_utils.log_info("finding caption_el")
                caption_el = self._find_child_element(target, caption_selectors, by='xpath')
                text = caption_el.text_content().strip() if caption_el else None
                data["caption"] = text
                self.insta_utils.log_info("caption: {}".format(data["caption"]))
                if text:
                    self.insta_utils.log_info("extracting mentions and hashtags")
                    data["mentions"] = re.findall(r'@\w+', text)
                    data["hashtags"] = re.findall(r'#\w+', text)
                    self.insta_utils.log_info("mentions: {}, hashtags: {}".format(data["mentions"], data["hashtags"]))
            else:
                self.insta_utils.log_info("using fallback")
                # Fallback
                author_fallback_selectors = ["//main//hr[1]/preceding-sibling::div[1]/div[1]//div[2]//span[1]/div[1]"]
                self.insta_utils.log_info("finding author_el fallback")
                author_el = self._find_element_with_selectors(author_fallback_selectors, by='xpath')
                if author_el:
                    data["author"] = author_el.text_content().strip() or None
                    self.insta_utils.log_info("author fallback: {}".format(data["author"]))
                time_fallback_selectors = ["//main//section[1]/following::div[1]//time"]
                self.insta_utils.log_info("finding time_tag fallback")
                time_tag = self._find_element_with_selectors(time_fallback_selectors, by='xpath')
                if time_tag:
                    data["timestamp"] = time_tag.get_attribute("datetime") or None
                    self.insta_utils.log_info("timestamp fallback: {}".format(data["timestamp"]))
            # Likes
            likes_selectors = ["//main[1]//section[1]/div[1]/span[2]", "//main[1]//section[2]/div[1]/div[1]/span[1]/a[1]/span[1]/span[1]"]
            self.insta_utils.log_info("finding likes_el")
            likes_el = self._find_element_with_selectors(likes_selectors, by='xpath', timeout=5)
            data["likes"] = likes_el.text_content().strip() if likes_el else "0"
            self.insta_utils.log_info("likes: {}".format(data["likes"]))
            # Media
            media_urls = []
            media_set = set()
            max_steps = 50
            steps = 0
            self.insta_utils.log_info("starting media loop")
            while steps < max_steps:
                self.insta_utils.log_info("media step: {}".format(steps))
                steps += 1
                img_selectors = ["//main//div//ul//img","//main/div[1]/div[1]/div[1]/div[1]/div[1]//img","//main/div[1]/div[1]//div[@role='button']/div//img[1]"]
                self.insta_utils.log_info("finding imgs")
                imgs = self._find_elements_with_selectors(img_selectors, by='xpath',retries=1, wait=False)
                self.insta_utils.log_info("imgs found: {}".format(len(imgs)))
                for im in imgs:
                    try:
                        self.insta_utils.log_info("getting img src")
                        src = im.get_attribute("src")
                        self.insta_utils.log_info("src: {}".format(src))
                        if src and src.startswith("https://") and src not in media_set:
                            self.insta_utils.log_info("adding src")
                            media_set.add(src)
                            media_urls.append(src)
                    except:
                        self.insta_utils.log_info("exception in img processing")
                        continue
                vid_selectors = ["//video"]
                self.insta_utils.log_info("finding vids")
                vids = self._find_elements_with_selectors(vid_selectors, by='xpath',retries=1, wait=False)
                self.insta_utils.log_info("vids found: {}".format(len(vids)))
                for v in vids:
                    try:
                        self.insta_utils.log_info("getting vid src")
                        src = v.get_attribute("src")
                        self.insta_utils.log_info("src: {}".format(src))
                        if src and src.startswith("https://") and src not in media_set:
                            self.insta_utils.log_info("adding src")
                            media_set.add(src)
                            media_urls.append(src)
                    except:
                        self.insta_utils.log_info("exception in vid processing")
                        continue
                    source_selectors = ["source"]
                    self.insta_utils.log_info("finding sources")
                    sources = self._find_child_elements(v, source_selectors, by='tag')
                    self.insta_utils.log_info("sources found: {}".format(len(sources)))
                    for s in sources:
                        try:
                            self.insta_utils.log_info("getting source src")
                            ssrc = s.get_attribute("src")
                            self.insta_utils.log_info("ssrc: {}".format(ssrc))
                            if ssrc and ssrc.startswith("https://") and ssrc not in media_set:
                                self.insta_utils.log_info("adding ssrc")
                                media_set.add(ssrc)
                                media_urls.append(ssrc)
                        except:
                            self.insta_utils.log_info("exception in source processing")
                            continue
                # Next button
                next_selectors = ["//button[@aria-label='Next' and ancestor::main]"]
                self.insta_utils.log_info("finding next_btn")
                next_btn = self._find_element_with_selectors(next_selectors, by='xpath', wait=False,retries=1)
                self.insta_utils.log_info("next_btn found: {}".format(next_btn is not None))
                if not next_btn:
                    self.insta_utils.log_info("no next_btn, breaking")
                    break
                try:
                    self.insta_utils.log_info("clicking next_btn")
                    next_btn.click()
                except Exception:
                    self.insta_utils.log_info("exception in click, using evaluate")
                    self.page.evaluate("btn => btn.click()", next_btn)
                self.insta_utils.random_delay(1.0, 2.0)
                self.insta_utils.log_info("random delay done")
            data["media"] = media_urls
            self.insta_utils.log_info("media: {}".format(data["media"]))
            # Comments
            self.insta_utils.log_info("extracting comments")
            data["comments"] = self._extract_comments(href)
            self.insta_utils.log_info("comments extracted, len: {}".format(len(data["comments"])))
            self.insta_utils.log_info("_scrape_single_post finished")
            return data
        except Exception as e:
            self.insta_utils.log_error(f"_scrape_single_post failed for {href}: {e}")
            return None

    def _extract_comments(self, href: str):
        self.insta_utils.log_info("_extract_comments started with href={}".format(href))
        comments = []
        seen = set()
        # Scroll to load comments (try multiple selectors until success)
        comment_scroll_selectors = ["//main//hr[1]/following-sibling::div[1]", "//div[contains(@class, 'comments')]"]
        scrolled = False
        self.insta_utils.log_info("starting scroll for comments")
        for sel in comment_scroll_selectors:
            self.insta_utils.log_info("trying scroll sel: {}".format(sel))
            locator = self.page.locator(f"xpath={sel}")  # Create Locator here
            if self.insta_utils.scroll_until_end(self.page, locator):
                self.insta_utils.log_info("scrolled successfully")
                scrolled = True
                break
        if not scrolled:
            self.insta_utils.log_info("Could not scroll comments section with any selector.")
        main_selectors = ["//main//hr[1]/following::div[1]/div[1]", "//article//section/following-sibling::div[1]/div[1]", "//div[contains(@class, 'comments')]/div[1]"]
        self.insta_utils.log_info("finding main for comments")
        main = self._find_element_with_selectors(main_selectors, by='xpath')
        self.insta_utils.log_info("main found: {}".format(main is not None))
        if not main:
            self.insta_utils.log_info("no main, returning empty")
            return comments
        block_selectors = ["./div", "./section", "./ul"]
        self.insta_utils.log_info("finding blocks")
        blocks = self._find_child_elements(main, block_selectors, by='xpath')
        self.insta_utils.log_info("blocks len: {}".format(len(blocks)))
        if not blocks:
            self.insta_utils.log_info("no blocks, returning empty")
            return comments
        target_block = blocks[-1]
        self.insta_utils.log_info("target_block selected")
        try:
            h2_selectors = [".//h2", ".//div[contains(text(), 'No comments')]", ".//span[contains(@class, 'no-comments')]"]
            self.insta_utils.log_info("finding h2")
            h2 = self._find_child_element(target_block, h2_selectors, by='xpath')
            self.insta_utils.log_info("h2 found: {}".format(h2 is not None))
            if h2 and "No comments yet." in h2.text_content().strip():
                self.insta_utils.log_info("no comments, returning empty")
                return []
        except:
            self.insta_utils.log_info("exception in h2 check")
            pass
        container_selectors = ["./div", "./ul/li", "./div[contains(@role, 'presentation')]/div"]
        self.insta_utils.log_info("finding containers")
        containers = self._find_child_elements(target_block, container_selectors, by='xpath')
        self.insta_utils.log_info("containers len: {}".format(len(containers)))
        for container in tqdm(containers, desc="Processing comments"):
            self.insta_utils.log_info("processing container")
            try:

                parsed = self.insta_utils.parse_instagram_comment(container)
                self.insta_utils.log_info("parsed: {}".format(parsed))
                comments.append(parsed)
            except Exception as e:
                self.insta_utils.log_error(f"Error processing comment container: {e}")
                continue
        self.insta_utils.log_info("_extract_comments finished, comments len: {}".format(len(comments)))
        return comments