import asyncio

from loguru import logger

from app.parser.crawl import run_download
from app.infra.queue import queue


@queue.task(name="download_fresh_videos")
def download_fresh_videos_task(limit: int, headless: bool) -> None:
    try:
        asyncio.run(run_download(limit=limit, headless=headless))
        logger.success(f"Download fresh videos task with limit {limit} successfully done")
    except Exception as e:
        logger.error(f"Download failed: {e}")


def download_caller(limit: int, headless: bool = True) -> str:
    task_id = download_fresh_videos_task.delay(limit=limit, headless=headless)
    return task_id

if __name__ == "__main__":
    download_caller(1, True)
