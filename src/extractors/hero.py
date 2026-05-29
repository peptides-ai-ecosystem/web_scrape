from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from src.extractors.base import BaseExtractor
from src.core.models import HeroData, HeroFact

class HeroExtractor(BaseExtractor):
    def extract(self, driver, wait) -> HeroData:
        hero = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.peptide-hero-gradient")))
        name = hero.find_element(By.TAG_NAME, "h1").text.strip()
        subtitle = hero.find_element(By.TAG_NAME, "p").text.strip()
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
        return HeroData(name=name, subtitle=subtitle, facts=facts)
