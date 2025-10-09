import asyncio
from collections import defaultdict
from loguru import logger
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from app.db.models import Video
from app.config import config


async def init_mongo():
    uri = f"mongodb://{config.DB_USER}:{config.DB_PASS}@{config.DB_HOST}:27017/adminauth?authSource=admin"
    client = AsyncIOMotorClient(uri)
    await init_beanie(database=client[config.DB_NAME], document_models=[Video])
    logger.info(f"[DB] Connected to MongoDB at {DB_HOST}/{config.DB_NAME}")


async def cleanup_duplicates():
    """
    Script: cleanup_duplicates.py

    Purpose:
        Scans the 'Video' collection in the MongoDB database and removes duplicate
        entries based on the 'jav_code' field.

    Behavior:
        • Groups videos by jav_code.
        • Keeps only one record per code using the following priority:
            1. Record with javguru_status == "downloaded".
            2. Record with existing sources, thumbnail_url, and release_date.
            3. The oldest record (created_at).
        • Deletes all other duplicates.
        • Logs every action and summary statistics.

    Usage:
        python scripts/cleanup_duplicates.py
    """
    await init_mongo()
    logger.info("[Cleanup] Removing duplicate jav_code entries...")

    all_videos = await Video.find({"jav_code": {"$ne": ""}}).to_list()
    seen = defaultdict(list)
    for v in all_videos:
        seen[v.jav_code].append(v)

    dup_count = 0
    removed_count = 0

    for code, vids in seen.items():
        if len(vids) <= 1:
            continue

        dup_count += 1
        vids_sorted = sorted(
            vids,
            key=lambda v: (
                v.javguru_status != "downloaded",
                not bool(v.sources),
                not bool(v.thumbnail_url),
                not bool(v.release_date),
                v.created_at or 0,
            ),
        )

        to_keep = vids_sorted[0]
        logger.info(f"[Keep] jav_code={code} | id={to_keep.id} | status={to_keep.javguru_status}")

        for v in vids_sorted[1:]:
            try:
                await v.delete()
                removed_count += 1
                logger.info(
                    f"[Deleted] id={v.id} | status={v.javguru_status} | title={v.title[:80]!r} | link={v.page_link}"
                )
            except Exception as e:
                logger.error(f"[Error] Failed to delete {v.id}: {e}")

    logger.success(f"[Cleanup] Done. Groups processed: {dup_count}, duplicates removed: {removed_count}")
    if dup_count == 0:
        logger.success("[Cleanup] No duplicates found.")
    else:
        logger.info(f"[Cleanup] Total duplicate groups: {dup_count}")


if __name__ == "__main__":
    asyncio.run(cleanup_duplicates())
