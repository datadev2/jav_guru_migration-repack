from datetime import datetime
from beanie import Document, Link
from pydantic import Field, BaseModel, HttpUrl


class Studio(Document):
    name: str
    source_url: HttpUrl | None = None
    site: str = Field(default="unknown")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "studios"


class Model(Document):
    name: str
    type: str = Field(default="actress")
    profile_url: HttpUrl | None = None
    image_url: HttpUrl | None = None
    site: str = Field(default="unknown")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "models"


class Category(Document):
    name: str
    source_url: HttpUrl | None = None
    site: str = Field(default="unknown")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "categories"


class Tag(Document):
    name: str
    source_url: HttpUrl | None = None
    site: str = Field(default="unknown")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "tags"


class Video(Document):
    title: str
    jav_code: str
    page_link: HttpUrl
    site: str = Field(default="unknown")

    site_download_link_st: HttpUrl | None = None
    site_download_link_720p: HttpUrl | None = None
    site_download_link_1080p: HttpUrl | None = None
    site_download_link_2k: HttpUrl | None = None
    site_download_link_4k: HttpUrl | None = None
    
    s3_path: str | None = None
    format: str | None = None
    file_size: int | None = None
    file_hash_md5: str | None = None
    file_name: str | None = None
    width: int | None = None
    height: int | None = None

    thumbnail_url: HttpUrl | None = None

    categories: list[Link[Category]] = Field(default_factory=list)
    tags: list[Link[Tag]] = Field(default_factory=list)

    actresses: list[Link[Model]] = Field(default_factory=list)
    actors: list[Link[Model]] = Field(default_factory=list)
    directors: list[Link[Model]] = Field(default_factory=list)

    studio: Link[Studio] | None = None
    release_date: datetime | None = None
    uncensored: bool = Field(default=False)
    runtime_minutes: int | None = None

    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "videos"

# ---------- Scraper Schemas ----------
class ParsedVideo(BaseModel):
    title: str
    jav_code: str
    page_link: HttpUrl
    site: str

    thumbnail_url: HttpUrl | None = None
    release_date: str | None = None
    categories: list[str] = []
    tags: list[str] = []
    directors: list[str] = []
    actresses: list[str] = []
    studio: str | None = None
    uncensored: bool = False

Collections = [Video, Model, Studio, Category, Tag]