import asyncio

from loguru import logger

from app.config import config
from app.db.database import init_mongo
from app.parser.service import Parser
from app.parser.sites.guru import GuruAdapter
from app.parser.sites.javct import JavctAdapter
from app.parser.sites.javtiful import JavtifulAdapter

from app.parser.driver import SeleniumDriver
from app.parser.interactions import SeleniumService
from app.parser.sites.guru import GuruAdapter
from app.download.service import download_fresh_videos


SITE_TO_ADAPTER = {
    "guru": GuruAdapter,
    "javct": JavctAdapter,
    "javtiful": JavtifulAdapter,
}

site = config.SITE_NAME
if site not in SITE_TO_ADAPTER:
    raise RuntimeError(f"No adapter for site: {site}")

adapter = SITE_TO_ADAPTER[site]()
AdapterCls = SITE_TO_ADAPTER[site]

async def run_parse():
    await init_mongo()
    try:
        with Parser(adapter=adapter, headless=True) as parser:
            parser.init_adblock()
            # --
            # await parser.get_categories()
            # await parser.get_tags()
            # await parser.get_models()
            # await parser.get_studios()
            # --
            await parser.get_videos(start_page=4409, end_page=4409)     # one page
            await parser.get_videos_data(max_videos=1)

            logger.info("Pipeline finished successfully.")
    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error("Pipeline failed: {}", e, exc_info=True)

async def run_download(limit: int, headless: bool):
    await init_mongo()
    with SeleniumDriver(headless=headless) as driver:
        selenium = SeleniumService(driver)
        adapter = AdapterCls()
        await download_fresh_videos(selenium, adapter, limit=limit) # limit=1


if __name__ == "__main__":
    asyncio.run(run_parse())
    asyncio.run(run_download(1, True))
