# Deploying to Railway

This project ships **as a single Docker container** that runs:

1. The FastAPI backend (`api_server.py` → REST API at `/api/v1/*`, Swagger at `/docs`).
2. The static frontend (HTML/CSS/JS in `src/visualization/`, mounted at `/visualization/`).
3. Chromium + ChromeDriver, so the scraper / scheduler endpoints work in‑container.

Everything is served by one Uvicorn process on Railway's injected `$PORT`.

---

## 1. Prerequisites

- A Railway account ([railway.com](https://railway.com)).
- A reachable Postgres database. The simplest options:
  - The **existing Supabase project** referenced by `DATABASE_URL` in your `.env`.
  - Or a new Railway Postgres plugin (Railway → New → Database → PostgreSQL).
- This repo pushed to GitHub (Railway pulls from GitHub for auto‑deploys).

---

## 2. Files Railway uses

| File | Purpose |
|---|---|
| `Dockerfile` | Defines the single image (Python 3.12 + uv + Chromium + your code). |
| `railway.json` | Tells Railway to build with the Dockerfile and how to start / health‑check. |
| `.dockerignore` | Keeps `.env`, caches, and local CSV junk out of the image. |

`docker-compose.yml` is **local-dev only** and Railway ignores it (it's in `.dockerignore`).

---

## 3. Environment variables (set in Railway dashboard → Variables)

| Variable | Required | Example |
|---|---|---|
| `DATABASE_URL` | ✅ | `postgresql://USER:PASS@HOST:6543/postgres` (Supabase pooler URL) |
| `TIMEOUT` | optional | `10` |
| `OUTPUT_DIR` | optional | `/app/output` (Dockerfile default) |
| `LOG_DIR` | optional | `/app/log` (Dockerfile default) |
| `PORT` | **do not set** | Railway injects this automatically. |

> Never commit `.env`. The `.dockerignore` already excludes it.

---

## 4. Deploy steps

### Option A — Deploy from GitHub (recommended)

1. Push this branch to GitHub.
2. Railway dashboard → **New Project** → **Deploy from GitHub repo** → pick this repo.
3. Railway will detect `railway.json` + `Dockerfile` and start a build.
4. While the build runs, open the service → **Variables** tab and add `DATABASE_URL` (and any optional vars from the table above).
5. Once the build finishes, Railway will hit `/` for a healthcheck and route public traffic to the service.
6. Open **Settings → Networking → Generate Domain** to get a public URL like `https://<service>.up.railway.app`.

### Option B — Deploy with the Railway CLI

```bash
# one-time
npm i -g @railway/cli
railway login

# from the project root
railway init                                       # link a new Railway project
railway variables --set DATABASE_URL="postgresql://..."
railway up                                         # build + deploy
railway domain                                     # expose a public URL
```

---

## 5. After it's live

Replace `<your-domain>` with the URL Railway gave you:

| Endpoint | URL |
|---|---|
| Home (links to everything) | `https://<your-domain>/` |
| Swagger / OpenAPI docs | `https://<your-domain>/docs` |
| Pharmacokinetics viewer (frontend) | `https://<your-domain>/visualization/` |
| Core Data inspector (frontend) | `https://<your-domain>/visualization/core.html` |
| Operations dashboard (frontend) | `https://<your-domain>/visualization/dashboard.html` |
| Health / job stats | `https://<your-domain>/api/v1/operations/health` |
| Scheduler status | `https://<your-domain>/api/v1/scheduler/status` |

---

## 6. Persistent storage for the scraped CSV (recommended)

By default the container's `/app/output` is **ephemeral** — every redeploy wipes
the scraped `pep_pedia_master.csv`. To persist it:

1. Railway service → **Settings → Volumes → Add Volume**
2. Mount path: `/app/output`
3. Redeploy.

The CSV inspector endpoints and the scheduler will now keep state across deploys.
You can do the same with `/app/log` if you want to keep historical logs.

> If you don't add a volume, the scheduler will simply regenerate the CSV on
> its next run (default every 12 hours, or trigger manually via
> `POST /api/v1/sync/core`).

---

## 7. The scheduler runs automatically — disable if you don't want it

`api_server.py` calls `start_scheduler()` on boot with a **12‑hour interval**, so
Railway will start running scraping jobs against `pep-pedia.org` 12 h after
boot, and again every 12 h after that.

To control it after deploy:

```bash
# Pause
curl -X POST https://<your-domain>/api/v1/scheduler/pause

# Resume
curl -X POST https://<your-domain>/api/v1/scheduler/resume

# Change interval
curl -X POST "https://<your-domain>/api/v1/scheduler/start?interval_hours=24"
```

To **never** start the scheduler, edit `api_server.py` and remove the
`start_scheduler()` / `shutdown_scheduler()` calls in `lifespan` before
deploying.

---

## 8. Resources & limits

Selenium + Chromium are memory-hungry. Recommended Railway plan:

- **Memory:** ≥ 1 GB (Chromium alone needs ~300–500 MB during a scrape).
- **CPU:** the default shared CPU is fine; scraping is I/O bound.
- **Disk:** ≥ 1 GB volume if you persist `/app/output`.

If a scrape OOMs, bump the plan or restrict the scheduler's `limit` parameter:

```bash
curl -X POST "https://<your-domain>/api/v1/scheduler/start?interval_hours=12&limit=20"
```

---

## 9. Build sanity-check locally (optional)

```bash
# Build the same image Railway will build
docker build -t peptide-pipeline .

# Run it locally with your .env (just for smoke testing)
docker run --rm -p 8000:8000 --env-file .env peptide-pipeline

# Open http://localhost:8000
```

---

## 10. Troubleshooting

| Symptom | Cause / Fix |
|---|---|
| Healthcheck fails on first deploy | The pool warms up on startup — bump `healthcheckTimeout` in `railway.json` or check `DATABASE_URL`. |
| `RuntimeError: DATABASE_URL environment variable is not set.` | Add `DATABASE_URL` in Railway → Variables and redeploy. |
| Scraper fails with `chrome not reachable` | Make sure the image was built with the new `Dockerfile` (chromium + chromium-driver installed). Re-deploy. |
| `pep_pedia_master.csv` disappears after redeploy | Mount a Railway Volume at `/app/output` (see §6). |
| 502 / connection refused | App is binding the wrong port — confirm the start command uses `$PORT` (it does in `railway.json` and the Dockerfile `CMD`). |
