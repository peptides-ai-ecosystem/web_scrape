from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from src.infrastructure.webdriver_factory import WebDriverFactory
from tqdm import tqdm
import time
def crawl_peptide_urls():
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
        # print(f"[DEBUG] Page source length: {len(source)}")
        # print(f"[DEBUG] Page source snippet:\n{source[:1500]}\n")

        all_links = driver.find_elements(By.TAG_NAME, "a")
        print(f"[DEBUG] Found total {len(all_links)} links on page")

        links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/peptides/']")
        print(f"[DEBUG] Found {len(links)} peptide links")

        peptide_urls = [link.get_attribute("href") for link in tqdm(links[:20], desc="Extracting URLs", unit="link")]
        return list(set(peptide_urls))
    finally:
        driver.quit()
