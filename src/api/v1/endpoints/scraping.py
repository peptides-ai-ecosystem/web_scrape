
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
import time

from src.utils.crawl_peptide_urls import crawl_peptide_urls
from src.services.scraper_manager import ScraperManager
from src.config import log_debug, log_error, OUTPUT_DIR
from src.utils.error_tracker import ErrorTracker


router = APIRouter()

class AutoScrapeRequest(BaseModel):
    limit: Optional[int] = None

class TargetedScrapeRequest(BaseModel):
    urls: List[str]

def run_scraper_task(urls: List[str], limit: Optional[int]):
    tracker = ErrorTracker()
    try:
        if limit is not None:
            urls = urls[:limit]
        
        log_debug(f"Starting ScraperManager for {len(urls)} URLs", "scraping_endpoint")
        manager = ScraperManager()
        manager.run(urls, tracker=tracker)
    except Exception as e:
        log_error(f"Fatal error during scraping background task: {e}", "scraping_endpoint")
    finally:
        if tracker.has_errors():
            report_path = tracker.save(OUTPUT_DIR / "tracker_report.json")
            tracker.print_summary()


@router.post("/start")
async def start_auto_scraping(request: AutoScrapeRequest, background_tasks: BackgroundTasks):
    """
    Trigger the peptide scraping process with automatic URL crawling.
    """
    urls = crawl_peptide_urls()
    if not urls:
        raise HTTPException(status_code=404, detail="No URLs discovered.")
        
    background_tasks.add_task(run_scraper_task, urls, request.limit)
    return {"message": "Auto-scraping started in the background", "urls_count": len(urls), "limit": request.limit}


@router.post("/scrape-urls")
async def start_targeted_scraping(request: TargetedScrapeRequest, background_tasks: BackgroundTasks):
    """
    Trigger the peptide scraping process with a specified list of URLs.
    """
    if not request.urls:
        raise HTTPException(status_code=400, detail="The URLs list cannot be empty.")
        
    background_tasks.add_task(run_scraper_task, request.urls, None)
    return {"message": "Targeted scraping started in the background", "urls_count": len(request.urls)}
