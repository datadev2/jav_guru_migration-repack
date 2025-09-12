import csv
from typing import Dict, List, Type, Iterable
import aiohttp
import re
import urllib.parse
import hashlib
from selenium.webdriver.common.by import By

from pydantic import BaseModel
from pymongo.errors import DuplicateKeyError
from io import BytesIO, StringIO

from app.config import config
from app.db.models import Video
from app.db.exports import VideoCSV
from app.parser.interactions import SeleniumService
from app.parser.sites.guru import GuruAdapter
from app.download.exceptions import DownloadFailedException
from app.infra.s3 import s3
from app.logger import init_logger


logger = init_logger()



class GuruDownloader:
    """
    Mongo -> page_link -> открыть -> _extract_video_src() -> скачать -> обновить Video -> Загрузить в S3
    """

    def __init__(self, selenium: SeleniumService, parser: GuruAdapter) -> None:
        self.selenium = selenium
        self.parser = parser

    async def _download_to_buffer(self, url: str, timeout_sec: int = 3600) -> BytesIO:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout_sec)) as session:
            async with session.get(url, ssl=False) as response:
                if response.status != 200:
                    raise DownloadFailedException(f"HTTP {response.status} {url}")

                buf = BytesIO()
                async for chunk in response.content.iter_chunked(64 * 1024):
                    buf.write(chunk)
                buf.seek(0)
                return buf

    # --- core ---
    async def download_one(self, video: Video) -> bool:
        page_url = str(video.page_link)

        try:
            self.selenium.get(page_url, wait_selector=(By.XPATH, "//div[contains(@class,'inside-article')]"))
            src = self.parser._extract_video_src(self.selenium, timeout_sec=2)
            if not src:
                logger.error(f"no video src {page_url}")
                return False

            buf = await self._download_to_buffer(src)
            if not buf.getbuffer().nbytes:
                logger.error(f"empty buffer {page_url}")
                return False

            file_size = buf.getbuffer().nbytes
            md5 = hashlib.md5(buf.getbuffer()).hexdigest()

            s3_filename = f"{video.jav_code}_{md5}.mp4"
            s3_key = f"{config.S3_FOLDER}/{s3_filename}".lstrip("/")
            await s3.put_object(buf, s3_key)

            video.file_name = s3_filename
            video.s3_path = f"https://{config.S3_ENDPOINT}/{config.S3_BUCKET}/{s3_key}"
            video.file_size = file_size
            video.file_hash_md5 = md5
            await video.save()

            logger.success(f"OK {s3_filename} | {file_size} bytes")
            return True

        except (DownloadFailedException, DuplicateKeyError) as e:
            logger.error(f"{type(e).__name__}: {e}")
        except Exception as e:
            logger.exception(e)

        return False

    async def download_from_db(
        self,
        limit: int | None = None,
        only_missing: bool = True,
        ids: Iterable[str] | None = None,
    ) -> int:
        if ids:
            videos = [video async for video in Video.find({"_id": {"$in": list(ids)}})]
        else:
            query = Video.find(Video.file_size == None) if only_missing else Video.find({})
            if limit:
                query = query.limit(limit)
            else:
                query = query.limit(50)
            videos = await query.to_list()

        total, success_count = len(videos), 0
        logger.info(f"К обработке: {total}")

        for i, video in enumerate(videos, start=1):
            logger.info(f"[{i}/{total}] {video.jav_code} | {str(video.page_link)}")
            if await self.download_one(video):
                success_count += 1

        return success_count


async def download_fresh_videos(selenium: SeleniumService, parser: GuruAdapter, limit: int | None = None) -> None:
    logger.info("Загрузка свежеспарсенных видео...")
    downloader = GuruDownloader(selenium, parser)
    await downloader.download_from_db(limit=limit, only_missing=True)


class CSVDump:
    def __init__(self, schema: Type[BaseModel]):
        self._schema = schema

    def __call__(self, data: List[Video], *, include_headers: bool = True, delimiter: str = ";") -> str:
        rows = [self._schema(**v.model_dump()).model_dump() for v in data]
        return self._make_csv(rows, include_headers, delimiter)

    @staticmethod
    def _make_csv(rows: List[Dict], include_headers: bool, delimiter: str) -> str:
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=rows[0].keys(), delimiter=delimiter)
        if include_headers:
            writer.writeheader()
        writer.writerows(rows)
        return output.getvalue()

csv_dump = CSVDump(VideoCSV)
