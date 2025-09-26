from dataclasses import dataclass
from io import BytesIO

import aiohttp

from app.config import config
from app.download.exceptions import DownloadFailedException
from app.download.utils import calculate_md5, extract_filename


@dataclass
class DownloadedFile:
    content: BytesIO
    filename: str
    md5: str


class Downloader:
    def __init__(
        self,
        *,
        timeout: int = 3600,
        chunk_size: int = config.CHUNK,
    ):
        self.timeout = timeout
        self.chunk_size = chunk_size

    async def download_file(
        self,
        url: str,
        headers: dict[str, str] | None = None,
    ) -> DownloadedFile:
        timeout = aiohttp.ClientTimeout(total=self.timeout)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    raise DownloadFailedException(f"Download failed with status {response.status} for {url}")

                chunks: list[bytes] = []

                while True:
                    chunk = await response.content.read(self.chunk_size)
                    if not chunk:
                        break
                    chunks.append(chunk)

                content = b"".join(chunks)
                file_obj = BytesIO(content)
                filename = extract_filename(url)
                md5_hash = calculate_md5(file_obj)

                return DownloadedFile(content=file_obj, filename=filename, md5=md5_hash)
