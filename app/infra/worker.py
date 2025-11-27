import asyncio
import time
from typing import Literal

from loguru import logger

from app.db.database import init_mongo
from app.db.models import Video
from app.download.service import run_download
from app.google_export.export import GSheetService
from app.infra.kvs_cleanup import kvs_cleanup_chunk
from app.infra.queue import queue
from app.parser.crawl import (get_current_range, pipeline_enrich, pipeline_guru_enrich, pipeline_guru_pages,
                              pipeline_thumbnails, pipeline_titles, save_next_range)


@queue.task(name="download_single_video")
def download_video_task(video_id: str, origin_source: Literal["guru", "pornolab"], headless: bool) -> None:
    if origin_source not in ("guru", "pornolab"):
        raise ValueError("Origin source must be in ('guru', 'pornolab')!")
    asyncio.run(run_download(video_id, origin_source, headless))


@queue.task(name="download_videos_from_guru")
def download_fresh_videos_from_guru_task(limit: int = 50, headless: bool = True) -> str:
    """
    Initiates a task to download fresh videos from Javguru.

    This function triggers background tasks that download a specified number of fresh videos.
    It should be used as the main entry point for starting the download process.

    Args:
        limit (int): The maximum number of videos to download.
        origin_source (Literal["guru", "pornolab"]): The source where the system should download from.
        headless (bool, optional): Whether to run the download process using Selenium in headless mode.
            Defaults to True.

    Returns:
        str: A descriptive message about the result.
    """

    async def look_up(limit: int) -> list:
        await init_mongo()
        return await Video.find({"sources": {"$size": 0}, "javguru_status": "parsed"}).limit(limit).to_list()

    videos_to_download = asyncio.run(look_up(limit))
    if not videos_to_download:
        return "No videos found to download."

    video_ids = []
    for video in videos_to_download:
        download_video_task.delay(str(video.id), "guru", headless)
        video_ids.append(str(video.id))
        time.sleep(0.5)

    return f"Sent {len(videos_to_download)} videos for download from javguru: {', '.join(video_ids)}"


@queue.task(name="guru_pipeline_pages")
def guru_pipeline_pages_task(start_page: int, end_page: int) -> None:
    asyncio.run(pipeline_guru_pages(start_page, end_page))


@queue.task(name="guru_pipeline_enrich")
def guru_pipeline_enrich_task(max_videos: int) -> None:
    asyncio.run(pipeline_guru_enrich(max_videos))


@queue.task(name="enrich_videos_with_data")
def enrich_videos_with_data_task(site_name: str, max_videos: int) -> None:
    asyncio.run(pipeline_enrich(site_name=site_name, max_videos=max_videos))


@queue.task(name="generate_new_titles")
def generate_new_titles_task() -> None:
    asyncio.run(pipeline_titles())


@queue.task(name="save_video_thumbnails")
def save_video_thumbnails_task() -> None:
    asyncio.run(pipeline_thumbnails())


@queue.task(name="export_video_data_to_gsheet")
def export_video_data_to_gsheet_task(
    gsheet_read_range: str = "A2:A",
    latest_exported_video_mongo_id: str | None = None,
    gsheet_write_start_row: int = 0,
) -> None:
    gsheet_svc = GSheetService()
    asyncio.run(
        gsheet_svc.update_export_data_to_gsheet(
            gsheet_read_range,
            latest_exported_video_mongo_id,
            gsheet_write_start_row,
        )
    )


@queue.task(name="update_s3_paths_and_resolutions")
def update_s3_paths_and_resolutions_task(read_range: str = "A2:T", write_start_cell: str = "P2") -> None:
    gsheet_svc = GSheetService()
    asyncio.run(gsheet_svc.update_s3_paths_and_resolutions(read_range, write_start_cell))


@queue.task(name="kvs_cleanup_chunk")
def kvs_cleanup_chunk_task():
    asyncio.run(kvs_cleanup_chunk())


# Use functions below to send celery tasks manually via app/send_tasks.py


def download_fresh_videos_from_guru_task_caller(limit: int = 50):
    download_fresh_videos_from_guru_task.delay(**locals())
    logger.info(f"Sent task to download {limit} videos from jav.guru")


def guru_pipeline_pages_caller():
    current_data = get_current_range()
    start_page = current_data["start_page"]
    end_page = current_data["end_page"]
    guru_pipeline_pages_task.delay(start_page, end_page)
    logger.info(f"Sent task: guru pipeline pages [{start_page} -> {end_page}]")
    save_next_range(current_data)


def guru_pipeline_enrich_caller():
    current_data = get_current_range()
    max_videos = current_data["max_videos"]
    guru_pipeline_enrich_task.delay(max_videos)
    logger.info(f"Sent task: guru enrichment ({max_videos} videos)")


def enrich_videos_with_data_task_caller(site_name: str):
    current_data = get_current_range()
    max_videos = current_data["max_videos"]
    enrich_videos_with_data_task.delay(site_name=site_name, max_videos=max_videos)
    logger.info("Sent task to enrich jav.guru")


def generate_new_titles_task_caller():
    generate_new_titles_task.delay()
    logger.info("Sent task to generate new titles.")


def save_video_thumbnails_task_caller():
    save_video_thumbnails_task.delay()
    logger.info("Sent task to save video thumbnails")


def export_video_data_to_gsheet_task_caller(
    gsheet_read_range: str = "A2:A",
    latest_exported_video_mongo_id: str | None = None,
    gsheet_write_start_row: int = 0,
):
    export_video_data_to_gsheet_task.delay(**locals())
    logger.info("Sent task to export video data to gsheet")


def update_s3_paths_and_resolutions_task_caller(read_range: str = "A2:T", write_start_cell: str = "P2"):
    update_s3_paths_and_resolutions_task.delay(**locals())
    logger.info("Sent task to update S3 paths and resolutions in gsheet")


def kvs_cleanup_caller():
    kvs_cleanup_chunk_task.delay()
    logger.info("Sent KVS cleanup task")
