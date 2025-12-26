import os
import json
import time
import random
from datetime import datetime
import re

class InstaUtils:
    @staticmethod
    def log_info(msg):
        print(f"INFO: {msg}")

    @staticmethod
    def log_error(msg):
        print(f"ERROR: {msg}")

    @staticmethod
    def log_success(msg):
        print(f"SUCCESS: {msg}")

    @staticmethod
    def load_cookies(page, path):
        print("INFO: load_cookies started with path={}".format(path))
        if os.path.exists(path):
            print("INFO: path exists")
            with open(path, 'r') as f:
                print("INFO: opening file")
                cookies = json.load(f)
                print("INFO: cookies loaded")
            page.context.add_cookies(cookies)
            print("INFO: cookies added")
            print("INFO: load_cookies finished true")
            return True
        print("INFO: load_cookies finished false")
        return False

    @staticmethod
    def save_cookies(page, path):
        print("INFO: save_cookies started with path={}".format(path))
        cookies = page.context.cookies()
        print("INFO: cookies got")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        print("INFO: dir made")
        with open(path, 'w') as f:
            print("INFO: opening file")
            json.dump(cookies, f)
            print("INFO: cookies dumped")
        print("INFO: save_cookies finished")

    @staticmethod
    def prepare_target(text):
        print("INFO: prepare_target started with text={}".format(text))
        if not text:
            print("INFO: no text, returning None")
            return None
        text = text.strip()
        print("INFO: text stripped: {}".format(text))
        if text.startswith('@'):
            target = f"https://www.instagram.com/{text[1:]}/"
            print("INFO: @ target: {}".format(target))
            return target
        elif text.startswith('#'):
            target = f"https://www.instagram.com/explore/tags/{text[1:]}/"
            print("INFO: # target: {}".format(target))
            return target
        elif 'instagram.com' in text:
            print("INFO: instagram.com in text, returning text")
            return text
        else:
            target = f"https://www.instagram.com/explore/search/keyword/?q={text}"
            print("INFO: default target: {}".format(target))
            return target

    @staticmethod
    def random_delay(min_sec, max_sec):
        print("INFO: random_delay started with min={}, max={}".format(min_sec, max_sec))
        delay = random.uniform(min_sec, max_sec)
        print("INFO: delay: {}".format(delay))
        time.sleep(delay)
        print("INFO: random_delay finished")

    @staticmethod
    def scroll_page(page, pause, max_scrolls):
        print("INFO: scroll_page started with pause={}, max_scrolls={}".format(pause, max_scrolls))
        for i in range(max_scrolls):
            print("INFO: scroll {}".format(i))
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            print("INFO: evaluate done")
            time.sleep(pause)
            print("INFO: sleep done")
        print("INFO: scroll_page finished")

    @staticmethod
    def convert_date(date_str):
        print("INFO: convert_date started with date_str={}".format(date_str))
        try:
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            print("INFO: fromisoformat success: {}".format(dt))
            return dt
        except ValueError:
            print("INFO: fromisoformat failed")
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                print("INFO: strptime success: {}".format(dt))
                return dt
            except ValueError:
                print("INFO: strptime failed")
                return None

    @staticmethod
    def parse_instagram_comment(container):
        # --- Username ---
        link_el = container.query_selector("xpath=.//a[@role='link' and @tabindex='0']")
        username = link_el.get_attribute("href") if link_el else None

        # --- Time ---
        time_el = container.query_selector("xpath=.//time[@title] | .//span[@title]")
        time = time_el.get_attribute("title") if time_el else None

        # --- Message ---
        message_el = container.query_selector(
            "xpath=.//time/ancestor::div[1]/following-sibling::*[self::span or self::div][1]"
        )
        if not message_el:
            message_el = container.query_selector(
                "xpath=.//time/ancestor::div[2]/descendant::span[normalize-space()][last()]"
            )
        message = message_el.text_content().strip() if message_el else None

        like_el = container.query_selector(
            "xpath=.//*[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'like')]"
        )

        likes = 0
        if like_el:
            likes_text = like_el.text_content().strip()
            # Extract the number of likes; default to 0 if no number found
            match = re.search(r'(\d+)', likes_text.replace('\xa0', ' '))
            if match:
                likes = int(match.group(1))


        # --- Replies ---
        reply_el = container.query_selector(
            "xpath=.//div[@role='button' and @tabindex='0' and contains(., 'View all')]"
        )
        num_replies = 0
        if reply_el:
            replies_text = reply_el.text_content().strip()
            match = re.search(r'View all (\d+) replies', replies_text)
            if match:
                num_replies = int(match.group(1))

        media_el = container.query_selector("xpath=.//img[contains(@src, '/media/')]")
        print("========= media image",media_el)
        media = media_el.get_attribute("src") if media_el else None

        # --- Parsed dictionary ---
        parsed = {
            "username": username,
            "time": time,
            "message": message,
            "likes": likes,
            "replies": num_replies
        }
        if media:
            parsed["media"] = media

        print("INFO: parsed: {}".format(parsed))
        return parsed

    @staticmethod
    def scroll_until_end(page, locator, pause=2, max_tries=5):
        locator.wait_for(state="visible", timeout=2000)
        tries = 0

        while True:
            # Try to find and click 'View hidden comments' button if present
            load_more = locator.locator('div[role="button"]:has-text("View hidden comments")')
            if load_more.count() > 0:
                try:
                    load_more.first.scroll_into_view_if_needed()
                    load_more.first.click()
                    page.wait_for_timeout(3000)  # Wait for new comments to load
                    tries = 0  # Reset tries since new content loaded
                    continue  # Continue to check again
                except Exception as e:
                    print(f"Error clicking view hidden: {e}")

            # Get current height
            last_height = locator.evaluate("el => el.scrollHeight")

            # Scroll to bottom
            locator.evaluate("el => el.scrollTo(0, el.scrollHeight)")
            page.wait_for_timeout(pause * 1000)  # Pause in ms

            # Get new height
            new_height = locator.evaluate("el => el.scrollHeight")

            if new_height == last_height:
                tries += 1
            else:
                tries = 0

            if tries >= max_tries:
                break

        return True
