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


@app.get("/csv")
async def fetch_csv_for_import(last_video_code: str = "", limit: int = 0):
    search_params = {
        "javguru_status": "downloaded",
        "rewritten_title": {"$ne": None},
        "thumbnail_s3_url": {"$ne": None},
        "javct_enriched": True,
        "javtiful_enriched": True,
    }
    if last_video_code:
        video = await Video.find_one({"jav_code": last_video_code})
        if not video:
            raise ValueError(f"Video not found by {last_video_code}!")
        last_video_id = video.id
        if not last_video_id:
            raise AttributeError(f"Video {last_video_code} doesn't have Mongo ID!")
        search_params.update({"_id": {"$lte": last_video_id}})
    mongo_query_coro = Video.find_many(search_params, fetch_links=True)
    if limit:
        mongo_query_coro = mongo_query_coro.limit(limit)
    logger.info(
        f"Fetching videos with filters: {search_params}, last_video_code={last_video_code or 'none'}, "
        f"limit={limit or 'none'}"
    )
    videos = await mongo_query_coro.to_list()
    logger.info(f"Found {len(videos)} videos satisfying the search params")
    csv_data, ids = csv_dump(videos)
    logger.info(f"Fetched {len(ids)} videos that can be imported to KVS")
    return Response(content=csv_data, media_type="text/plain", headers={"X-Video-IDs": json.dumps(ids)})
