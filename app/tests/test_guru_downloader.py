import pytest
from io import BytesIO

from app.db.models import Video, VideoSource
from app.download.service import GuruDownloader


# ---------- UNIT TESTS ----------
@pytest.mark.parametrize("height,expected", [
    (240, "480p"),
    (720, "720p"),
    (1080, "1080p"),
    (1440, "2k"),
    (2160, "4k"),
])
def test_detect_resolution(monkeypatch, height, expected):
    """
    Проверяем, что _detect_resolution правильно мапит height -> resolution
    """

    buf = BytesIO(b"fake")

    class FakeTrack:
        track_type = "Video"
        def __init__(self, h): self.height = h

    class FakeMediaInfo:
        def __init__(self, h): self.tracks = [FakeTrack(h)]

    monkeypatch.setattr(
        "app.download.service.MediaInfo.parse",
        lambda *_: FakeMediaInfo(height)
    )

    d = GuruDownloader(None, None)
    res = d._detect_resolution(buf, "test.mp4")
    assert res == expected


# ---------- INTEGRATION TESTS ----------
@pytest.mark.asyncio
async def test_download_one_inserts_source(monkeypatch, init_db):
    """
    Проверяем, что download_one добавляет VideoSource в Video и сохраняет в Mongo
    """

    class DummyParser:
        def _extract_video_src(self, *_ , **__): return "http://fake/video.mp4"

    class DummySelenium:
        def get(self, *_ , **__): return None

    async def fake_download(url, *_ , **__):
        return BytesIO(b"0" * 1024)

    async def fake_put(buf, key): return True

    monkeypatch.setattr("app.download.service.GuruDownloader._download_to_buffer", fake_download)
    monkeypatch.setattr("app.download.service.s3.put_object", fake_put)
    monkeypatch.setattr("app.download.service.GuruDownloader._detect_resolution", lambda *_: "720p")

    video = Video(title="TestVid", jav_code="TST-001", page_link="https://x")
    await video.insert()

    d = GuruDownloader(DummySelenium(), DummyParser())
    ok = await d.download_one(video)
    assert ok

    import asyncio
    await asyncio.sleep(1)

    saved = await Video.find_one(Video.jav_code == "TST-001")

    assert saved is not None
    assert len(saved.sources) == 1
    assert saved.sources[0].resolution == "720p"
    assert saved.sources[0].file_size == 1024


@pytest.mark.asyncio
async def test_append_second_source(monkeypatch, init_db):
    """
    Проверяем, что download_one добавляет второй VideoSource, если первый уже есть
    """

    video = Video(
        title="TestVid",
        jav_code="TST-001",
        page_link="https://x/",
        sources=[
            VideoSource(
                origin="pornolab",
                resolution="720p",
                s3_path="https://s3.serviceforapi.net/videos/javguru/TST-001_pornolab.mp4",
                file_name="TST-001_pornolab.mp4",
                file_size=1024,
                hash_md5="hash-pornolab",
            )
        ],
    )

    await video.insert()

    class DummyParser:
        def _extract_video_src(self, *_ , **__): return "http://fake/video2.mp4"

    class DummySelenium:
        def get(self, *_ , **__): return None

    async def fake_download(url, *_ , **__):
        return BytesIO(b"1" * 2048)

    async def fake_put(buf, key): return True

    monkeypatch.setattr("app.download.service.GuruDownloader._download_to_buffer", fake_download)
    monkeypatch.setattr("app.download.service.s3.put_object", fake_put)
    monkeypatch.setattr("app.download.service.GuruDownloader._detect_resolution", lambda *_: "1080p")

    d = GuruDownloader(DummySelenium(), DummyParser())
    ok = await d.download_one(video)
    assert ok

    saved = await Video.get(video.id)
    assert saved is not None
    assert len(saved.sources) == 2

    origins = [s.origin for s in saved.sources]
    assert "guru" in origins
    assert "pornolab" in origins