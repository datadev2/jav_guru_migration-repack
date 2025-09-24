from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from app.db.database import init_mongo


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing MongoDB...")
    await init_mongo()
    logger.success("MongoDB initialized")
    yield


app = FastAPI(title="JavGuru Parser/Downloader", version="1.0.0", lifespan=lifespan)


@app.post("/export-kvs")
async def export_kvs_feed(limit: int = 15):
    # This is a temporary function, just for a test, not fully implemented.
    # videos = (
    #     await Video.find(
    #         Video.s3_path != None,
    #         fetch_links=True,
    #     )
    #     .limit(limit)
    #     .to_list()
    # )

    # csv_data = csv_dump(videos)
    # video_ids = [str(v.id) for v in videos]
    # return Response(content=csv_data, media_type="text/plain", headers={"X-Video-IDs": json.dumps(video_ids)})
    pass
