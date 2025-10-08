# tests/test_video_models.py
import pytest

from app.db.models import Video, VideoSource, ParsedVideo
from app.parser.service import Parser


class MockAdapter:
    site_name = "guru"

    def parse_videos(self, selenium, start_page=None, end_page=None):
        return [
            ParsedVideo(title="video_1", jav_code="TEST-1", page_link="https://test/1", site="guru"),
            ParsedVideo(title="video_2", jav_code="TEST-2", page_link="https://test/2", site="guru"),
            ParsedVideo(title="video_3", jav_code="TEST-1", page_link="https://test/1", site="guru"),
        ]

@pytest.mark.asyncio
async def test_get_videos_inserts_only_unique(init_db):
    parser = Parser(adapter=MockAdapter(), headless=True)
    await parser.get_videos(start_page=1, end_page=1)

    videos = await Video.find_all().to_list()
    assert len(videos) == 2
    links = {str(v.page_link) for v in videos}
    assert "https://test/1" in links and "https://test/2" in links


@pytest.mark.asyncio
async def test_insert_video_multiple_sources(init_db, mock_load_data):
    data = mock_load_data("download_source.json")
    record = next(r for r in data if r["jav_code"] == "MOCK-003")
    sources = [VideoSource(**s) for s in record["sources"]]

    video = Video(
        title=record["title"],
        jav_code=record["jav_code"],
        page_link=record["page_link"],
        javguru_status=record["javguru_status"],
        sources=sources,
    )
    await video.insert()

    saved = await Video.find_one(Video.jav_code == record["jav_code"])
    assert saved is not None
    assert len(saved.sources) == len(record["sources"])
    assert {s.resolution for s in saved.sources} == {s["resolution"] for s in record["sources"]}


@pytest.mark.asyncio
async def test_insert_video_empty_sources(init_db):
    video = Video(
        title="Empty Sources Video",
        jav_code="DEV-EMPTY-SRC",
        page_link="https://example.com/1/dev-empty-src/",
        javguru_status="added",
        sources=[],
    )
    await video.insert()

    saved = await Video.find_one(Video.jav_code == "DEV-EMPTY-SRC")
    assert saved is not None
    assert saved.sources == []


@pytest.mark.asyncio
async def test_insert_video_duplicate_jav_code(init_db, mock_load_data):
    data = mock_load_data("download_source.json")
    record = next(r for r in data if r["jav_code"] == "MOCK-002")
    sources = [VideoSource(**s) for s in record["sources"]]

    video1 = Video(
        title=record["title"],
        jav_code=record["jav_code"],
        page_link=record["page_link"],
        javguru_status=record["javguru_status"],
        sources=sources,
    )
    await video1.insert()
    
    existing = await Video.find_one(Video.jav_code == record["jav_code"])
    assert existing is not None

    with pytest.raises(ValueError, match="Duplicate jav_code"):
        if existing:
            raise ValueError("Duplicate jav_code")

@pytest.mark.asyncio
async def test_insert_video_pornolab(init_db):
    video = Video(
        title="Pornolab Video",
        jav_code="DEV-LAB",
        page_link="https://pornolab.net/1/dev-lab/",
        javguru_status="added",
        sources=[
            VideoSource(
                origin="pornolab",
                resolution="1080p",
                s3_path="s3://videos/javguru/dev-lab-1080p.mp4",
                file_name="dev-lab-1080p.mp4",
                file_size=222,
                hash_md5="hash-lab",
            )
        ],
    )
    await video.insert()
    saved = await Video.find_one(Video.jav_code == "DEV-LAB")
    assert saved.sources[0].origin == "pornolab"


@pytest.mark.asyncio
async def test_insert_video_other(init_db):
    video = Video(
        title="Other Source Video",
        jav_code="DEV-OTHER",
        page_link="https://example.com/1/dev-other/",
        javguru_status="added",
        sources=[
            VideoSource(
                origin="other",
                resolution="720p",
                s3_path="s3://videos/javguru/dev-other-720p.mp4",
                file_name="dev-other-720p.mp4",
                file_size=333,
                hash_md5="hash-other",
            )
        ],
    )
    await video.insert()
    saved = await Video.find_one(Video.jav_code == "DEV-OTHER")
    assert saved.sources[0].origin == "other"
