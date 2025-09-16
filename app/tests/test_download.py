# app/tests/test_download.py
import pytest
import io
from unittest.mock import AsyncMock, patch

from app.download.downloader import Downloader, DownloadedFile


class MockResponse:
    def __init__(self, content: bytes, status: int = 200):
        self.status = status
        self.headers = {"Content-Length": str(len(content))}
        self.content = AsyncMock()
        self.content.read = AsyncMock(side_effect=[content, b""])


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
async def test_downloader_fetch_mocked():
    fake_content = b"test data"
    fake_url = "https://example.com/video.mp4"
    
    mock_response = MockResponse(fake_content)
    mock_session = MockSession(mock_response)

    with patch("aiohttp.ClientSession") as mock_client_session:
        mock_client_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_client_session.return_value.__aexit__ = AsyncMock(return_value=None)
        
        downloader = Downloader()
        result: DownloadedFile = await downloader.download_file(url=fake_url)

        assert result.filename == "video.mp4"
        assert result.md5 == "eb733a00c0c9d336e65691a37ab54293"
        assert isinstance(result.content, io.BytesIO)
        assert result.content.getvalue() == fake_content