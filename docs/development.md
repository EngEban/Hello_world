# Development

## Prerequisites

- Python 3.14 (same as `backend/.python-version`, the Dockerfile and CI)
- Node.js 22 (same as the Dockerfile and CI) and npm
- `backend/.env` created from `backend/.env.example` (never commit it)

## Run locally

Backend (PowerShell):

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

`DJANGO_SECRET_KEY` must be set (in `backend/.env` or the shell). Health check:
`http://127.0.0.1:8000/api/health/` returns `{"status": "ok", "database": "ok"}`.

Frontend:

```powershell
cd frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:5173/` (dashboard: `/dashboard/login`). Vite proxies `/api` to Django;
point it elsewhere with `VITE_API_PROXY_TARGET`.

Useful local settings in `backend/.env`:

- `DJANGO_DEBUG=true` for development only (production refuses to start with it).
- `DJANGO_EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend` prints confirmation
  and reset links in the Django console.
- `NEWSLETTER_SEND_INLINE=true` sends newsletters right away instead of waiting for
  `python manage.py process_outbox`.

### تشغيل سريع (بالعربية)

1. الخادم: داخل `backend` أنشئ البيئة `.venv` وثبّت `requirements.txt` ثم شغّل `migrate` و`runserver`.
2. الواجهة: داخل `frontend` نفّذ `npm ci` ثم `npm run dev` وافتح `http://127.0.0.1:5173/`.
3. لا ترفع أبدًا ملفات `.env` أو `db.sqlite3` أو `media` أو `.venv` أو `node_modules` أو `dist`.

## Checks before every push

```powershell
cd backend
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test accounts blog dashboard research_analyzer core usage redirects --parallel 4

cd ..\frontend
npm run lint    # must show 0 errors
npm run build
```

CI (`.github/workflows/ci.yml`) also runs `check --deploy` with production settings, `pip-audit`,
`npm audit`, a tracked-file secret scan and `docker build`. To run the deploy check locally:

```bash
RESREF_ENV=production DJANGO_DEBUG=false DJANGO_SECRET_KEY=<50+ random chars> \
SERVE_FRONTEND_FROM_DJANGO=true PUBLIC_HOSTNAME=resref.example.com REDIS_URL=redis://redis.example.internal:6379/0 FRONTEND_BASE_URL=https://resref.example.com \
python manage.py check --deploy --fail-level WARNING
```

## Conventions

Backend
- Keep views thin: workflows go in the app's `services.py`, read-only queries in `selectors.py`,
  shared helpers in `backend/core/`.
- Function-based JSON views; read the body with `get_payload()` and fields with `text_field`,
  `id_field` and `choice_field` (`core/payload.py`): an absent key keeps the current value,
  bad types are a 400.
- Protect dashboard views with `@api_permission_required('<module>.<action>')`; call
  `log_activity(...)` on every write; never return exception text to the client.
- List endpoints are paginated and must not issue one query per row (use `select_related`,
  `annotate(Count)`, `Prefetch`); add an `assertNumQueries`-style test for new lists.
- Every behaviour change gets a test in the app's `tests.py` (or `test_*.py`).

Frontend
- Call the backend only through `src/api/*Api.js`; pass `{ signal }` from an `AbortController`
  in data effects and ignore `AbortError`.
- Admin-entered links go through `safeHref()`.
- Pages are lazy-loaded in `src/main.jsx`; route errors are handled by `RouteErrorBoundary`.
- Design tokens (CSS custom properties) live only in `src/styles/design-system.css` (`@layer tokens`).
  Keep the global stylesheet order in `main.jsx`: later files intentionally override earlier ones.
- Tool workspaces (local + account sync) use `src/hooks/useToolWorkspace.js`.

### Adding a dashboard module

1. Model in the owning app, serializer in `dashboard/serializers.py`.
2. Views in `dashboard/api/<domain>.py`, routes in `dashboard/api_urls.py`, audit logging.
3. Permission strings in `DASHBOARD_MODULES` / `ROLE_PERMISSIONS` (`dashboard/permissions.py`).
4. Export: add to `EXPORT_SERIALIZERS` and `EXPORT_READ_PERMISSIONS` (`dashboard/api/reports.py`).
5. API method in `frontend/src/api/dashboardApi.js`, page in `src/pages/dashboard/<domain>/`,
   route in `src/main.jsx`, sidebar link in `src/layouts/DashboardLayout.jsx`.

## Integrations

- **Stripe (test mode only):** `STRIPE_SECRET_KEY` must start with `sk_test_`. For local webhooks run
  `stripe listen --forward-to 127.0.0.1:8000/api/accounts/billing/webhook/` and put the printed
  signing secret in `STRIPE_WEBHOOK_SECRET`; set the monthly/yearly Price IDs. Test card 4242 4242 4242 4242.
- **Google sign-in:** hidden until `GOOGLE_OAUTH_CLIENT_ID` is set; add the exact frontend origins
  (local and production) as Authorized JavaScript origins in Google Cloud.
- **Reference lookup:** Crossref (`CROSSREF_POLITE_EMAIL`), optional OpenAlex (`OPENALEX_API_KEY`).
  Website URLs are never fetched server-side (no SSRF).
