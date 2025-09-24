from loguru import logger
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By

from app.db.models import Category, Tag, Video
from app.parser.interactions import SeleniumService


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

    def enrich_video(
        self,
        selenium: SeleniumService,
        video: Video,
        all_categories: list[Category],
        all_tags: list[Tag],
    ) -> Video:
        video.javtiful_enriched = True  # Make this flag True anyway.
        # Look up for a video using the jav code provided.
        search_url = f"{self.BASE_URL}/search/videos?search_query={video.jav_code.lower()}"
        selenium.get(search_url)
        found_video_card = selenium.find_first("/html/body/main/div[3]/div[2]/section/div[2]")
        if not found_video_card:
            logger.info(f"[!] Search on Javtiful failed: video {video.jav_code} not found")
            return video
        # Look up for video attributes on the video page found.
        try:
            movie_page_tag = found_video_card.find_element(By.TAG_NAME, "a")
            movie_page_link = movie_page_tag.get_attribute("href")
            selenium.get(movie_page_link)  # type: ignore
            video_tags_el = selenium.find_first(
                "/html/body/main/div[3]/div[2]/div/section[1]/div[5]/div[2]/div[2]/div[2]"
            )
            tags_found = [tag.text for tag in video_tags_el.find_elements(By.TAG_NAME, "a")]
            video_categories_el = selenium.find_first(
                "/html/body/main/div[3]/div[2]/div/section[1]/div[5]/div[2]/div[3]/div[2]"
            )
            categories_found = [cat.text for cat in video_categories_el.find_elements(By.TAG_NAME, "a")]
            video_type_el = selenium.find_first(
                "/html/body/main/div[3]/div[2]/div/section[1]/div[5]/div[2]/div[5]/div[2]"
            )
            video_type_found = video_type_el.find_element(By.TAG_NAME, "a").text
        except NoSuchElementException:
            logger.info(f"[!] Search on Javtiful failed: video {video.jav_code} not found")
            return video
        # Enrich with javtiful categories.
        for cat in categories_found:
            try:
                category_from_db = next((c for c in all_categories if c.name == cat))
                video.categories.append(category_from_db)  # type: ignore
            except StopIteration:
                logger.info(f"[!] Category {cat} not found in DB!")
        # Enrich with javtiful tags.
        for tag in tags_found:
            try:
                tag_from_db = next((t for t in all_tags if t.name == tag))
                video.tags.append(tag_from_db)  # type: ignore
            except StopIteration:
                logger.info(f"[!] Tag {tag} not found in DB!")
        # Enrich with javtiful type and save video.
        video.type_javtiful = video_type_found
        return video
