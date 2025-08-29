from typing import Optional
from selenium.webdriver.common.by import By

from app.db.models import Video, Category
from app.parser.interactions import SeleniumService
from app.logger import init_logger

logger = init_logger()


class GuruAdapter:
    site_name = "guru"
    BASE_URL = "https://jav.guru/"

    def parse_videos(self, selenium: SeleniumService) -> list[Video]:
        page = 1
        while True:
            url = self.BASE_URL if page == 1 else f"{self.BASE_URL}page/{page}/"
            logger.info(f"[GuruAdapter] Open page {page}: {url}")

            selenium.get(url, (By.CLASS_NAME, "site-logo"))

            logo = selenium.wait_for_element((By.CLASS_NAME, "site-logo"))
            if not logo:
                logger.info(f"[GuruAdapter] No logo found, stop at page {page}")
                break


            logger.info(f"[GuruAdapter] Logo found on page {page}")
            page += 1

    def parse_video(self, selenium: SeleniumService, video: Video) -> Optional[Video]:
        pass