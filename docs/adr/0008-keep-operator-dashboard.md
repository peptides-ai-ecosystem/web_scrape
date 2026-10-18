# 0008 Keep the operator dashboard

Status: Accepted (2026-10-18)

`app/visualization/` (static HTML, JS and CSS) is served at `/visualization` by `app/factory.py`. It is the operator
dashboard for scrape runs, not dead code, and stays. It is plain static files with no Python dependency: the
Streamlit, Altair and Matplotlib packages dropped earlier are not imported anywhere, and `pyproject.toml` / `uv.lock`
carry none of them. Add a dependency only when code imports it.

Enforced in: `app/factory.py` (the mount), `app/visualization/`.
