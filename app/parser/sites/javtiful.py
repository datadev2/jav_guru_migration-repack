from app.db.models import Category
from app.logger import init_logger
from selenium.webdriver.common.by import By
from app.parser.interactions import SeleniumService

logger = init_logger()


class JavtifulAdapter:
    site_name = "javtiful"
    BASE_URL = "https://javtiful.com"
    CATEGORIES_URL = "https://javtiful.com/categories"


    def parse_categories(self, selenium: SeleniumService) -> list[Category]:
        selenium.get(self.CATEGORIES_URL, (By.XPATH, "//span[@class='label-category']"))

        categories: dict[str, Category] = {}
        els = selenium.find_elements("//a[@class='category-tmb']")
        for el in els:
            try:
                name_el = el.find_element(By.XPATH, ".//span[@class='label-category']")
                name = name_el.text.strip()
                href = el.get_attribute("href")
                if name and name not in categories:
                    categories[name] = Category(name=name, source_url=href, site=self.site_name)
                    logger.info(f"[JavtifulAdapter] Found category: {name}")
            except Exception as e:
                logger.warning(f"[JavtifulAdapter] Failed to parse category element: {e}")

        return list(categories.values())