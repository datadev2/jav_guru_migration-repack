from typing import List, Optional
from datetime import datetime
from beanie import Document
from pydantic import Field, HttpUrl


class Video(Document):
    name: str
    page_link: HttpUrl
    site_download_link: Optional[HttpUrl] = Field(default=None)
    s3_path: Optional[str] = Field(default=None)
    format: Optional[str] = Field(default=None)
    file_size: Optional[int] = Field(default=None)
    file_hash_md5: Optional[str] = Field(default=None)
    file_name: Optional[str] = Field(default=None)
    width: Optional[int] = Field(default=None)
    height: Optional[int] = Field(default=None)
    tags: List[str] = Field(default_factory=list)
    category: List[str] = Field(default_factory=list)
    description: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    class Settings:
        name = "videos"


class Category(Document):
    name: str
    category_url: HttpUrl
    is_parsed: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "categories"


Collections = [Video, Category]