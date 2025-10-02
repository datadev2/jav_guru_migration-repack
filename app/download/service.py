import hashlib
import tempfile
from io import BytesIO

import aiohttp
from loguru import logger
from pymediainfo import MediaInfo
from pymongo.errors import DuplicateKeyError
from selenium.webdriver.common.by import By

from app.config import config
from app.db.database import init_mongo
from app.db.models import Video, VideoSource
from app.download.exceptions import DownloadFailedException
from app.infra.s3 import s3
from app.parser.driver import SeleniumDriver
from app.parser.interactions import SeleniumService
from app.parser.sites.guru import GuruAdapter


class GuruDownloader:
    """
    Video -> page_link -> open -> _extract_video_src() -> download -> update Video -> upload to S3
    """

    def __init__(self, selenium: SeleniumService, parser: GuruAdapter) -> None:
        self.selenium = selenium
        self.parser = parser

    async def __call__(self, video: Video) -> bool:
        page_url = str(video.page_link)
        try:
            self.selenium.get(page_url, wait_selector=(By.XPATH, "//div[contains(@class,'inside-article')]"))  # type: ignore
            src = self.parser._extract_video_src(self.selenium, timeout_sec=2)
            if not src:
                logger.error(f"No video src on {page_url}")
                return False

            buf = await self._download_to_buffer(src)
            if not buf.getbuffer().nbytes:
                logger.error(f"empty buffer {page_url}")
                return False

            file_size = buf.getbuffer().nbytes
            md5 = hashlib.md5(buf.getbuffer()).hexdigest()

            s3_filename = f"{video.jav_code}_{md5}.mp4"
            s3_key = f"{config.S3_FOLDER}/{s3_filename}".lstrip("/")
            buf.seek(0)
            await s3.put_object(buf, s3_key)

            s3_path = f"https://{config.S3_ENDPOINT}/{config.S3_BUCKET}/{s3_key}"
            resolution = self._detect_resolution(buf, s3_filename)
            runtime_minutes = self._detect_runtime(buf, s3_filename)

            video.runtime_minutes = runtime_minutes

            source = VideoSource(
                origin="guru",
                resolution=resolution,
                s3_path=s3_path,
                file_name=s3_filename,
                file_size=file_size,
                hash_md5=md5,
            )
            video.sources.append(source)
            await video.save()
            logger.success(f"OK {s3_filename} | {file_size} bytes | {resolution}")
            return True
        except (DownloadFailedException, DuplicateKeyError) as e:
            logger.error(f"{type(e).__name__}: {e}")
        except Exception as e:
            logger.exception(e)
        return False

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

    @staticmethod
    def _detect_runtime(buf: BytesIO, s3_filename: str) -> int | None:
        """
        Parse video buffer with pymediainfo and return runtime in minutes.

        Runtime is extracted from track.duration (milliseconds → minutes).
        If not detected or parsing fails, returns None.
        """
        try:
            buf.seek(0)
            media_info = MediaInfo.parse(buf)
            for track in media_info.tracks:
                if track.track_type == "Video" and track.duration:
                    return int(track.duration / 60000)
        except Exception:
            with tempfile.NamedTemporaryFile(delete=True) as tmp_file:
                buf.seek(0)
                tmp_file.write(buf.read())
                tmp_file.flush()
                media_info = MediaInfo.parse(tmp_file.name)
                for track in media_info.tracks:
                    if track.track_type == "Video" and track.duration:
                        return int(track.duration / 60000)

        logger.warning(f"runtime not detected {s3_filename}")
        return None

    @staticmethod
    def _detect_resolution(buf: BytesIO, s3_filename: str) -> str:
        """
        Parse video buffer with pymediainfo and return resolution label.

        Resolution is derived from track.height and normalized to:
        "480p", "720p", "1080p", "2k", or "4k".
        If not detected, returns "unknown".
        """
        height = None
        try:
            buf.seek(0)
            media_info = MediaInfo.parse(buf)
            for track in media_info.tracks:
                if track.track_type == "Video" and track.height:
                    height = track.height
                    break
            else:
                logger.warning(f"resolution not detected {s3_filename}")
                return "unknown"

        except Exception:
            with tempfile.NamedTemporaryFile(delete=True) as tmp_file:
                buf.seek(0)
                tmp_file.write(buf.read())
                tmp_file.flush()

                media_info = MediaInfo.parse(tmp_file.name)
                for track in media_info.tracks:
                    if track.track_type == "Video" and track.height:
                        height = track.height
                        break
                else:
                    logger.warning(f"resolution not detected {s3_filename}")
                    return "unknown"

        if height <= 480:
            return "480p"
        if height <= 720:
            return "720p"
        if height <= 1080:
            return "1080p"
        if height <= 1440:
            return "2k"
        return "4k"


async def run_download(video_id: str, origin_source: str, headless: bool) -> None:
    await init_mongo()
    video = await Video.get(video_id)
    if not video:
        raise ValueError(f"No video {video_id} found in DB!")
    if origin_source == "guru":
        if video.javguru_status != "parsed":
            logger.info(f"Video {video_id} has javguru status {video.javguru_status}. Download rejected.")
            return
        video.javguru_status = "downloading"
        await video.save()
        with SeleniumDriver(headless=headless) as driver:
            selenium = SeleniumService(driver)
            adapter = GuruAdapter()
            downloader = GuruDownloader(selenium, adapter)
            success = await downloader(video=video)
        if success:
            video.javguru_status = "downloaded"
            await video.save()
            return
        video.javguru_status = "failed"
        await video.save()
        return

    elif origin_source == "pornolab":
        # TODO: implement a mechanism to send a task to the Pornolab downloader.
        pass
