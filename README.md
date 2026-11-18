# ResRef

ResRef is a medical research platform:

- **Public website**: research database, learning articles (Mastering Research), questionnaires,
  opportunities, expert consultation, join the team, FAQ and legal pages.
- **Research tools** (for signed-in members): Journal Finder, Reference Generator, Sample Size
  Calculator, Research Analyzer.
- **Member accounts**: email verification, Free/Premium plans with configurable usage limits.
- **Admin dashboard**: content, media, users, inbox and forms, newsletter, opportunities,
  services, reports, premium controls and site settings.

| Layer | Technology | Folder |
|---|---|---|
| Frontend | React 18 + Vite (single-page app, React Router) | [`frontend/`](frontend/README.md) |
| Backend | Django 5.2 JSON API, session auth + CSRF (no DRF/JWT) | [`backend/`](backend/README.md) |
| Hosting | One Docker image on Railway (Django serves the built SPA) + PostgreSQL + Redis + a cron service | [`docs/deployment.md`](docs/deployment.md) |

Active branch: `resref-workspace` (the team's working branch); `main` is the stable branch.

## Quick start (local)

```powershell
# Backend (http://127.0.0.1:8000)
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env          # then set DJANGO_SECRET_KEY
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000

# Frontend (http://127.0.0.1:5173, proxies /api to Django)
cd frontend
npm ci
npm run dev
```

Full setup, tests and conventions: [`docs/development.md`](docs/development.md).

## Repository layout

```text
.
├── backend/                Django project (API, admin, management commands)  → backend/README.md
├── frontend/               React + Vite single-page app                        → frontend/README.md
├── docs/                   All documentation                                   → docs/README.md
│   ├── development.md      Local setup, tests, conventions
│   ├── deployment.md       Railway deployment and environment variables
│   ├── architecture.md     How the pieces fit, folder-by-folder guide
│   ├── launch/             Pre-launch audit results and the launch checklist
│   └── archive/            Older notes, audits and design screenshots (reference only)
├── scripts/                Operations scripts (public image optimisation, local start)
├── .github/workflows/      CI: Django checks/tests/audit, frontend lint/build/audit, Docker build, secret scan
├── Dockerfile              Builds the frontend, then the Django runtime image (non-root)
├── railway.json            Railway web service (pre-deploy migrate, health check)
├── railway.cron.json       Railway cron service (newsletter outbox)
├── compose.yaml            Optional local stack (Postgres + app) with postgres.env.example
└── README.md
```

## Where to start reading

1. [`docs/architecture.md`](docs/architecture.md): the map of the code base.
2. [`docs/launch/README.md`](docs/launch/README.md): what is done and what is left before launch.
3. [`docs/deployment.md`](docs/deployment.md): Railway services and environment variables.

## Golden rules

- Secrets only come from environment variables; never commit `.env`, databases, `media/`,
  `.venv/`, `node_modules/` or `dist/` (enforced by `.gitignore`, `.dockerignore` and a CI secret scan).
- Authorization is always enforced on the server; hiding a button in React is only a convenience.
- Database changes are additive migrations; never edit an existing migration.
- Keep CI green: `manage.py test`, `makemigrations --check`, `npm run lint` (0 errors), `npm run build`.
