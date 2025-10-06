import csv
from io import StringIO
from typing import Type

from pydantic import BaseModel

from app.db.models import Video, VideoCSV


class CSVDump:
    def __init__(self, schema: Type[BaseModel], delimiter=";"):
        self._schema = schema
        self._delimiter = delimiter

    def __call__(self, videos: list[Video]) -> str:
        validated_data = []
        for video in videos:
            raw = {
                "jav_code": video.jav_code,
                "title": video.title,
                "release_date": video.release_date,
                "file_hash": video.file_hash_md5,
                "models": [actress.name for actress in video.actresses],
                "categories": [cat.name for cat in video.categories],
                "tags": [tag.name for tag in video.tags],
                "s3_path": video.s3_path,
                "studio": video.studio,
                "poster_url": video.thumbnail_s3_url.unicode_string(),
            }
            validated_data.append(self._schema(**raw).model_dump(mode="json"))
        return self._make_csv_string(validated_data)

    def _make_csv_string(self, data: list[dict]):
        output = StringIO()
        writer = csv.writer(output, delimiter=self._delimiter)
        for row in data:
            writer.writerow(row.values())
        return output.getvalue()


csv_dump = CSVDump(VideoCSV)
