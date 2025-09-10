import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from app.db.models import Video, Category, Studio, ParsedVideo, Tag, Model
from app.parser.interactions import SeleniumService
from app.logger import init_logger


logger = init_logger()


class GuruAdapter:
    site_name = "guru"
    BASE_URL = "https://jav.guru/"
    STUDIO_URL = "https://jav.guru/jav-makers-list/"
    TAG_URL = "https://jav.guru/jav-tags-list/"

    def _open_video_tab(self, selenium: SeleniumService, url: str) -> None:
        selenium.driver.execute_script(f"window.open('{url}', '_blank');")
        selenium.driver.switch_to.window(selenium.driver.window_handles[-1])

    def _close_video_tab(self, selenium: SeleniumService, main_window: str) -> None:
        selenium.driver.close()
        selenium.driver.switch_to.window(main_window)

    def _extract_video_src(self, selenium: SeleniumService, timeout_sec: int = 300) -> str | None:
        try:
            # === Step 1: STREAM ST ===
            logger.info("[GuruAdapter] Step 1: ищем кнопку STREAM ST")
            btns = selenium.find_elements("//a[contains(text(),'STREAM ST')]")
            if not btns:
                logger.error("[GuruAdapter] STREAM ST кнопка не найдена")
                return None

            btn = next((b for b in btns if b.is_displayed()), None)
            if not btn:
                logger.error("[GuruAdapter] STREAM ST кнопка невидима")
                return None

            selenium.driver.execute_script("arguments[0].click();", btn)
            logger.success("[GuruAdapter] STREAM ST button clicked")

            # === Step 2: первый iframe ===
            logger.info("[GuruAdapter] Step 2: ждём первый iframe")
            first_iframe = selenium.wait_for_element((By.XPATH, "//iframe[@data-localize]"), timeout=30)
            if not first_iframe:
                logger.error("[GuruAdapter] Первый iframe не найден")
                return None
            selenium.driver.switch_to.frame(first_iframe)

            logger.info("[GuruAdapter] Step 2: кликаем .playbutton")
            play_btn = selenium.wait_for_element((By.XPATH, "//*[contains(@class,'playbutton')]"), timeout=30)
            if not play_btn:
                logger.error("[GuruAdapter] .playbutton не найден")
                selenium.driver.switch_to.default_content()
                return None
            selenium.driver.execute_script("arguments[0].click();", play_btn)
            logger.success("[GuruAdapter] .playbutton clicked")

            selenium.driver.switch_to.default_content()

            # === Step 2.5: реклама ===
            wait_time = 180
            logger.info(f"[GuruAdapter] Step 2.5: ждём рекламу до {wait_time} сек")
            for i in range(wait_time):
                if i % 10 == 0:
                    logger.info(f"[GuruAdapter] ... прошло {i} сек ожидания рекламы")
                time.sleep(1)
            logger.success("[GuruAdapter] Завершили ожидание рекламы, ищем plyr iframe")

            # === Step 3: второй iframe ===
            second_iframe = selenium.wait_for_element(
                (By.XPATH, "//iframe[contains(@src,'searcho/?dr=')]"),
                timeout=60
            )
            if not second_iframe:
                logger.error("[GuruAdapter] Второй iframe не найден")
                return None
            selenium.driver.switch_to.frame(second_iframe)

            # === Step 3: цикл overlay+play + src ===
            logger.info("[GuruAdapter] Step 3: начинаем долбить overlay+play и читать mainvideo.src")
            deadline = time.time() + 180
            src = None
            attempt = 0

            while time.time() < deadline:
                attempt += 1
                logger.info(f"[GuruAdapter] Попытка #{attempt}: overlay+play + чтение src")

                js_code = """
                    document.querySelector(".play-overlay")?.click();
                    setTimeout(() => {
                        document.querySelector("[data-plyr='play']")?.click();
                    }, 500);
                    return document.querySelector('#mainvideo')?.getAttribute('src');
                """
                candidate = selenium.driver.execute_script(js_code)

                if candidate:
                    src = candidate
                    logger.success(f"[GuruAdapter] Нашли src на попытке #{attempt}: {src}")
                    break

                logger.info("[GuruAdapter] src нет, ждём 8 сек...")
                time.sleep(8)

            if not src:
                logger.error("[GuruAdapter] src так и не появился")
                return None

            if src.startswith("//"):
                src = "https:" + src

            logger.success(f"[GuruAdapter] Final video src = {src}")
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
        return [
            Category(
                name=tag.name, 
                source_url=tag.source_url, 
                site=self.site_name)
                for tag in self.parse_tags(selenium)]

    def parse_models(self, selenium: SeleniumService) -> list[Model]:
        models: dict[str, Model] = {}
        page = 1

        while True:
            url = f"{self.BASE_URL}jav-actress-list/page/{page}/"
            logger.info(f"[GuruAdapter] Open actress page {page}: {url}")
            selenium.get(url, (By.XPATH, "//div[@class='actress-box']"))

            cards = selenium.find_elements("//div[@class='actress-box']/a")
            if not cards:
                logger.info(f"[GuruAdapter] No actress cards found, stop at page {page}")
                break
            
            for card in cards:
                try:
                    profile_url = card.get_attribute("href")

                    name_el = card.find_element(By.XPATH, ".//span[@class='actrees-name']")
                    name = name_el.text.strip() if name_el else None

                    img_el = card.find_element(By.XPATH, ".//img")
                    image_url = img_el.get_attribute("src") if img_el else None

                    if name and name not in models:
                        models[name] = Model(
                            name=name,
                            type="actress",
                            profile_url=profile_url,
                            image_url=image_url,
                            site=self.site_name,
                        )
                        logger.info(f"[GuruAdapter] Found actress: {name}")
                except Exception as e:
                    logger.warning(f"[GuruAdapter] Failed to parse actress element: {e}")

            page += 1

        logger.info(f"[GuruAdapter] Collected {len(models)} actresses")
        return list(models.values())

    def parse_videos(self, selenium: SeleniumService) -> list[ParsedVideo]:
        videos: list[ParsedVideo] = []
        page = 1

        while True:
            url = self.BASE_URL if page == 1 else f"{self.BASE_URL}page/{page}/"
            logger.info(f"[GuruAdapter] Open page {page}: {url}")
            selenium.get(url, (By.XPATH, "//div[contains(@class,'site-content')]"))

            cards = selenium.wait_for_elements((By.XPATH, "//div[contains(@class,'inside-article')]"))
            if not cards:
                logger.info(f"[GuruAdapter] No cards found, stop at page {page}")
                break
            
            #todo DEBUG
            if page == 5:
                break
            #todo DEBUG

            for idx, card in enumerate(cards, start=1):
                try:
                    a = card.find_element(By.XPATH, ".//div[contains(@class,'grid1')]//h2/a")
                    page_link = a.get_attribute("href")
                    title = a.get_attribute("title") or a.text

                    jav_code = ""
                    if title and "[" in title and "]" in title:
                        jav_code = title.split("[")[1].split("]")[0]

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

            page += 1

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
            video.release_date = date_el.text.replace("Release Date:", "").strip()

        # categories
        cats = selenium.find_elements("//li[strong[text()='Category:']]/a")
        video.categories = [c.text.strip() for c in cats if c.text.strip()]

        # directors
        dirs = selenium.find_elements("//li[strong[text()='Director:']]/a")
        video.directors = [d.text.strip() for d in dirs if d.text.strip()]

        # studio
        studio_el = selenium.find_first("//li[strong[text()='Studio:']]/a")
        if studio_el:
            video.studio = studio_el.text.strip()

        # tags
        tags = selenium.find_elements("//li[contains(@class,'w1')]/a[@rel='tag']")
        video.tags = [t.text.strip() for t in tags if t.text.strip()]

        # actresses
        acts = selenium.find_elements("//li[strong[text()='Actress:']]/a")
        video.actresses = [a.text.strip() for a in acts if a.text.strip()]

        # uncensored
        video.uncensored = any(c.lower() == "uncensored" for c in video.categories)

        return video