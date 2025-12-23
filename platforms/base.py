from core.utils import ScraperUtils

class ScraperBase:
    def __init__(self, headless: bool = True, user_data_dir: str = None):
        self.headless = headless
        self.user_data_dir = user_data_dir
        self.utils = ScraperUtils

    def close(self):
        pass