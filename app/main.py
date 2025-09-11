from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi import FastAPI, status
from fastapi.responses import JSONResponse

from app.db.database import init_mongo
from app.infra.worker import download_caller
from app.logger import init_logger


logger = init_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing MongoDB...")
    await init_mongo()
    logger.success("MongoDB initialized")
    yield

app = FastAPI(
    title="LuxureTV Parser",
    version="1.0.0",
    lifespan=lifespan
)

@app.post("/start-download", tags=["Download"])
async def start_download(limit: int = 15):
    count = await download_caller(limit)
    return {"status": "Success", "msg": f"Sent {count} tasks"}


@app.get("/healthcheck", tags=["Debug"], summary="Health Check")
async def healthcheck():
    logger.debug("Healthcheck ping")
    return JSONResponse(
        status_code=status.HTTP_200_OK, 
        content={"status": "ok"}
        )  
