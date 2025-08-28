import motor.motor_asyncio
from beanie import init_beanie

from app.config import config
from app.db.models import Collections


async def init_mongo():
    client = motor.motor_asyncio.AsyncIOMotorClient(str(config.database_dsn))
    await init_beanie(database=client.get_database(config.DB_NAME), document_models=Collections)
