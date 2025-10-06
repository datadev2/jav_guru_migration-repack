import asyncio
import io

import httpx
from loguru import logger

from app.config import config
from app.db.models import Video
from app.infra.s3 import s3


class ThumbnailSaver:
    def __init__(self, s3_client=s3):
        self._s3 = s3_client

    async def __call__(self, _semaphore: int = 5):
        videos = await Video.find_many(
            Video.thumbnail_url != None,  # noqa
            Video.thumbnail_s3_url == None,  # noqa
            fetch_links=True,
        ).to_list()
        if not videos:
            logger.info("No videos found for ThumbnailServer.")
            return
        logger.info(f"Starting downloading and saving thumbnails for {len(videos)} videos on S3")
        semaphore = asyncio.Semaphore(_semaphore)
        async with httpx.AsyncClient(verify=False, timeout=30) as client:
            tasks = [
                self._download_and_save_thumbnail(
                    client,
                    semaphore,
                    video.thumbnail_url.unicode_string(),  # type: ignore
                    f"{video.jav_code.replace(" ", "").replace("/", "").lower()}.jpg",
                    video,
                )
                for video in videos
            ]
            await asyncio.gather(*tasks)

    async def _download_and_save_thumbnail(
        self,
        http_client: httpx.AsyncClient,
        semaphore: asyncio.Semaphore,
        url: str,
        file_name: str,
        video: Video,
    ) -> None:
        async with semaphore:
            async with http_client.stream("GET", url) as response:
                response.raise_for_status()
                file_bytes = io.BytesIO()
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    file_bytes.write(chunk)
                file_bytes.seek(0)
                s3_key = f"{config.S3_THUMBNAILS_FOLDER}/{file_name}"
            try:
                await self._s3.put_object(file_bytes, s3_key, content_type="image/jpeg")
                video.thumbnail_s3_url = f"https://{config.S3_ENDPOINT}/{config.S3_BUCKET}/{s3_key}"  # type: ignore
                await video.save()  # type: ignore
                logger.info(f"Thumbnail {file_name} successfully uploaded to S3")
            except Exception as e:
                logger.error(f"Error occurred when uploading thumbnail {file_name} to S3: {e}")
                raise
