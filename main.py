import argparse
import os
import time
from dotenv import load_dotenv
from src.config import ERROR_LOG, OUTPUT_DIR, clear_logs, log_error, log_debug
from src.utils.error_tracker import ErrorTracker

load_dotenv()
from src.utils.crawl_peptide_urls import crawl_peptide_urls
from src.services.scraper_manager import ScraperManager
from src.mappers.db_import_orchestrator import DbImportOrchestrator
from src.infrastructure.db_manager import DbManager
from src.infrastructure.csv_storage import CSVStorage

MODULE_NAME="main"
def scrape_peptides(args) -> None:
    """Crawl URLs and scrape peptide data."""
    start_total = time.time()
    # clear_logs()

    log_debug("Starting scraper execution", MODULE_NAME)
    print("[INFO] Crawling peptide URLs...")

    tracker = ErrorTracker()
    try:
        urls = crawl_peptide_urls()
        if args.limit is not None:
            urls = urls[:args.limit]
        log_debug(f"Found {len(urls)} URLs to scrape", MODULE_NAME)
        print(f"[INFO] Found {len(urls)} URLs to scrape.")

        manager = ScraperManager()
        manager.run(urls, tracker=tracker)

    except Exception as e:
        log_error(f"Fatal error during scraping: {e}", MODULE_NAME)
        print(f"[ERROR] Fatal error: {e}")
    finally:
        total_time = round(time.time() - start_total, 2)
        log_debug(f"Total execution time: {total_time} seconds", MODULE_NAME)
        print(f"[INFO] Total scraping time: {total_time} seconds")
        if tracker.has_errors():
            report_path = tracker.save(OUTPUT_DIR / "tracker_report.json")
            tracker.print_summary()
            print(f"[TRACKER] Report saved to {report_path}")



def db_sync() -> None:
    """Sync CSV data to database."""
    csv_store = CSVStorage()
    rows = csv_store.read()

    tracker = ErrorTracker()
    orchestrator = DbImportOrchestrator()
    print("Starting sync...")
    orchestrator.sync_to_db(os.getenv("DATABASE_URL"), rows, tracker=tracker)
    print("Sync completed.")
    if tracker.has_errors():
        report_path = tracker.save(OUTPUT_DIR / "tracker_report.json")
        tracker.print_summary()
        print(f"[TRACKER] Report saved to {report_path}")
    else:
        print("Sync completed successfully with no errors.")

def delete_peptide(slug: str) -> None:
    """Delete a peptide and its related data by slug."""
    db = DbManager(os.getenv("DATABASE_URL"))
    try:
        db.delete_peptide_data(slug)
    finally:
        db.close()

def setup_argument_parser() -> argparse.ArgumentParser:
    """Configure and return argument parser."""
    parser = argparse.ArgumentParser(description="Sync Peptide CSV data to PostgreSQL")
    parser.add_argument("--delete", metavar="SLUG", help="Delete a peptide and its related data by slug")
    parser.add_argument("--scrape", action="store_true", help="Run scraper before sync")
    parser.add_argument("--sync", action="store_true", help="Run sync without scraping")
    parser.add_argument("--limit", type=int, help="Limit the number of peptides to scrape (for testing)")
    return parser

def main() -> None:
    """Main entry point."""
    parser = setup_argument_parser()
    args = parser.parse_args()

    if args.delete:
        delete_peptide(args.delete)
        return

    if args.scrape:
        scrape_peptides(args)
    if args.sync:
        db_sync()

if __name__ == "__main__":
    main()
