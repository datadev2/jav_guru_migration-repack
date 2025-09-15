import asyncio

from loguru import logger

from app.config import config
from app.db.database import init_mongo
from app.db.models import Video
from app.google_export.gsheets import gsheets


class GSheetService:
    def __init__(self, gsheet_svc = gsheets):
        self._gsheets_svc = gsheet_svc
        self._gsheet_id = config.G_SPREADSHEET_ID
        self._gsheet_tab = config.G_SPREADSHEET_TAB

    async def update_export_data_to_gsheet(self, gsheet_read_range: str = "A2:A"):
        data_to_export = []
        mongo_videos_ = await Video.find_all(fetch_links=True).to_list()
        latest_exported_mongo_id, write_start_row = self._get_latest_exported_video(
            self._gsheet_id, self._gsheet_tab, gsheet_read_range
        )
        if latest_exported_mongo_id:
            mongo_videos = [
                video for video in mongo_videos_
                if str(video.id) > latest_exported_mongo_id
            ]
            for video in mongo_videos:
                data_to_export.append(
                    [
                        str(video.id),  # Mongo ID
                        video.jav_code,
                        video.thumbnail_url.unicode_string() if video.thumbnail_url else "",
                        video.title,
                        "",  # video title rewritten
                        ", ".join([actress.name for actress in video.actresses]),
                        ", ".join([actor.name for actor in video.actors]),
                        "",  # category JavGuru
                        "",  # category JavctNET
                        "",  # categories JavtifulCOM
                        ", ".join([tag.name for tag in video.tags]),  # tags JavGuru
                        "", # tags JavtifulCOM
                        video.studio.name,
                        video.release_date.strftime("%d-%m-%Y") if video.release_date else "",
                        ", ".join([director.name for director in video.directors]),
                        "",  # type from javtifulCOM,
                        "",  # running time
                        "✓" if video.s3_path else "",
                        round(video.file_size / 1073741824, 2) if video.file_size else "",
                        "",  # downloaded from pornolab
                        "",  # pornolab file size
                    ]
                )
            self._gsheets_svc.write_to_sheet(data_to_export, self._gsheet_tab, f"A{write_start_row}", self._gsheet_id)
            

    def _get_latest_exported_video(
            self, gsheet_id: str, gsheet_tab: str, gsheet_read_range: str
        ) -> tuple[str, int]:
            exported_videos = self._gsheets_svc.read_sheet(gsheet_tab, gsheet_read_range, gsheet_id)
            try:
                last_exported_video = exported_videos[-1]
                last_exported_mongo_id = last_exported_video[0]
                write_start_row_num = len(exported_videos) + 2  # Because the first row with data is the row #2.
                return last_exported_mongo_id, write_start_row_num
            except IndexError:
                logger.error("[!] ERROR! Failed to get latest exported video ID due to IndexError!")
                return "", 0


if __name__ == "__main__":

    async def main():
        await init_mongo()
        gsh_svc = GSheetService()
        await gsh_svc.update_export_data_to_gsheet()

    asyncio.run(main())
