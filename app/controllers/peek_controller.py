"""Reference-page peek as a job (``/api/v1/sync/peek``, AWD-17).

A peek drives a headless browser through one page, which takes longer than a
gateway hop should wait, so ``POST /sync/peek`` only queues a job and returns
its id; the client polls ``GET /sync/peek/jobs/{id}``. Nothing is written
anywhere: the job result is the mapped payload (``app/services/peek_service``).

Guard rails:

* **Allow-list.** The URL must be https on a ``PEEK_ALLOWED_HOSTS`` host
  (``app/infrastructure/reference_url.py``); the URL the browser ends on must be
  on the list too, otherwise the result is discarded.
* **Timeout.** The scrape runs on a worker thread and is given up after
  ``PEEK_TIMEOUT_SECONDS``.
* **Few browsers.** At most ``PEEK_MAX_RUNNING`` peeks at once (409 beyond);
  a start for a URL that is already being read returns that job.
* **Memory.** Jobs live in memory; finished ones are dropped after 24 h.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from app.core.config import settings
from app.core.errors import ConflictError, InvalidInputError, NotFoundError
from app.core.job_queue import JobStatus, get_job_queue
from app.core.logging import log_error, log_info
from app.core.sentry import capture_background_failure
from app.infrastructure.reference_url import check_reference_url, final_url_allowed
from app.infrastructure.url_safety import UnsafeTargetURLError
from app.services import peek_service

PEEK_JOB_ENDPOINT = "/sync/peek"
JOB_RETENTION_HOURS = 24

Schedule = Callable[..., Any]


def _active_peeks() -> list:
    return [
        job
        for job in get_job_queue().list_jobs()
        if job.endpoint == PEEK_JOB_ENDPOINT and job.status in (JobStatus.PENDING, JobStatus.RUNNING)
    ]


def _scrape_with_timeout(url: str, seconds: float):
    """Run the blocking scrape on a daemon thread; ``TimeoutError`` after ``seconds``."""
    box: dict[str, Any] = {}

    def work() -> None:
        try:
            box["value"] = peek_service.scrape_reference_page(url)
        except Exception as exc:  # noqa: BLE001 - reported through the job
            box["error"] = exc

    thread = threading.Thread(target=work, name="peek-scrape", daemon=True)
    thread.start()
    thread.join(seconds if seconds > 0 else None)
    if thread.is_alive():
        raise TimeoutError(f"The reference page did not finish loading within {int(seconds)} s.")
    if "error" in box:
        raise box["error"]
    return box["value"]


def _run_peek_task(job_id: str, url: str) -> None:
    job = get_job_queue().get_job(job_id)
    if not job or job.status is JobStatus.CANCELLED:
        return
    job.start()
    log_info(f"PEEK STARTED — job={job_id}", "peek")
    try:
        results, errors = _scrape_with_timeout(url, float(settings.PEEK_TIMEOUT_SECONDS))
        if job.status is JobStatus.CANCELLED:
            return
        if any(not final_url_allowed(data.url) for data in results):
            job.fail("The page redirected away from the configured reference site; nothing was read.")
            return
        if not results:
            reason = errors[0]["error"] if errors else "no data"
            job.fail(f"Nothing could be read from the reference page ({reason}).")
            return
        job.progress = 100
        job.complete(peek_service.build_peek(url, results))
        log_info(f"PEEK FINISHED — job={job_id}", "peek")
    except Exception as exc:  # noqa: BLE001
        trace_id = capture_background_failure(exc, job="sync_peek", job_id=job_id)
        log_error(f"Peek job {job_id} failed (trace_id={trace_id}): {exc}", "peek")
        if job.status is not JobStatus.CANCELLED:
            job.fail(str(exc))


class PeekController:
    """Starts and reports peeks. ``schedule(fn, *args)`` runs ``fn`` after the response."""

    def __init__(self, schedule: Schedule):
        self._schedule = schedule

    def start(self, url: str) -> dict[str, Any]:
        """Queue a peek: 422 for a URL off the allow-list, 409 when too many browsers are busy."""
        try:
            url = check_reference_url(url)
        except UnsafeTargetURLError as exc:
            raise InvalidInputError(f"URL refused: {exc}") from None
        queue = get_job_queue()
        queue.cleanup_old_jobs(hours=JOB_RETENTION_HOURS)
        active = _active_peeks()
        for job in active:
            if job.parameters.get("url") == url:
                return self._started(job)
        if len(active) >= int(settings.PEEK_MAX_RUNNING):
            raise ConflictError("Other pages are being read right now; try again shortly.")
        job = queue.create_job(PEEK_JOB_ENDPOINT, {"url": url})
        self._schedule(_run_peek_task, job.job_id, url)
        return self._started(job)

    @staticmethod
    def _started(job) -> dict[str, Any]:
        return {
            "job_id": job.job_id,
            "status": job.status.value,
            "message": "Peek started. Poll /api/v1/sync/peek/jobs/{job_id}.",
        }

    @staticmethod
    def get_job(job_id: str) -> dict[str, Any]:
        job = get_job_queue().get_job(job_id)
        if job is None or job.endpoint != PEEK_JOB_ENDPOINT:
            raise NotFoundError(f"No peek job '{job_id}'.")
        payload = job.to_dict()
        payload["url"] = job.parameters.get("url")
        return payload
