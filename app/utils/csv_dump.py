import csv
from io import StringIO
from typing import Type

from pydantic import BaseModel

from app.db.models import Video, VideoCSV, VideoSource


class CSVDump:
    def __init__(self, schema: Type[BaseModel], delimiter=";"):
        self._schema = schema
        self._delimiter = delimiter

    def __call__(self, videos: list[Video]) -> tuple[str, list]:
        validated_data = []
        ids = []
        for video in videos:
            best_hd_source = self._fetch_best_source(video.sources)
            if not best_hd_source:
                continue
            raw = {
                "jav_code": video.jav_code,
                "title": video.rewritten_title,
                "release_date": video.release_date,
                "file_hash": best_hd_source.hash_md5,
                "models": [actress.name for actress in video.actresses],
                "categories": [cat.name for cat in video.categories],
                "tags": [tag.name for tag in video.tags],
                "s3_path": best_hd_source.s3_path,
                "poster_for_main_page_url": video.thumbnail_s3_url.unicode_string(),
                "studio": video.studio.name,
            }
            validated_data.append(self._schema(**raw).model_dump(mode="json"))
            ids.append(str(video.id))
        csv_string = self._make_csv_string(validated_data)
        return csv_string, ids

    @staticmethod
    def _fetch_best_source(sources: list[VideoSource], res=["4k", "2k", "1080p", "720p"]) -> VideoSource | None:
        res_normalized = [r.lower() for r in res]
        valid = [s for s in sources if s.resolution.lower() in res_normalized]
        if not valid:
            return None
        return min(valid, key=lambda s: res_normalized.index(s.resolution.lower()))

    def _make_csv_string(self, data: list[dict]):
        output = StringIO()
        writer = csv.writer(output, delimiter=self._delimiter)
        for row in data:
            writer.writerow(row.values())
        return output.getvalue()


csv_dump = CSVDump(VideoCSV)
