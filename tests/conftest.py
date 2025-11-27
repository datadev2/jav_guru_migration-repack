import json
import os
from pathlib import Path

import pytest
import pytest_asyncio
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

os.environ.setdefault("KVS_FEED_ENDPOINT", "http://localhost")
os.environ.setdefault("KVS_FEED_PASSWORD", "TESTPASS")

from app.config import config
from app.db.models import Category, Model, Studio, Tag, Video




@pytest.fixture(scope="module")
def mock_load_data():
    def _loader(file_name: str):
        path = Path(__file__).parent / "mocks" / file_name
        with path.open(encoding="utf-8") as f:
            return json.load(f)

    return _loader


@pytest_asyncio.fixture
async def init_db():
    user = config.DB_USER
    pwd = config.DB_PASS
    host = config.DB_HOST
    db_name = "javguru_tests"

    if user and pwd:
        uri = f"mongodb://{user}:{pwd}@{host}/{db_name}?authSource=admin"
    else:
        uri = f"mongodb://{host}/{db_name}"
        
    client = AsyncIOMotorClient(uri)
    db = client[db_name]

    for coll in await db.list_collection_names():
        await db.drop_collection(coll)

    await init_beanie(
        database=db,
        document_models=[Video, Category, Tag, Model, Studio],
    )

    yield db

    await client.drop_database(db_name)
    client.close()
