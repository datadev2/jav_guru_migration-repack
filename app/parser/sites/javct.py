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
    
    async def enrich_video_with_javct_data(self, video: Video, all_categories: list[Category], selenium: SeleniumService) -> None:
        logger.info(f"Enriching video document {video.jav_code} with JAVCT data...")
        search_url = f"{self.BASE_URL}/v/{video.jav_code.lower()}"
        # TODO Implement timeout processing
        selenium.get(search_url)
        categories_found = []
        categories_list_el = selenium.find_first("/html/body/section[2]/div[2]/div/div[1]/div/div[1]/div/div/div/div[2]/div/ul/li[5]")
        if not categories_list_el:
            logger.error(f"Search on Javct failed: video {video.jav_code} not found")
            return
        try:
            categories = categories_list_el.find_elements(By.TAG_NAME, "a")  # type: ignore
            for cat in categories:
                cat_name = cat.get_attribute("title")
                if not cat_name:
                    continue
                categories_found.append(cat_name.strip())
        except NoSuchElementException:
            logger.error(f"Search on Javct failed: video {video.jav_code} not found or page elements not found")
            return
        for cat in categories_found:
            try:
                category_from_db = next((c for c in all_categories if c.name == cat))
                video.categories.append(category_from_db)  # type: ignore
            except StopIteration:
                new_cat = Category(name=cat, site=self.site_name)
                inserted = await Category.insert_one(new_cat)
                video.categories.append(inserted)  # type: ignore
        await video.save()  # type: ignore
        logger.success(f"Video {video.jav_code} has been successfully enriched with the data from Javct")


if __name__ == "__main__":
    import asyncio
    from app.db.database import init_mongo
    from app.parser.driver import SeleniumDriver
    javct_adapter = JavctAdapter()

    async def test_run():
        await init_mongo()
        all_categories = await Category.find_all().to_list()
        video = await Video.find_one(Video.jav_code == "EBOD-506")
        with SeleniumDriver(headless=False) as driver:
            selenium = SeleniumService(driver)
            await javct_adapter.enrich_video_with_javct_data(video, all_categories, selenium)

    asyncio.run(test_run())
