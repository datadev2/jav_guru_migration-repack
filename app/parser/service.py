from typing import Callable
from beanie import Document
from beanie.operators import In

from app.db.database import init_mongo
from app.db.models import Category, Video, Studio, Tag, Model
from app.parser.driver import SeleniumDriver
from app.parser.interactions import SeleniumService
from app.parser.base import ParserAdapter
from loguru import logger


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

    async def _insert_unique(
        self,
        model: type[Document],
        raw_items: list,
        key_fn: Callable[[object], str],
        build_fn: Callable[[object], Document],
    ) -> int:
        keys = [key_fn(item) for item in raw_items]
        existing = await model.find(In(key_fn(model), keys)).to_list()
        existing_keys = {key_fn(x) for x in existing}

        to_insert = [build_fn(item) for item in raw_items if key_fn(item) not in existing_keys]
        if to_insert:
            await model.insert_many(to_insert)
            logger.info(f"[Parser] Inserted {len(to_insert)} new {model.__name__}s")

        return len(to_insert)
    
    async def get_studios(self) -> int:
        """
        Crawl site and insert unique studios into MongoDB.
        """
        await init_mongo()
        raw_studios = self.adapter.parse_studios(self.selenium)

        logger.info(f"[Parser] Found {len(raw_studios)} raw studios from {self.adapter.site_name}")

        return await self._insert_unique(
            Studio,
            raw_studios,
            key_fn=lambda studio: studio.name,
            build_fn=lambda studio: studio,
        )

    async def get_tags(self) -> int:
        """
        Crawl site and insert unique tags into MongoDB.
        """
        await init_mongo()
        raw_tags = self.adapter.parse_tags(self.selenium)

        logger.info(f"[Parser] Found {len(raw_tags)} raw tags from {self.adapter.site_name}")

        return await self._insert_unique(
            Tag,
            raw_tags,
            key_fn=lambda tag: tag.name,
            build_fn=lambda tag: tag,
        )

    async def get_categories(self) -> int:
        """
        Crawl site and insert unique categories into MongoDB.
        For Guru: categories == tags (same source).
        """
        await init_mongo()
        raw_categories = self.adapter.parse_categories(self.selenium)

        logger.info(f"[Parser] Found {len(raw_categories)} raw categories from {self.adapter.site_name}")

        return await self._insert_unique(
            Category,
            raw_categories,
            key_fn=lambda c: c.name,
            build_fn=lambda c: c,
        )

    async def get_actresses(self) -> int:
        """
        Crawl site and insert unique actresses into MongoDB.
        """
        await init_mongo()
        raw_models = self.adapter.parse_actress(self.selenium)

        logger.info(f"[Parser] Found {len(raw_models)} actresses from {self.adapter.site_name}")

        return await self._insert_unique(
            Model,
            raw_models,
            key_fn=lambda m: m.name,
            build_fn=lambda m: m,
        )

    async def get_actors(self) -> int:
        """
        Crawl site and insert unique actors into MongoDB.
        """
        await init_mongo()
        raw_models = self.adapter.parse_actors(self.selenium)

        logger.info(f"[Parser] Found {len(raw_models)} actors from {self.adapter.site_name}")

        return await self._insert_unique(
            Model,
            raw_models,
            key_fn=lambda m: m.name,
            build_fn=lambda m: m,
        )

    async def get_directors(self) -> int:
        """
        Crawl site and insert unique directors into MongoDB.
        """
        await init_mongo()
        raw_models = self.adapter.parse_directors(self.selenium)

        logger.info(f"[Parser] Found {len(raw_models)} directors from {self.adapter.site_name}")

        return await self._insert_unique(
            Model,
            raw_models,
            key_fn=lambda m: m.name,
            build_fn=lambda m: m,
        )

    async def get_videos(
            self,
            start_page: int | None = None,
            end_page: int = 1):
        await init_mongo()
        raw_videos = self.adapter.parse_videos(
            self.selenium,
            start_page=start_page,
            end_page=end_page,
        )

        logger.info(f"[Parser] Found {len(raw_videos)} raw videos from {self.adapter.site_name}")

        return await self._insert_unique(
            Video,
            raw_videos,
            key_fn=lambda v: v.page_link,
            build_fn=lambda v: Video(
                title=v.title,
                jav_code=v.jav_code,
                page_link=v.page_link,
                site=v.site,
                thumbnail_url=v.thumbnail_url,
            ),
        )
    
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
            if not parsed:
                continue

            video.title = parsed.title
            video.thumbnail_url = parsed.thumbnail_url
            video.jav_code = parsed.jav_code
            video.release_date = parsed.release_date
            video.uncensored = parsed.uncensored

            if parsed.categories:
                video.categories = await Category.find(
                    In(Category.name, parsed.categories),
                    Category.site == self.adapter.site_name
                ).to_list()

            if parsed.tags:
                video.tags = await Tag.find(
                    In(Tag.name, parsed.tags),
                    Tag.site == self.adapter.site_name
                ).to_list()

            if parsed.directors:
                video.directors = await Model.find(
                    In(Model.name, parsed.directors),
                    Model.type == "director",
                    Model.site == self.adapter.site_name
                ).to_list()

            if parsed.actors:
                video.actors = await Model.find(
                    In(Model.name, parsed.actors),
                    Model.type == "actor",
                    Model.site == self.adapter.site_name
                ).to_list()

            if parsed.actresses:
                video.actresses = await Model.find(
                    In(Model.name, parsed.actresses),
                    Model.type == "actress",
                    Model.site == self.adapter.site_name
                ).to_list()

            if parsed.studio:
                studio = await Studio.find_one(
                    Studio.name == parsed.studio,
                    Studio.site == self.adapter.site_name
                )
                if studio:
                    video.studio = studio

            await video.save()
            logger.info(f"[Parser] Updated {video.jav_code} | {video.title[:50]}...")