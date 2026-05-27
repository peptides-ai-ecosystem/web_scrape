from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from src.extractors.base import BaseExtractor
from typing import Dict

class CommunityExtractor(BaseExtractor):
    def extract(self, driver, wait) -> Dict[str, Dict[str, str]]:
        return {
            "insights": self._get_community_insights(driver, wait),
            "polls": self._get_poll_results(driver, wait)
        }

    def _get_community_insights(self, driver, wait):
        if not driver.find_elements(By.XPATH, "//h3[contains(.,'Community Insights')]"):
            return {}
        try:
            card = wait.until(EC.presence_of_element_located(
                (By.XPATH, "//h3[contains(.,'Community Insights')]/ancestor::div[contains(@class,'rounded-xl')]")
            ))
            heading = card.find_element(By.TAG_NAME, "h3").text.strip()
            responses = wait.until(EC.visibility_of_element_located(
                (By.XPATH, "//h3[contains(.,'Community Insights')]/ancestor::div[contains(@class,'rounded-xl')]//p[contains(.,'responses')]")
            )).text
            rows = card.find_elements(By.CSS_SELECTOR, "div.flex.gap-3.items-start")
            insights = {heading: responses}
            insights.update({
                f"{heading}_{r.find_element(By.CSS_SELECTOR, '.text-label-sm').text.strip()}":
                r.find_element(By.CSS_SELECTOR, ".text-body-sm").text.strip()
                for r in rows
            })
            return insights
        except TimeoutException:
            return {}

    def _get_poll_results(self, driver, wait):
        if not driver.find_elements(By.XPATH, "//h3[contains(.,'Poll Results')]"):
            return {}
        try:
            card = wait.until(EC.presence_of_element_located(
                (By.XPATH, "//h3[contains(text(),'Poll Results')]/ancestor::div[contains(@class,'rounded-xl')]")
            ))
            first_dot = card.find_element(By.CSS_SELECTOR, "button[aria-label='Go to question 1']")
            driver.execute_script("arguments[0].click();", first_dot)
            self.wait_for_loading()
            
            heading = card.find_element(By.TAG_NAME, "h3").text.strip()
            responses = card.find_element(By.XPATH, ".//p[contains(.,'responses')]").text.strip()
            poll_results = {heading: responses}
            
            slides = card.find_elements(By.CSS_SELECTOR, "div[role='group'][aria-roledescription='slide']")
            total_slides = len(slides)
            
            for i in range(total_slides):
                current_slide = slides[i]
                question = current_slide.find_element(By.TAG_NAME, "h4").text.strip()
                options = current_slide.find_elements(By.CSS_SELECTOR, "div.relative")
                for option in options:
                    try:
                        label = option.find_element(By.CSS_SELECTOR, "span.truncate").text.strip()
                        value = option.find_element(By.CSS_SELECTOR, "span.whitespace-nowrap").text.strip()
                        poll_results[f"poll_{question}_{label}"] = value
                    except:
                        continue
                if i < total_slides - 1:
                    next_btn = card.find_element(By.CSS_SELECTOR, "button[aria-label='Next question']")
                    driver.execute_script("arguments[0].click();", next_btn)
                    self.wait_for_loading()
                    slides = card.find_elements(By.CSS_SELECTOR, "div[role='group'][aria-roledescription='slide']")
            return poll_results
        except Exception:
            return {}
