import json
from pathlib import Path

import pytest
import pytest_asyncio
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from app.config import config
from app.db.models import Category, Model, Studio, Tag, Video


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
    db_name = "javguru_tests"

    uri = f"mongodb://{user}:{pwd}@{host}/{db_name}?authSource=admin"

    client = AsyncIOMotorClient(uri)
    db = client[db_name]

    await init_beanie(
        database=db,
        document_models=[Video, Category, Tag, Model, Studio],
    )
    yield db
    client.close()
