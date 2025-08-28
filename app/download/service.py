import csv
import io
from typing import Dict, List, Type

from pydantic import BaseModel
from pymongo.errors import DuplicateKeyError

from app.config import config
from app.db.models import Video
from app.db.exports import VideoCSV
from app.download.downloader import Downloader, DownloadedFile
from app.download.exceptions import DownloadFailedException
from app.infra.s3 import S3Client, s3
from app.logger import init_logger


logger = init_logger()

class DownloadService:
    def __init__(
        self,
        s3_client: S3Client = s3,
        downloader_cls: Type[Downloader] = Downloader,
    ):
        self._s3 = s3_client
        self._downloader_cls = downloader_cls

    async def __call__(self, video: Video, *, show_progress: bool = False) -> None:
        try:
            file = await self._download_file(video.site_download_link, show_progress)
            s3_path = self._upload_path(video.name)

            await self._upload_to_s3(file, s3_path)
            await self._save_video(video, file.md5, s3_path)

            logger.success(f"Saved: {video.name} → {s3_path}")
        except DownloadFailedException as e:
            logger.error(f"Download failed: {video.name} → {e}")
        except DuplicateKeyError as e:
            logger.warning(f"Duplicate video key: {video.name} → {e}")

    async def _download_file(self, link: str, show_progress: bool) -> DownloadedFile:
        downloader = self._downloader_cls(disable_progress=not show_progress)
        return await downloader.fetch(link)

    async def _upload_to_s3(self, file: DownloadedFile, path: str) -> None:
        await self._s3.put_object(file.content, path)

    async def _save_video(self, video: Video, file_hash: str, path: str) -> None:
        video.s3_path = path
        video.file_hash_md5 = file_hash
        await video.save()

    @staticmethod
    def _upload_path(name: str) -> str:
        filename = name.replace(" ", "") + ".mp4"
        return f"{config.S3_FOLDER}/{filename}"

class CSVDump:
    def __init__(self, schema: Type[BaseModel]):
        self._schema = schema

    def __call__(self, data: List[Video], *, include_headers: bool = True, delimiter: str = ";") -> str:
        rows = [self._schema(**v.model_dump()).model_dump() for v in data]
        return self._make_csv(rows, include_headers, delimiter)

    @staticmethod
    def _make_csv(rows: List[Dict], include_headers: bool, delimiter: str) -> str:
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=rows[0].keys(), delimiter=delimiter)
        if include_headers:
            writer.writeheader()
        writer.writerows(rows)
        return output.getvalue()

csv_dump = CSVDump(VideoCSV)
