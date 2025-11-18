import asyncio
import re

from loguru import logger
from openai import OpenAI

from app.config import config
from app.db.models import Video
from app.google_export.export import PromptService


class TitleGenerator:
    SEPARATOR_PATTERN = re.compile(r"\s*\|\s*")
    MAX_RETRIES = 3
    _MAX_TITLE_LENGTH = 120
    _MIN_TITLE_LENGTH = 10
    _INVALID_TITLE = "N/A"

    def __init__(self, batch_size=5):
        self._client = OpenAI(
            base_url="https://api.x.ai/v1",
            api_key=config.GROK_API_KEY,
        )
        self._prompt = PromptService().get_prompt()
        self.BATCH_SIZE = batch_size

    @classmethod
    def is_valid(cls, title: str, is_batch: bool = False) -> bool:
        if not title or not isinstance(title, str):
            return False
        t = title.strip()
        if not t.startswith("["):
            return False
        if not (cls._MIN_TITLE_LENGTH <= len(t) <= cls._MAX_TITLE_LENGTH):
            return False
        if is_batch and cls.SEPARATOR not in t:
            return False
        return True

    @staticmethod
    def validate_title(title: str, expected_code: str) -> bool:
        if not title or not isinstance(title, str):
            return False

        t = title.strip()
        prefix = f"[{expected_code}]"

        if not t.startswith(prefix):
            return False

        if not (10 <= len(t) <= 120):
            return False

        return True

    def _prepare_batch_input(self, videos: list) -> str:
        lines = []
        for video in videos:
            actresses = [m.name for m in video.actresses][:2] if video.actresses else []
            tags = [t.name for t in video.tags][:2] if video.tags else []

            parts = [f"[{video.jav_code}] {video.title}"]
            if actresses:
                parts.append(f"Actresses: {', '.join(actresses)}")
            if tags:
                parts.append(f"Tags: {', '.join(tags)}")

            lines.append(" — ".join(parts))
        return "\n".join(lines)
    
    def _call_api(self, content: str) -> str:
        response = self._client.chat.completions.create(
            model="grok-3-mini-beta",
            messages=[{"role": "system", "content": self._prompt}, {"role": "user", "content": content}],
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()

    async def _generate_batch(self, videos: list) -> list[str]:
        if not videos or len(videos) > self.BATCH_SIZE:
            raise ValueError(f"Batch size must be 1-{self.BATCH_SIZE}")

        content = self._prepare_batch_input(videos)
        logger.debug(f"[Grok] Batch input:\n{content}")

        raw = await asyncio.to_thread(self._call_api, content)
        titles = self.validate_batch(raw, len(videos))

        empty_count = sum(1 for t in titles if not t)
        if empty_count > len(titles) // 2:
            logger.error(f"Batch mostly empty. {empty_count}/{len(titles)} titles are blank. Raw: {raw}")
            raise ValueError("Batch quality too low")

        if len(titles) != len(videos):
            logger.error(f"Title count mismatch. Expected {len(videos)}, got {len(titles)}. Raw: {raw}")
            raise ValueError("Title count mismatch")

        return titles

    async def _fetch_batch(self) -> list[Video]:
        query = {
            "rewritten_title": None,
            "javguru_status": "parsed",
            "javct_enriched": True,
            "javtiful_enriched": True,
        }

        videos = await Video.find(query).limit(self.BATCH_SIZE).to_list()

        for video in videos:
            await video.fetch_link(Video.actresses)
            await video.fetch_link(Video.tags)

        return videos

    async def _process_batch(self, videos: list) -> None:
        for attempt in range(self.MAX_RETRIES):
            try:
                titles = await self._generate_batch(videos)
                break
            except Exception as e:
                wait = 2**attempt
                logger.error(f"Batch failed (attempt {attempt + 1}/{self.MAX_RETRIES}): {e}. Retry in {wait}s")
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(wait)
                else:
                    logger.critical(f"Batch permanently failed for codes: {[video.jav_code for video in videos]}")
                    return
        else:
            return

        for video, title in zip(videos, titles):
            if not self.validate_title(title, video.jav_code):
                title = ""

            video.rewritten_title = title

            try:
                await video.save()
                logger.info(f"[Title] {video.jav_code}: {title}")
            except Exception as e:
                logger.error(f"Failed to save {video.jav_code}: {e}")

    async def run_pipeline(self) -> None:
        while True:
            videos = await self._fetch_batch()
            if not videos:
                logger.info("No more videos to process")
                break

            await self._process_batch(videos)
