# ResRef backend (Django)

Django 5.2 JSON API, admin and management commands. Python version: see `.python-version`.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env      # set DJANGO_SECRET_KEY; never commit .env
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Tests (same set as CI):

```powershell
.\.venv\Scripts\python.exe manage.py test accounts blog dashboard research_analyzer core usage redirects
```

| App | Purpose |
|---|---|
| `resref/` | Settings, root URLs, server-side SEO (`seo.py`) |
| `core/` | Shared middleware, errors, pagination, permissions, logging, monitoring |
| `accounts/` | Members, auth flows, profiles, plans, entitlements, emails |
| `usage/` | Free/Premium usage limits engine |
| `blog/` | Public content API, reference lookup, WordPress import |
| `dashboard/` | Admin API and admin-managed models |
| `research_analyzer/` | Research Analyzer tool |
| `redirects/` | Legacy URL redirects |

Useful commands: `seed_reference_data` (roles, plans, features), `process_outbox` (send queued newsletters),
`import_wordpress --dry-run ...` (see `docs/launch/wordpress-migration.md`), `ensure_staging_admin` (staging only).

More: [`../docs/architecture.md`](../docs/architecture.md), [`../docs/development.md`](../docs/development.md).
