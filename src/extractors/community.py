from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
from src.extractors.base import BaseExtractor
from typing import Dict

class CommunityExtractor(BaseExtractor):
    def extract(self, driver, wait) -> Dict[str, Dict[str, str]]:
        return {
            "insights": self._get_community_insights(driver, wait),
            "polls": self._get_poll_results(driver, wait)
        }

    # Verified against the live site (pep-pedia.org, AOD-9604/Semaglutide):
    # - "Community Insights" no longer exists — the sidebar shows the
    #   "Community Poll" survey (radio inputs) + the "Poll Results" card.
    # - The results card (`bg-white ... rounded-xl p-6`) is a SIBLING of the
    #   h3 header row, NOT an ancestor. The old
    #   `ancestor::div[contains(@class,'rounded-xl')]` XPath never matched.
    # - Questions are switched with pill buttons
    #   (`div.flex.flex-wrap.gap-2 > button`) — there is NO carousel, so the
    #   old "Go to question 1"/"Next question"/`aria-roledescription='slide'`
    #   logic always failed.
    _POLL_CARD_XPATH = (
        "//h3[contains(text(),'Poll Results')]"
        "/parent::div/following-sibling::div[contains(@class,'rounded-xl')][1]"
    )

    def _get_community_insights(self, driver, wait):
        # The "Community Insights" card was removed from the site (verified on
        # AOD-9604, Semaglutide and BPC-157). Keep a SHORT bounded wait in case
        # it lazy-hydrates somewhere, then bail out quickly — do not block the
        # whole wait (5s) on a section that no longer exists.
        try:
            WebDriverWait(driver, 1.5).until(EC.presence_of_element_located(
                (By.XPATH, "//h3[contains(.,'Community Insights')]")
            ))
            card = wait.until(EC.presence_of_element_located(
                (By.XPATH, "//h3[contains(.,'Community Insights')]"
                           "/parent::div/following-sibling::div[contains(@class,'rounded-xl')][1]")
            ))
            heading = self.get_text(driver, card.find_element(By.TAG_NAME, "h3")).strip()
            responses = self.get_text(driver, card.find_element(
                By.XPATH, ".//p[contains(.,'responses')]"
            )).strip()
            rows = card.find_elements(By.CSS_SELECTOR, "div.flex.gap-3.items-start")
            insights = {heading: responses}
            insights.update({
                f"{heading}_{self.get_text(driver, r.find_element(By.CSS_SELECTOR, '.text-label-sm')).strip()}":
                self.get_text(driver, r.find_element(By.CSS_SELECTOR, ".text-body-sm")).strip()
                for r in rows
            })
            return insights
        except TimeoutException:
            return {}

    def _get_poll_results(self, driver, wait):
        try:
            wait.until(EC.presence_of_element_located(
                (By.XPATH, "//h3[contains(text(),'Poll Results')]")
            ))
            card = wait.until(EC.presence_of_element_located(
                (By.XPATH, self._POLL_CARD_XPATH)
            ))
            poll_results = {}

            responses = self.get_text(driver, card.find_element(
                By.XPATH, ".//p[contains(.,'responses')]"
            )).strip()
            if responses:
                poll_results["poll_responses"] = responses

            # Questions are switched with the pill buttons below the options;
            # if a card has no pills it only ever shows one question.
            pill_buttons = card.find_elements(
                By.CSS_SELECTOR, "div.flex.flex-wrap.gap-2 button"
            )
            if not pill_buttons:
                pill_buttons = [None]

            for pill in pill_buttons:
                try:
                    if pill is not None:
                        self.safe_click(driver, wait, pill)
                        self.wait_for_loading(0.4)
                    # Current question title (h4), scoped to its container so a
                    # pill switch that toggles visibility can't leak options
                    # from other questions.
                    h4 = card.find_element(By.TAG_NAME, "h4")
                    question = self.get_text(driver, h4).strip()
                    question_box = h4.find_element(By.XPATH, "./parent::div")
                    for row in question_box.find_elements(
                        By.CSS_SELECTOR, "div.space-y-3 > div"
                    ):
                        spans = row.find_elements(By.TAG_NAME, "span")
                        if len(spans) >= 2:
                            label = self.get_text(driver, spans[0]).strip()
                            value = self.get_text(driver, spans[1]).strip()
                            if label and value:
                                poll_results[f"poll_{question}_{label}"] = value
                except Exception:
                    continue
            return poll_results
        except Exception:
            return {}
