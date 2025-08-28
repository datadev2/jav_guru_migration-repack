from app.parser.driver import SeleniumDriver
from app.parser.interactions import SeleniumService
from app.parser.service import Parser
from app.logger import init_logger


logger = init_logger()


def run():
    with SeleniumDriver(headless=False) as driver:
        selenium = SeleniumService(driver)
        parser = Parser(selenium)
        parser.parse_videos(" ")
        logger.info("Parser launched successfully!")

if __name__ == "__main__":
    run()