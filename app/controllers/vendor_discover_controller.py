"""Async competitor discovery preview (``/api/v1/vendors/discover/jobs``, AID-2).

The preview reads a store as politely as a scrape run (robots.txt, at least 5 s
between requests per host, a request budget), so it can run for minutes, longer
than any gateway timeout. Starting one therefore only queues a background job
and returns its id; the client polls it. The synchronous ``POST
/vendors/discover`` stays for clients that still use it.

Guard rails:

* **Deadline.** A preview stops after ``VENDOR_DISCOVERY_DEADLINE_SECONDS`` and
  completes with what it has read (``result.stopped_early`` is true), so a slow
  store cannot hold a slot for hours. The preview also honours a robots.txt
  Crawl-delay only up to ``VENDOR_DISCOVERY_MAX_CRAWL_DELAY_SECONDS``.
* **Cancel.** A cancelled job (the operations cancel route) stops
  fetching at its next request and its status is never overwritten.
* **One store at a time.** Each preview builds its own rate limiter, so two
  previews of the same host would double the request rate. A start whose host,
  URL and options all match a running preview returns that job; a different
  URL or options for a host that is busy gets its own job, which waits for the
  host (``pending``) and runs after the first one finishes.
* **Memory.** Jobs live in memory and finished ones are dropped after 24 h
  (checked at each start). A restart loses them: polling an unknown job is 404
  and the client must start the preview again.
"""

import threading
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit

from app.core.config import settings
from app.core.errors import ConflictError, NotFoundError, ServiceError
from app.core.job_queue import JobStatus, get_job_queue
from app.core.logging import log_error, log_info
from app.core.sentry import capture_background_failure
from app.services import vendor_target_service

DISCOVER_JOB_ENDPOINT = "/vendors/discover"
# Previews to different stores may overlap, but not without bound: each one
# holds a worker thread for as long as the store's pacing makes it take.
MAX_RUNNING_PREVIEWS = 3
JOB_RETENTION_HOURS = 24

Schedule = Callable[..., Any]

#: Monotonic clock for the deadline; tests replace it.
_clock: Callable[[], float] = time.monotonic

_host_locks: dict[str, threading.Lock] = {}
_host_locks_guard = threading.Lock()


def _host_of(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def _host_lock(host: str) -> threading.Lock:
    with _host_locks_guard:
        return _host_locks.setdefault(host, threading.Lock())


def _running_previews() -> list:
    return [
        job
        for job in get_job_queue().list_jobs()
        if job.endpoint == DISCOVER_JOB_ENDPOINT and job.status in (JobStatus.PENDING, JobStatus.RUNNING)
    ]


def _job_view(job) -> dict[str, Any]:
    payload = job.to_dict()
    payload["url"] = job.parameters.get("url")
    return payload


def _run_discover_task(job_id: str, url: str, max_products: int, currency: str | None) -> None:
    """Background task: run the blocking preview and store its result on the job."""
    job = get_job_queue().get_job(job_id)
    if not job:
        return
    # One preview per host at a time; a cancel while waiting ends the job here.
    with _host_lock(_host_of(url)):
        if job.status is JobStatus.CANCELLED:
            return
        job.start()
        deadline_seconds = float(settings.VENDOR_DISCOVERY_DEADLINE_SECONDS)
        deadline = _clock() + deadline_seconds if deadline_seconds > 0 else None

        def should_stop() -> bool:
            return job.status is JobStatus.CANCELLED or (deadline is not None and _clock() >= deadline)

        log_info(f"VENDOR DISCOVER STARTED — job={job_id}", "vendors_endpoint")
        try:
            result = vendor_target_service.discover(url, max_products, currency, should_stop=should_stop)
            if job.status is JobStatus.CANCELLED:
                return
            if deadline is not None and _clock() >= deadline and isinstance(result, dict):
                result = {**result, "stopped_early": True}
            job.progress = 100
            job.complete(result)
            log_info(
                f"VENDOR DISCOVER FINISHED — job={job_id}, requests={result.get('requests_made')}",
                "vendors_endpoint",
            )
        except ServiceError as exc:
            if job.status is not JobStatus.CANCELLED:
                job.fail(exc.detail)
        except Exception as exc:  # noqa: BLE001
            trace_id = capture_background_failure(exc, job="vendor_discover", job_id=job_id)
            log_error(f"Vendor discover job {job_id} failed (trace_id={trace_id}): {exc}", "vendors_endpoint")
            if job.status is not JobStatus.CANCELLED:
                job.fail(str(exc))


class VendorDiscoverController:
    """Starts and reports discovery previews. ``schedule(fn, *args)`` runs ``fn`` after the response."""

    def __init__(self, schedule: Schedule):
        self._schedule = schedule

    def start(self, url: str, max_products: int, currency: str | None) -> dict[str, Any]:
        """Queue a preview. 422 for a bad URL (as the sync route); 409 when too many are running.

        A running preview with the same host, URL and options is returned
        instead of a second one.
        """
        url = vendor_target_service.check_discover_url(url)
        queue = get_job_queue()
        queue.cleanup_old_jobs(hours=JOB_RETENTION_HOURS)
        params = {"url": url, "max_products": max_products, "currency": currency}
        running = _running_previews()
        host = _host_of(url)
        for job in running:
            if _host_of(job.parameters.get("url", "")) == host and job.parameters == params:
                return self._started(job)
        if len(running) >= MAX_RUNNING_PREVIEWS:
            raise ConflictError(f"{MAX_RUNNING_PREVIEWS} previews are already running; try again shortly.")
        job = queue.create_job(DISCOVER_JOB_ENDPOINT, params)
        self._schedule(_run_discover_task, job.job_id, url, max_products, currency)
        return self._started(job)

    @staticmethod
    def _started(job) -> dict[str, Any]:
        return {
            "job_id": job.job_id,
            "status": job.status.value,
            "message": "Preview started. Poll /api/v1/vendors/discover/jobs/{job_id}.",
        }

    @staticmethod
    def get_job(job_id: str) -> dict[str, Any]:
        """One preview job (``status``, ``result`` when completed, ``error`` when failed); 404 otherwise."""
        job = get_job_queue().get_job(job_id)
        if job is None or job.endpoint != DISCOVER_JOB_ENDPOINT:
            raise NotFoundError(f"No discover job '{job_id}'.")
        return _job_view(job)
