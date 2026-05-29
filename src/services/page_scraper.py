from selenium.webdriver.common.by import By
from src.core.models import PeptideData
from src.core.interfaces import IScraper
from src.extractors.hero import HeroExtractor
from src.extractors.quick_guide import QuickGuideExtractor
from src.extractors.community import CommunityExtractor
from src.extractors.section import SectionExtractor
from src.extractors.graph import GraphExtractor
from src.infrastructure.webdriver_factory import WebDriverFactory
from src.config import log_debug, log_error
from typing import List, Tuple, Optional
from tqdm import tqdm
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
            log_debug(f"Starting scrape for URL: {url}", "page_scraper.py")
            driver.get(url)
            time.sleep(1)

            results = []
            # Get categories (e.g. Injection, Nasal, Oral)
            categories = self._get_categories(driver, wait)
            log_debug(f"Found {len(categories)} categories for {url}", "page_scraper.py")

            for cat in tqdm(categories, desc="Processing categories", unit="category", leave=False):
                # Click the category button
                self._click_category(driver, wait, cat)
                log_debug(f"Processing category '{cat}' for {url}", "page_scraper.py")
                
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
            log_debug(f"Successfully scraped {len(results)} results from {url}", "page_scraper.py")
            return results, None
        except Exception as e:
            error_msg = f"{url} - {str(e)}"
            print(f"[ERROR] {error_msg}")
            log_error(error_msg, "page_scraper.py")
            return [], error_msg
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
