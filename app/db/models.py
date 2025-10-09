from datetime import datetime
from typing import Literal

from beanie import Document, Link
from pydantic import BaseModel, Field, HttpUrl, model_validator


class Studio(Document):
    name: str
    source_url: HttpUrl | None = None
    site: str = Field(default="unknown")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "studios"


class Model(Document):
    name: str
    type: Literal["actress", "actor", "director"] = Field(default="actress")
    profile_url: HttpUrl | None = None
    image_url: HttpUrl | None = None
    site: str = Field(default="unknown")
    birth_date: datetime | None = None
    height_cm: int | None = None
    bust: int | None = None
    waist: int | None = None
    hips: int | None = None
    cup_size: str | None = None
    debut_date: datetime | None = None
    agency: str | None = None

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


class VideoSource(BaseModel):
    origin: str
    resolution: str
    s3_path: str
    file_name: str = ""
    file_size: int = 0
    hash_md5: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Video(Document):
    title: str
    rewritten_title: str | None = None
    jav_code: str
    page_link: HttpUrl
    site: str = Field(default="unknown")

    thumbnail_url: HttpUrl | None = None
    thumbnail_s3_url: HttpUrl | None = None

    categories: list[Link[Category]] = Field(default_factory=list)
    tags: list[Link[Tag]] = Field(default_factory=list)

    actresses: list[Link[Model]] = Field(default_factory=list)
    actors: list[Link[Model]] = Field(default_factory=list)
    directors: list[Link[Model]] = Field(default_factory=list)

    studio: Link[Studio] | None = None
    release_date: datetime | None = None
    uncensored: bool | None = None
    runtime_minutes: int | None = None
    type_javtiful: str | None = None

    sources: list[VideoSource] = Field(default_factory=list)

    javct_enriched: bool = False
    javtiful_enriched: bool = False

    javguru_status: Literal["added", "parsed", "downloading", "downloaded", "failed", "imported", "deleted"]
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


class VideoCSV(BaseModel):
    jav_code: str
    title: str
    release_date: datetime
    file_hash: str
    models: list
    categories: list
    tags: list
    s3_path: str
    poster_url: str
    studio: str

    @model_validator(mode="after")
    def validator(self):
        self.release_date = self.release_date.strftime("%d-%m-%Y")  # type: ignore
        self.models = ", ".join(self.models)
        self.categories = ", ".join(self.categories)
        self.tags = ", ".join(self.tags)
        return self


Collections = [Video, Model, Studio, Category, Tag]
