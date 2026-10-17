"""Competitor price scrape use case (``/api/v1/vendors/scrape*``).

A run coordinates the scrape (``vendor_scrape_runner.run_vendor_scrape``: fetch,
extract, score) with the writes it makes to ``vendor_price_observations``, as a
background job in the in-memory queue. One run at a time: two concurrent runs
would double the request rate against the same hosts. The nightly cron
(``app/core/scheduler.py``) runs the same pipeline.
"""
from typing import Any, Callable, Dict, List, Optional

from app.core.logging import log_error, log_info
from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.core.job_queue import JobStatus, get_job_queue
from app.core.sentry import capture_background_failure
from app.services.vendor_scrape_runner import run_vendor_scrape, select_targets

SCRAPE_JOB_ENDPOINT = "/vendors/scrape"

Schedule = Callable[..., Any]


def _running_scrape_job():
    for job in get_job_queue().list_jobs():
        if job.endpoint == SCRAPE_JOB_ENDPOINT and job.status in (JobStatus.PENDING, JobStatus.RUNNING):
            return job
    return None


def _job_view(job) -> Dict[str, Any]:
    payload = job.to_dict()
    payload["progress_detail"] = getattr(job, "progress_detail", None)
    return payload


def _run_scrape_task(job_id: str, vendors: Optional[List[str]], limit: Optional[int]):
    """Background task wrapper around the shared runner."""
    queue = get_job_queue()
    job = queue.get_job(job_id)
    if not job:
        return

    def on_progress(done: int, total: int) -> None:
        job.progress_detail = {"done": done, "total": total}
        job.progress = int(done * 100 / total) if total else 0

    job.start()
    log_info(f"VENDOR SCRAPE STARTED — job={job_id}, vendors={vendors or 'all enabled'}", "vendors_endpoint")
    try:
        result = run_vendor_scrape(vendors=vendors, limit_per_vendor=limit, on_progress=on_progress)
        job.progress = 100
        job.complete(result)
        log_info(
            f"VENDOR SCRAPE FINISHED — job={job_id}, "
            f"urls={result.get('urls_processed')}, review={result.get('review_counts')}",
            "vendors_endpoint",
        )
    except Exception as exc:  # noqa: BLE001
        # FEEDBACK-3 G15: the run failed as a whole — one Sentry event under
        # its own trace_id (the 202 has already been sent).
        trace_id = capture_background_failure(exc, job="vendor_scrape", job_id=job_id)
        log_error(f"Vendor scrape job {job_id} failed (trace_id={trace_id}): {exc}", "vendors_endpoint")
        job.fail(str(exc))


class VendorScrapeController:
    """Starts and reports competitor scrape runs. ``schedule(fn, *args)`` runs ``fn`` after the response."""

    def __init__(self, schedule: Optional[Schedule] = None):
        self._schedule = schedule

    def trigger(self, vendors: Optional[List[str]], limit_per_vendor: Optional[int]) -> Dict[str, Any]:
        """Queue a run; 409 while one is running, 400 when no enabled, approved target matches."""
        running = _running_scrape_job()
        if running is not None:
            raise ConflictError(f"A vendor scrape is already running (job {running.job_id}).")

        targets = select_targets(vendors)
        if not targets:
            raise BadRequestError(
                "No enabled, approved vendor targets match this request. "
                "Add, enable or approve one first."
            )

        queue = get_job_queue()
        job = queue.create_job(
            SCRAPE_JOB_ENDPOINT,
            {
                "vendors": [t.slug for t in targets],
                "limit_per_vendor": limit_per_vendor,
            },
        )
        job.progress_detail = {"done": 0, "total": None}
        self._schedule(_run_scrape_task, job.job_id, [t.slug for t in targets], limit_per_vendor)
        return {
            "job_id": job.job_id,
            "status": job.status.value,
            "vendors": [t.slug for t in targets],
            "message": "Vendor scrape started. Poll /api/v1/vendors/scrape/jobs/{job_id}.",
        }

    @staticmethod
    def list_jobs(limit: int) -> Dict[str, Any]:
        """Recent scrape jobs, newest first, without the per-URL report."""
        jobs = [j for j in get_job_queue().list_jobs() if j.endpoint == SCRAPE_JOB_ENDPOINT]
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        views = []
        for job in jobs[:limit]:
            view = _job_view(job)
            # The list is a summary; the full per-URL report stays on the job read.
            if isinstance(view.get("result"), dict):
                view["result"] = {k: v for k, v in view["result"].items() if k != "observations"}
            views.append(view)
        return {"count": len(views), "jobs": views}

    @staticmethod
    def get_job(job_id: str) -> Dict[str, Any]:
        """One scrape job with ``progress_detail``; 404 for an unknown or non-scrape job."""
        job = get_job_queue().get_job(job_id)
        if job is None or job.endpoint != SCRAPE_JOB_ENDPOINT:
            raise NotFoundError(f"No vendor scrape job '{job_id}'.")
        return _job_view(job)
