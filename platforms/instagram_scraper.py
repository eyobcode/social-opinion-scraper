from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from platforms.base import ScraperBase
from core.browser import BrowserEngine
import json
import time
import re
import os

class InstagramScraper(ScraperBase):
    def __init__(self, headless: bool = True, user_data_dir: str = None):
        super().__init__(headless=headless, user_data_dir=user_data_dir)
        self.browser_engine = BrowserEngine(headless=headless, user_data_dir=user_data_dir)
        self.page = self.browser_engine.create_driver()
        self.context = self.browser_engine.context

    def _find_element_with_selectors(self, selectors, timeout=10):
        for sel in selectors:
            try:
                elem = self.page.locator(sel)
                elem.wait_for(state='visible', timeout=timeout * 1000)
                return elem
            except PlaywrightTimeoutError:
                continue
        return None

    def _find_elements_with_selectors(self, selectors):
        for sel in selectors:
            try:
                elements = self.page.locator(sel).all()
                if elements:
                    return elements
            except Exception:
                continue
        return []

    def login(self, username: str = None, password: str = None, cookie_path="cookies/x_cookies.json"):
        def retry_goto(url, max_retries=3, timeout=60000):
            for attempt in range(max_retries):
                try:
                    self.page.goto(url, timeout=timeout)
                    self.page.wait_for_load_state('networkidle', timeout=timeout)
                    return True
                except Exception as e:
                    self.utils.log_error(f"Attempt {attempt+1} failed for {url}: {e}")
                    if attempt == max_retries - 1:
                        return False
                    time.sleep(5)  # Wait before retry

        # Priority 1: Try cookies or existing session
        cookies = self.utils.load_cookies(path=cookie_path)  # Returns None if not exist
        if cookies:
            self.context.add_cookies(cookies)
            self.utils.log_info("Loaded existing cookies.")

        # Attempt to access home to check if logged in
        if not retry_goto("https://x.com/home"):
            return False

        # Check current URL after attempting home
        current_url = self.page.url
        if "/home" in current_url:
            self.utils.log_success("Logged in via cookies or existing session.")
            self.utils.save_cookies(self.context.cookies(), path=cookie_path)  # Update cookies
            return True
        else:
            self.utils.log_info("Not logged in; redirected to {current_url}. Proceeding to login.")

        # Ensure we are on the login page
        if "/login" not in current_url and "/i/flow/login" not in current_url:
            if not retry_goto("https://x.com/i/flow/login"):
                return False

        # Priority 2: If username and password provided, attempt auto login
        if username and password:
            try:
                # Username step
                username_selectors = [
                    'input[name="text"][autocomplete="username"]',
                    'input[name="text"]'
                ]
                username_input = self._find_element_with_selectors(username_selectors, timeout=20)
                if not username_input:
                    raise PlaywrightTimeoutError("Username input not found.")
                username_input.fill(username)

                # Next button
                next_button_selectors = [
                    'xpath=//button[.//span[contains(text(), "Next")]]',
                    'button[data-testid*="Next"]'
                ]
                next_btn = self._find_element_with_selectors(next_button_selectors, timeout=20)
                if next_btn:
                    next_btn.click()
                    self.page.wait_for_load_state('load', timeout=60000)
                else:
                    raise PlaywrightTimeoutError("Next button not found.")

                # Possible intermediate verification (e.g., confirm handle)
                verification_selectors = [
                    'input[name="text"][autocomplete="username"]',
                    'input[name="text"]'
                ]
                try:
                    verification_input = self._find_element_with_selectors(verification_selectors, timeout=10)
                    if verification_input:
                        handle = username.split('@')[0] if '@' in username else username
                        verification_input.fill(handle)
                        next_btn = self._find_element_with_selectors(next_button_selectors, timeout=10)
                        if next_btn:
                            next_btn.click()
                            self.page.wait_for_load_state('load', timeout=60000)
                except PlaywrightTimeoutError:
                    self.utils.log_info("No verification step detected; proceeding.")

                # Password step
                password_selectors = [
                    'input[name="password"][autocomplete="current-password"]',
                    'input[name="password"]'
                ]
                password_input = self._find_element_with_selectors(password_selectors, timeout=20)
                if not password_input:
                    raise PlaywrightTimeoutError("Password input not found.")
                password_input.fill(password)

                # Login button
                login_button_selectors = [
                    'xpath=//button[.//span[contains(text(), "Log in")]]',
                    'button[data-testid="ocf_LoginSubmitButton"]',
                    'button[data-testid*="Login_Button"]'
                ]
                login_btn = self._find_element_with_selectors(login_button_selectors, timeout=20)
                if login_btn:
                    login_btn.click()
                    self.page.wait_for_load_state('networkidle', timeout=60000)
                else:
                    raise PlaywrightTimeoutError("Login button not found.")

                self.page.wait_for_url(lambda url: not "/login" in url, timeout=60000)

                # Handle post-login popups
                popup_selectors = [
                    'xpath=//button[contains(@data-testid, "skip") or .//span[contains(text(), "Skip")]]',
                    'xpath=//button[.//span[contains(text(), "Not now")]]'
                ]
                try:
                    popup_btn = self._find_element_with_selectors(popup_selectors, timeout=10)
                    if popup_btn:
                        popup_btn.click()
                        self.utils.log_info("Handled post-login popup.")
                except PlaywrightTimeoutError:
                    self.utils.log_info("No post-login popup detected.")

            except Exception as e:
                self.utils.log_error(f"Auto login failed: {e}. Check for CAPTCHA, 2FA, or invalid credentials.")
                return False
        else:
            # Priority 3: Manual login if no credentials and not headless
            if self.headless:
                self.utils.log_error("No credentials provided and headless mode enabled; cannot perform manual login.")
                return False
            try:
                print("Please complete the login manually in the opened browser window.")
                input("Press Enter when login is complete and you are on the home page...")
                self.page.wait_for_load_state('networkidle', timeout=60000)
                # Handle post-login popups
                popup_selectors = [
                    'xpath=//button[contains(@data-testid, "skip") or .//span[contains(text(), "Skip")]]',
                    'xpath=//button[.//span[contains(text(), "Not now")]]'
                ]
                try:
                    popup_btn = self._find_element_with_selectors(popup_selectors, timeout=10)
                    if popup_btn:
                        popup_btn.click()
                        self.utils.log_info("Handled post-login popup.")
                except PlaywrightTimeoutError:
                    self.utils.log_info("No post-login popup detected.")
            except Exception as e:
                self.utils.log_error(f"Manual login setup failed: {e}")
                return False

        # Final verification
        try:
            if not retry_goto("https://x.com/home"):
                return False
            home_selectors = [
                'xpath=//div[@data-testid="primaryColumn"]',
                'xpath=//div[@data-testid="Home"]'
            ]
            if self._find_element_with_selectors(home_selectors, timeout=20):
                self.utils.save_cookies(self.context.cookies(), path=cookie_path)
                self.utils.log_success("Login verified and cookies saved.")
                return True
            else:
                self.utils.log_error(f"Login verification failed. Current URL: {self.page.url}")
                return False
        except Exception as e:
            self.utils.log_error(f"Post-login verification error: {e}")
            return False

    def search(self, text: str, max_posts=5):
        # Implement Instagram search logic here
        return []  # Placeholder

    def close(self):
        self.browser_engine.quit_driver()