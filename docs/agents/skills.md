# Skills — how to use them here

Skills are step-by-step procedures for the recurring tasks of this service. They live in
`.claude/skills/<name>/SKILL.md`, inside this repo, so they work when the repo is opened on its own.

- **Claude Code**: describe the task ("add a competitor", "sync fails on an unknown column") and the matching skill loads by its description, or type `/<skill-name>`.
- **Cursor**: skills are discovered from `.claude/skills/`; describe the task or mention the skill by name.
- Each skill names the real files and commands; run them from the repo root. The workflows in `docs/agents/workflows/` are the short checklists; the mapper and vendor-target ones just point at their skill.
- `tests/ops/test_agent_skills.py` fails when a skill has bad frontmatter, points outside the repo, or names a path that does not exist.

| Skill | Use when | Files it touches |
|---|---|---|
| `adding-a-scraper` | a new kind of site needs a package | `app/scrapers/`, `app/scrapers/registry.py`, `alembic/versions/`, `tests/` |
| `add-a-vendor-target` | a competitor target or how it is read changes | `app/scrapers/vendors/`, `app/infrastructure/url_safety.py`, `config/`, `tests/vendors/` |
| `change-a-mapper` | a sync mapper (group A-F) changes | `app/services/sync/`, `app/repositories/`, `docs/product/sync-schema.md`, `tests/sync/` |
| `platform-schema-dependency` | SQL touches a platform table (XR-8) | `app/repositories/`, `app/repositories/peptide.py`, `contracts/platform-schema/`, `tests/sync/test_platform_schema_contract.py` |
| `debugging-a-scrape` | a call or job fails | `app/api/v1/routers.py`, `app/scrapers/`, `docs/agents/troubleshooting.md` |
