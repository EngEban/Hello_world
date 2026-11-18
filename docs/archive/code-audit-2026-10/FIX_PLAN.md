# ResRef — Audit Fix Plan

Source: full audit on 2026-10-18 (backend, frontend, security, DevOps). Finding IDs (B-xx, F-xx, S-xx, D-xx)
match the "ResRef audit" dashboard. Hosting: **Railway** (Dockerfile build). Stripe is **not live yet**.

## Rules for every task

1. One task = one branch + one PR/commit, titled `[T-xx] <title>`. Do not mix tasks.
2. Do not touch files outside the task's scope. Note other bugs under "Discovered" at the bottom.
3. Every task that changes backend behavior adds or updates a test in the app's `tests.py`.
4. Before finishing: `cd backend && python manage.py check && python manage.py makemigrations --check --dry-run && python manage.py test accounts blog dashboard research_analyzer` must pass; frontend tasks must also pass `cd frontend && npm run build`.
5. When done, set the task's status in the table below and list the files changed.
6. Never commit `.env`, `db.sqlite3`, `media/`, `.venv/`, `frontend/dist/`.

## Status

| Task | Phase | Findings | Status | Files changed |
|---|---|---|---|---|
| T-01 | 1 | B-03, S-01 | DONE 2026-10-18 | dashboard/api/users.py, dashboard/tests.py |
| T-02 | 1 | S-02, D-17 | DONE 2026-10-18 | .dockerignore, .gitignore, .gitattributes |
| T-03 | 1 | D-01 | DONE 2026-10-18 | resref/settings.py, resref/urls.py, requirements.txt, .env.example |
| T-04 | 1 | D-04, D-07, Railway | DONE 2026-10-18 | Dockerfile, backend/start.sh, railway.json, resref/settings.py, resref/urls.py |
| T-05 | 1 | D-03, D-05, D-06 | DONE 2026-10-18 | ci.yml, frontend/package.json, package-lock.json, eslint.config.js |
| T-06 | 1 | S-03 | DONE 2026-10-18 | accounts/api_views.py, accounts/tests.py |
| T-07 | 1 | S-04, S-09, S-08 | DONE 2026-10-18 | frontend main.jsx, utils/safeHref.js, SiteFooter, AboutUsPage, HomePrimitives; resref/url_safety.py; dashboard/api/notifications.py, settings.py |
| T-08 | 1 | S-05, B-24 | DONE 2026-10-18 | accounts/security.py, accounts/api_views.py, dashboard/api/auth.py, resref/urls.py, resref/settings.py |
| T-09 | 2 | B-07, B-08, B-21, B-22 | DONE 2026-10-18 | accounts/entitlements.py, accounts/migrations/0009_seed_reference_data.py, accounts/management/commands/seed_reference_data.py, accounts/api_views.py, dashboard/permissions.py, dashboard/serializers.py, dashboard/api/users.py, dashboard/api/posts.py, dashboard/api/settings.py, blog/api_views.py, backend/start.sh, dashboard/tests.py |
| T-10 | 2 | B-09, B-10 | DONE 2026-10-18 | dashboard/outbox.py, dashboard/management/commands/process_outbox.py, dashboard/models.py, dashboard/migrations/0011, dashboard/api/contacts.py, dashboard/api/services.py, dashboard/api/notifications.py, accounts/models.py, accounts/migrations/0010, accounts/notifications.py, accounts/api_views.py, resref/settings.py, railway.cron.json, NewsletterPage.jsx, DEPLOY_RAILWAY.md, .env.example, tests |
| T-11 | 2 | B-06, S-06, B-25 | DONE 2026-10-18 (signed pickle instead of parquet: exact dtypes, no pyarrow) | research_analyzer/models.py, migrations/0001_initial.py, session_store.py, views.py, services/data_service.py, management/commands/cleanup_analyzer_sessions.py, tests/test_api.py, resref/settings.py, resref/urls.py, start.sh, .env.example |
| T-12 | 2 | B-05, B-26 | DONE 2026-10-18 (see decision below) | accounts/entitlements.py, accounts/api_views.py, accounts/api_urls.py, blog/api_views.py, research_analyzer/views.py, frontend accountApi.js, JournalFinderPage.jsx, tests |
| T-13 | 2 | B-13 | DONE 2026-10-18 | dashboard/public_forms.py, blog/api_urls.py, dashboard/api/contacts.py (CV download), dashboard/api_urls.py, dashboard/serializers.py, dashboard/models.py + migration 0012, publicWebsiteApi.js, RequestForm.jsx, ContactForm.jsx, JoinOurTeamPage.jsx, ExpertConsultationPage.jsx, ApplicationsPage.jsx, test_platform.py |
| T-14 | 2 | B-17, B-18, B-19, B-34, B-29 | DONE 2026-10-18 | resref/api_errors.py, resref/settings.py, resref/urls.py, dashboard/api/common.py, posts.py, services.py, faq.py, settings.py, contacts.py, auth.py, accounts/api_views.py, tests |
| T-15 | 2 | F-01, F-11, F-19 | DONE 2026-10-18 | main.jsx, components/RouteErrorBoundary.jsx, layouts/ResRefPublicLayout.jsx, layouts/DashboardLayout.jsx, api/apiClient.js, api/dashboardApi.js, contexts/AccountContext.jsx, pages/dashboard/auth/LoginPage.jsx, styles/polish.css, eslint.config.js |
| T-16 | 2 | F-02, F-03, F-04, F-08, F-09, F-10 | DONE 2026-10-18 | components/public/PublicPagination.jsx, DatabasePage.jsx, LearningArticlesPage.jsx, main.jsx, dashboard/posts/index.jsx, researchAnalyzer components (5), DynamicContentPage.jsx, ResearchOpportunitiesPage.jsx, publicWebsiteApi.js, polish.css |
| T-17 | 3 | B-01, B-04, B-14 | DONE 2026-10-18 (test mode only) | accounts/billing.py, accounts/api_views.py, accounts/tests.py |
| T-18 | 3 | S-15, S-16, S-10, S-14 | DONE 2026-10-18 (owner chose: confirm email before first sign-in; newsletter double opt-in) | accounts/api_views.py, api_urls.py, models.py + migration 0011, blog/api_views.py, blog/api_urls.py, blog/search.py, dashboard/models.py + migration 0013, dashboard/api/contacts.py, reports.py, serializers.py, research_analyzer/services/data_service.py, resref/settings.py, frontend AccountAuthPage, ConfirmEmailPage, NewsletterConfirmPage, NewsletterPage, main.jsx, APIs, DEPLOY_RAILWAY.md, tests |
| T-19 | 4 | Cleanup: B-30, B-31, F-16, D-10, D-12, D-18 | DONE 2026-10-18 | deleted 5 backend scripts, blog/views+urls, dashboard/views+urls+api_views, accounts/views, empty templatetags + migration_tools, render.yaml, scripts/ (Render), 15 unreachable frontend files, duplicate public/journal-finder/*; docs merged into README.md, DEVELOPMENT.md, DEPLOYMENT.md (17 old docs removed) |
| T-20 | 4 | Refactor: B-36, F-05, F-14, F-15, F-18 | DONE 2026-10-18 (58-screenshot visual regression identical; tool CSS kept global, see commit) | backend/core/ (payload, errors, pagination, permissions; resref/api_errors.py moved), accounts|blog|dashboard services.py + selectors.py, dashboard/api/common.py; frontend main.jsx (lazy DashboardLayout), admin.css/research-analyzer.css loaded by their components, design-system.css @layer tokens (124 tokens consolidated), hooks/useToolWorkspace.js, features/journalFinder/journalFinderModel.js, features/sampleSizeCalculator/sampleSizePageParts.jsx, README/DEVELOPMENT |

---

## Phase 1 — Critical and security (do first, in order)

### T-01 Admin user edits: rollback on 403 and role hierarchy (B-03, S-01)
- File: `backend/dashboard/api/users.py` (`save_user_api`), helpers in `backend/dashboard/permissions.py`.
- Problem: a 403 is returned *after* `user.save()` inside `transaction.atomic()`, so the change is committed. Also a non-super admin can edit email/password of a user who holds the `super_admin` AccountRole but is not a Django superuser.
- Do: compute all permission decisions **before any write**. Treat a target as protected if `user.is_superuser` OR their account role has `is_super_admin=True`. A non-super admin must not change email, password, role, `is_staff`, `is_superuser` or `is_active` of a protected user or of any user at their own level or above.
- Tests: (a) non-super admin posts `{first_name:'X', is_staff:true, account_role:'super_admin'}` → 403 and DB unchanged; (b) non-super admin cannot change password/email of a super_admin-role user → 403.

### T-02 Docker build must not include secrets or the local DB (S-02)
- Files: `.dockerignore`, `.gitignore`.
- Do: replace root-only patterns with `**/.env`, `**/.env.*`, `!**/.env.example`, `**/*.sqlite3`, `**/.venv`, `**/venv`, `**/node_modules`, `**/dist`, `backend/media`, `backend/staticfiles`, `backend/frontend_dist`, `product-audit/`, `**/*.pdf`. In `.gitignore` add `backend/frontend_dist/`, `.venv/` at any depth.
- Check: `git ls-files backend/.env backend/db.sqlite3` prints nothing.

### T-03 Uploaded media works in production and survives deploys (D-01)
- Files: `backend/resref/settings.py`, `backend/resref/urls.py`, `backend/requirements.txt`, `backend/.env.example`.
- Do: support two modes chosen by env:
  1. **Object storage** (preferred): if `MEDIA_STORAGE=s3`, use `django-storages[s3]` (`storages.backends.s3.S3Storage`) with `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_ENDPOINT_URL` (works with Cloudflare R2), `AWS_S3_CUSTOM_DOMAIN` optional, `AWS_QUERYSTRING_AUTH=False` for public images. Use Django 5 `STORAGES = {"default": ..., "staticfiles": ...}` and keep WhiteNoise for static.
  2. **Volume** (fallback): `MEDIA_ROOT` from env `MEDIA_ROOT` (e.g. Railway volume mounted at `/data/media`), and serve `/media/` in production via `django.views.static.serve` **only for safe types** (images, pdf) with `Content-Disposition: attachment` for pdf/docx and `X-Content-Type-Options: nosniff`. CV files (job applications) must NOT be publicly served: serve them through an authenticated dashboard endpoint instead.
- Document all new env vars in `backend/.env.example`.
- Tests: with `DEBUG=False` and volume mode, `GET /media/<existing image>` → 200; CV path → 404/403 without login.

### T-04 Railway runtime: hosts, proxy, gunicorn, non-root (D-04, D-07)
- Files: `Dockerfile`, `backend/resref/settings.py`, new `railway.json`, delete `render.yaml` (keep a copy only if still used — it is not).
- Do:
  - settings: also append `RAILWAY_PUBLIC_DOMAIN` (Railway injects it) to `ALLOWED_HOSTS`, and to `CSRF_TRUSTED_ORIGINS` as `https://<domain>`, same as the existing `RENDER_EXTERNAL_HOSTNAME` logic. Default `DEBUG` to `False` (S-07) and raise `ImproperlyConfigured` if `DEBUG` is on while `RESREF_ENV=production`.
  - Dockerfile: create a non-root user and `USER app`; `CMD` must `exec gunicorn ... --worker-class gthread --threads 4 --max-requests 200 --max-requests-jitter 50 --timeout 120`. Move `migrate` out of `CMD` into Railway's pre-deploy command. `ensure_staging_admin` must never crash the container (log and continue when env vars are partial).
  - `railway.json`: builder `DOCKERFILE`, `deploy.preDeployCommand` = `python manage.py migrate --noinput`, `deploy.healthcheckPath` = `/api/health/`, restart policy `ON_FAILURE`.
  - `/api/health/` should run `SELECT 1` on the DB and return 503 if it fails (B-38).
- Python version: one value everywhere (`backend/.python-version`, Dockerfile, CI). Use 3.13 unless all deps are confirmed on 3.14.

### T-05 CI green and meaningful (D-03, D-05, D-06, F-24)
- Files: `.github/workflows/ci.yml`, `frontend/package.json`, `frontend/package-lock.json`.
- Do: move `vite` and `@vitejs/plugin-react` to `devDependencies`; bump `dompurify` to `>=3.4.17`; `npm audit fix`. CI: `setup-python` with `python-version-file: backend/.python-version`; Node 22 (same as Dockerfile); add steps `makemigrations --check --dry-run`, `check --deploy` with production-like env, and a `docker build .` job. Add `"lint"` script + minimal ESLint (react-hooks) config.

### T-06 Google sign-in account linking (S-03)
- File: `backend/accounts/api_views.py` (Google login, ~line 294).
- Do: link Google to an existing account only if that account's email is verified (or the account has no usable password). Reject if the profile already has a different `google_subject`. Reject `is_active=False`. Return generic error text (S-14), log details.
- Tests for each rule.

### T-07 Redirect and URL safety (S-04, S-09, S-08)
- Files: `frontend/src/main.jsx` (~65-75), `backend/dashboard/api/notifications.py` (~385), `backend/dashboard/api/settings.py`, new `frontend/src/utils/safeHref.js`, `SiteFooter.jsx`, `AboutUsPage.jsx`.
- Do: build the redirect from the configured origin and assert same origin (no `//evil.com`). Reject `action_url` starting with `//` or `/\`. Validate URL-type site settings server-side (http/https/mailto/tel or relative only); use `safeHref()` for every admin-controlled link.

### T-08 Brute force protection (S-05, B-24)
- Files: `backend/accounts/security.py`, `backend/resref/settings.py`, `backend/resref/urls.py`.
- Do: cache backend from env `REDIS_URL` (Railway Redis) using `django.core.cache.backends.redis.RedisCache`; in production refuse to start with LocMem. Add a per-account counter (ignoring IP) and a per-IP global counter on login. Protect `/admin/` login with the same throttle (or move admin to a secret path from env `DJANGO_ADMIN_PATH`).

---

## Phase 2 — Stability, performance, broken features

### T-09 Query count (B-07, B-08, B-21, B-22)
- Stop calling `ensure_default_entitlements()` per request (seed via a data migration + idempotent command `seed_reference_data`). Memoize role/permissions on `request`. Role filter in `users.py` as ORM `Q`. Use `annotate(Count)` / `Prefetch` in `blog/api_views.py` categories & FAQ and in dashboard taxonomy/authors.
- Tests with `assertNumQueries`: `/api/accounts/me/` ≤ 10, `/api/dashboard/users/?per_page=10` ≤ 15.

### T-10 Background jobs (B-09, B-10)
- Newsletter send and opportunity notifications must not run inside the request. Minimal option without a worker service: create the campaign with status `queued` and a management command `process_outbox` run by a Railway cron service every 5 min. Opportunity notifications: one broadcast row + per-user read state, dedupe per opportunity.

### T-11 Research analyzer sessions (B-06, S-06, B-25)
- Store uploaded datasets as parquet files under `MEDIA_ROOT/analyzer/<user_id>/<session>.parquet` (or object storage) + a `AnalyzerSession` model; per-user cap; cleanup command. Check XLSX uncompressed size and column count before full parse. Keep dtypes (no JSON round-trip).

### T-12 Usage metering (B-05, B-26)
- Workspace autosave must not consume usage. Meter only real tool actions (generate reference, run journal match, run analysis/master report). Confirm units with Jamil before changing limits.
- **Decision 2026-10-18** (owner asked Claude to decide; revisit later): limits unchanged. Counted, for signed-in users only:
  successful reference lookup (1), journal match (1), Analyzer test run (1), Analyzer master report (1).
  Not counted: workspace autosave, dataset upload, anonymous use. Single source of truth:
  `METERED_ACTIONS` in `accounts/entitlements.py`. Open question for the owner: require sign-in for all tools?

### T-13 Public application and service-request forms (B-13)
- Add rate-limited, validated `POST /api/applications/` (with CV upload: pdf/docx, size limit) and `POST /api/service-requests/`; point `publicWebsiteApi.js` to them.

### T-14 Robust dashboard input handling (B-17, B-18, B-19, B-34, B-29)
- `get_payload` returns `{}` for non-dict JSON; a `_text()` helper for strings; `parse_int` for ids → 400. Saves update only provided fields (no silent publish, no plan/role reset). One JSON error handler (404/405/403-CSRF/500 as JSON for `/api/`), wrong credentials → 401.

### T-15 Frontend resilience (F-01, F-11, F-19)
- `createBrowserRouter` + `errorElement` (reload once on chunk-load error); Suspense inside layouts. Central 401 handling in `apiClient`; only 401/403 redirect to login. Fix header merge and allow caller `signal`.

### T-16 Broken frontend features (F-02, F-03, F-04, F-08, F-09, F-10)
- Pagination on Database and Learning Articles pages; dashboard posts reads `q`/`new` from URL; analyzer errors use `err.message`; AbortController in data effects; `/articles` routes directly; `/:slug` falls back only on 404 and shows `NotFoundPage`.

---

## Phase 3 — Before turning Stripe on

### T-17 Stripe correctness (B-01, B-04, B-14)
- `as_dict` → `obj.to_dict()`; subscript access on Stripe objects; read period end from `subscription.items.data[0].current_period_end`; tests using `stripe.Event.construct_from(...)` and a signed payload through `construct_event`. Make webhook idempotency atomic (unique constraint on event id).

### T-18 Account hardening (S-15, S-16, S-10, S-14)
- Neutral register response; newsletter double opt-in; `has_dashboard_access` before any role check in `blog/search.py` and per-module read permission in exports; generic error messages.

## Phase 4 — Cleanup and refactor (after phases 1-3)

### T-19 Cleanup
- Delete: `backend/add_services.py`, `restore_services.py`, `setup_smart_citation.py`, `setup.sh`, unrouted `blog/views.py`, `blog/urls.py`, `dashboard/views.py`, `dashboard/urls.py`, `dashboard/api_views.py`, dead frontend files listed in F-16, `python-magic` from requirements. Merge docs into `README.md`, `DEVELOPMENT.md`, `DEPLOYMENT.md` (Railway).

### T-20 Refactor
- Backend: `core/` (errors, payload, pagination, permissions), `services.py` + `selectors.py` per app. Frontend: lazy `DashboardLayout` + its CSS, per-feature CSS, `useToolWorkspace` hook, split 700+ line pages, `design-system.css` as the only token source with `@layer`.

---

## Discovered

- Railway deployment guide: DEPLOYMENT.md (moved from docs/DEPLOY_RAILWAY.md in T-19).
- render.yaml deleted in T-19.
- Production without REDIS_URL logs a RuntimeWarning instead of failing, so the free plan keeps working.
- 2026-10-18: production CSP blocked Google Fonts (Roboto/Comfortaa) and the Google sign-in stylesheet on every
  page — fixed in a separate commit (resref/settings.py, test in dashboard/test_platform.py).
- 2026-10-18: saving a new FAQ question without a category returned 500 (reading an unset non-null FK);
  found by the Playwright click-test, fixed with a regression test.
- 2026-10-18: the four tools are already behind `RequireAccount` in the router, so they already require sign-in.
