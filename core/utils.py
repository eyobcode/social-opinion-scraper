import json
import logging
import random
import time
import os
from datetime import datetime
from pathlib import Path
from pprint import pprint
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
import re

# Setup logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger('scraper')


class ScraperUtils:
    @staticmethod
    def log_error(message):
        logger.error(message)

    @staticmethod
    def log_info(message):
        logger.info(message)

    @staticmethod
    def log_success(message):
        logger.info(message)

    @staticmethod
    def load_cookies(path):
        if os.path.exists(path):
            with open(path, 'r') as f:
                return json.load(f)
        return None

    @staticmethod
    def save_cookies(cookies, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            json.dump(cookies, f)

    @staticmethod
    def random_delay(min_delay=1.0, max_delay=3.0):
        time.sleep(random.uniform(min_delay, max_delay))

    @staticmethod
    def convert_date(date_str):
        try:
            from dateutil import parser
            return parser.isoparse(date_str)
        except ImportError:
            from datetime import datetime
            try:
                return datetime.strptime(date_str, '%a %b %d %H:%M:%S %z %Y')
            except ValueError:
                return None

    # --- HELPER METHODS FOR JSON PARSING ---

    @staticmethod
    def _get_text_from_objects(legacy, tweet_result):
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
            try:
                note_tweet = tweet_result.get('note_tweet', {})
                note_result = note_tweet.get('note_tweet_results', {}).get('result', {})
                text = note_result.get('text') or note_result.get('full_text')
            except Exception:
                pass
        return text

    @staticmethod
    def _get_handle_from_user(user_result, user_legacy, user_core):
        handle_dicts = [user_core, user_legacy, user_result]
        handle_keys = ['screen_name', 'username', 'handle', 'user_name', 'user_commenter']
        user_handle = None
        for d in handle_dicts:
            for k in handle_keys:
                if k in d:
                    user_handle = d[k]
                    break
            if user_handle:
                break
        return user_handle

    @staticmethod
    def _get_media_from_legacy(legacy, tweet_result):
        # Ensure we are using the correct variable names
        extended_entities = legacy.get('extended_entities') or tweet_result.get('extended_entities') or {}
        media_items = extended_entities.get('media', [])
        media_list = []
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
            media_list.append(media_obj)
        return media_list

    @staticmethod
    def parse_tweet_json(data):
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
        post["text"] = ScraperUtils._get_text_from_objects(legacy, main_tweet_result)

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
        post["media"] = ScraperUtils._get_media_from_legacy(legacy, main_tweet_result)

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
            else:
                quoted_user_result = quoted_user_result

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

    @staticmethod
    def parse_comments_from_json(data):
        """
        Extracts comments from a single TweetDetail JSON response.
        Returns a list of comment dictionaries.
        """
        comments = []
        seen = set()

        try:
            data_dict = data if isinstance(data, dict) else json.loads(data)
        except Exception:
            return comments

        instructions = data_dict.get('data', {}).get('threaded_conversation_with_injections_v2', {}).get('instructions', [])
        for instr in instructions:
            if instr.get('type') == 'TimelineAddEntries':
                entries = instr.get('entries', [])
                for entry in entries:
                    entry_id = entry.get('entryId', '')
                    # Filter for conversation threads, but ensure we don't pick up main tweet
                    if entry_id.startswith('conversationthread-'):
                        items = entry.get('content', {}).get('items', [])

                        for item in items:
                            # Scope variables for this iteration
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
                                local_legacy = tweet_result['legacy']
                                if 'retweeted_status' in local_legacy:
                                    inner_result = local_legacy['retweeted_status']
                                    inner_type = 'repost'
                                elif 'quoted_status' in local_legacy:
                                    inner_result = local_legacy['quoted_status']
                                    inner_type = 'quote'

                            # Define scope for current comment (outer)
                            core = tweet_result.get('core', {})
                            user_results = core.get('user_results', {}).get('result', {})

                            if user_results.get('__typename') == 'UserWithVisibilityResults':
                                user_result = user_results.get('user', {})
                            else:
                                user_result = user_results

                            user_core = user_result.get('core', {})
                            user_result_legacy = user_result.get('legacy', {})
                            legacy = tweet_result.get('legacy', {})

                            # Extract Text (Outer)
                            text = ScraperUtils._get_text_from_objects(legacy, tweet_result)

                            # Extract Handle (Outer)
                            user_handle = ScraperUtils._get_handle_from_user(user_result, user_result_legacy, user_core)
                            user = f"https://x.com/{user_handle}" if user_handle else None

                            # Extract Timestamp (Outer)
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

                            # Extract Likes (Outer)
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

                            # Extract Reposts (Outer)
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

                            # Extract Views (Outer)
                            views_obj = tweet_result.get('views', {}) or tweet_result.get('view_count', {})
                            views = str(views_obj.get('count') or views_obj.get('value') or tweet_result.get('view_count') or '')

                            # Only build comment if user and text exist
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

                                # Media Extraction (Outer)
                                media = ScraperUtils._get_media_from_legacy(legacy, tweet_result)
                                img = next((m['media_url'] for m in media if m['type'] == 'photo'), None)
                                video = None
                                for m in media:
                                    if m['type'] in ['video', 'animated_gif']:
                                        variants = m.get('variants', [])
                                        if variants:
                                            video = max(variants, key=lambda v: v.get('bitrate', 0))['url']
                                        break
                                if img:
                                    comment["img"] = img
                                if video:
                                    comment["video"] = video

                                # Handle inner post (Nested)
                                inner_img = None
                                inner_video = None
                                if inner_result:
                                    inner_legacy_data = inner_result.get('legacy', {}) if 'legacy' in inner_result else inner_result
                                    inner_core_data = inner_result.get('core', {})
                                    inner_user_results_data = inner_core_data.get('user_results', {}).get('result', {})
                                    if inner_user_results_data.get('__typename') == 'UserWithVisibilityResults':
                                        inner_user_results_data = inner_user_results_data.get('user', {})
                                    inner_user_core_data = inner_user_results_data.get('core', {})
                                    inner_user_legacy_data = inner_user_results_data.get('legacy', {})
                                    inner_text = ScraperUtils._get_text_from_objects(inner_legacy_data, inner_result)
                                    inner_user_handle = ScraperUtils._get_handle_from_user(inner_user_results_data, inner_user_legacy_data, inner_user_core_data)
                                    inner_user = f"https://x.com/{inner_user_handle}" if inner_user_handle else None
                                    # Build repost
                                    repost_post = {}
                                    repost_post["id"] = inner_result.get('rest_id') or inner_legacy_data.get('id_str')
                                    repost_post["created_at"] = inner_legacy_data.get('created_at') or inner_result.get('created_at')
                                    repost_post["text"] = inner_text
                                    repost_post["author"] = {
                                        "name": inner_user_core_data.get('name') or inner_user_results_data.get('name') or inner_user_legacy_data.get('name'),
                                        "screen_name": inner_user_handle,
                                        "rest_id": inner_user_results_data.get('rest_id'),
                                        "avatar_url": inner_user_results_data.get('profile_image_url') or inner_user_results_data.get('avatar', {}).get('image_url') or inner_user_legacy_data.get('profile_image_url_https')
                                    }
                                    repost_post["metrics"] = {
                                        "favorite_count": inner_legacy_data.get('favorite_count') or inner_result.get('favorite_count'),
                                        "reply_count": inner_legacy_data.get('reply_count') or inner_result.get('reply_count'),
                                        "retweet_count": inner_legacy_data.get('retweet_count') or inner_result.get('retweet_count'),
                                        "quote_count": inner_legacy_data.get('quote_count') or inner_result.get('quote_count'),
                                        "views_count": inner_result.get('views', {}).get('count')
                                    }
                                    entities = inner_legacy_data.get('entities', {}) or inner_result.get('entities', {})
                                    repost_post["entities"] = {
                                        "hashtags": entities.get('hashtags', []),
                                        "urls": entities.get('urls', []),
                                        "user_mentions": entities.get('user_mentions', [])
                                    }
                                    repost_post["media"] = ScraperUtils._get_media_from_legacy(inner_legacy_data, inner_result)
                                    if not repost_post["text"]:
                                        note_tweet = inner_result.get('note_tweet', {})
                                        note_result = note_tweet.get('note_tweet_results', {}).get('result', {})
                                        repost_post["text"] = note_result.get('text') or note_result.get('full_text')
                                    repost_url = legacy.get('quoted_status_permalink', {}).get('expanded') or inner_result.get('quoted_status_permalink', {}).get('expanded')
                                    if not repost_url and inner_user_handle and repost_post["id"]:
                                        repost_url = f"https://x.com/{inner_user_handle}/status/{repost_post['id']}"
                                    if repost_url and 'twitter.com' in repost_url:
                                        repost_url = repost_url.replace('twitter.com', 'x.com')
                                    comment["repost"] = {
                                        "url": repost_url,
                                        "post": repost_post
                                    }
                                    # Add inner media to top level if not present
                                    inner_media = repost_post["media"]
                                    inner_img = next((m['media_url'] for m in inner_media if m['type'] == 'photo'), None)
                                    inner_video = None
                                    for m in inner_media:
                                        if m['type'] in ['video', 'animated_gif']:
                                            variants = m.get('variants', [])
                                            if variants:
                                                inner_video = max(variants, key=lambda v: v.get('bitrate', 0))['url']
                                            break
                                if inner_img and "img" not in comment:
                                    comment["img"] = inner_img
                                if inner_video and "video" not in comment:
                                    comment["video"] = inner_video

                                comments.append(comment)

        return comments

    @staticmethod
    def extract_comments(page, max_scrolls=30, max_no_change=3):
        """
        Extracts additional comments by scrolling page and intercepting GraphQL responses.
        Returns a list of comment dictionaries.
        """
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

        # Attach listener
        page.on("response", handle_response)

        # Scroll whole page logic as requested
        # We are already on page, but scrolling triggers new requests

        last_height = page.evaluate("document.body.scrollHeight")
        scrolls = 0
        no_change_count = 0

        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(), TextColumn("[progress.percentage]{task.percentage:>3.0f}%")) as progress:
            task_load = progress.add_task("[magenta]Loading comments...", total=max_scrolls)

            while scrolls < max_scrolls and no_change_count < max_no_change:
                # Scroll to bottom of page (whole page)
                page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                page.wait_for_timeout(2000)  # Wait for content to load

                # Handle "Show" buttons (replies/spam)
                try:
                    # prefer explicit xpath prefix for xpath selectors
                    button_selectors = ["xpath=//button[contains(., 'Show probable spam')]", "div[role='button']:has-text('Show')"]
                    for selector in button_selectors:
                        try:
                            locator = page.locator(selector)
                            count = locator.count()
                            for i in range(count):
                                try:
                                    btn = locator.nth(i)
                                    if btn.is_visible():
                                        btn.click()
                                        page.wait_for_timeout(500)
                                        no_change_count = 0
                                except Exception:
                                    pass
                        except Exception:
                            pass
                except Exception:
                    pass

                new_height = page.evaluate("document.body.scrollHeight")
                if new_height == last_height:
                    no_change_count += 1
                else:
                    no_change_count = 0
                    last_height = new_height

                scrolls += 1
                progress.update(task_load, advance=1)

        # Remove listener
        try:
            page.off("response", handle_response)
        except Exception:
            # fallback if page.off unavailable
            try:
                page.remove_listener("response", handle_response)
            except Exception:
                pass

        ScraperUtils.log_info(f"Scroll finished. Parsing {len(captured)} additional responses.")

        # Parse captured GraphQL JSONs for comments
        for data in captured:
            try:
                # Use the robust parser utility
                batch_comments = ScraperUtils.parse_comments_from_json(data)
                for c in batch_comments:
                    # Dedup based on user + text snippet
                    key = f"{c.get('user', '')}||{c.get('text', '')[:200]}"
                    if key not in seen:
                        seen.add(key)
                        comments.append(c)
            except Exception:
                pass
        ScraperUtils.log_info(f"Extracted {len(comments)} additional comments via scroll.")
        return comments
    @staticmethod
    def _make_serializable(obj):
        """ Recursively convert datetime to ISO string for JSON serialization. """
        if isinstance(obj, dict):
            return {k: ScraperUtils._make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [ScraperUtils._make_serializable(i) for i in obj]
        elif isinstance(obj, datetime):
            return obj.isoformat()
        else:
            return obj

    @staticmethod
    def save_json(path: str, data):
        base_dir = Path("data")
        path = Path(path)

        if path.parent == Path("."):
            path = base_dir / path.name
        else:
            path = base_dir / path

        path.parent.mkdir(parents=True, exist_ok=True)

        serializable_data = ScraperUtils._make_serializable(data)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(serializable_data, f, ensure_ascii=False, indent=2)