from fake_useragent import FakeUserAgent
from selenium import webdriver
from selenium_stealth import stealth

from app.config import config


class SeleniumDriver:
    def __init__(
        self,
        driver_path : str = config.DRIVER or None,
        adblock_path: str = config.AD_BLOCK,
        headless: bool = True,
    ):
        chrome_service = (
            webdriver.ChromeService(executable_path=driver_path)
            if driver_path else webdriver.ChromeService()
        )
        
        options = webdriver.ChromeOptions()

        if adblock_path:
            options.add_argument(adblock_path)

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
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        prefs = {
            "profile.managed_default_content_settings.images": 2,   # off images
            "profile.managed_default_content_settings.javascript": 1,  # on js
            "profile.managed_default_content_settings.notifications": 2,  # off notifications
            "profile.managed_default_content_settings.media_stream": 2,  # off media
        }
        options.add_experimental_option("prefs", prefs)
        
        self.driver = webdriver.Chrome(options=options, service=chrome_service)
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
        self.driver.quit()