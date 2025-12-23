import json
import logging
import random
import time
from datetime import datetime
import os
from pathlib import Path


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
            return datetime.strptime(date_str, '%a %b %d %H:%M:%S %z %Y')
        except ValueError:
            return None

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