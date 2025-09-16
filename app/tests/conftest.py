import json
import pytest
import pytest_asyncio
from pathlib import Path
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from app.db.models import Video, VideoSource, Category, Tag, Model, Studio
from app.config import config


@pytest.fixture(scope="module")
def mock_video_data():
    path = Path(__file__).parent / "mocks" / "video_source.json"
    with path.open() as f:
        return json.load(f)

@pytest_asyncio.fixture
async def init_db():
    user = config.DB_USER
    pwd = config.DB_PASS
    host = config.DB_HOST
    db_name = config.DB_NAME

    uri = f"mongodb://{user}:{pwd}@{host}/{db_name}?authSource=admin"

    client = AsyncIOMotorClient(uri)
    db = client[db_name]

    await init_beanie(
        database=db,
        document_models=[Video, Category, Tag, Model, Studio],
    )
    yield db
    client.close()
