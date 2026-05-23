from pathlib import Path
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
import time

# -------------------- CONFIG -------------------- #
TIMEOUT = 5  # increased from 5
OUTPUT_DIR = Path("output_v6")
OUTPUT_DIR.mkdir(exist_ok=True)
MASTER_CSV = OUTPUT_DIR / "pep_pedia_master.csv"
ERROR_LOG = OUTPUT_DIR / "error_log.txt"

TIME_RANGES = ["24h", "7d", "14d", "30d"]

button_skip_list = [
    "peak", "half-life", "cleared", "hrs", "hr", "day",
] + TIME_RANGES

def crawl_peptide_urls():
    from .infrastructure.webdriver_factory import WebDriverFactory
    driver, wait = WebDriverFactory.create_driver()
    try:
        driver.get("https://pep-pedia.org/browse")

        # Wait for JS to render — wait until at least one <a> tag exists
        try:
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "a")))
        except Exception:
            pass

        # Extra buffer for slow JS frameworks
        time.sleep(1)

        # Debug info — check what the page actually loaded
        source = driver.page_source
        print(f"[DEBUG] Page source length: {len(source)}")
        print(f"[DEBUG] Page source snippet:\n{source[:1500]}\n")

        all_links = driver.find_elements(By.TAG_NAME, "a")
        print(f"[DEBUG] Found total {len(all_links)} links on page")

        links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/peptides/']")
        print(f"[DEBUG] Found {len(links)} peptide links")

        peptide_urls = [link.get_attribute("href") for link in links]
        return list(set(peptide_urls[:30]))
    finally:
        driver.quit()