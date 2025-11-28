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
        params = {
            "skip": offset,
            "limit": limit,
            "feed_format": "json",
        }
        timeout = aiohttp.ClientTimeout(total=10)
        for _ in range(3):
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    r = await session.get(url, params=params)
                    if r.status == 200:
                        return await r.json()
                    return []
            except Exception:
                await asyncio.sleep(1)
        return []

    async def _gather_feed(self) -> list[dict]:
        """Never call in production. Left only for rare manual checks."""
        feed: list[dict] = []
        limit = 1000
        offset = 0
        while True:
            tasks = [self._get_feed_part(limit=limit, offset=offset + i * limit) for i in range(10)]
            offset += limit * 10

            parts = await asyncio.gather(*tasks, return_exceptions=True)

            empty_chunks = 0
            for body in parts:
                if isinstance(body, Exception):
                    empty_chunks += 1
                    continue
                if not body:
                    empty_chunks += 1
                else:
                    feed.extend(body)

            if empty_chunks == 10:
                break

        return feed

    async def get_full_feed(self) -> list[dict]:
        feed = await self._gather_feed()
        if not feed:
            logger.info("No KVS feed")
            return []
        return feed

    async def get_feed_chunk(self, *, limit: int, skip: int) -> list[KVSSchema]:
        raw = await self._get_feed_part(limit=limit, offset=skip)

        out: list[KVSSchema] = []
        for row in raw:
            try:
                out.append(self._schema.model_validate(row))
            except ValidationError:
                logger.warning(f"KVS row validation failed: {row}")

        return out


kvs_feed = KVS()
