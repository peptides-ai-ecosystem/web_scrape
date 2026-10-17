"""Request model for the sync-quality evaluation API (``/api/v1/evaluation``)."""
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class EvaluationRequest(BaseModel):
    """
    Request body for triggering a sync-quality evaluation.

    - `limit` restricts how many peptides from the CSV are checked.
    - `output_json` optionally writes the full report to a JSON file on the server.
    """
    limit: Optional[int] = Field(
        None,
        description="Number of peptides (CSV rows) to evaluate. `null` means all available.",
        ge=1,
        examples=[None, 10, 50, 100],
    )
    output_json: Optional[str] = Field(
        None,
        description="Optional server-side file path to write the full evaluation report as JSON. "
                    "If `null`, results are only returned in the job result on retrieval.",
        examples=[None, "/tmp/core_eval_report.json", "/tmp/graph_eval_report.json"],
    )

    @field_validator("limit")
    @classmethod
    def validate_limit(cls, v):
        if v is not None and v < 1:
            raise ValueError("limit must be a positive integer (≥1) if provided.")
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"limit": 10, "output_json": None},
                {"limit": 50, "output_json": "/tmp/eval_report.json"},
                {"limit": None, "output_json": None},
            ]
        }
    }

