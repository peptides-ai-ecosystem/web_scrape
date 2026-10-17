"""Request model for the pep-pedia sync API (``/api/v1/sync``)."""

from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator


class SyncRequest(BaseModel):
    """
    Request body for triggering a sync operation (core, graph, or graph-missing).

    - Omit `urls` (or pass `null`) to **auto-discover** peptide URLs via the crawler.
    - Provide a specific `urls` list for **targeted scraping** of known pages.
    - Use `limit` to cap the number of URLs processed (useful for testing).
    """

    limit: int | None = Field(
        None,
        description="Maximum number of URLs to scrape & sync. `null` means unlimited (process all discovered or provided URLs).",
        ge=1,
        examples=[5, 10, 50],
    )
    urls: list[str] | None = Field(
        None,
        description="Specific peptide page URLs to scrape. When `null` or empty, URLs are auto-discovered via the peptide URL crawler.",
        examples=[None, ["https://pep-pedia.org/peptide/1", "https://pep-pedia.org/peptide/2"]],
    )
    fill_empty_only: bool = Field(
        False,
        description=(
            "Never overwrite curated data. `/core`: only empty columns of the matched peptide "
            "row are filled (no insert), and child rows (benefits, side effects, interactions, "
            "indications, references, protocols + dosages) are added only for kinds the peptide "
            "has none of. `/graph`: PK curves are written only for peptides with no graph rows. "
            "`/graph-missing` never overwrites, so the flag changes nothing there. "
            "Default `false` keeps the existing behaviour."
        ),
    )

    @field_validator("limit")
    @classmethod
    def validate_limit(cls, v):
        if v is not None and v < 1:
            raise ValueError("limit must be a positive integer (≥1) if provided.")
        return v

    @field_validator("urls")
    @classmethod
    def validate_urls(cls, v):
        if not v:
            return v
        cleaned = []
        for url in v:
            if not isinstance(url, str) or not url.strip():
                raise ValueError("urls must be a list of non-empty strings.")
            candidate = url.strip()
            parsed = urlsplit(candidate)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                raise ValueError(
                    f"Invalid URL '{candidate}'. Must be an absolute http(s) URL, "
                    "e.g. 'https://pep-pedia.org/peptide/bpc-157'."
                )
            cleaned.append(candidate)
        return cleaned

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"limit": 5, "urls": None},
                {"limit": 10, "urls": ["https://pep-pedia.org/peptide/1"]},
                {"limit": None, "urls": ["https://pep-pedia.org/peptide/1", "https://pep-pedia.org/peptide/2"]},
            ]
        }
    }
