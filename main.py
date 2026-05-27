import argparse
import csv
import os
import sys
import time
from typing import List, Dict, Any
from src.config import ERROR_LOG, clear_logs, log_error, log_debug
from src.utils.crawl_peptide_urls import crawl_peptide_urls
from src.services.scraper_manager import ScraperManager
from src.mappers.db_import_orchestrator import DbImportOrchestrator
from src.infrastructure.db_manager import DbManager

MODULE_NAME="main"
def scrape_peptides() -> None:
    """Crawl URLs and scrape peptide data."""
    start_total = time.time()
    clear_logs()
    
    log_debug("Starting scraper execution", MODULE_NAME)
    print("[INFO] Crawling peptide URLs...")
    
    try:
        urls = crawl_peptide_urls()
        log_debug(f"Found {len(urls)} URLs to scrape", MODULE_NAME)
        print(f"[INFO] Found {len(urls)} URLs to scrape.")

        manager = ScraperManager()
        error_logs = manager.run(urls)

        if error_logs:
            log_debug(f"Scraping completed with {len(error_logs)} errors", MODULE_NAME)
            for error in error_logs:
                log_error(error, "scraper_manager")
            print(f"[INFO] {len(error_logs)} errors logged at {ERROR_LOG}")
        else:
            log_debug("Scraping completed successfully with no errors", MODULE_NAME)
            print("[INFO] Scraping completed successfully!")

    except Exception as e:
        log_error(f"Fatal error during scraping: {e}", MODULE_NAME)
        print(f"[ERROR] Fatal error: {e}")
    finally:
        total_time = round(time.time() - start_total, 2)
        log_debug(f"Total execution time: {total_time} seconds", MODULE_NAME)
        print(f"[INFO] Total scraping time: {total_time} seconds")

def read_csv(csv_path: str, limit: int) -> List[Dict[str, Any]]:
    """Read CSV file with optional row limit."""
    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found at {csv_path}")
        sys.exit(1)

    rows: List[Dict[str, Any]] = []
    with open(csv_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            rows.append(row)
            if i >= int(limit):
                break

    return rows

def sync(csv_path: str, limit: int) -> None:
    """Sync CSV data to database."""
    rows = read_csv(csv_path, limit)
    print(f"Read {len(rows)} rows from {csv_path}")
    
    orchestrator = DbImportOrchestrator()
    print("Starting sync...")
    orchestrator.sync_to_db(os.getenv("DATABASE_URL"), rows)
    print("Sync completed successfully.")

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
    parser.add_argument("--csv", default="peptides.csv", help="Path to the CSV file")
    parser.add_argument("--delete", metavar="SLUG", help="Delete a peptide and its related data by slug")
    parser.add_argument("--limit", type=int, default=100, help="Limit the number of rows to insert")
    parser.add_argument("--scrape", action="store_true", help="Run scraper before sync")
    parser.add_argument("--sync", action="store_true", help="Run sync without scraping")
    return parser

def main() -> None:
    """Main entry point."""
    parser = setup_argument_parser()
    args = parser.parse_args()

    if args.delete:
        delete_peptide(args.delete)
        return

    if args.scrape:
        scrape_peptides()
    if args.sync:
        sync(args.csv, args.limit)

if __name__ == "__main__":
    main()
