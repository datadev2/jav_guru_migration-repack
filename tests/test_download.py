# tests/test_download.py
import io
from unittest.mock import AsyncMock, patch

import pytest

from app.download.downloader import DownloadedFile, Downloader
from app.download.exceptions import DownloadFailedException


class MockResponse404:
    def __init__(self, status: int = 404):
        self.status = status
        self.headers = {}
        self.content = AsyncMock()
        self.content.read = AsyncMock(return_value=b"")


class MockResponseEmpty:
    def __init__(self, status: int = 200):
        self.status = status
        self.headers = {"Content-Length": "0"}
        self.content = AsyncMock()

        async def _read(_):
            return b""

        self.content.read = AsyncMock(side_effect=_read)


class MockResponse:
    def __init__(self, content: bytes, status: int = 200):
        self.status = status
        self.headers = {"Content-Length": str(len(content))}
        self.content = AsyncMock()
        self._chunks = [content, b""]

        async def _read(_):
            return self._chunks.pop(0)

        self.content.read = AsyncMock(side_effect=_read)


class MockSession:
    def __init__(self, response: MockResponse):
        self._response = response

    def get(self, *args, **kwargs):
        return MockContextManager(self._response)


class MockContextManager:
    def __init__(self, response: MockResponse):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, *args):
        pass


@pytest.mark.asyncio
async def test_downloader_with_json_mock(mock_load_data):
    data = mock_load_data("download_source.json")
    record = data[0]
    source = record["sources"][0]

    fake_content = b"x" * source["file_size"]
    mock_response = MockResponse(fake_content)
    mock_session = MockSession(mock_response)

    with patch("aiohttp.ClientSession") as mock_client_session:
        mock_client_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_client_session.return_value.__aexit__ = AsyncMock(return_value=None)

        downloader = Downloader(chunk_size=1024)
        result: DownloadedFile = await downloader.download_file(url="https://fake.local/" + source["file_name"])

        assert result.filename == source["file_name"]
        assert isinstance(result.content, io.BytesIO)
        assert len(result.content.getvalue()) == source["file_size"]
        assert isinstance(result.md5, str) and result.md5


@pytest.mark.asyncio
async def test_downloader_chunked_read(mock_load_data):
    data = mock_load_data("download_source.json")
    record = next(r for r in data if r["jav_code"] == "MOCK-CHUNKS")
    source = record["sources"][0]

    fake_content = b"x" * source["file_size"]
    chunks = [fake_content[i : i + 3] for i in range(0, len(fake_content), 3)] + [b""]
    mock_response = MockResponse(b"".join(chunks))
    mock_response._chunks = chunks.copy()

    mock_session = MockSession(mock_response)

    with patch("aiohttp.ClientSession") as mock_client_session:
        mock_client_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_client_session.return_value.__aexit__ = AsyncMock(return_value=None)

        downloader = Downloader(chunk_size=3)
        result: DownloadedFile = await downloader.download_file(url="https://fake.local/" + source["file_name"])

        assert result.filename == source["file_name"]
        assert len(result.content.getvalue()) == source["file_size"]
        assert result.content.getvalue() == fake_content
        assert result.md5 == source["hash_md5"]


@pytest.mark.asyncio
async def test_downloader_error_404(mock_load_data):
    data = mock_load_data("download_source.json")
    record = next(r for r in data if r["jav_code"] == "MOCK-404")
    source = record["sources"][0]

    mock_response = MockResponse404(status=404)
    mock_session = MockSession(mock_response)

    with patch("aiohttp.ClientSession") as mock_client_session:
        mock_client_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_client_session.return_value.__aexit__ = AsyncMock(return_value=None)

        downloader = Downloader(chunk_size=1024)
        with pytest.raises(DownloadFailedException) as excinfo:
            await downloader.download_file(url="https://fake.local/" + source["file_name"])

        assert "404" in str(excinfo.value)
        assert source["file_name"] in str(excinfo.value) or "https://fake.local/" in str(excinfo.value)


@pytest.mark.asyncio
async def test_downloader_empty_content(mock_load_data):
    data = mock_load_data("download_source.json")
    record = next(r for r in data if r["jav_code"] == "MOCK-EMPTY")
    source = record["sources"][0]

    mock_response = MockResponseEmpty()
    mock_session = MockSession(mock_response)

    with patch("aiohttp.ClientSession") as mock_client_session:
        mock_client_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_client_session.return_value.__aexit__ = AsyncMock(return_value=None)

        downloader = Downloader(chunk_size=1024)
        result: DownloadedFile = await downloader.download_file(url="https://fake.local/" + source["file_name"])

        assert result.filename == source["file_name"]
        assert isinstance(result.content, io.BytesIO)
        assert len(result.content.getvalue()) == 0
        assert result.md5 == source["hash_md5"]
