from multiprocessing import Pool, cpu_count
from typing import List, Callable
from tqdm import tqdm
from .page_scraper import PageScraper
from src.infrastructure.csv_storage import CSVStorage
from src.config import log_debug, log_error, MASTER_CSV

def scrape_url_wrapper(url: str):
    scraper = PageScraper()
    return scraper.scrape(url)

class ScraperManager:
    def __init__(self, storage=None, max_processes=None):
        self.storage = storage or CSVStorage()
        self.max_processes = max_processes or min(cpu_count(), 4)
        log_debug(f"ScraperManager initialized with {self.max_processes} processes", "scraper_manager.py")

    def run(self, urls: List[str]):
        all_results = []
        error_logs = []
        
        log_debug(f"Starting scrape batch with {len(urls)} URLs", "scraper_manager.py")

        with Pool(processes=self.max_processes) as pool:
            results = list(tqdm(pool.imap_unordered(scrape_url_wrapper, urls), total=len(urls), desc="Scraping URLs", unit="url"))
            
            for p_data_list, error in results:
                if p_data_list:
                    all_results.extend(p_data_list)
                if error:
                    error_logs.append(error)

        if all_results:
            log_debug(f"Saving {len(all_results)} records to {MASTER_CSV}", "scraper_manager.py")
            self.storage.save(all_results)
        else:
            log_debug("No results to save - all_results is empty", "scraper_manager.py")
            print("[WARNING] No data was scraped. Check URLs and scraper errors.")
        
        if error_logs:
            log_debug(f"Batch completed with {len(error_logs)} errors", "scraper_manager.py")
        else:
            log_debug("Batch completed successfully with no errors", "scraper_manager.py")
        
        return error_logs
