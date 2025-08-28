import asyncio
from app.db.models import Video
from app.db.database import init_mongo
from app.download.service import DownloadService
from app.infra.queue import queue
from app.logger import init_logger


logger = init_logger()

async def download_caller(limit: int | None = None) -> int:
    await init_mongo()
    not_downloaded = await Video.find(
        Video.file_hash_md5 == None,
        Video.site_download_link != None,
    ).to_list()

    limit = len(not_downloaded) if limit is None else limit
    for video in not_downloaded[:limit]:
        payload = video.model_dump(mode="json")
        download_task.delay(video=payload)
        logger.debug(f"Task queued: {video.page_link}")

    logger.info(f"Queued {limit} download tasks")
    return len(not_downloaded)


@queue.task(name="download_video")
def download_task(video: dict) -> None:
    logger.info(f"Received video task: {video.get('name')}")
    try:
        asyncio.run(_handle_download(video))
        logger.success(f"Successfully processed video: {video.get('name')}")
    except Exception as e:
        logger.error(f"Download failed: {e}")


async def _handle_download(video: dict):
    await init_mongo()
    video_obj = Video(**video)
    service = DownloadService()
    await service(video_obj)