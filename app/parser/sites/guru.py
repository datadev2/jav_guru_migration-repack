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

    def _extract_video_src(self, selenium: SeleniumService, timeout_sec: int = 15) -> str | None:
        current_window = selenium.driver.current_window_handle
        old_handles = selenium.driver.window_handles
        try:
            buttons = selenium.driver.find_elements(By.XPATH, "//a[contains(text(),'STREAM ST')]")
            logger.info(f"[GuruAdapter] Found {len(buttons)} STREAM ST buttons in DOM")
            btn = next((b for b in buttons if b.is_displayed()), None)
            if not btn:
                logger.error("[GuruAdapter] No visible STREAM ST button found")
                return None

            selenium.driver.execute_script("arguments[0].click();", btn)
            logger.success("[GuruAdapter] STREAM ST button clicked")
            time.sleep(20)


            WebDriverWait(selenium.driver, timeout_sec).until(
                lambda d: len(d.window_handles) > len(old_handles)
            )
            new_handles = [h for h in selenium.driver.window_handles if h not in old_handles]
            logger.info(f"[GuruAdapter] {len(new_handles)} new window handles detected: {new_handles}")

            for handle in new_handles:
                try:
                    selenium.driver.switch_to.window(handle)
                    logger.info(f"[GuruAdapter] Switched to handle={handle}, url={selenium.driver.current_url}")
                    WebDriverWait(selenium.driver, timeout_sec).until(
                        lambda d: d.execute_script("return document.readyState") == "complete"
                    )
                    logger.debug("[GuruAdapter] Document readyState=complete")

                    video_tag = WebDriverWait(selenium.driver, timeout_sec).until(
                        EC.presence_of_element_located((By.ID, "mainvideo"))
                    )
                    if not video_tag:
                        logger.warning(f"[GuruAdapter] No <video id='mainvideo'> in {handle}")
                        continue

                    src = video_tag.get_attribute("src")
                    logger.info(f"[GuruAdapter] mainvideo src attribute={src}")

                    if src and src.startswith("//"):
                        src = "https:" + src

                    logger.success(f"[GuruAdapter] Final video src={src}")

                    selenium.driver.close()
                    logger.debug(f"[GuruAdapter] Closed handle={handle}")

                    selenium.driver.switch_to.window(current_window)
                    logger.debug("[GuruAdapter] Returned to main window")
                    return src

                except Exception as e:
                    logger.warning(f"[GuruAdapter] Failed on handle={handle} | {e}", exc_info=True)
                    try:
                        selenium.driver.close()
                        logger.debug(f"[GuruAdapter] Closed handle={handle} after failure")
                    except Exception:
                        pass

            selenium.driver.switch_to.window(current_window)
            logger.error("[GuruAdapter] mainvideo not found in any new tab")
            return None

        except Exception as e:
            logger.error(f"[GuruAdapter] _extract_video_src fatal: {e}", exc_info=True)
            try:
                if current_window in selenium.driver.window_handles:
                    selenium.driver.switch_to.window(current_window)
            except Exception:
                pass
            return None

        
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