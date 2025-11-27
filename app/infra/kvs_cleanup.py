import json
from pathlib import Path
from urllib.parse import urlparse

from botocore.exceptions import ClientError
from loguru import logger

from app.db.database import init_mongo
from app.db.models import Video
from app.infra.kvs import kvs_feed
from app.infra.s3 import s3

KVS_RANGE_PATH = Path(__file__).parent / "kvs_range.json"


def get_kvs_range():
    with KVS_RANGE_PATH.open() as f:
        return json.load(f)


def save_next_kvs_range(data):
    new_data = {
        "skip": data["skip"] + data["limit"],
        "limit": data["limit"],
    }
    with KVS_RANGE_PATH.open("w") as f:
        json.dump(new_data, f)


async def kvs_cleanup_chunk():
    """
    Process one KVS chunk:
    - fetch KVS feed
    - classify
    - delete valid objects
    - update DB
    - shift pagination window
    """
    await init_mongo()
    rng = get_kvs_range()

    kvs_items = await kvs_feed.get_feed_chunk(
        limit=rng["limit"],
        skip=rng["skip"],
    )

    to_delete = []
    skipped = []

    for item in kvs_items:
        file_hash = item.file_hash_md5

        if not file_hash or len(file_hash) != 32:
            skipped.append({"hash": file_hash, "reason": "invalid"})
            continue

        db_video = await Video.find_one({"sources.hash_md5": file_hash})
        if not db_video:
            skipped.append({"hash": file_hash, "reason": "not_in_db"})
            continue

        source = next(
            (s for s in db_video.sources if s.hash_md5 == file_hash and s.status == "imported"),
            None,
        )

        if not source:
            skipped.append({"hash": file_hash, "reason": "not_imported"})
            continue

        to_delete.append(
            {
                "hash": file_hash,
                "video_id": str(db_video.id),
                "s3_url": source.s3_path,
            }
        )

    deleted_items = []

    for item in to_delete:
        parsed = urlparse(item["s3_url"])
        path = parsed.path.lstrip("/")
        bucket, key = path.split("/", 1)

        logger.info(f"DELETE {bucket}/{key}")

        ok = await s3.delete_object(bucket, key)
        if not ok:
            continue

        try:
            await s3.object_info(bucket, key)
            continue
        except ClientError as e:
            if e.response["Error"]["Code"] != "404":
                continue

        db_video = await Video.get(item["video_id"])
        for src in db_video.sources:
            if src.hash_md5 == item["hash"]:
                src.status = "deleted"
        await db_video.save()

        deleted_items.append(item)

    save_next_kvs_range(rng)
    logger.info(f"deleted {len(deleted_items)} items, skipped {len(skipped)}")

    return {"deleted": deleted_items, "skipped": skipped, "range": rng}
