import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from loguru import logger

from app.db.database import init_mongo
from app.db.models import Video
from app.infra.worker import download_caller
from app.download.csv_dump import csv_dump


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing MongoDB...")
    await init_mongo()
    logger.success("MongoDB initialized")
    yield

app = FastAPI(
    title="JavGuru Parser/Downloader",
    version="1.0.0",
    lifespan=lifespan
)

# @app.post("/start-download", tags=["Download"])
# async def start_download(limit: int = 15):
#     count = await download_caller(limit)
#     return {"status": "Success", "msg": f"Sent {count} tasks"}


# @app.get("/healthcheck", tags=["Debug"], summary="Health Check")
# async def healthcheck():
#     logger.debug("Healthcheck ping")
#     return JSONResponse(
#         status_code=status.HTTP_200_OK, 
#         content={"status": "ok"}
#         )  


@app.post("/export-kvs")
async def export_kvs_feed(limit: int = 15):
    videos = await Video.find(
        Video.s3_path != None, fetch_links=True,
    ).limit(limit).to_list()

    csv_data = csv_dump(videos)
    video_ids = [str(v.id) for v in videos]

    return Response(
        content=csv_data,
        media_type="text/plain",
        headers={"X-Video-IDs": json.dumps(video_ids)}
    )
