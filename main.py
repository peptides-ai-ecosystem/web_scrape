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
from src.mappers.db_import_orchestrator_v2 import DbImportOrchestratorV2
from src.infrastructure.db.service import DbManager
from src.infrastructure.csv_storage import CSVStorage

MODULE_NAME="main"
def scrape_peptides(args) -> None:
    """Crawl URLs and scrape peptide data."""
    start_total = time.time()
    # clear_logs()

    log_debug("Starting scraper execution", MODULE_NAME)

    tracker = ErrorTracker()
    try:
        if getattr(args, "url", None):
            urls = args.url
            print(f"[INFO] Using {len(urls)} directly provided URL(s).")
        else:
            print("[INFO] Crawling peptide URLs...")
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



def db_sync(args) -> None:
    """Sync CSV data to database (v1 — original)."""
    csv_store = CSVStorage()
    rows = csv_store.read()
    if getattr(args, "limit", None) is not None:
        rows = rows[:args.limit]

    tracker = ErrorTracker()
    orchestrator = DbImportOrchestrator()
    print("Starting sync...")
    log_debug("Starting database sync (v1)", MODULE_NAME)
    orchestrator.sync_to_db(os.getenv("DATABASE_URL"), rows, tracker=tracker)
    log_debug("Database sync (v1) completed", MODULE_NAME)
    print("Sync completed.")
    if tracker.has_errors():
        report_path = tracker.save(OUTPUT_DIR / "tracker_report.json")
        tracker.print_summary()
        print(f"[TRACKER] Report saved to {report_path}")
    else:
        print("Sync completed successfully with no errors.")


def db_sync_v2(args) -> None:
    """Sync CSV data to database (v2 — optimized: single tx per row, ON CONFLICT upserts)."""
    csv_store = CSVStorage()
    rows = csv_store.read()
    if getattr(args, "limit", None) is not None:
        rows = rows[:args.limit]

    tracker = ErrorTracker()
    orchestrator = DbImportOrchestratorV2()
    print("Starting sync (v2 optimized)...")
    orchestrator.sync_to_db(os.getenv("DATABASE_URL"), rows, tracker=tracker)
    print("Sync v2 completed.")
    if tracker.has_errors():
        report_path = tracker.save(OUTPUT_DIR / "tracker_report.json")
        tracker.print_summary()
        print(f"[TRACKER] Report saved to {report_path}")
    else:
        print("Sync v2 completed successfully with no errors.")

def delete_peptide(slug: str) -> None:
    """Delete a peptide and its related data by slug."""
    db = DbManager(os.getenv("DATABASE_URL"))
    try:
        deleted = db.delete_peptide_data(slug)
        if deleted:
            print(f"[INFO] Deleted peptide {slug} and its related data.")
        else:
            print(f"[WARNING] Peptide with slug '{slug}' not found.")
    except Exception as e:
        print(f"[ERROR] Failed to delete peptide {slug}: {e}")
    finally:
        db.close()

def setup_argument_parser() -> argparse.ArgumentParser:
    """Configure and return argument parser."""
    parser = argparse.ArgumentParser(
        description="Scrape peptide data and sync to PostgreSQL. "
                    "By default, runs both scrape and sync (v2). "
                    "Use flags to run individual steps."
    )
    parser.add_argument("--delete", metavar="SLUG", help="Delete a peptide and its related data by slug")
    parser.add_argument("--scrape", action="store_true", help="Run scraper only (no sync)")
    parser.add_argument("--sync", action="store_true", help="Run sync only — v1 original (no scraping)")
    parser.add_argument("--sync-v2", action="store_true", dest="sync_v2",
                        help="Run sync only — v2 optimized: single tx/row, ON CONFLICT upserts (no scraping)")
    parser.add_argument(
        "--url", metavar="URL", nargs="+",
        help="One or more direct peptide URLs to scrape (skips crawling)"
    )
    parser.add_argument("--limit", type=int, help="Limit the number of peptides to scrape (for testing)")
    return parser

def main() -> None:
    """Main entry point.

    Default (no flags): runs scrape then sync (v2).
    Individual flags run only that step:
      --scrape     → scrape only
      --sync       → sync v1 only
      --sync-v2    → sync v2 only
    """
    parser = setup_argument_parser()
    args = parser.parse_args()

    if args.delete:
        delete_peptide(args.delete)
        return

    any_flag = args.scrape or args.sync or args.sync_v2

    if not any_flag:
        # Default: run full pipeline
        scrape_peptides(args)
        db_sync(args)
    else:
        if args.scrape:
            scrape_peptides(args)
        if args.sync:
            db_sync(args)
        if args.sync_v2:
            db_sync_v2(args)

if __name__ == "__main__":
    main()
