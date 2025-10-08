# noqa

from app.infra.worker import (download_fresh_videos_from_guru_task_caller, enrich_videos_with_data_task_caller,
                              export_video_data_to_gsheet_task_caller, generate_new_titles_task_caller,
                              parse_jav_guru_task_caller, save_video_thumbnails_task_caller,
                              update_s3_paths_and_resolutions_task_caller)

if __name__ == "__main__":
    # download_fresh_videos_from_guru_task_caller(limit=94)
    # parse_jav_guru_task_caller(start_page=0, end_page=0, headless=True)
    # enrich_videos_with_data_task_caller()
    # generate_new_titles_task_caller()
    # save_video_thumbnails_task_caller()
    # export_video_data_to_gsheet_task_caller()
    # update_s3_paths_and_resolutions_task_caller()
    pass
