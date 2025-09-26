import asyncio
import time
from typing import Literal

from app.db.database import init_mongo
from app.db.models import Video
from app.download.service import run_download
from app.infra.queue import queue


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

    return f"Sent {len(videos_to_download)} videos for download from javguru: {", ".join(video_ids)}"


def download_fresh_videos_from_guru_task_caller(limit: int = 50, headless: bool = True):
    """For sending task manually. See app/send_tasks.py."""
    download_fresh_videos_from_guru_task.delay(limit, headless)
    print(f"Sent the task to download {limit} videos from javguru.")
