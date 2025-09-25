from io import BytesIO

import pytest

from app.db.models import Video, VideoSource
from app.download.service import GuruDownloader


# ---------- UNIT TESTS ----------
@pytest.mark.parametrize(
    "height,expected",
    [
        (240, "480p"),
        (720, "720p"),
        (1080, "1080p"),
        (1440, "2k"),
        (2160, "4k"),
    ],
)
def test_detect_resolution(monkeypatch, height, expected):
    """
    Ensure that _detect_resolution correctly maps video height -> resolution string.
    """

    buf = BytesIO(b"fake")

    class FakeTrack:
        track_type = "Video"

        def __init__(self, h):
            self.height = h

    class FakeMediaInfo:
        def __init__(self, h):
            self.tracks = [FakeTrack(h)]

    monkeypatch.setattr("app.download.service.MediaInfo.parse", lambda *_: FakeMediaInfo(height))

    d = GuruDownloader(None, None)
    res = d._detect_resolution(buf, "test.mp4")
    assert res == expected


@pytest.mark.parametrize(
    "duration,expected",
    [
        (60_000, 1),
        (125_000, 2),
        (3_600_000, 60),
    ],
)
def test_detect_runtime(monkeypatch, duration, expected):
    """
    Ensure that _detect_runtime correctly converts duration (ms) -> minutes.
    """

    buf = BytesIO(b"fake")

    class FakeTrack:
        track_type = "Video"

        def __init__(self, d):
            self.duration = d

    class FakeMediaInfo:
        def __init__(self, d):
            self.tracks = [FakeTrack(d)]

    monkeypatch.setattr("app.download.service.MediaInfo.parse", lambda *_: FakeMediaInfo(duration))

    d = GuruDownloader(None, None)
    res = d._detect_runtime(buf, "test.mp4")
    assert res == expected


# ---------- INTEGRATION TESTS ----------
@pytest.mark.asyncio
async def test_download_one_full_video(monkeypatch, init_db):
    """
    Ensure that download_one creates a complete Video record with all required fields.
    """

    class DummyParser:
        def _extract_video_src(self, *_, **__):
            return "http://fake/video.mp4"

    class DummySelenium:
        def get(self, *_, **__):
            return None

    async def fake_download(url, *_, **__):
        return BytesIO(b"0" * 2048)

    async def fake_put(buf, key):
        return True

    monkeypatch.setattr("app.download.service.GuruDownloader._download_to_buffer", fake_download)
    monkeypatch.setattr("app.download.service.s3.put_object", fake_put)
    monkeypatch.setattr("app.download.service.GuruDownloader._detect_resolution", lambda *_: "1080p")
    monkeypatch.setattr("app.download.service.GuruDownloader._detect_runtime", lambda *_: 99)

    video = Video(
        title="Full Test Video",
        jav_code="TST-003",
        page_link="https://x/full",
        site="guru",
        thumbnail_url="https://x/thumb.jpg",
        actresses=[],
        actors=[],
        directors=[],
        categories=[],
        tags=[],
        studio=None,
        release_date=None,
        uncensored=False,
        sources=[
            VideoSource(
                origin="pornolab",
                resolution="720p",
                s3_path="https://s3.serviceforapi.net/videos/javguru/TST-003_pornolab.mp4",
                file_name="TST-003_pornolab.mp4",
                file_size=1024,
                hash_md5="hash-pornolab",
            )
        ],
    )
    await video.insert()

    d = GuruDownloader(DummySelenium(), DummyParser())
    ok = await d.download_one(video)
    assert ok

    saved = await Video.get(video.id)
    assert saved is not None

    assert saved.title == "Full Test Video"
    assert saved.jav_code == "TST-003"
    assert saved.site == "guru"
    assert str(saved.thumbnail_url) == "https://x/thumb.jpg"

    assert len(saved.sources) == 2

    resolutions = [s.resolution for s in saved.sources]
    assert "720p" in resolutions
    assert "1080p" in resolutions

    origins = [s.origin for s in saved.sources]
    assert "pornolab" in origins
    assert "guru" in origins

    guru_src = next(s for s in saved.sources if s.origin == "guru")
    assert guru_src.resolution == "1080p"
    assert guru_src.file_size == 2048
    assert guru_src.hash_md5 is not None
    assert guru_src.s3_path.startswith("https://")

    assert saved.runtime_minutes == 99


@pytest.mark.asyncio
async def test_download_one_sets_runtime(monkeypatch, init_db):
    """
    Ensure that download_one writes runtime_minutes into the Video record.
    """

    class DummyParser:
        def _extract_video_src(self, *_, **__):
            return "http://fake/video.mp4"

    class DummySelenium:
        def get(self, *_, **__):
            return None

    async def fake_download(url, *_, **__):
        return BytesIO(b"0" * 1024)

    async def fake_put(buf, key):
        return True

    monkeypatch.setattr("app.download.service.GuruDownloader._download_to_buffer", fake_download)
    monkeypatch.setattr("app.download.service.s3.put_object", fake_put)
    monkeypatch.setattr("app.download.service.GuruDownloader._detect_resolution", lambda *_: "720p")
    monkeypatch.setattr("app.download.service.GuruDownloader._detect_runtime", lambda *_: 99)

    video = Video(title="TestVid", jav_code="TST-002", page_link="https://x")
    await video.insert()

    d = GuruDownloader(DummySelenium(), DummyParser())
    ok = await d.download_one(video)
    assert ok

    saved = await Video.get(video.id)
    assert saved is not None
    assert saved.runtime_minutes == 99


@pytest.mark.asyncio
async def test_download_one_inserts_source(monkeypatch, init_db):
    """
    Ensure that download_one adds a VideoSource into Video and persists it in MongoDB.
    """

    class DummyParser:
        def _extract_video_src(self, *_, **__):
            return "http://fake/video.mp4"

    class DummySelenium:
        def get(self, *_, **__):
            return None

    async def fake_download(url, *_, **__):
        return BytesIO(b"0" * 1024)

    async def fake_put(buf, key):
        return True

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
    Ensure that download_one appends a second VideoSource if one already exists.
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
        def _extract_video_src(self, *_, **__):
            return "http://fake/video2.mp4"

    class DummySelenium:
        def get(self, *_, **__):
            return None

    async def fake_download(url, *_, **__):
        return BytesIO(b"1" * 2048)

    async def fake_put(buf, key):
        return True

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
