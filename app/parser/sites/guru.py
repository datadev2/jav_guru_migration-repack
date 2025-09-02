from typing import Optional
from selenium.webdriver.common.by import By
from app.db.models import Video, Category, ParsedVideo
from app.parser.interactions import SeleniumService
from app.logger import init_logger

logger = init_logger()


class GuruAdapter:
    site_name = "guru"
    BASE_URL = "https://jav.guru/"

    def _open_video_tab(self, url: str) -> None:
        """Opens the video URL in a new browser tab and switches to it."""
        self.selenium.driver.execute_script(f"window.open('{url}', '_blank');")
        self.selenium.driver.switch_to.window(self.selenium.driver.window_handles[-1])

    def _close_video_tab(self, main_window: str) -> None:
        """Closes the current browser tab and switches back to the main one."""
        self.selenium.driver.close()
        self.selenium.driver.switch_to.window(main_window)

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