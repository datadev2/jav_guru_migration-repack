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

    async def get_videos(self, max_pages: int | None = None):
        """
        Crawl the site index pages and insert new video entries into MongoDB.
        Args:
            max_pages: maximum number of pages to crawl (None = crawl all).
        """
        await init_mongo()
        raw_videos = self.adapter.parse_videos(self.selenium)
        if max_pages:
            raw_videos = raw_videos[:max_pages]

        logger.info(f"[Parser] Found {len(raw_videos)} raw videos from {self.adapter.site_name}")

        links = [video.page_link for video in raw_videos]
        existing = await Video.find(In(Video.page_link, links)).to_list()
        existing_links = {video.page_link for video in existing}

        to_insert = [
            Video(
                title=video.title,
                jav_code=video.jav_code,
                page_link=video.page_link,
                site=video.site,
                thumbnail_url=video.thumbnail_url,
            )
            for video in raw_videos if video.page_link not in existing_links
        ]

        if to_insert:
            await Video.insert_many(to_insert)
            logger.info(f"[Parser] Inserted {len(to_insert)} new videos")

        return len(to_insert)
    
    async def get_videos_data(self, max_videos: int | None = None):
        """
        Enrich existing video entries with detailed information from their pages.
        Args:
            max_videos: maximum number of videos to enrich (None = process all).
        """
        await init_mongo()

        query = Video.find(
            Video.site == self.adapter.site_name,
            Video.studio == None
        )
        videos = await query.to_list()
        if max_videos:
            videos = videos[:max_videos]

        logger.info(f"[Parser] Enriching {len(videos)} videos with details")

        for video in videos:
            parsed = self.adapter.parse_video(self.selenium, video)
            if parsed:
                video.title = parsed.title
                video.thumbnail_url = parsed.thumbnail_url
                video.jav_code = parsed.jav_code
                video.release_date = parsed.release_date
                video.categories = parsed.categories
                video.tags = parsed.tags
                video.directors = parsed.directors
                video.actresses = parsed.actresses
                video.studio = parsed.studio
                video.uncensored = parsed.uncensored
                await video.save()
                logger.info(f"[Parser] Updated {video.jav_code} | {video.title[:50]}...")