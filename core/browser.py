import random
import os
from playwright.sync_api import sync_playwright

class BrowserEngine:
    def __init__(self, headless: bool = False, window_size: str = "1280,900", user_data_dir: str | None = None):
        # Dedicated directory for Playwright profile to avoid conflicts
        self.user_data_dir = user_data_dir or os.path.join(os.getcwd(), "chrome_profile")
        os.makedirs(self.user_data_dir, exist_ok=True)
        self.headless = headless
        self.window_size = window_size
        self.playwright = None
        self.context = None
        self.page = None

    def create_driver(self):
        self.playwright = sync_playwright().start()
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
        ]
        ua = random.choice(user_agents)
        width, height = map(int, self.window_size.split(','))
        self.context = self.playwright.chromium.launch_persistent_context(
            self.user_data_dir,
            headless=self.headless,
            viewport={"width": width, "height": height},
            user_agent=ua,
            bypass_csp=True,
            ignore_https_errors=True,
            java_script_enabled=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-infobars',
                '--disable-notifications',
                '--disable-dev-shm-usage',
                '--disable-gpu' if self.headless else '',
                '--disable-web-security',
                '--disable-site-isolation-trials',
                '--no-experiments',
                '--allow-running-insecure-content',
                '--disable-features=IsolateOrigins,site-per-process',
                '--disable-setuid-sandbox'
            ],
            slow_mo=100 if not self.headless else 0  # Slight delay for realism in non-headless
        )
        self.page = self.context.new_page()


        # Additional enhanced stealth scripts (layered on top of stealth plugin)
        self.page.add_init_script("""
        Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});
        Object.defineProperty(navigator, 'deviceMemory', {get: () => 8});
        Object.defineProperty(navigator, 'maxTouchPoints', {get: () => 0});
        window.chrome = { runtime: {} };
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
          parameters.name === 'notifications' ?
            Promise.resolve({ state: Notification.permission }) :
            originalQuery(parameters)
        );
        """)

        return self.page

    def get_driver(self):
        if self.page is None:
            return self.create_driver()
        return self.page

    def restart_driver(self):
        self.quit_driver()
        return self.create_driver()

    def quit_driver(self):
        if self.context:
            self.context.close()
        if self.playwright:
            self.playwright.stop()