from loguru import logger
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By

from app.db.models import Category, Tag, Video
from app.parser.interactions import SeleniumService


class JavctAdapter:
    site_name = "javct"
    BASE_URL = "https://javct.net"
    CATEGORIES_URL = "https://javct.net/categories"

    def parse_tags(self, selenium: SeleniumService) -> list[Tag]:
        logger.info("[JavctAdapter] Method not implemented")
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
        self,
        selenium: SeleniumService,
        video: Video,
        all_categories: list[Category],
        all_tags: list[Tag],

    ) -> Video | None:
        search_url = f"{self.BASE_URL}/v/{video.jav_code.lower()}"

        try:
            selenium.get(search_url)
        except TimeoutException:
            logger.warning(f"[Javct] Timeout while loading {video.jav_code}")
            return None

        not_found = selenium.find_first("//h1[contains(text(),'404')]") or not selenium.find_elements(
            "//div[contains(@class,'card__content')]"
        )
        if not_found:
            logger.info(f"[Javct] Page {search_url} not found (404 or empty). Marking as processed.")
            video.javct_enriched = True
            return video

        categories_el = selenium.find_first("//ul[@class='card__meta']/li[span[contains(text(),'Categories:')]]")
        if not categories_el:
            logger.info(f"[Javct] No categories found for {video.jav_code}")
            video.javct_enriched = True
            return video

        try:
            anchors = categories_el.find_elements(By.TAG_NAME, "a")
            categories_found = [
                a.get_attribute("title") or a.text.strip() for a in anchors if a.text or a.get_attribute("title")
            ]
            categories_found = [c.strip() for c in categories_found if c]
        except Exception as e:
            logger.warning(f"[Javct] Failed to parse categories for {video.jav_code}: {e}")
            video.javct_enriched = True
            return video

        category_map = {c.name: c for c in all_categories}
        for cat_name in categories_found:
            cat_obj = category_map.get(cat_name)
            if cat_obj:
                video.categories.append(cat_obj)
            else:
                logger.debug(f"[Javct] Category '{cat_name}' not found in DB")

        video.javct_enriched = True
        return video
