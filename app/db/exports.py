from pydantic import BaseModel, HttpUrl


class VideoCSV(BaseModel):
    name: str
    category: list[str] | str
    tags: list[str] | str
    file_hash: str
    server_download_link: HttpUrl
