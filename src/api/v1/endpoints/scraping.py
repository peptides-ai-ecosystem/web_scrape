
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
import time

from src.utils.crawl_peptide_urls import crawl_peptide_urls
from src.services.scraper_manager import ScraperManager
from src.config import log_debug, log_error, OUTPUT_DIR
from src.utils.error_tracker import ErrorTracker
from src.core.job_queue import get_job_queue


router = APIRouter()

class AutoScrapeRequest(BaseModel):
    limit: Optional[int] = None

class TargetedScrapeRequest(BaseModel):
    urls: List[str]

def run_scraper_task(job_id: str, urls: List[str], limit: Optional[int]):
    queue = get_job_queue()
    job = queue.get_job(job_id)
    if not job:
        return
    
    job.start()
    tracker = ErrorTracker()
    try:
        if limit:
            urls = urls[:limit]
        
        log_debug(f"Starting ScraperManager for {len(urls)} URLs", "scraping_endpoint")
        manager = ScraperManager()
        manager.run(urls, tracker=tracker)
        
        job.complete({
            "urls_scraped": len(urls),
            "errors": len(tracker.scrape_errors) if tracker.has_errors() else 0
        })
    except Exception as e:
        log_error(f"Fatal error during scraping background task: {e}", "scraping_endpoint")
        job.fail(str(e))
    finally:
        if tracker.has_errors():
            report_path = tracker.save(OUTPUT_DIR / "tracker_report.json")
            tracker.print_summary()


@router.post("/start")
async def start_auto_scraping(request: AutoScrapeRequest, background_tasks: BackgroundTasks):
    """
    Trigger the peptide scraping process with automatic URL crawling.
    Returns job_id for tracking progress.
    """
    urls = crawl_peptide_urls()
    if not urls:
        raise HTTPException(status_code=404, detail="No URLs discovered.")
    
    queue = get_job_queue()
    job = queue.create_job("/scraping/start", {"limit": request.limit, "auto_discover": True})
    background_tasks.add_task(run_scraper_task, job.job_id, urls, request.limit)
    
    return job.to_dict()


@router.post("/scrape-urls")
async def start_targeted_scraping(request: TargetedScrapeRequest, background_tasks: BackgroundTasks):
    """
    Trigger the peptide scraping process with a specified list of URLs.
    Returns job_id for tracking progress.
    """
    if not request.urls:
        raise HTTPException(status_code=400, detail="The URLs list cannot be empty.")
    
    queue = get_job_queue()
    job = queue.create_job("/scraping/scrape-urls", {"urls_count": len(request.urls)})
    background_tasks.add_task(run_scraper_task, job.job_id, request.urls, None)
    
    return job.to_dict()
