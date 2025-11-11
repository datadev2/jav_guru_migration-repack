import asyncio
from typing import Any

import aiohttp
from loguru import logger
from pydantic import BaseModel, Field, ValidationError

from app.config import Config, config



class KVSSchema(BaseModel):
    kvs_id: int = Field(alias="id")
    file_hash_md5: str = Field(alias="custom2", min_length=32, max_length=32)


class KVS:
    def __init__(self, schema: type[KVSSchema] = KVSSchema, cfg: Config = config):
        self._endpoint = cfg.KVS_FEED_ENDPOINT.unicode_string()
        self._password = cfg.KVS_FEED_PASSWORD.get_secret_value()
        self._schema = schema

    async def _get_feed_part(self, limit: int = 1000, offset: int = 0) -> list[dict[str, Any]]:
        # Странное решение KVS принимать пароль как параметр запроса, но другого пути пока нет.
        url = f"{self._endpoint}?password={self._password}"
        async with aiohttp.ClientSession() as session:
            request = await session.get(url, params={"skip": offset, "limit": limit, "feed_format": "json"})
            status = request.status
            if status == 200:
                return await request.json()
            return []

    async def _gather_feed(self) -> list[dict]:
        feed = []
        limit = 1000
        offset = 0
        stop = False

        while not stop:
            coros = []
            for _ in range(10):
                coros.append(self._get_feed_part(limit=limit, offset=offset))
                offset += limit
            response = await asyncio.gather(*coros)
            for body in response:
                if body:
                    feed.extend(body)
                else:
                    stop = True
        return feed

    async def get_uploaded_videos(self) -> list[tuple[int, str]]:
        feed = await self._gather_feed()
        if not feed:
            logger.info("No KVS feed")
            return []
        validated = []
        for video_ in feed:
            try:
                video = self._schema.model_validate(video_)
                validated.append((video.kvs_id, video.file_hash_md5))
            except ValidationError:
                logger.error(f"Validation error on video {video_}")
                raise
        return validated


kvs_feed = KVS()
