from typing import Optional, Tuple
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
from selenium.common.exceptions import TimeoutException
from app.logger import init_logger


logger = init_logger()

class SeleniumService:
    def __init__(self, driver: WebDriver, timeout: int = 10):
        self.driver = driver
        self._wait = WebDriverWait(driver, timeout)

    def get(self, url: str, wait_selector: Optional[Tuple[By, str]] = None, timeout: Optional[int] = None):
        try:
            self.driver.get(url)
            logger.debug(f"Navigated to {url}")
            if wait_selector:
                self.wait_for_element(wait_selector, timeout=timeout)
                logger.debug(f"Element appeared: {wait_selector}")
        except Exception as e:
            logger.error(f"Failed to get URL {url}: {e}", exc_info=True)


    def wait_for_element(self, element: Tuple[By, str], timeout: Optional[int] = None):
        try:
            wait = WebDriverWait(self.driver, timeout or self._wait._timeout)
            result = wait.until(ec.visibility_of_element_located(element))
            return result
        except TimeoutException:
            logger.warning(f"Timeout waiting for {element}")
            return None
        except Exception as e:
            logger.warning(f"Element not found: {element} | {e}", exc_info=True)
            return None

        
    def wait_for_elements(self, selector: Tuple[By, str]) -> list[WebElement]:
        try:
            elements = self._wait.until(ec.presence_of_all_elements_located(selector))
            return elements if elements else []
        except Exception as e:
            logger.warning(f"Elements not found: {selector} | {e}")
            return []
