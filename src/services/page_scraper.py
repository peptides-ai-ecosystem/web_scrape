from selenium.webdriver.common.by import By
from ..core.models import PeptideData
from ..core.interfaces import IScraper
from ..extractors.hero import HeroExtractor
from ..extractors.quick_guide import QuickGuideExtractor
from ..extractors.community import CommunityExtractor
from ..extractors.section import SectionExtractor
from ..extractors.graph import GraphExtractor
from ..infrastructure.webdriver_factory import WebDriverFactory
from typing import List, Tuple, Optional
import time

class PageScraper(IScraper):
    def __init__(self):
        self.hero_extractor = HeroExtractor()
        self.quick_guide_extractor = QuickGuideExtractor()
        self.community_extractor = CommunityExtractor()
        self.section_extractor = SectionExtractor()
        self.graph_extractor = GraphExtractor()

    def scrape(self, url: str) -> Tuple[List[PeptideData], Optional[str]]:
        driver, wait = WebDriverFactory.create_driver()
        try:
            print(f"[INFO] Processing: {url}")
            driver.get(url)
            time.sleep(2)

            results = []
            # Get categories (e.g. Injection, Nasal, Oral)
            categories = self._get_categories(driver, wait)

            for cat in categories:
                # Click the category button
                self._click_category(driver, wait, cat)
                
                hero_data = self.hero_extractor.extract(driver, wait)
                quick_guide = self.quick_guide_extractor.extract(driver, wait)
                community = self.community_extractor.extract(driver, wait)
                sections = self.section_extractor.extract(driver, wait)
                graph_data = self.graph_extractor.extract(driver, wait)

                results.append(PeptideData(
                    name=hero_data.name,
                    full_name=hero_data.subtitle,
                    method=cat,
                    url=driver.current_url,
                    hero=hero_data,
                    quick_guide=quick_guide,
                    community_insights=community["insights"],
                    poll_results=community["polls"],
                    sections=sections,
                    graph_data=graph_data
                ))
            return results, None
        except Exception as e:
            print(f"[ERROR] {url}: {e}")
            return [], f"{url} - {str(e)}"
        finally:
            driver.quit()

    def _get_categories(self, driver, wait):
        from selenium.webdriver.support import expected_conditions as EC
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.flex.gap-2.bg-white\\/10")))
        buttons = driver.find_elements(By.CSS_SELECTOR, "div.flex.gap-2.bg-white\\/10 button")
        return [b.text.strip() for b in buttons if b.text.strip()]

    def _click_category(self, driver, wait, cat_text):
        buttons = driver.find_elements(By.CSS_SELECTOR, "div.flex.gap-2.bg-white\\/10 button")
        for b in buttons:
            if b.text.strip() == cat_text:
                self.hero_extractor.safe_click(driver, wait, b)
                # Wait until the clicked button reflects an active/selected state
                # to ensure the method's content (including graph) has re-rendered.
                try:
                    wait.until(lambda d: any(
                        btn.text.strip() == cat_text and (
                            "active" in (btn.get_attribute("class") or "") or
                            btn.get_attribute("aria-selected") == "true" or
                            btn.get_attribute("data-state") == "active"
                        )
                        for btn in d.find_elements(
                            By.CSS_SELECTOR, "div.flex.gap-2.bg-white\\/10 button"
                        )
                    ))
                except Exception:
                    # Fallback: short sleep if active-state detection fails
                    self.hero_extractor.wait_for_loading(1.0)
                break
