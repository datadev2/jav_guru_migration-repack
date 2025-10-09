import asyncio
from typing import Literal

from loguru import logger

from app.config import config
from app.db.database import init_mongo
from app.db.models import Video
from app.download.thumbnails import ThumbnailSaver
from app.infra.title_generator import TitleGenerator
from app.parser.service import Parser
from app.parser.sites.guru import GuruAdapter
from app.parser.sites.javct import JavctAdapter
from app.parser.sites.javtiful import JavtifulAdapter

SITE_TO_ADAPTER = {
    "guru": GuruAdapter,
    "javct": JavctAdapter,
    "javtiful": JavtifulAdapter,
}

site = config.SITE_NAME
if site not in SITE_TO_ADAPTER:
    raise RuntimeError(f"No adapter for site: {site}")

adapter = SITE_TO_ADAPTER[site]()


async def pipeline_init(start_page: int, end_page: int, headless: bool = False):
    await init_mongo()
    try:
        with Parser(adapter=adapter, headless=headless) as parser:
            parser.init_adblock()
            # --
            # await parser.get_categories()
            # await parser.get_tags()
            # await parser.get_actresses()
            # await parser.get_studios()
            # --
            await parser.get_videos(start_page=start_page, end_page=end_page)
            await parser.get_videos_data()

            logger.info("Pipeline finished successfully.")
    except Exception as e:
        import traceback

        traceback.print_exc()
        logger.error("Pipeline failed: {}", e, exc_info=True)


async def pipeline_enrich(site_name: Literal["javct", "javtiful"], headless: bool = False):
    if site_name not in ("javct", "javtiful"):
        raise ValueError("Site name arg must be either javct or javtiful!")
    adapter = SITE_TO_ADAPTER[site_name]()
    await init_mongo()
    try:
        with Parser(adapter=adapter, headless=headless) as parser:
            parser.init_adblock()
            await parser.enrich_videos()
            logger.info("Pipeline finished successfully.")
    except Exception as e:
        import traceback

        traceback.print_exc()
        logger.error("Pipeline failed: {}", e, exc_info=True)


async def pipeline_titles():
    await init_mongo()
    title_generator = TitleGenerator()
    while video := await Video.find_one({"rewritten_title": None}):
        new_title = await title_generator.generate(video)
        video.rewritten_title = new_title
        await video.save()
        logger.info(f"[Title] {video.jav_code}: {new_title}")

async def pipeline_thumbnails():
    await init_mongo()
    saver = ThumbnailSaver()
    await saver()
    logger.info("Process finished")


async def main():
    # await pipeline_init(start_page=4455, end_page=4450, headless=True)
    # await pipeline_enrich(headless=True)
    # await pipeline_titles()
    await pipeline_thumbnails()


if __name__ == "__main__":
    asyncio.run(main())
