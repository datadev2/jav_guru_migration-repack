from typing import Protocol
from app.db.models import Video
from app.parser.interactions import SeleniumService


class ParserAdapter(Protocol):
    site_name: str

    def parse_videos(self, selenium: SeleniumService) -> list[Video]:
        ...

    def parse_video(self, selenium: SeleniumService, video: Video) -> Video | None:
        ...