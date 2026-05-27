import time
from src.config import  ERROR_LOG, DEBUG_LOG, clear_logs, log_error, log_debug
from src.utils.crawl_peptide_urls import crawl_peptide_urls
from src.services.scraper_manager import ScraperManager

if __name__ == "__main__":
    start_total = time.time()
    
    # Clear logs at start of execution
    clear_logs()
    
    log_debug("Starting scraper execution", "main.py")
    print("[INFO] Crawling peptide URLs...")
    
    try:
        urls = crawl_peptide_urls()
        log_debug(f"Found {len(urls)} URLs to scrape", "main.py")
        print(f"[INFO] Found {len(urls)} URLs to scrape.")

        # Instantiate manager and run
        manager = ScraperManager()
        error_logs = manager.run(urls)

        # Save error log
        if error_logs:
            log_debug(f"Scraping completed with {len(error_logs)} errors", "main.py")
            for error in error_logs:
                log_error(error, "scraper_manager")
            print(f"[INFO] {len(error_logs)} errors logged at {ERROR_LOG}")
        else:
            log_debug("Scraping completed successfully with no errors", "main.py")
            print("[INFO] Scraping completed successfully!")

    except Exception as e:
        log_error(f"Fatal error during scraping: {e}", "main.py")
        print(f"[ERROR] Fatal error: {e}")
    finally:
        total_time = round(time.time() - start_total, 2)
        log_debug(f"Total execution time: {total_time} seconds", "main.py")
        print(f"[INFO] Total scraping time: {total_time} seconds")
