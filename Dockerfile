# syntax=docker/dockerfile:1.7
#
# Single-container image for Railway.
#
# This image bundles:
#   * the FastAPI backend  (api_server.py + src/api/...)
#   * the static frontend  (src/visualization/*.html|css|js — mounted by FastAPI at /visualization/)
#   * Chromium + ChromeDriver for the Selenium-based scraper / scheduler jobs
#
# The container binds to Railway's $PORT at runtime. Override CMD or set
# `startCommand` in railway.json to disable the scheduler / scraper if you want
# an API-only deploy.

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
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# ---------------------------------------------------------------------------
# 3. Application source
# ---------------------------------------------------------------------------
COPY src/ ./src/
COPY api_server.py main.py ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ---------------------------------------------------------------------------
# 4. Runtime directories (Railway ephemeral by default — mount a Volume at
#    /app/output to persist the scraped CSV across deploys).
# ---------------------------------------------------------------------------
RUN mkdir -p /app/output /app/log

# ---------------------------------------------------------------------------
# 5. Environment
# ---------------------------------------------------------------------------
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
# 6. Entrypoint — bind to Railway-provided $PORT (falls back to 8000 locally).
#    Using `sh -c` so ${PORT:-8000} is expanded at container start, not build.
# ---------------------------------------------------------------------------
CMD ["sh", "-c", "uvicorn api_server:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
