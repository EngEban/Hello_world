# Verification report — audit fixes T-01 … T-20

## Update 2026-10-19: after merging the 55 remote commits

- Backend tests: **231 passed** (both sides' suites combined); `check`, migrations check and
  `check --deploy` (production settings with Redis/Postgres URLs) clean.
- Frontend: lint 0 errors, build passes, the remote's 20 Node tests pass.
- Click test (staging mode locally, because production now requires a real Redis): **70/70 passed,
  no browser console errors**.
- Found and fixed after the merge: the public site-settings endpoint was limited to 60 requests/hour per
  IP and is called on every page load, so it throttled normal browsing; raised to 1200/hour plus a
  5-minute browser cache (test added).
- Not re-run after the merge: the 58-screenshot comparison (the remote changed the design, so the old
  baseline no longer applies). The T-20 design-token consolidation was dropped in favour of the remote's
  brand-colour refresh.


Date: 2026-10-18 · Branch: `resref-workspace` · Commits `ec8a61a` … `454aab5` (16 commits on top of `94e896f`).
Environment: Windows 11, Python 3.14.5 (same as `.python-version` / Dockerfile), Node 24.15 locally
(CI and the Dockerfile use Node 22), Playwright 1.56 / Chromium.

## Summary

| Check | Result |
|---|---|
| Backend tests (`accounts blog dashboard research_analyzer`) | **145 passed** (99 before this work) |
| `manage.py check` | no issues |
| `makemigrations --check --dry-run` | no changes |
| `check --deploy --fail-level WARNING` with production settings | no issues (2 intentionally silenced: HSTS `includeSubDomains`/`preload`, a decision for the final custom domain) |
| `pip-audit -r requirements.txt` | no known vulnerabilities |
| `npm audit --omit=dev --audit-level=moderate` | 0 vulnerabilities |
| `npm run lint` | **0 errors**, 17 warnings (react-hooks/exhaustive-deps and unused vars in untouched files) |
| `npm run build` | passes |
| `/api/health/` on a production-like server | `{"status": "ok", "database": "ok"}` |
| Playwright click test (production-like server) | **70 / 70 steps passed, no browser console errors** |
| Visual regression for the T-20 refactor (58 screenshots, desktop + mobile) | **identical** before/after |
| Docker image build | **not run locally** (Docker is not installed on this machine); covered by the new `docker` CI job |
| No secrets / local data tracked | `git ls-files` shows no `.env`, `*.sqlite3`, `media/`, `.venv`, `node_modules`, `dist`; CI secret scan pattern finds nothing |

## How "like production" was run locally

- Frontend built exactly as the Dockerfile does (`VITE_ASSET_BASE_PATH=/static/ npm run build`), copied to
  `backend/frontend_dist`, then `collectstatic` (WhiteNoise, manifest storage).
- Django with `RESREF_ENV=production`, `DJANGO_DEBUG=false`, `SERVE_FRONTEND_FROM_DJANGO=true`, CSP on,
  Postgres replaced by a **copy** of the developer SQLite DB, media in a scratch folder. Only the
  HTTPS-only flags (SSL redirect, secure cookies, HSTS) were turned off because the local server is plain HTTP.
- WSGI server: `waitress` (gunicorn does not run on Windows). The gunicorn command line itself is only
  exercised on Railway/CI.
- Emails used the console backend; the click test read confirmation/reset links from the server log.

## Click test (Playwright) — 70 steps

- **Public pages (16):** `/`, `/database`, `/articles`, `/tools`, `/faq`, `/about`, `/contact`, `/consultation`,
  `/opportunities`, `/join`, privacy/terms/cookie policies, `/questionnaires`, `/sign-in`, `/register` — all 200 with
  the expected heading. Database pagination (`?page=2`) and search work.
- **404:** unknown URL shows the Not Found page; unknown `/api/…` returns JSON 404.
- **Arabic:** an Arabic article renders and the Arabic text is marked `lang="ar"` / `dir="auto"`;
  the Research Analyzer switches to Arabic (RTL). (The existing database has no real Arabic article;
  the two candidates only had Arabic in image file names, so a test article was published in the DB copy.)
- **Forms:** contact form, Join-the-team application **with PDF CV**, expert-consultation service request,
  newsletter sign-up → confirmation email → `/newsletter/confirm` → confirmed.
- **Accounts:** register → "check your inbox" (not signed in) → password login refused with
  `email_unconfirmed` → confirmation link signs in → logout → login → password reset by emailed link →
  login with the new password.
- **Tools (signed-in member):** Journal Finder (30 matches), Reference Generator DOI lookup via Crossref,
  Sample Size Calculator (428 participants for the default proportion design), Research Analyzer
  (upload CSV, t-test, master report).
- **Dashboard (22 pages load inside the admin shell)** plus actions: create user, header search → posts,
  create draft post, upload image (served from `/media/`), add FAQ question (appears on public FAQ),
  create + publish opportunity (appears on public API), create service, forms list shows the public
  submissions, CV download (admin 200, anonymous 401), newsletter send → queued, save public settings,
  CSV export.
- **Newsletter outbox:** `python manage.py process_outbox` then sent every queued QA campaign
  (14 sent, 0 failed); campaign status `sent`.
- **Tool workspace sync (T-20 hook):** journal shortlist, reference list and sample-size study type are
  autosaved to the account and restored after `localStorage` is cleared.

## Problems found during verification and fixed

1. **CSP blocked Google Fonts and the Google sign-in stylesheet on every page** (pre-existing in production) —
   fixed in `a33d551`, with a test.
2. **Saving a new FAQ question without a category returned 500** (pre-existing) — fixed in `454aab5`, with a test.
3. During T-20 the screenshot suite caught that loading the three tool stylesheets from their pages
   changes the cascade; they were kept global in their original order (documented in `main.jsx`).

## Not verified here (needs the Railway deployment)

- `docker build` and the gunicorn `gthread` runtime (CI `docker` job / Railway build).
- PostgreSQL (tests and the local run use SQLite), Redis-backed throttling, S3/R2 media, real SMTP delivery,
  the Railway cron service, Google sign-in, and a Stripe test-mode checkout with real test keys
  (Stripe code paths are covered by unit tests with SDK objects and signed webhooks only).
- The live site: to be click-tested the same way after the merge and deploy.

## Railway variables

Web service — required: `RESREF_ENV=production`, `DJANGO_DEBUG=false`, `DJANGO_SECRET_KEY`,
`DATABASE_URL=${{Postgres.DATABASE_URL}}`, `SERVE_FRONTEND_FROM_DJANGO=true`, SMTP
(`DJANGO_EMAIL_BACKEND`, `DJANGO_EMAIL_HOST`, `DJANGO_EMAIL_PORT`, `DJANGO_EMAIL_USE_TLS`,
`DJANGO_EMAIL_HOST_USER`, `DJANGO_EMAIL_HOST_PASSWORD`, `DJANGO_DEFAULT_FROM_EMAIL`), and one media option
(R2: `MEDIA_STORAGE=s3` + `AWS_*`; or a volume: `MEDIA_STORAGE=local`, `MEDIA_ROOT=/data/media`, `RAILWAY_RUN_UID=0`).
Recommended: `REDIS_URL=${{Redis.REDIS_URL}}`, `DJANGO_ADMIN_PATH`. Optional: `GOOGLE_OAUTH_CLIENT_ID`,
`CROSSREF_POLITE_EMAIL`, Stripe **test** keys. Cron service: config file `/railway.cron.json` and the same
database/email variables. Details: [DEPLOYMENT.md](../../DEPLOYMENT.md).
