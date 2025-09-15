from selenium.webdriver.common.by import By

from app.db.models import Category, Tag
from app.parser.interactions import SeleniumService
from loguru import logger


class JavctAdapter:
    site_name = "javct"
    BASE_URL = "https://javct.net"
    CATEGORIES_URL = "https://javct.net/categories"

    def parse_tags(self, selenium: SeleniumService) -> list[Tag]:
        logger.info(f"[JavctAdapter] Method not implemented")
        return None

    def parse_categories(self, selenium: SeleniumService) -> list[Category]:
        selenium.get(self.CATEGORIES_URL, (By.XPATH, "//span[@class='label-category']"))

        categories: dict[str, Category] = {}
        els = selenium.find_elements("//div[@class='card__content']//h3[@class='card__title']/a")
        for el in els:
            try:
                name = el.text.strip()
                href = el.get_attribute("href")
                if name and name not in categories:
                    categories[name] = Category(name=name, source_url=href, site=self.site_name)
                    logger.info(f"[JavctAdapter] Found category: {name}")
            except Exception as e:
                logger.warning(f"[JavctAdapter] Failed to parse category element: {e}")

        return list(categories.values())