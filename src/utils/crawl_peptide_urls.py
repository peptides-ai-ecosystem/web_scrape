from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from src.infrastructure.webdriver_factory import WebDriverFactory
from src.config import log_debug, log_error
from tqdm import tqdm
import time
def crawl_peptide_urls():
    log_debug("Starting peptide URL crawl", "crawl_peptide_urls")
    driver, wait = WebDriverFactory.create_driver()
    try:
        log_debug("Navigating to https://pep-pedia.org/browse", "crawl_peptide_urls")
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
        # print(f"[DEBUG] Page source length: {len(source)}")
        # print(f"[DEBUG] Page source snippet:\n{source[:1500]}\n")

        all_links = driver.find_elements(By.TAG_NAME, "a")
        print(f"[DEBUG] Found total {len(all_links)} links on page")

        links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/peptides/']")
        log_debug(f"Found {len(links)} peptide links on page", "crawl_peptide_urls")

        peptide_urls = [link.get_attribute("href") for link in tqdm(links, desc="Extracting URLs", unit="link")]
        log_debug(f"Extracted {len(set(peptide_urls))} unique peptide URLs", "crawl_peptide_urls")
        return list(set(peptide_urls))
    finally:
        driver.quit()
