import asyncio

from app.config import config
from app.db.database import init_mongo
from app.logger import init_logger
from app.parser.service import Parser
from app.parser.sites.guru import GuruAdapter


logger = init_logger()

SITE_TO_ADAPTER = {
    "guru": GuruAdapter,
}

site = config.SITE_NAME
if site not in SITE_TO_ADAPTER:
    raise RuntimeError(f"No adapter for site: {site}")

adapter = SITE_TO_ADAPTER[site]()

async def run_pipeline():
    await init_mongo()
    try:
        with Parser(adapter=adapter, headless=False) as parser:
            parser.init_adblock()
            await parser.get_videos(max_pages=5)
            await parser.get_videos_data(max_videos=5)
            logger.info("Pipeline finished successfully.")
    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error("Pipeline failed: {}", e, exc_info=True)


if __name__ == "__main__":
    asyncio.run(run_pipeline())