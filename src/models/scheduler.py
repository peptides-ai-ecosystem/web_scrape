"""Request models for the scheduler API (``/api/v1/scheduler``)."""
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class SchedulerConfigRequest(BaseModel):
    """Configuration for the automated background sync scheduler."""
    interval_hours: Optional[float] = Field(
        12.0,
        description="Interval in hours between scheduled sync runs. Defaults to 12.",
        ge=0.0,
        examples=[6.0, 12.0, 24.0],
    )
    interval_minutes: Optional[float] = Field(
        0.0,
        description="Additional interval in minutes. Added to `interval_hours` for finer control.",
        ge=0.0,
        le=59.0,
        examples=[0, 30],
    )
    limit: Optional[int] = Field(
        None,
        description="Maximum URLs to scrape per scheduled run. `null` means unlimited.",
        ge=1,
        examples=[None, 10, 50],
    )

    @field_validator("limit")
    @classmethod
    def validate_limit(cls, v):
        if v is not None and v < 1:
            raise ValueError("limit must be a positive integer (≥1) if provided.")
        return v

    @model_validator(mode="after")
    def validate_interval(self):
        total_hours = (self.interval_hours or 0.0) + (self.interval_minutes or 0.0) / 60.0
        if total_hours <= 0:
            raise ValueError(
                "interval_hours and interval_minutes cannot both be zero — "
                "the scheduler needs a positive interval."
            )
        return self

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"interval_hours": 12.0, "interval_minutes": 0.0, "limit": None},
                {"interval_hours": 6.0, "interval_minutes": 30.0, "limit": 10},
                {"interval_hours": 24.0, "interval_minutes": 0.0, "limit": 50},
            ]
        }
    }


class VendorScrapeScheduleRequest(BaseModel):
    """Cron configuration for the nightly competitor price scrape."""

    hour: int = Field(3, description="Hour of day (server time) to run at.", ge=0, le=23)
    minute: int = Field(15, description="Minute of the hour to run at.", ge=0, le=59)
    vendors: Optional[list[str]] = Field(
        None,
        description="Target slugs to scrape nightly. `null` means every enabled target.",
        examples=[None, ["competitor-a"]],
    )
    limit_per_vendor: Optional[int] = Field(
        None,
        description="Cap on product URLs fetched per vendor per run.",
        ge=1,
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"hour": 3, "minute": 15, "vendors": None, "limit_per_vendor": None},
            ]
        }
    }
