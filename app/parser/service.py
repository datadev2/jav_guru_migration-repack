from app.parser.interactions import SeleniumService
from app.logger import init_logger


logger = init_logger()


class Parser:
    def __init__(self, selenium: SeleniumService):
        self.selenium = selenium

    def parse_videos(self, url) -> list[dict]:
        self.selenium.get(url)
        return []