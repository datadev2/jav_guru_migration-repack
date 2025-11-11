import csv
from io import StringIO
from typing import Type

from pydantic import BaseModel

from app.db.models import Video, VideoCSV, VideoSource


class CSVDump:
    def __init__(self, schema: Type[BaseModel], delimiter=";"):
        self._schema = schema
        self._delimiter = delimiter

    def __call__(self, videos: list[Video]) -> tuple[str, int]:
        validated_data = []
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
                "categories": [cat.name.title() for cat in video.categories],
                "tags": [tag.name.title() for tag in video.tags],
                "s3_path": best_hd_source.s3_path,
                "poster_for_main_page_url": video.thumbnail_s3_url.unicode_string(),
                "studio": video.studio.name if video.studio else "",
            }
            validated_data.append(self._schema(**raw).model_dump(mode="json"))
        csv_string = self._make_csv_string(validated_data)
        return csv_string, len(validated_data)

    @staticmethod
    def _fetch_best_source(
        sources: list[VideoSource],
        res: list[str] = ["4k", "2k", "1080p", "720p"]
    ) -> VideoSource | None:
        """Select a source with the highest resolution.
        E.g., if sources = [
            VideoSource(origin="pornolab", status="imported", resolution="1080p"),
            VideoSource(origin="ijavtorrent", status="saved", resolution="4k"),
        ], the method will return "ijavtorrent" source, as its resolution is higher and
        it was not imported to the KVS yet.
        If sources = [
            VideoSource(origin="pornolab", status="imported", resolution="1080p"),
            VideoSource(origin="myjavbay", status="saved", resolution="1080p"),
        ], the method will return None, as the new, recently saved source "myjavbay" has the same
        resolution as the "pornolab"'s and there's no point in importing the source with the same resolution.

        """
        valid = [s for s in sources if s.resolution in res]
        if not valid:
            return None
        non_saved = [s for s in valid if s.status != "saved"]
        if non_saved:
            best_non_saved_res = min(non_saved, key=lambda s: res.index(s.resolution)).resolution
            best_non_saved_index = res.index(best_non_saved_res)
        else:
            best_non_saved_index = len(res)
        better_saved = [s for s in valid if s.status == "saved" and res.index(s.resolution) < best_non_saved_index]
        if not better_saved:
            return None
        return min(better_saved, key=lambda s: res.index(s.resolution))

    def _make_csv_string(self, data: list[dict]):
        output = StringIO()
        writer = csv.writer(output, delimiter=self._delimiter)
        for row in data:
            writer.writerow(row.values())
        return output.getvalue()


csv_dump = CSVDump(VideoCSV)
