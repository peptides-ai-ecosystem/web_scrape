"""Async competitor discovery preview (``/api/v1/vendors/discover/jobs``, AID-2).

The preview reads a store as politely as a scrape run (robots.txt, at least 5 s
between requests per host, a request budget), so it can run for minutes, longer
than any gateway timeout. Starting one therefore only queues a background job
and returns its id; the client polls it. The synchronous ``POST
/vendors/discover`` stays for clients that still use it.
"""

from collections.abc import Callable
from typing import Any

from app.core.errors import ConflictError, NotFoundError, ServiceError
from app.core.job_queue import JobStatus, get_job_queue
from app.core.logging import log_error, log_info
from app.core.sentry import capture_background_failure
from app.services import vendor_target_service

DISCOVER_JOB_ENDPOINT = "/vendors/discover"
# Previews to different stores may overlap, but not without bound: each one
# holds a worker thread for as long as the store's pacing makes it take.
MAX_RUNNING_PREVIEWS = 3

Schedule = Callable[..., Any]


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
    job.start()
    log_info(f"VENDOR DISCOVER STARTED — job={job_id}", "vendors_endpoint")
    try:
        result = vendor_target_service.discover(url, max_products, currency)
        job.progress = 100
        job.complete(result)
        log_info(
            f"VENDOR DISCOVER FINISHED — job={job_id}, requests={result.get('requests_made')}",
            "vendors_endpoint",
        )
    except ServiceError as exc:
        job.fail(exc.detail)
    except Exception as exc:  # noqa: BLE001
        trace_id = capture_background_failure(exc, job="vendor_discover", job_id=job_id)
        log_error(f"Vendor discover job {job_id} failed (trace_id={trace_id}): {exc}", "vendors_endpoint")
        job.fail(str(exc))


class VendorDiscoverController:
    """Starts and reports discovery previews. ``schedule(fn, *args)`` runs ``fn`` after the response."""

    def __init__(self, schedule: Schedule):
        self._schedule = schedule

    def start(self, url: str, max_products: int, currency: str | None) -> dict[str, Any]:
        """Queue a preview. 422 for a bad URL (as the sync route); 409 when too many are running.

        A preview of the same URL that is still running is returned instead of
        a second one: two at once would double the request rate on that host.
        """
        url = vendor_target_service.check_discover_url(url)
        running = _running_previews()
        for job in running:
            if job.parameters.get("url") == url:
                return self._started(job)
        if len(running) >= MAX_RUNNING_PREVIEWS:
            raise ConflictError(f"{MAX_RUNNING_PREVIEWS} previews are already running; try again shortly.")
        job = get_job_queue().create_job(
            DISCOVER_JOB_ENDPOINT, {"url": url, "max_products": max_products, "currency": currency}
        )
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
