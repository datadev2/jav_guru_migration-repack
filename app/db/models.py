from datetime import datetime
from beanie import Document
from pydantic import Field, HttpUrl


class Video(Document):
    title: str
    video_code: str
    page_link: HttpUrl
    site_download_link: HttpUrl | None = Field(default=None)
    s3_path: str | None = Field(default=None)
    format: str | None = Field(default=None)
    file_size: int | None = Field(default=None)
    file_hash_md5: str | None = Field(default=None)
    file_name: str | None = Field(default=None)
    width: int | None = Field(default=None)
    height: int | None = Field(default=None)

    thumbnail_url: HttpUrl | None = Field(default=None)

    categories: list[str] | None = Field(default=None)
    tags: list[str] | None = Field(default=None)

    actresses: list[str] | None = Field(default=None)
    actors: list[str] | None = Field(default=None)

    studio: str | None = Field(default=None)
    director: str | None = Field(default=None)
    release_date: datetime | None = Field(default=None)
    video_type: str | None = Field(default=None)   # censored / uncensored
    runtime_minutes: int | None = Field(default=None)

    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "videos"


class Category(Document):
    name: str
    source_url: HttpUrl | None = None
    is_parsed: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "categories"


Collections = [Video, Category]