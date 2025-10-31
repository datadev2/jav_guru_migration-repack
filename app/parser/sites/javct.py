import asyncio
import random
from typing import Optional

from curl_cffi.requests import AsyncSession
from loguru import logger
from selectolax.lexbor import LexborHTMLParser as HTMLTree

from app.config import config
from app.db.models import Category, Tag, Video


class JavctAdapter:
    site_name = "javct"
    BASE_URL = "https://javct.net"
    CATEGORIES_URL = "https://javct.net/categories"

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
                logger.warning(f"[Javct] Cloudflare block on {url}")
                await asyncio.sleep(random.uniform(15, 35))
                return None
            return HTMLTree(resp.content)
        except Exception as e:
            logger.error(f"[Javct] Request failed for {url}: {e}")
            await asyncio.sleep(random.uniform(5, 10))
            return None

    async def parse_tags(self) -> list[Tag]:
        logger.info("[Javct] No tags implemented yet")
        return []

    async def parse_categories(self) -> list[Category]:
        tree = await self._request(self.CATEGORIES_URL)
        if not tree:
            logger.error("[Javct] ✗ Failed to load categories page")
            return []

        categories = {}

        anchors = tree.css("a.card__category, ul.card__meta li a[href*='/category/']")
        for a in anchors:
            name = a.text(strip=True) or a.attributes.get("title")
            href = a.attributes.get("href")
            if not name or not href:
                continue
            if name not in categories:
                categories[name] = Category(name=name, source_url=href, site=self.site_name)
                logger.debug(f"[Javct] Found category: {name}")

        logger.success(f"[Javct] ✓ Parsed {len(categories)} categories total")
        return list(categories.values())

    async def enrich_video(
        self,
        video: Video,
        all_categories: list[Category],
        all_tags: list[Tag],
    ) -> Video | None:
        search_url = f"{self.BASE_URL}/v/{video.jav_code.lower()}"
        tree = await self._request(search_url)
        if not tree:
            logger.warning(f"[Javct] ✗ Failed to load page for {video.jav_code}")
            return None

        # 404 check
        if tree.css_first("h1") and "404" in tree.css_first("h1").text():
            logger.info(f"[Javct] Page {search_url} not found (404)")
            video.javct_enriched = True
            return video

        categories_found = []
        for li in tree.css("ul.card__meta li"):
            span = li.css_first("span")
            if not span:
                continue
            if span.text(strip=True).lower().startswith("categories"):
                for a in li.css("a[href*='/category/']"):
                    name = a.text(strip=True) or a.attributes.get("title")
                    if name:
                        categories_found.append(name.strip())
                break

        category_map = {c.name: c for c in all_categories}
        for cat_name in categories_found:
            cat_obj = category_map.get(cat_name)
            if cat_obj:
                video.categories.append(cat_obj)
            else:
                logger.debug(f"[Javct] Category '{cat_name}' not found in DB")

        video.javct_enriched = True
        logger.success(f"[Javct] ✓ Enriched {video.jav_code} with {len(categories_found)} categories")
        return
