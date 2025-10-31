import asyncio
import random
from typing import Optional

from curl_cffi.requests import AsyncSession
from loguru import logger
from selectolax.lexbor import LexborHTMLParser as HTMLTree

from app.config import config
from app.db.models import Category, Tag, Video


class JavtifulAdapter:
    site_name = "javtiful"
    BASE_URL = "https://javtiful.com"
    CATEGORIES_URL = "https://javtiful.com/categories"

    def __init__(self):
        self.proxy_pool = config.PROXY_POOL  # list[str] socks5://user:pass@ip:port
        self.impersonate_pool = ["chrome124", "chrome120"]
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/129.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-CH-UA": '"Chromium";v="129", "Not=A?Brand";v="8"',
            "Sec-CH-UA-Platform": '"Windows"',
        }

    async def __aenter__(self):
        self.session = AsyncSession(
            impersonate=random.choice(self.impersonate_pool),
            headers=self.headers,
            timeout=20,
        )
        return self

    async def __aexit__(self, *args):
        await self.session.close()

    async def _request(self, url: str) -> Optional[HTMLTree]:
        proxy = random.choice(self.proxy_pool)
        try:
            resp = await self.session.get(url, proxy=proxy)
            if resp.status_code == 403 or "cf-chl" in resp.text:
                logger.warning(f"[Javtiful] Cloudflare block on {url}")
                await asyncio.sleep(random.uniform(15, 35))
                return None
            return HTMLTree(resp.content)
        except Exception as e:
            logger.error(f"[Javtiful] Request failed for {url}: {e}")
            await asyncio.sleep(random.uniform(5, 10))
            return None

    async def parse_categories(self) -> list[Category]:
        tree = await self._request(self.CATEGORIES_URL)
        if not tree:
            logger.error("[Javtiful] ✗ Failed to load categories page")
            return []

        categories = {}
        for a in tree.css("a.category-tmb span.label-category"):
            name = a.text(strip=True)
            href_el = a.parent
            href = href_el.attributes.get("href") if href_el else None
            if not name or not href:
                continue
            if name not in categories:
                categories[name] = Category(name=name, source_url=href, site=self.site_name)
                logger.debug(f"[Javtiful] Found category: {name}")

        logger.success(f"[Javtiful] ✓ Parsed {len(categories)} categories total")
        return list(categories.values())

    async def enrich_video(
        self,
        video: Video,
        all_categories: list[Category],
        all_tags: list[Tag],
    ) -> Video | None:
        search_url = f"{self.BASE_URL}/search/videos?search_query={video.jav_code.lower()}"
        logger.info(f"[Javtiful] → Searching for {video.jav_code}")
        tree = await self._request(search_url)
        if not tree:
            logger.warning(f"[Javtiful] ✗ Failed to load search page for {video.jav_code}")
            return None

        card = tree.css_first("a[href*='/video/']")
        if not card:
            logger.info(f"[Javtiful] Video {video.jav_code} not found on search")
            video.javtiful_enriched = True
            return video

        video_url = card.attributes.get("href")
        if not video_url.startswith("http"):
            video_url = self.BASE_URL + video_url
        logger.debug(f"[Javtiful] → Opening video page {video_url}")

        tree = await self._request(video_url)
        if not tree:
            logger.warning(f"[Javtiful] ✗ Failed to load video page {video_url}")
            return None

        categories_found, tags_found, actresses_found = [], [], []
        video_type_found = None

        for item in tree.css("div.video-details__item"):
            label = item.css_first("div.video-details__label")
            if not label:
                continue
            label_text = label.text(strip=True).lower()

            if label_text.startswith("tags"):
                tags_found = [
                    a.text(strip=True) for a in item.css("div.video-details__item_links a") if a.text(strip=True)
                ]
            elif label_text.startswith("category"):
                categories_found = [
                    a.text(strip=True) for a in item.css("div.video-details__item_links a") if a.text(strip=True)
                ]
            elif label_text.startswith("actress"):
                actresses_found = [
                    a.text(strip=True) for a in item.css("div.video-details__item_links span") if a.text(strip=True)
                ]
            elif label_text.startswith("type"):
                type_a = item.css_first("div.video-details__item_links a")
                if type_a:
                    video_type_found = type_a.text(strip=True)

        video.categories = categories_found
        video.tags = tags_found
        video.actresses = actresses_found
        video.type_javtiful = video_type_found

        video.javtiful_enriched = True
        logger.success(
            f"[Javtiful] ✓ Parsed {video.jav_code}: {len(categories_found)} categories, "
            f"{len(tags_found)} tags, {len(actresses_found)} actresses, type={video_type_found}"
        )
        return video
