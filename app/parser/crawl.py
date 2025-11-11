import asyncio
import json
import traceback
from pathlib import Path
from typing import Literal

from loguru import logger

from app.config import config
from app.db.database import init_mongo
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


async def pipeline_init(start_page: int, end_page: int, max_videos: int):
    await init_mongo()
    try:
        async with Parser(adapter=adapter) as parser:
            await parser.get_videos(start_page=start_page, end_page=end_page)
            await parser.get_videos_data(max_videos=max_videos)

        logger.info("Pipeline finished successfully.")
    except Exception as e:
        traceback.print_exc()
        logger.error("Pipeline failed", e, exc_info=True)


async def pipeline_enrich(site_name: Literal["javct", "javtiful"], max_videos: int):
    if site_name not in ("javct", "javtiful"):
        raise ValueError("Site name arg must be either javct or javtiful!")
    adapter = SITE_TO_ADAPTER[site_name]()
    await init_mongo()
    try:
        async with Parser(adapter=adapter) as parser:
            parser.init_adblock()
            await parser.enrich_videos(max_videos=max_videos)
            logger.info("Pipeline finished successfully.")
    except Exception as e:
        traceback.print_exc()
        logger.error("Pipeline failed: {}", e, exc_info=True)


async def pipeline_titles():
    await init_mongo()
    generator = TitleGenerator()
    await generator.run_pipeline()


async def pipeline_thumbnails():
    await init_mongo()
    saver = ThumbnailSaver()
    await saver()
    logger.info("Process finished")


RANGE_PATH = Path(__file__).parent / "current_range.json"


def get_current_range():
    with open(RANGE_PATH) as f:
        return json.load(f)


def save_next_range(current_data):
    step = current_data["step"]
    end_candidate = max(0, current_data["end_page"] - step)

    new_range = {
        "start_page": current_data["end_page"],
        "end_page": end_candidate,
        "step": step,
        "max_videos": current_data["max_videos"],
    }

    with open(RANGE_PATH, "w") as f:
        json.dump(new_range, f)


async def main():
    # ---
    # current = get_current_range()
    # await pipeline_init(
    #     start_page=current["start_page"],
    #     end_page=current["end_page"],
    #     max_videos=current["max_videos"]
    # )
    # save_next_range(current)
    # ---

    # await pipeline_enrich(config.SITE_NAME, max_videos=1000)

    # --- Fast run ---
    # await pipeline_enrich("javct", max_videos=1)
    # await pipeline_enrich("javtiful", max_videos=14)
    # --- Fast run ---

    await pipeline_titles()
    # await pipeline_thumbnails()


if __name__ == "__main__":
    asyncio.run(main())
