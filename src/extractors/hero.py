from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from src.extractors.base import BaseExtractor
from src.core.models import HeroData, HeroFact

class HeroExtractor(BaseExtractor):
    def extract(self, driver, wait) -> HeroData:
        hero = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.peptide-hero-gradient")))
        name = hero.find_element(By.TAG_NAME, "h1").text.strip()
        subtitle = hero.find_element(By.TAG_NAME, "p").text.strip()
        research_level = self._extract_research_level(driver, hero)
        facts = []
        cards = hero.find_elements(By.XPATH, ".//div[contains(@class,'rounded-2xl')]")
        for card in cards:
            lines = [l.strip() for l in card.text.split("\n") if l.strip()]
            if len(lines) >= 2:
                facts.append(HeroFact(
                    label=lines[0],
                    value=lines[1],
                    extra=lines[2] if len(lines) > 2 else ""
                ))
        return HeroData(name=name, subtitle=subtitle, facts=facts, research_level=research_level)

    def _extract_research_level(self, driver, hero) -> str:
        """Read the research level badge next to the h1.

        Some peptides omit the badge — those default to "Limited Research".
        """
        badges = hero.find_elements(By.XPATH, ".//div[contains(@class,'font-dm-mono') and contains(@class,'rounded-full')]")
        if badges:
            text = self.get_text(driver, badges[0]).strip()
            if text:
                return text
        return "Limited Research"
