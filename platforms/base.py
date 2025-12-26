from core.utils import ScraperUtils
from core.insta_utils import InstaUtils

class ScraperBase:
    def __init__(self, headless: bool = True, user_data_dir: str = None):
        self.headless = headless
        self.user_data_dir = user_data_dir
        self.utils = ScraperUtils
        self.insta_utils = InstaUtils

    def close(self):
        pass