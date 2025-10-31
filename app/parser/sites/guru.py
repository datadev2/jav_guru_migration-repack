import asyncio
import random
from typing import AsyncGenerator, List, Optional

from curl_cffi.requests import AsyncSession
from dateutil import parser as dateparser
from loguru import logger
from selectolax.lexbor import LexborHTMLParser as HTMLTree

from app.config import config
from app.db.models import Category, Model, ParsedVideo, Studio, Tag


class GuruAdapter:
    site_name = "guru"
    BASE_URL = "https://jav.guru/"
    STUDIO_URL = "https://jav.guru/jav-makers-list/"
    TAG_URL = "https://jav.guru/jav-tags-list/"
    CATEGORY_URL = "https://jav.guru/?s="

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
        self.session = AsyncSession(impersonate=random.choice(self.impersonate_pool), headers=self.headers, timeout=20)
        return self

    async def __aexit__(self, *args):
        await self.session.close()

    async def _request(self, url: str) -> Optional[HTMLTree]:
        url = str(url)
        proxy = random.choice(self.proxy_pool)
        try:
            resp = await self.session.get(url, proxy=proxy)
            if resp.status_code == 403 or "cf-chl" in resp.text:
                logger.warning(f"CF block: {url}")
                await asyncio.sleep(random.uniform(15, 35))
                return None
            return HTMLTree(resp.content)
        except Exception as e:
            logger.error(f"Request failed {url}: {e}")
            await asyncio.sleep(random.uniform(10, 20))
            return None

    async def fetch_page_links(self, start_page: Optional[int] = None) -> AsyncGenerator[str, None]:
        if start_page is None:
            tree = await self._request(self.BASE_URL)
            if tree:
                last = tree.css_first("a.last")
                if last:
                    start_page = int(last.attributes.get("href", "").strip("/").split("/")[-1])
                else:
                    start_page = 1
            else:
                start_page = 1

        page = start_page
        while True:
            url = self.BASE_URL if page == 1 else f"{self.BASE_URL}page/{page}/"
            tree = await self._request(url)
            if not tree:
                break

            cards = tree.css("div.inside-article")
            if not cards:
                break

            for card in reversed(cards):
                a = card.css_first("div.grid1 h2 a")
                if a and (href := a.attributes.get("href")):
                    yield href

            logger.success(f"Page {page}: {len(cards)} links")
            page -= 1
            await asyncio.sleep(random.uniform(3, 8))

    async def parse_videos(
        self,
        start_page: int | None = None,
        end_page: int | None = None,
    ) -> list[ParsedVideo]:
        videos: list[ParsedVideo] = []

        # --- определить стартовую страницу ---
        if start_page is None:
            tree = await self._request(self.BASE_URL)
            if not tree:
                logger.error("[guru] ✗ Failed to load main page for pagination")
                return []
            last_link = tree.css_first("a.last")
            if last_link:
                try:
                    start_page = int(last_link.attributes.get("href", "").rstrip("/").split("/")[-1])
                except Exception:
                    start_page = 1
            else:
                start_page = 1
        if end_page is None:
            end_page = 1

        logger.info(f"[guru] → Starting crawl from page {start_page} down to {end_page}")

        # --- обход страниц ---
        for page in range(start_page, end_page - 1, -1):
            url = self.BASE_URL if page == 1 else f"{self.BASE_URL}page/{page}/"
            logger.info(f"[guru] → Fetching list page: {url}")

            tree = await self._request(url)
            if not tree:
                logger.warning(f"[guru] ✗ Failed to load page {page}, stopping crawl")
                break

            cards = tree.css("div.inside-article")
            if not cards:
                logger.info(f"[guru] ⚙ Page {page} empty, stopping crawl")
                break

            logger.debug(f"[guru] ✓ Found {len(cards)} video cards on page {page}")

            for idx, card in enumerate(reversed(cards), start=1):
                try:
                    a = card.css_first("div.grid1 h2 a")
                    if not a:
                        continue

                    href = a.attributes.get("href")
                    title = a.attributes.get("title") or a.text(strip=True)

                    if not href:
                        logger.debug(f"[guru] Skipping card {idx}: missing href")
                        continue

                    video = ParsedVideo(
                        title=title.strip() if title else "N/A",
                        jav_code="",
                        page_link=href,
                        site=self.site_name,
                    )
                    videos.append(video)

                    logger.debug(f"[guru] [{page}:{idx}] Collected → {title[:60]}")

                except Exception as e:
                    logger.warning(f"[guru] ⚠ Failed to parse card {idx} on page {page}: {e}")

            await asyncio.sleep(random.uniform(3, 8))

        logger.success(f"[guru] ✓ Collected {len(videos)} videos total")
        return videos

    async def parse_video(self, video: ParsedVideo) -> Optional[ParsedVideo]:
        url = str(video.page_link)
        logger.info(f"[guru] → Fetching page: {url}")

        tree = await self._request(url)
        if not tree:
            logger.error(f"[guru] ✗ Failed to load DOM for {url}")
            return None
        logger.debug(f"[guru] ✓ DOM fetched, start parsing: {url}")

        try:
            # --- title ---
            if h1 := tree.css_first("h1.titl"):
                video.title = h1.text(strip=True)
                logger.debug(f"[guru] Title parsed: {video.title}")

            # --- thumbnail ---
            if img := tree.css_first("div.large-screenimg img"):
                video.thumbnail_url = img.attributes.get("src")
                logger.debug("[guru] Thumbnail found")

            # --- code ---
            video.jav_code = None
            for li in tree.css("li"):
                text = li.text(strip=True)
                if text.lower().startswith("code:"):
                    code = text.replace("Code:", "").strip()
                    if code:
                        video.jav_code = code
                        logger.debug(f"[guru] Code parsed: {video.jav_code}")
                        break

            # --- release date ---
            for li in tree.css("li"):
                text = li.text(strip=True)
                if text.lower().startswith("release date:"):
                    raw = text.replace("Release Date:", "").strip()
                    try:
                        video.release_date = dateparser.parse(raw)
                        logger.debug(f"[guru] Release date parsed: {video.release_date}")
                    except Exception as e:
                        logger.warning(f"[guru] Failed to parse release date '{raw}': {e}")
                    break

            # --- categories ---
            cats = []
            for li in tree.css("li"):
                if "Category:" in li.text():
                    for a in li.css("a"):
                        name = a.text(strip=True)
                        if name:
                            cats.append(name)
            video.categories = cats
            logger.debug(f"[guru] Categories: {cats}")

            # --- directors ---
            dirs = []
            for li in tree.css("li"):
                if "Director:" in li.text():
                    for a in li.css("a"):
                        name = a.text(strip=True)
                        if name:
                            dirs.append(name)
            video.directors = dirs
            logger.debug(f"[guru] Directors: {dirs}")

            # --- studio ---
            for li in tree.css("li"):
                if "Studio:" in li.text():
                    a = li.css_first("a")
                    if a:
                        video.studio = a.text(strip=True)
                        logger.debug(f"[guru] Studio: {video.studio}")
                    break

            # --- tags ---
            tags = [a.text(strip=True) for a in tree.css("li.w1 a[rel='tag']") if a.text(strip=True)]
            video.tags = tags
            logger.debug(f"[guru] Tags: {tags}")

            # --- actors ---
            acts_male = []
            for li in tree.css("li"):
                if "Actor:" in li.text():
                    for a in li.css("a"):
                        name = a.text(strip=True)
                        if name:
                            acts_male.append(name)
            video.actors = acts_male
            logger.debug(f"[guru] Actors: {acts_male}")

            # --- actresses ---
            acts_female = []
            for li in tree.css("li"):
                if "Actress:" in li.text():
                    for a in li.css("a"):
                        name = a.text(strip=True)
                        if name:
                            acts_female.append(name)
            video.actresses = acts_female
            logger.debug(f"[guru] Actresses: {acts_female}")

            # --- uncensored ---
            video.uncensored = any(
                ("uncensored" in (a.attributes.get("href") or "").lower())
                or ("uncensored" in a.text(strip=True).lower())
                for li in tree.css("li")
                if "Category:" in li.text()
                for a in li.css("a")
            )
            logger.debug(f"[guru] Uncensored: {video.uncensored}")

            # --- валидация ---
            if not video.jav_code:
                logger.warning(f"[guru] ✗ Missing jav_code for {url}")
                return None

            logger.success(f"[guru] ✓ Parsed {video.jav_code} | {video.title or 'No title'}")
            return video

        except Exception as e:
            logger.error(f"[guru] ✗ Unexpected parsing error at {url}: {e}", exc_info=True)
            return None

    # --- Метаданные ---
    async def parse_studios(self) -> List[Studio]:
        tree = await self._request(self.STUDIO_URL)
        if not tree:
            return []
        studios = {}
        for a in tree.css("main ul li a"):
            name = a.text().strip()
            href = a.attributes.get("href")
            if name and name not in studios:
                studios[name] = Studio(name=name, source_url=href, site=self.site_name)
        return list(studios.values())

    async def parse_tags(self) -> List[Tag]:
        tree = await self._request(self.TAG_URL)
        if not tree:
            return []
        tags = {}
        for a in tree.css("div#content li a[rel='tag']"):
            name = a.text().strip().split("(")[0].strip()
            href = a.attributes.get("href")
            if name and name not in tags:
                tags[name] = Tag(name=name, source_url=href, site=self.site_name)
        return list(tags.values())

    async def parse_categories(self) -> List[Category]:
        tree = await self._request(self.CATEGORY_URL)
        if not tree:
            return []
        categories = []
        for div in tree.css("div.dropdown-menu > div"):
            name = div.text().strip()
            data_value = div.attributes.get("data-value")
            if not name or data_value == "all":
                continue
            source_url = f"{self.BASE_URL}?s=&category_name={data_value}"
            categories.append(Category(name=name, source_url=source_url, site=self.site_name))
        return categories

    async def _parse_people(self, base_path: str, type_: str) -> List[Model]:
        people = {}
        page = 1
        while True:
            url = f"{self.BASE_URL}{base_path}/page/{page}/"
            tree = await self._request(url)
            if not tree:
                break
            cards = tree.css("div.actress-box > a")
            if not cards:
                break
            for card in cards:
                href = card.attributes.get("href")
                name_el = card.css_first("span.actrees-name")
                img = card.css_first("img")
                name = name_el.text().strip() if name_el else None
                if name and name not in people:
                    people[name] = Model(
                        name=name,
                        type=type_,
                        profile_url=href,
                        image_url=img.attributes.get("src") if img else None,
                        site=self.site_name,
                    )
            page += 1
            await asyncio.sleep(random.uniform(2, 5))
        return list(people.values())

    async def parse_actress(self) -> List[Model]:
        return await self._parse_people("jav-actress-list", "actress")

    async def parse_actors(self) -> List[Model]:
        return await self._parse_people("jav-actors", "actor")

    async def parse_directors(self) -> List[Model]:
        return await self._parse_people("jav-directors-list", "director")

    # --- Sync wrappers ---
    def parse_studios_sync(self) -> List[Studio]:
        return asyncio.run(self.parse_studios())

    def parse_tags_sync(self) -> List[Tag]:
        return asyncio.run(self.parse_tags())

    def parse_categories_sync(self) -> List[Category]:
        return asyncio.run(self.parse_categories())

    def parse_actress_sync(self) -> List[Model]:
        return asyncio.run(self.parse_actress())

    def parse_actors_sync(self) -> List[Model]:
        return asyncio.run(self.parse_actors())

    def parse_directors_sync(self) -> List[Model]:
        return asyncio.run(self.parse_directors())
