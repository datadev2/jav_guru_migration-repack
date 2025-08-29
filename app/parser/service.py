from typing import Optional
from beanie.operators import In
from pymongo import UpdateOne
from selenium.webdriver.common.by import By

from app.db.database import init_mongo
from app.db.models import Category, Video
from app.parser.driver import SeleniumDriver
from app.parser.interactions import SeleniumService
from app.parser.base import ParserAdapter
from app.logger import init_logger


logger = init_logger()

class Parser(SeleniumDriver):
    def __init__(self, adapter: ParserAdapter, headless: bool = True):
        super().__init__(headless=headless)
        self.selenium = SeleniumService(self.driver)
        self.adapter = adapter

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.driver.quit()

    def init_adblock(self):
        try:
            self.selenium.get("about:blank")
            handles = self.driver.window_handles
            if len(handles) < 2:
                return
            second = handles[-1]
            if second != self.driver.current_window_handle:
                self.driver.switch_to.window(second)
            self.driver.close()
            self.driver.switch_to.window(self.driver.window_handles[0])
        except Exception:
            pass

    def parse_videos(self) -> list[Video]:
        return self.adapter.parse_videos(self.selenium)
