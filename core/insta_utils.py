from tqdm import tqdm
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
    def prepare_target(text):
        if not text:
            return None
        text = text.strip()
        if text.startswith('@'):
            target = f"https://www.instagram.com/{text[1:]}/"
            return target
        elif text.startswith('#'):
            target = f"https://www.instagram.com/explore/tags/{text[1:]}/"
            return target
        elif 'instagram.com' in text:
            return text
        else:
            target = f"https://www.instagram.com/explore/search/keyword/?q={text}"
            return target

    @staticmethod
    def random_delay(min_sec, max_sec):
        delay = random.uniform(min_sec, max_sec)
        time.sleep(delay)

    @staticmethod
    def scroll_page(page, pause, max_scrolls):
        for i in range(max_scrolls):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(pause)
        print("INFO: scroll_page finished")

    @staticmethod
    def convert_date(date_str):
        try:
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return dt
        except ValueError:
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                return dt
            except ValueError:
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

        return parsed


    @staticmethod
    def scroll_until_end(page, locator, pause=2, max_tries=3):
        locator.wait_for(state="visible", timeout=2000)
        tries = 0

        # Get initial scroll height
        last_height = locator.evaluate("el => el.scrollHeight")

        RED     = "\033[91m"
        GREEN   = "\033[92m"
        YELLOW  = "\033[93m"
        BLUE    = "\033[94m"
        MAGENTA = "\033[95m"
        CYAN    = "\033[96m"
        RESET   = "\033[0m"


       # Initialize tqdm progress bar
        progress_bar = tqdm(
            total=last_height,
            bar_format=f"{GREEN}Scrolling comments:{RESET} {{bar}} |{{percentage:3.0f}}% | Time: {{elapsed}}",
            colour="blue",
        )
        while True:
            # Try to find and click 'View hidden comments' button if present
            load_more = locator.locator('div[role="button"]:has-text("View hidden comments")')
            if load_more.count() > 0:
                try:
                    load_more.first.scroll_into_view_if_needed()
                    load_more.first.click()
                    page.wait_for_timeout(3000)
                    tries = 0
                    continue
                except Exception as e:
                    print(f"Error clicking view hidden: {e}")

            # Get current scroll position
            current_height = locator.evaluate("el => el.scrollTop + el.clientHeight")
            total_height = locator.evaluate("el => el.scrollHeight")

            # Scroll to bottom
            locator.evaluate("el => el.scrollTo(0, el.scrollHeight)")
            page.wait_for_timeout(pause * 1000)

            # Update progress bar
            progress_bar.total = total_height  # update total if new content loaded
            progress_bar.n = min(current_height, total_height)
            progress_bar.refresh()

            # Check if scroll height changed
            new_height = locator.evaluate("el => el.scrollHeight")
            if new_height == total_height:
                tries += 1
            else:
                tries = 0

            if tries >= max_tries:
                break

        progress_bar.n = progress_bar.total
        progress_bar.refresh()
        progress_bar.close()
        return True

