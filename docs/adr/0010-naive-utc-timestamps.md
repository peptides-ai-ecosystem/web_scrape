# 0010 Timestamps stay naive UTC, through one helper

Status: Accepted (2026-10-18)

`datetime.utcnow()` is deprecated, so every call goes through `utc_now_naive()` in `app/core/clock.py`
(`datetime.now(timezone.utc).replace(tzinfo=None)`). Value and `.timestamp()` behaviour are identical to before (job ids
and the job-history cutoff in `app/core/job_queue.py`). Moving to aware timestamps is a separate change.

Enforced in: `app/core/clock.py`, `tests/ops/test_clock.py` (also fails if a `utcnow` call returns).
