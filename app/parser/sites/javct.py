from loguru import logger
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

from app.db.models import Category, Tag, Video
from app.parser.interactions import SeleniumService


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
    
    def enrich_video(
        self, selenium: SeleniumService, video: Video, all_categories: list[Category], all_tags: list[Tag]
    ) -> Video:
        video.javct_enriched = True  # Make this flag True anyway.
        search_url = f"{self.BASE_URL}/v/{video.jav_code.lower()}"
        selenium.get(search_url)
        categories_found = []
        categories_list_el = selenium.find_first("/html/body/section[2]/div[2]/div/div[1]/div/div[1]/div/div/div/div[2]/div/ul/li[5]")
        if not categories_list_el:
            logger.info(f"[!] Search on Javct failed: video {video.jav_code} not found")
            return video
        try:
            categories = categories_list_el.find_elements(By.TAG_NAME, "a")  # type: ignore
            for cat in categories:
                cat_name = cat.get_attribute("title")
                if not cat_name:
                    continue
                categories_found.append(cat_name.strip())
        except NoSuchElementException:
            logger.info(f"[!] Search on Javct failed: video {video.jav_code} not found or page elements not found")
            return video
        for cat in categories_found:
            try:
                category_from_db = next((c for c in all_categories if c.name == cat))
                video.categories.append(category_from_db)  # type: ignore
            except StopIteration:
                logger.info(f"[!] Category {cat} not found in DB!")
        return video
