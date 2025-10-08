import undetected_chromedriver as uc
from fake_useragent import FakeUserAgent
from selenium_stealth import stealth

from app.config import config


class SeleniumDriver:
    def __init__(
        self,
        driver_path: str | None = config.DRIVER or None,
        adblock_path: str = config.AD_BLOCK,
        headless: bool = True,
        skip_driver: bool = False,
    ):
        if skip_driver:
            self.driver = None
            return

        options = uc.ChromeOptions()

        if adblock_path:
            options.add_argument(f"--load-extension={adblock_path}")

        user_agent = FakeUserAgent().googlechrome
        options.add_argument(f"user-agent={user_agent}")

        if headless:
            options.add_argument("--headless=new")
        else:
            options.add_argument("--start-maximized")

        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--ignore-certificate-errors")

        prefs = {
            "profile.managed_default_content_settings.images": 2,  # off images
            "profile.managed_default_content_settings.javascript": 1,  # on js
            "profile.managed_default_content_settings.notifications": 2,  # off notifications
            "profile.managed_default_content_settings.media_stream": 2,  # off media
        }
        options.add_experimental_option("prefs", prefs)

        self.driver = uc.Chrome(
            driver_executable_path=driver_path,
            options=options,
            headless=headless,
        )

        stealth(
            self.driver,
            languages=["en-US", "en"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True,
            run_on_insecure_origins=True,
        )

    def __enter__(self):
        return self.driver

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.driver:
            self.driver.quit()
