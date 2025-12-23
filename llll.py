import asyncio
import json
import random
import sys
import os
from playwright.async_api import async_playwright

# ==========================================
#           USER CONFIGURATION
# ==========================================

# --- PATH TO YOUR CHROME PROFILE ---
# Replace with your actual path. 
# Note: Use raw strings (r"...") on Windows to handle backslashes.
# Windows Example:
# USER_DATA_DIR = r"C:\Users\YourName\AppData\Local\Google\Chrome\User Data"
USER_DATA_DIR = r"twitter_profile"

# If you have multiple profiles (e.g., "Profile 1", "Profile 2"), specify the name here.
# Leave empty if you just use the default "Default" profile.
PROFILE_NAME = "Default"

# Target Settings
TARGET_URL = "https://x.com/elonmusk" # Can also be "https://x.com/home" for feed
MAX_POSTS = 3
HEADLESS = False # Keep False to verify your profile loaded correctly

# Output
OUTPUT_FILE = "tweets_data.json"

# ==========================================
#               THE SCRIPT
# ==========================================

def get_tweet_data(tweet_element):
    """Extracts data from a single tweet element."""
    try:
        # Text
        text_element = tweet_element.locator('[data-testid="tweetText"]').first
        text = text_element.inner_text() if text_element.count() > 0 else ""

        # Author Info
        name_element = tweet_element.locator('[data-testid="User-Name"]').first
        author = name_element.inner_text() if name_element.count() > 0 else ""

        # Stats (Likes, Retweets, Replies)
        # X uses aria-label for counts (e.g., "1,200 Likes")
        like_elem = tweet_element.locator('[data-testid="like"]').first
        like_label = like_elem.get_attribute('aria-label') if like_elem.count() > 0 else "0 likes"

        rt_elem = tweet_element.locator('[data-testid="retweet"]').first
        rt_label = rt_elem.get_attribute('aria-label') if rt_elem.count() > 0 else "0 reposts"

        reply_elem = tweet_element.locator('[data-testid="reply"]').first
        reply_label = reply_elem.get_attribute('aria-label') if reply_elem.count() > 0 else "0 replies"

        return {
            "text": text,
            "author": author.replace('\n', ' | '),
            "stats": {
                "likes": like_label,
                "retweets": rt_label,
                "replies": reply_label
            }
        }
    except Exception as e:
        # print(f"Parse error: {e}")
        return None

async def main():
    # Validation
    if not os.path.exists(USER_DATA_DIR):
        print(f"[ERROR] The path '{USER_DATA_DIR}' does not exist.")
        print("Please update the USER_DATA_DIR variable with your actual Chrome profile path.")
        sys.exit(1)

    print("--- X.com Profile Scraper ---")
    print(f"Loading Profile: {USER_DATA_DIR}")
    print(f"Target: {TARGET_URL}")
    print(f"Goal: {MAX_POSTS} posts")

    async with async_playwright() as p:
        # 1. Launch Persistent Context (The Magic Step)
        # 'channel="chrome"' forces it to use your actual Chrome installation 
        # rather than the bundled Chromium, ensuring better compatibility.
        context = await p.chromium.launch_persistent_context(
            USER_DATA_DIR,
            headless=HEADLESS,
            channel="chrome",
            args=["--disable-blink-features=AutomationControlled"], # Helps bypass bot detection
            viewport={'width': 1280, 'height': 800}
        )

        # If multiple pages open (like the Chrome welcome page), close extras or use the main one
        if len(context.pages) > 0:
            page = context.pages[0]
        else:
            page = await context.new_page()

        # 2. Go to Target
        print("[*] Navigating...")
        await page.goto(TARGET_URL, wait_until="domcontentloaded")

        # Give a moment for login cookies to be processed
        await asyncio.sleep(2)

        # 3. Scrape Loop
        scraped_tweets = []
        seen_tweets = set()
        last_height = 0

        print("[*] Scraping loop started...")

        while len(scraped_tweets) < MAX_POSTS:
            tweets_locator = page.locator('article[data-testid="tweet"]')
            count = await tweets_locator.count()

            for i in range(count):
                if len(scraped_tweets) >= MAX_POSTS:
                    break

                try:
                    tweet = tweets_locator.nth(i)
                    text_preview = await tweet.locator('[data-testid="tweetText"]').inner_text() if await tweet.locator('[data-testid="tweetText"]').count() > 0 else ""
                    unique_id = f"{text_preview[:50]}"

                    if unique_id not in seen_tweets:
                        data = get_tweet_data(tweet)
                        if data:
                            scraped_tweets.append(data)
                            seen_tweets.add(unique_id)
                            print(f"Collected: {len(scraped_tweets)}/{MAX_POSTS}")
                except Exception:
                    continue

            # Human-like scrolling
            scroll_height = await page.evaluate("document.body.scrollHeight")
            await page.evaluate(f"window.scrollTo(0, {scroll_height - random.randint(100, 500)})")
            await asyncio.sleep(random.uniform(1.0, 2.5))

            # Check for end of page
            current_height = await page.evaluate("document.body.scrollHeight")
            if current_height == last_height:
                print("[*] End of page reached.")
                break
            last_height = current_height

        # 4. Save Data
        print("\n--- Scraping Complete ---")
        print(f"Total tweets scraped: {len(scraped_tweets)}")

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(scraped_tweets, f, indent=4, ensure_ascii=False)

        print(f"Saved to: {OUTPUT_FILE}")

        await context.close()

if __name__ == "__main__":
    asyncio.run(main())