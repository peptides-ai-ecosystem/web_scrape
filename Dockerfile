# syntax=docker/dockerfile:1.7
#
# Single-container image, deployed to the EC2 host by .github/workflows/deploy.yml
# (docker-compose.deploy.yml for production, orchestrator's ms-staging for staging).
#
# This image bundles:
#   * the FastAPI backend  (main.py + src/api/...)
#   * the static frontend  (src/visualization/*.html|css|js — mounted by FastAPI at /visualization/)
#   * Chromium + ChromeDriver for the Selenium-based scraper / scheduler jobs
#     (Playwright, used by the competitor vendor scraper, launches this same
#      Chromium via CHROME_BIN rather than downloading a second browser)
#
# The container binds $PORT at runtime (8000 by default; the host publishes it on
# 8005). Set START_SCHEDULER=false for an API-only container.

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS base

# ---------------------------------------------------------------------------
# 1. System dependencies
#    * chromium + chromium-driver → Selenium scraper
#    * fonts-*                    → correct rendering for scraped pages
#    * ca-certificates / curl     → HTTPS + healthcheck friendliness
# ---------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
        chromium chromium-driver \
        fonts-liberation fonts-noto-color-emoji \
        ca-certificates curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ---------------------------------------------------------------------------
# 2. Python dependencies (cached layer)
#    uv reads pyproject.toml + uv.lock so the environment is reproducible.
# ---------------------------------------------------------------------------
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# ---------------------------------------------------------------------------
# 3. Application source
# ---------------------------------------------------------------------------
COPY src/ ./src/
COPY main.py ./
# The competitor-scrape tables are created on boot from these two files
# (src/infrastructure/db/vendor_schema.py). Without them in the image the
# bootstrap fails and the admin Scrape tab has no tables to use.
COPY migrations/migration_vendor_price_observations.sql migrations/migration_vendor_scrape_targets.sql ./migrations/

RUN uv sync --frozen --no-dev

# ---------------------------------------------------------------------------
# 4. Runtime directories (ephemeral — mount a volume at /app/output to persist
#    the scraped CSV across deploys).
# ---------------------------------------------------------------------------
RUN mkdir -p /app/output /app/log

# FEEDBACK-3 G36: the commit this image was built from, reported by /health,
# so "which code is running on the box?" is answered without reading the box.
# The deploy workflow passes the pushed sha; a local build reports "unknown".
ARG GIT_SHA=unknown

# ---------------------------------------------------------------------------
# 5. Environment
# ---------------------------------------------------------------------------
ENV GIT_SHA=${GIT_SHA}
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    CHROME_BIN=/usr/bin/chromium \
    CHROMEDRIVER_BIN=/usr/bin/chromedriver \
    OUTPUT_DIR=/app/output \
    LOG_DIR=/app/log \
    PORT=8000 \
    PATH="/app/.venv/bin:${PATH}"

EXPOSE 8000

# ---------------------------------------------------------------------------
# 6. Entrypoint — bind to $PORT (falls back to 8000).
#    Using `sh -c` so ${PORT:-8000} is expanded at container start, not build.
# ---------------------------------------------------------------------------
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
