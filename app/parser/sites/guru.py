import time
import re
from selenium.webdriver.common.by import By
from dateutil import parser as dateparser

from app.db.models import Category, Studio, ParsedVideo, Tag, Model
from app.parser.interactions import SeleniumService
from loguru import logger


class GuruAdapter:
    site_name = "guru"
    BASE_URL = "https://jav.guru/"
    STUDIO_URL = "https://jav.guru/jav-makers-list/"
    TAG_URL = "https://jav.guru/jav-tags-list/"
    CATEGORY_URL = "https://jav.guru/?s="

    def _open_video_tab(self, selenium: SeleniumService, url: str) -> None:
        selenium.driver.execute_script(f"window.open('{url}', '_blank');")
        selenium.driver.switch_to.window(selenium.driver.window_handles[-1])

    def _close_video_tab(self, selenium: SeleniumService, main_window: str) -> None:
        selenium.driver.close()
        selenium.driver.switch_to.window(main_window)

    def _get_last_page(self, selenium: SeleniumService) -> int:
        try:
            el = selenium.find_first("//a[@class='last']")
            if el:
                href = el.get_attribute("href")
                return int(href.strip("/").split("/")[-1])
            # fallback
            el = selenium.find_first("//span[@class='pages']")
            if el:
                m = re.search(r"of\s+([\d,]+)", el.text)
                if m:
                    return int(m.group(1).replace(",", ""))
        except Exception as e:
            logger.error(f"[GuruAdapter] Failed to get last page: {e}")
        return 1

    def _extract_video_src(self, selenium: SeleniumService, timeout_sec: int = 15) -> str | None:
        try:
            # --- Step 1: STREAM ST ---
            btns = selenium.find_elements("//a[contains(text(),'STREAM ST')]")
            if not btns:
                logger.error("[GuruAdapter] STREAM ST кнопка не найдена")
                return None

            btn = next((b for b in btns if b.is_displayed()), None)
            if not btn:
                logger.error("[GuruAdapter] STREAM ST кнопка невидима")
                return None

            selenium.driver.execute_script("arguments[0].click();", btn)
    
            # --- Step 2: first iframe ---
            first_iframe = selenium.wait_for_element((By.CSS_SELECTOR, "iframe[src*='jav.guru/searcho/']"), timeout=30)

            if not first_iframe:
                logger.error("[GuruAdapter] Первый iframe не найден")
                return None

            selenium.driver.switch_to.frame(first_iframe)

            play_btn = selenium.wait_for_element((By.XPATH, "//*[contains(@class,'playbutton')]"), timeout=30)
            selenium.driver.execute_script("arguments[0].click();", play_btn)

            # --- Step 3: second iframe ---
            second_iframe = selenium.wait_for_element(
                (By.XPATH, "//iframe[not(contains(@src, '.jpg'))]"),
                timeout=60
            )
            selenium.driver.switch_to.frame(second_iframe)

            streamtape_url = selenium.driver.execute_script("return document.location.href;")
            selenium.get(streamtape_url)

            # --- Step 4: overlay+play = src ---
            deadline = time.time() + 180
            src = None
            attempt = 0
            while time.time() < deadline:
                attempt += 1

                extract_src_js = """
                    document.querySelector(".play-overlay")?.click();
                    setTimeout(() => {
                        document.querySelector("[data-plyr='play']")?.click();
                    }, 500);
                    return document.querySelector('#mainvideo')?.getAttribute('src');
                """
                candidate = selenium.driver.execute_script(extract_src_js)

                if candidate:
                    src = candidate
                    break

            if not src:
                logger.error("[GuruAdapter] src так и не появился")
                return None

            if src.startswith("//"):
                src = "https:" + src
                logger.info(f"Source link extracted: {src}")
            return src

        except Exception as e:
            logger.error(f"[GuruAdapter] _extract_video_src failed: {e}", exc_info=True)
            return None
        finally:
            try:
                selenium.driver.switch_to.default_content()
            except Exception:
                pass
   
    def parse_studios(self, selenium: SeleniumService) -> list[Studio]:
        selenium.get(self.STUDIO_URL, (By.XPATH, "//main[@id='main']//ul/li"))

        studios: dict[str, Studio] = {}
        els = selenium.find_elements("//main[@id='main']//ul/li/a")
        for el in els:
            try:
                name = el.text.strip()
                href = el.get_attribute("href")
                if name and name not in studios:
                    studios[name] = Studio(name=name, source_url=href, site=self.site_name)
                    logger.info(f"[GuruAdapter] Found studio: {name}")
            except Exception as e:
                logger.warning(f"[GuruAdapter] Failed to parse studio element: {e}")

        return list(studios.values())
    
    def parse_tags(self, selenium: SeleniumService) -> list[Tag]:
        selenium.get(self.TAG_URL, (By.XPATH, "//div[@id='content']//li/a[@rel='tag']"))

        tags: dict[str, Tag] = {}
        els = selenium.find_elements("//div[@id='content']//li/a[@rel='tag']")
        for el in els:
            try:
                name = el.text.strip()
                href = el.get_attribute("href")
                if "(" in name:
                    name = name.split("(")[0].strip()
                if name and name not in tags:
                    tags[name] = Tag(name=name, source_url=href, site=self.site_name)
                    logger.info(f"[GuruAdapter] Found tag: {name}")
            except Exception as e:
                logger.warning(f"[GuruAdapter] Failed to parse tag element: {e}")

        return list(tags.values())
    
    def parse_categories(self, selenium: SeleniumService) -> list[Category]:
        selenium.get(self.CATEGORY_URL, (By.XPATH, "//div[@class='dropdown-menu']/div"))

        els = selenium.find_elements("//div[@class='dropdown-menu']/div")
        logger.debug(els)
        categories: list[Category] = []

        for el in els:
            try:
                name = el.get_attribute("textContent").strip()

                data_value = el.get_attribute("data-value")
                if not name or data_value == "all":
                    continue
                source_url = f"{self.BASE_URL}?s=&category_name={data_value}"
                categories.append(Category(name=name, source_url=source_url, site=self.site_name))
                logger.info(f"[GuruAdapter] Found category: {name} ({source_url})")
            except Exception as e:
                logger.warning(f"[GuruAdapter] Failed to parse category element: {e}")

        return categories

    def parse_people(self, selenium: SeleniumService, base_path: str, type_: str) -> list[Model]:
        people: dict[str, Model] = {}
        page = 1

        while True:
            url = f"{self.BASE_URL}{base_path}/page/{page}/"
            logger.info(f"[GuruAdapter] Open {type_} page {page}: {url}")
            selenium.get(url, (By.XPATH, "//div[@class='actress-box']"))

            cards = selenium.find_elements("//div[@class='actress-box']/a")
            if not cards:
                logger.info(f"[GuruAdapter] No {type_} cards found, stop at page {page}")
                break

            for card in cards:
                try:
                    profile_url = card.get_attribute("href")
                    name_el = card.find_element(By.XPATH, ".//span[@class='actrees-name']")
                    name = name_el.text.strip() if name_el else None
                    image_url = None
                    try:
                        img_el = card.find_element(By.XPATH, ".//img")
                        if img_el:
                            image_url = img_el.get_attribute("src")
                    except Exception:
                        pass

                    if name and name not in people:
                        people[name] = Model(
                            name=name,
                            type=type_,
                            profile_url=profile_url,
                            image_url=image_url,
                            site=self.site_name,
                        )
                        logger.info(f"[GuruAdapter] Found {type_}: {name}")
                except Exception as e:
                    logger.warning(f"[GuruAdapter] Failed to parse {type_} element: {e}")

            page += 1

        logger.info(f"[GuruAdapter] Collected {len(people)} {type_}s")
        return list(people.values())

    def parse_actress(self, selenium: SeleniumService) -> list[Model]:
        return self.parse_people(selenium, "jav-actress-list", "actress")

    def parse_actors(self, selenium: SeleniumService) -> list[Model]:
        return self.parse_people(selenium, "jav-actors", "actor")

    def parse_directors(self, selenium: SeleniumService) -> list[Model]:
        return self.parse_people(selenium, "jav-directors-list", "director")

    def parse_videos(
            self, 
            selenium: SeleniumService,
            start_page: int | None = None, 
            end_page: int | None = None
        ) -> list[ParsedVideo]:

        if start_page is None:
            start_page = self._get_last_page(selenium)
        if end_page is None:
            end_page = 1


        videos: list[ParsedVideo] = []
        for page in range(start_page, end_page - 1, -1):
            url = self.BASE_URL if page == 1 else f"{self.BASE_URL}page/{page}/"
            logger.info(f"[GuruAdapter] Open page {page}: {url}")
            selenium.get(url, (By.XPATH, "//div[contains(@class,'site-content')]"))

            cards = selenium.wait_for_elements((By.XPATH, "//div[contains(@class,'inside-article')]"))
            if not cards:
                logger.info(f"[GuruAdapter] No cards found, stop at page {page}")
                break
            
            for idx, card in enumerate(reversed(cards), start=1):
                try:
                    a = card.find_element(By.XPATH, ".//div[contains(@class,'grid1')]//h2/a")
                    page_link = a.get_attribute("href")
                    title = a.get_attribute("title") or a.text

                    jav_code = ""

                    video = ParsedVideo(
                        title=title.strip() if title else "N/A",
                        jav_code=jav_code,
                        page_link=page_link,
                        site=self.site_name,
                    )
                    videos.append(video)
                    logger.info(f"[GuruAdapter] [page {page} | {idx}] {jav_code} | {title[:60]}...")

                except Exception as e:
                    logger.warning(f"[GuruAdapter] Failed to parse card on page {page}, idx {idx}: {e}")

        logger.info(f"[GuruAdapter] Collected {len(videos)} video links")
        return videos

    def parse_video(self, selenium: SeleniumService, video: ParsedVideo) -> ParsedVideo:
        selenium.get(video.page_link.unicode_string(), (By.XPATH, "//div[contains(@class,'inside-article')]"))

        # title
        title_el = selenium.find_first("//h1[@class='titl']")
        if title_el:
            video.title = title_el.text.strip()

        # thumbnail
        thumb_el = selenium.find_first("//div[@class='large-screenimg']//img")
        if thumb_el:
            video.thumbnail_url = thumb_el.get_attribute("src")

        # code
        code_el = selenium.find_first("//li[strong/span[text()='Code: ']]")
        if code_el:
            code_text = code_el.text.replace("Code:", "").strip()
            if code_text:
                video.jav_code = code_text

        # release date
        date_el = selenium.find_first("//li[strong/span[text()='Release Date: ']]")
        if date_el:
            raw = date_el.text.replace("Release Date:", "").strip()
            try:
                video.release_date = dateparser.parse(raw)
            except Exception:
                video.release_date = None

        # categories
        cats = selenium.find_elements("//li[strong[text()='Category:']]/a")
        video.categories = [c.text.strip() for c in cats if c.text.strip()]
        logger.info(f"[GuruAdapter] {video.jav_code} categories parsed: {video.categories}")


        # directors
        dirs = selenium.find_elements("//li[strong[text()='Director:']]/a")
        video.directors = [d.text.strip() for d in dirs if d.text.strip()]
        logger.info(f"[GuruAdapter] {video.jav_code} directors parsed: {video.directors}")


        # studio
        studio_el = selenium.find_first("//li[strong[text()='Studio:']]/a")
        if studio_el:
            video.studio = studio_el.text.strip()

        # tags
        tags = selenium.find_elements("//li[contains(@class,'w1')]/a[@rel='tag']")
        video.tags = [t.text.strip() for t in tags if t.text.strip()]

        # actors
        acts_male = selenium.find_elements("//li[strong[text()='Actor:']]/a")
        video.actors = [a.text.strip() for a in acts_male if a.text.strip()]
        logger.info(f"[GuruAdapter] {video.jav_code} actors parsed: {video.actors}")

        # actresses
        acts = selenium.find_elements("//li[strong[text()='Actress:']]/a")
        video.actresses = [a.text.strip() for a in acts if a.text.strip()]

        # uncensored
        video.uncensored = any(c.lower() == "uncensored" for c in video.categories)

        return video