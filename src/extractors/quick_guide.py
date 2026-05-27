from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from src.extractors.base import BaseExtractor
from typing import Dict

class QuickGuideExtractor(BaseExtractor):
    def extract(self, driver, wait) -> Dict[str, str]:
        if not driver.find_elements(By.XPATH, "//h3[contains(text(),'Quick Start Guide')]"):
            return {}

        try:
            guide = wait.until(EC.presence_of_element_located(
                (By.XPATH, "//h3[contains(text(),'Quick Start Guide')]/ancestor::div[contains(@class,'rounded-xl')]")
            ))
            rows = guide.find_elements(By.CSS_SELECTOR, "div.flex.gap-3")
            return {
                r.find_element(By.CSS_SELECTOR, ".text-label-sm").text.strip():
                r.find_element(By.CSS_SELECTOR, ".text-body-sm").text.strip()
                for r in rows
            }
        except TimeoutException:
            return {}
