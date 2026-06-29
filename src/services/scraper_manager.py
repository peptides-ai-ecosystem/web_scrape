from functools import partial
from multiprocessing import Pool, cpu_count, TimeoutError as MpTimeoutError
from pathlib import Path
from typing import List, Optional
from tqdm import tqdm
from .page_scraper import PageScraper
from src.core.models import ScrapeMode
from src.infrastructure.csv_storage import CSVStorage
from src.config import log_debug, log_error
from src.utils.error_tracker import ErrorTracker

POOL_JOIN_TIMEOUT = 60  # seconds to wait for pool workers to finish


def scrape_url_wrapper(url: str, scrape_mode: ScrapeMode = ScrapeMode.FULL):
    try:
        scraper = PageScraper(scrape_mode=scrape_mode)
        results, errors = scraper.scrape(url)
        return url, results, errors
    except Exception as e:
        return url, [], [{"url": url, "category": None, "error": str(e)}]


class ScraperManager:
    def __init__(self, storage=None, max_processes=None, csv_path: Optional[Path] = None):
        if csv_path:
            self.storage = CSVStorage(csv_path=csv_path)
        else:
            self.storage = storage or CSVStorage()
        self.max_processes = max_processes or min(cpu_count(), 4)
        log_debug(f"ScraperManager initialized with {self.max_processes} processes", "scraper_manager.py")

    def run(self, urls: List[str], tracker: ErrorTracker = None, cancel_check=None,
            scrape_mode: ScrapeMode = ScrapeMode.FULL):
        all_results = []

        log_debug(f"Starting scrape batch with {len(urls)} URLs (mode={scrape_mode.value})", "scraper_manager.py")

        # Create a worker partial with the fixed scrape_mode
        worker = partial(scrape_url_wrapper, scrape_mode=scrape_mode)

        pool = Pool(processes=self.max_processes)
        try:
            iterator = pool.imap_unordered(worker, urls)

            with tqdm(total=len(urls), desc="Scraping URLs", unit="url") as pbar:
                processed_count = 0
                while processed_count < len(urls):
                    if cancel_check and cancel_check():
                        log_debug("Cancellation detected. Terminating scraper pool.", "scraper_manager.py")
                        pool.terminate()
                        break

                    try:
                        # Wait up to 2 seconds for a result so we can check cancellation frequently
                        url, p_data_list, errors = iterator.next(timeout=2.0)

                        if p_data_list:
                            all_results.extend(p_data_list)
                        if errors and tracker:
                            for err in errors:
                                tracker.record_scrape_error(err["url"], err["error"], err.get("category"))

                        processed_count += 1
                        pbar.update(1)
                    except MpTimeoutError:
                        continue
                    except StopIteration:
                        break
        finally:
            _drain_and_terminate_pool(pool)

        if all_results:
            log_debug(f"Saving {len(all_results)} records to CSV", "scraper_manager.py")
            self.storage.save(all_results)
        else:
            log_debug("No results to save - all_results is empty", "scraper_manager.py")
            print("[WARNING] No data was scraped. Check URLs and scraper errors.")

        if tracker and tracker.scrape_errors:
            log_debug(f"Batch completed with {len(tracker.scrape_errors)} scrape errors", "scraper_manager.py")
        else:
            log_debug("Batch completed successfully with no errors", "scraper_manager.py")


def _drain_and_terminate_pool(pool: Pool):
    """Safely drain and terminate a multiprocessing pool with a timeout.

    Avoids indefinite hangs when Selenium child processes don't respond
    to SIGTERM during Pool cleanup.
    """
    import threading as _threading
    pool.close()
    joiner = _threading.Thread(target=pool.join, daemon=True)
    joiner.start()
    joiner.join(timeout=POOL_JOIN_TIMEOUT)
    if joiner.is_alive():
        log_debug(
            f"Pool join timed out after {POOL_JOIN_TIMEOUT}s — "
            f"terminating stubborn worker(s) forcefully",
            "scraper_manager.py"
        )
        pool.terminate()
        pool.join()

