# platforms/universal_scraper.py
from platforms.instagram_scraper import InstagramScraper
from platforms.x_scraper import XScraper
from core.utils import ScraperUtils

class UniversalScraper:
    """
    Unified scraper class for Instagram and X platforms with flexible modes.
    """
    def __init__(self, platform: str = 'x', username: str = None, password: str = None, headless: bool = False, user_data_dir: str = None):
        """
        Initialize the scraper with platform and credentials.

        :param platform: 'instagram' or 'x'
        :param username: Login username
        :param password: Login password
        :param headless: Whether to run browser in headless mode
        :param user_data_dir: Path to Chrome user data dir for speed (optional, defaults to system)
        """
        self.platform = platform.lower()
        self.username = username
        self.password = password
        self.headless = headless
        self.user_data_dir = user_data_dir
        self.scraper = None
        self._initialize_scraper()

    def _initialize_scraper(self):
        if self.platform == 'instagram':
            self.scraper = InstagramScraper(headless=self.headless, user_data_dir=self.user_data_dir)
        elif self.platform == 'x':
            self.scraper = XScraper(headless=self.headless, user_data_dir=self.user_data_dir)
        else:
            raise ValueError(f"Unsupported platform: {self.platform}")

        # Attempt login
        if not self.scraper.login(username=self.username, password=self.password):
            raise Exception(f"{self.platform.capitalize()} login failed. Check credentials or network connection.")

    def run(self, search_text: str = "#Python", max_posts: int = 2,
            mode: str = 'search', single_href: str = None, blind_url: str = None) -> list:
        results = []
        try:
            if mode == 'search':
                results = self.scraper.search(text=search_text, max_posts=max_posts)

            elif mode == 'single':
                if not single_href:
                    raise ValueError("single_href is required for 'single' mode")
                results = self.scraper.search(text=single_href)

            elif mode == 'blind':
                # Determine target URL. If blind_url is provided, use it.
                # Otherwise, default to the current page (Home/Feed).
                target_url = blind_url if blind_url else self.scraper.driver.url

                # Pass the URL directly to blind_scrape to avoid double navigation
                # (The scraper handles the goto internally)
                results = self.scraper.blind_scrape(url=target_url, max_posts=max_posts)

            else:
                raise ValueError(f"Unsupported mode: {mode}")

        except Exception as e:
            ScraperUtils.log_error(f"Scraper run failed for {self.platform} in {mode} mode: {e}")
            # Re-raise or handle as necessary. Currently returning empty list on failure.

        finally:
            # Ensure the browser is closed after the run
            if self.scraper:
                self.scraper.close()

        return results