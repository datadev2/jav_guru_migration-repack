from loguru import logger

from app.config import config
from app.db.database import init_mongo
from app.db.models import Video, VideoSource
from app.google_export.gsheets import gsheets


class GSheetService:
    def __init__(self, gsheet_api=gsheets):
        self._gsheets_api = gsheet_api
        self._gsheet_id = config.G_SPREADSHEET_ID
        self._gsheet_main_tab = config.G_SPREADSHEET_MAIN_TAB
        self._pornolab_tab = config.G_SPREADSHEET_PORNOLAB_TAB

    async def update_export_data_to_gsheet(
        self,
        gsheet_read_range: str = "A2:A",
        latest_exported_video_mongo_id: str | None = None,
        gsheet_write_start_row: int = 0,
    ):
        data_to_export = []
        mongo_videos_ = await Video.find_all(fetch_links=True).to_list()
        if not (latest_exported_video_mongo_id and gsheet_write_start_row):
            latest_exported_video_mongo_id, gsheet_write_start_row = (
                self._get_latest_exported_video_and_write_start_row(
                    self._gsheet_id, self._gsheet_main_tab, gsheet_read_range
                )
            )
        if gsheet_write_start_row != 0:
            mongo_videos = [video for video in mongo_videos_ if str(video.id) > latest_exported_video_mongo_id]
            for video in mongo_videos:
                data_to_export.append(
                    [
                        str(video.id),  # Mongo ID
                        video.jav_code,
                        video.page_link.unicode_string(),
                        video.thumbnail_url.unicode_string() if video.thumbnail_url else "",
                        "",  # thumbnail enhanced URL
                        video.title,
                        video.rewritten_title,  # video title rewritten
                        ", ".join([actress.name for actress in video.actresses]),
                        ", ".join([actor.name for actor in video.actors]),
                        ", ".join([category.name for category in video.categories]),
                        ", ".join([tag.name for tag in video.tags]),
                        video.studio.name if video.studio else "",
                        video.release_date.strftime("%d-%m-%Y") if video.release_date else "",
                        ", ".join([director.name for director in video.directors]),
                        video.type_javtiful,
                    ]
                )
            self._gsheets_api.write_to_sheet(
                data_to_export, self._gsheet_main_tab, f"A{gsheet_write_start_row}", self._gsheet_id
            )

    async def update_rewritten_titles(self, gsheet_id: str | None = None):
        sheet_id = gsheet_id or self._gsheet_id
        exported_videos = self._gsheets_api.read_sheet(self._gsheet_main_tab, "A2:A", sheet_id)
        if not exported_videos:
            logger.info("No exported videos found in sheet")
            return

        updates = []
        for idx, row in enumerate(exported_videos, start=2):
            mongo_id = row[0]
            video = await Video.get(mongo_id)
            if video and video.rewritten_title:
                updates.append([video.rewritten_title])
            else:
                updates.append([""])
        if updates:
            self._gsheets_api.write_to_sheet(updates, self._gsheet_main_tab, "G2", sheet_id)
            logger.info(f"Updated rewritten titles for {len(updates)} rows")

    async def update_s3_paths_and_resolutions(self, read_range: str = "A2:T", write_start_cell: str = "P2"):
        await self._fetch_pornolab_data_and_save_in_mongo()
        data_to_export = []
        mongo_data = await Video.find().to_list()
        exported_data = self._gsheets_api.read_sheet(self._gsheet_main_tab, read_range, self._gsheet_id)
        exported_dict = {row[0]: row for row in exported_data}
        combined_data = [(video, exported_dict.get(str(video.id), [])) for video in mongo_data]
        for pair in combined_data:
            row_to_export = self._fetch_row_to_export(pair)
            data_to_export.append(row_to_export)
        self._gsheets_api.write_to_sheet(data_to_export, self._gsheet_main_tab, write_start_cell, self._gsheet_id)

    def _get_latest_exported_video_and_write_start_row(
        self,
        gsheet_id: str,
        gsheet_tab: str,
        gsheet_read_range: str,
    ) -> tuple[str, int]:
        exported_videos = self._gsheets_api.read_sheet(gsheet_tab, gsheet_read_range, gsheet_id)
        if not exported_videos:
            return "", 2
        try:
            last_exported_video = exported_videos[-1]
            last_exported_mongo_id = last_exported_video[0]
            write_start_row_num = len(exported_videos) + 2  # Because the first row with data is the row #2.
            return last_exported_mongo_id, write_start_row_num
        except IndexError:
            logger.error("[!] ERROR! Failed to get latest exported video ID due to IndexError!")
            return "", 0

    async def _fetch_pornolab_data_and_save_in_mongo(self, read_range: str = "B2:N") -> None:
        pl_excel_data = self._gsheets_api.read_sheet(self._pornolab_tab, read_range, self._gsheet_id)
        for row in pl_excel_data:
            try:
                if row[7] != "✓":
                    continue
            except IndexError:
                continue
            while len(row) < 13:
                row.append("")
            jav_code = row[0]
            video = await Video.find_one(Video.jav_code == jav_code)
            if not video:
                continue
            exists = "pornolab" in [source.origin for source in video.sources]
            if exists:
                continue
            s3_path = row[8]
            resolution = row[9]
            runtime = row[10]
            file_hash = row[11]
            video.sources.append(
                VideoSource(
                    origin="pornolab",
                    resolution=resolution,
                    s3_path=s3_path,
                    hash_md5=file_hash,
                )
            )
            video.runtime_minutes = runtime
            video.javguru_status = "downloaded"
            await video.save()
            row[-1] = "✓"
        self._gsheets_api.write_to_sheet(pl_excel_data, self._pornolab_tab, "B2", self._gsheet_id)

    @staticmethod
    def _fetch_row_to_export(mongo_and_excel_combined_data: tuple[Video, list]) -> list:
        excel_row = mongo_and_excel_combined_data[1]
        while len(excel_row) < 20:
            excel_row.append("")
        if not excel_row[16] or not excel_row[18]:
            mongo_video = mongo_and_excel_combined_data[0]
            runtime = mongo_video.runtime_minutes
            jav_s3_path, jav_resolution = next(
                ((source.s3_path, source.resolution) for source in mongo_video.sources if source.origin == "guru"),
                ("", ""),
            )
            pornolab_s3_path, pornolab_resolution = next(
                ((source.s3_path, source.resolution) for source in mongo_video.sources if source.origin == "pornolab"),
                ("", ""),
            )
            return [runtime, jav_s3_path, jav_resolution, pornolab_s3_path, pornolab_resolution]
        return [excel_row[i] for i in range(15, 20)]


class PromptService:
    def __init__(self, gsheet_api=gsheets):
        self._gsheets_api = gsheet_api
        self._sheet_id = config.G_SPREADSHEET_ID
        self._tab_name = config.G_SPREADSHEET_TAB_PROMPT

    def get_prompt(self, cell: str = "B1") -> str:
        values = self._gsheets_api.read_sheet(self._tab_name, cell, self._sheet_id)
        if values and values[0] and values[0][0]:
            logger.info(str(values[0][0]))
            return str(values[0][0])
        return config.PROMPT_DEFAULT


if __name__ == "__main__":
    import asyncio

    async def main():
        await init_mongo()
        gsh_svc = GSheetService()
        # await gsh_svc.update_export_data_to_gsheet()
        # await gsh_svc.update_rewritten_titles()
        await gsh_svc.update_s3_paths_and_resolutions()

    asyncio.run(main())
