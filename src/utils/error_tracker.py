import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class ErrorTracker:
    """Lightweight in-memory error tracker. Call save() at end of run."""

    def __init__(self):
        self.scrape_errors: dict = {}   # url -> {error, ts}
        self.db_errors: list = []       # [{row, stage, error, ts}]

    # ------------------------------------------------------------------ #
    # Scraping
    # ------------------------------------------------------------------ #

    def record_scrape_error(self, url: str, error: str, category: Optional[str] = None):
        key = f"{url}::{category}" if category else url
        self.scrape_errors[key] = {
            "url": url,
            "category": category,
            "error": str(error),
            "ts": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------ #
    # DB sync
    # ------------------------------------------------------------------ #

    def record_db_error(self, row_id: str, stage: str, error: Exception):
        self.db_errors.append({
            "row": row_id,
            "stage": stage,
            "error": str(error),
            "ts": datetime.now(timezone.utc).isoformat(),
        })

    # ------------------------------------------------------------------ #
    # Reporting
    # ------------------------------------------------------------------ #

    def has_errors(self) -> bool:
        return bool(self.scrape_errors or self.db_errors)

    def save(self, path: Path) -> Path:
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "scrape_errors": len(self.scrape_errors),
                "db_errors": len(self.db_errors),
            },
            "scrape_errors": self.scrape_errors,
            "db_errors": self.db_errors,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        return path

    def print_summary(self):
        print(f"[TRACKER] Scrape errors: {len(self.scrape_errors)} | DB errors: {len(self.db_errors)}")
