from typing import Protocol

from app.db.models import Category, ParsedVideo, Tag


class ParserAdapter(Protocol):
    site_name: str

    async def parse_videos(self, start_page: int | None = None, end_page: int | None = None) -> list[ParsedVideo]: ...
    async def parse_video(self, video: ParsedVideo) -> ParsedVideo | None: ...
    async def enrich_video(self, video: ParsedVideo, categories: list[Category], tags: list[Tag]) -> ParsedVideo: ...
