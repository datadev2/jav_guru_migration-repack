import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from loguru import logger

from app.db.database import init_mongo
from app.db.models import Video
from app.utils.csv_dump import csv_dump


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing MongoDB...")
    await init_mongo()
    logger.success("MongoDB initialized")
    yield


app = FastAPI(title="JavGuru Parser/Downloader", version="1.0.0", lifespan=lifespan)


@app.post("/csv")
async def fetch_csv_for_import(last_video_code: str = "", limit: int = 0):
    if last_video_code:
        video = await Video.find_one(Video.jav_code == last_video_code)
        if not video:
            raise ValueError(f"Video not found by {last_video_code}!")
        last_video_id = video.id
        if not last_video_id:
            raise AttributeError(f"Video {last_video_code} doesn't have Mongo ID!")
        mongo_query_coro = Video.find_many(
            Video.id <= last_video_id, Video.javguru_status == "downloaded", fetch_links=True
        )
    elif limit:
        mongo_query_coro = Video.find_many(Video.javguru_status == "downloaded", fetch_links=True).limit(limit)
    videos = await mongo_query_coro.to_list()
    csv_data = csv_dump(videos)
    video_ids = [str(v.id) for v in videos]
    return Response(content=csv_data, media_type="text/plain", headers={"X-Video-IDs": json.dumps(video_ids)})
