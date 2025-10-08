from typing import Callable

from beanie import Document
from beanie.operators import In
from loguru import logger

from app.db.models import Category, Model, Studio, Tag, Video
from app.parser.base import ParserAdapter
from app.parser.driver import SeleniumDriver
from app.parser.interactions import SeleniumService


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

    async def _load_and_insert(
        self,
        model: type[Document],
        parser_fn: Callable,
        label: str,
    ) -> int:
        raw_items = parser_fn(self.selenium)
        logger.info(f"[Parser] Found {len(raw_items)} {label} from {self.adapter.site_name}")
        return await self._insert_unique(
            model,
            raw_items,
            key_fn=lambda x: x.name,
            build_fn=lambda x: x,
        )

    async def get_studios(self):
        return await self._load_and_insert(Studio, self.adapter.parse_studios, "studios")

    async def get_tags(self):
        return await self._load_and_insert(Tag, self.adapter.parse_tags, "tags")

    async def get_categories(self):
        return await self._load_and_insert(Category, self.adapter.parse_categories, "categories")

    async def get_actresses(self):
        return await self._load_and_insert(Model, self.adapter.parse_actress, "actresses")

    async def get_actors(self):
        return await self._load_and_insert(Model, self.adapter.parse_actors, "actors")

    async def get_directors(self):
        return await self._load_and_insert(Model, self.adapter.parse_directors, "directors")

    async def get_videos(self, start_page: int | None = None, end_page: int = 1):
        raw_videos = self.adapter.parse_videos(
            self.selenium,
            start_page=start_page,
            end_page=end_page,
        )

        logger.info(f"[Parser] Found {len(raw_videos)} raw videos from {self.adapter.site_name}")

        existing_docs = await Video.find_all().to_list()
        existing_links = {str(v.page_link) for v in existing_docs if v.page_link}

        new_links = set()
        unique_videos = []
        for v in raw_videos:
            link = str(v.page_link)
            if link in existing_links or link in new_links:
                logger.debug(f"[Parser] Skipping duplicate page_link: {link}")
                continue
            new_links.add(link)
            unique_videos.append(v)

        if not unique_videos:
            logger.info("[Parser] No new videos to insert.")
            return

        await Video.insert_many(
            [
                Video(
                    title=v.title,
                    jav_code=v.jav_code,
                    page_link=str(v.page_link),
                    site=v.site,
                    thumbnail_url=v.thumbnail_url,
                    javguru_status="added",
                )
                for v in unique_videos
            ]
        )
        logger.info(f"[Parser] Inserted {len(unique_videos)} new Videos")

        return len(unique_videos)

    async def get_videos_data(self, max_videos: int | None = None):
        """
        Enrich existing video entries with detailed information from their pages.
        Args:
            max_videos: maximum number of videos to enrich (None = process all).
        """
        query = Video.find(Video.site == self.adapter.site_name, Video.studio == None)  # noqa E711
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
                    In(Category.name, parsed.categories), Category.site == self.adapter.site_name
                ).to_list()

            if parsed.tags:
                video.tags = await Tag.find(In(Tag.name, parsed.tags), Tag.site == self.adapter.site_name).to_list()

            if parsed.directors:
                video.directors = await Model.find(
                    In(Model.name, parsed.directors), Model.type == "director", Model.site == self.adapter.site_name
                ).to_list()

            if parsed.actors:
                video.actors = await Model.find(
                    In(Model.name, parsed.actors), Model.type == "actor", Model.site == self.adapter.site_name
                ).to_list()

            if parsed.actresses:
                video.actresses = await Model.find(
                    In(Model.name, parsed.actresses), Model.type == "actress", Model.site == self.adapter.site_name
                ).to_list()

            if parsed.studio:
                studio = await Studio.find_one(Studio.name == parsed.studio, Studio.site == self.adapter.site_name)
                if studio:
                    video.studio = studio

            video.javguru_status = "parsed"

            existing = None
            if video.jav_code:
                existing = await Video.find_one(Video.jav_code == video.jav_code, Video.id != video.id)

            if existing:
                logger.warning(
                    f"[Parser] Duplicate jav_code detected: {video.jav_code}. Deleting current placeholder {video.id}"
                )
                await video.delete()
                continue

            await video.save()
            logger.info(f"[Parser] Updated {video.jav_code} | {video.title[:50]}...")

    async def enrich_videos(self) -> None:
        all_categories = await Category.find_all().to_list()
        all_tags = await Tag.find_all().to_list()
        all_videos = await Video.find_all().to_list()
        site_name = self.adapter.site_name
        if site_name == "javct":
            videos_to_enrich = [video for video in all_videos if not video.javct_enriched]
        elif site_name == "javtiful":
            videos_to_enrich = [video for video in all_videos if not video.javtiful_enriched]
        logger.info(f"Videos to enrich: {len(videos_to_enrich)}")
        for video in videos_to_enrich:
            logger.info(f"Enriching video document {video.jav_code} with data from {site_name}...")
            video_enriched = self.adapter.enrich_video(self.selenium, video, all_categories, all_tags)
            await video_enriched.save()
            logger.success(f"Video {video.jav_code} has been processed using {site_name} adapter and saved")
