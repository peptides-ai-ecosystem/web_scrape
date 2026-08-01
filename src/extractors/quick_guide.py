from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from src.extractors.base import BaseExtractor
from typing import Dict

class QuickGuideExtractor(BaseExtractor):
    # Verified against the live site (pep-pedia.org, BPC-157):
    # - The "Quick Start Guide" card sits in the right sidebar. The h3 header
    #   and the `rounded-xl` content card are SIBLINGS inside a plain wrapper
    #   div (h3 first, card second) — NOT ancestor/descendant. The old
    #   `ancestor::div[contains(@class,'rounded-xl')]` XPath never matched.
    _CARD_XPATH = (
        "//h3[contains(text(),'Quick Start Guide')]"
        "/following-sibling::div[contains(@class,'rounded-xl')][1]"
    )

    def extract(self, driver, wait) -> Dict[str, str]:
        if not driver.find_elements(By.XPATH, "//h3[contains(text(),'Quick Start Guide')]"):
            return {}

        try:
            guide = wait.until(EC.presence_of_element_located(
                (By.XPATH, self._CARD_XPATH)
            ))
            rows = guide.find_elements(By.CSS_SELECTOR, "div.flex.gap-3")
            return {
                self.get_text(driver, r.find_element(By.CSS_SELECTOR, ".text-label-sm")).strip():
                self.get_text(driver, r.find_element(By.CSS_SELECTOR, ".text-body-sm")).strip()
                for r in rows
            }
        except TimeoutException:
            return {}
