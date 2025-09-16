import pytest

from app.db.models import Video, VideoSource, Category, Tag, Model, Studio
from app.config import config


@pytest.mark.asyncio
async def test_insert_video_guru(init_db):
    video = Video(
        title="Guru Video",
        jav_code="DEV-GURU",
        page_link="https://jav.guru/1/dev-guru/",
        sources=[
            VideoSource(
                origin="guru",
                resolution="480p",
                s3_path="s3://videos/javguru/dev-guru-480p.mp4",
                file_name="dev-guru-480p.mp4",
                file_size=111,
                hash_md5="hash-guru",
            )
        ],
    )
    await video.insert()
    saved = await Video.find_one(Video.jav_code == "DEV-GURU")
    assert saved is not None
    assert saved.sources[0].origin == "guru"


@pytest.mark.asyncio
async def test_insert_video_pornolab(init_db):
    video = Video(
        title="Pornolab Video",
        jav_code="DEV-LAB",
        page_link="https://pornolab.net/1/dev-lab/",
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