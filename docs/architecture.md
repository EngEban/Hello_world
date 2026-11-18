# Architecture

## Request flow

```text
Browser ──► Django (gunicorn, one Railway service)
            ├── /api/...          JSON API (accounts, blog, dashboard, usage, research analyzer)
            ├── /static/...       Built React assets (WhiteNoise, long-term cached)
            ├── /media/...        Uploaded images/PDFs (Railway volume or S3/R2)
            ├── /robots.txt, /sitemap.xml, /llms.txt
            └── every other URL   index.html with server-rendered SEO tags (resref/seo.py),
                                  then the React SPA takes over in the browser
PostgreSQL (data) · Redis (rate limits, login lockouts, usage counters cache) · Cron service (newsletter outbox)
```

- The SPA calls `/api/...` on the same origin with session cookies + CSRF. Every `/api/` error is JSON
  (`{success: false, error}`).
- Authorization is enforced server-side: dashboard views use `@api_permission_required('<module>.<action>')`
  with roles from `backend/dashboard/permissions.py` (`viewer`, `contributor`, `editor`, `admin`; super admins
  are Django superusers or the `super_admin` account role).
- Premium-capable tool actions go through the usage engine (`backend/usage/`), which counts per user (or per IP
  for visitors) with race-safe counters and limits editable in the dashboard.
- Newsletters are queued; `python manage.py process_outbox` (Railway cron) sends them through SMTP (Brevo).

## Backend (`backend/`)

| Path | Responsibility |
|---|---|
| `resref/` | Project package: `settings.py` (all configuration from env vars), `urls.py` (root routes, health check, media serving, SPA fallback), `seo.py` (server-rendered meta, JSON-LD, sitemap, robots, llms.txt), `wsgi.py` |
| `core/` | Shared infrastructure: JSON error middleware, request-size limit, payload parsing, pagination, permission decorators, log masking, optional Sentry |
| `accounts/` | Members: registration, login/lockout, email verification, password reset/change, email change, data export/deletion, profiles (country, phone), roles, plans, feature entitlements, Stripe (test mode), notifications, security emails (`templates/accounts/email/`) |
| `usage/` | Usage-limit engine: policies per tool, counters per day/month, `gate()` / `@metered`, `/api/usage/` endpoints, dashboard enforcement API |
| `blog/` | Public content API: posts, pages, categories, tags, authors, FAQ, search, reference lookup (Crossref/OpenAlex), contact and newsletter forms, image optimisation; `wordpress/` + `management/commands/import_wordpress.py` for the WordPress import |
| `dashboard/` | Admin API (`api/<domain>.py`: posts, media, users, contacts, services, settings, reports, notifications, faq, stats), models for forms/opportunities/services/newsletter, permissions, serializers, newsletter outbox |
| `research_analyzer/` | Dataset upload and parsing, statistics engine (`services/`), disk-backed analysis sessions; see its README |
| `redirects/` | Legacy URL redirects (table + WordPress rules) and the WordPress import ledger |
| `start.sh` | Container entrypoint: fixes volume ownership, drops to the non-root user, runs gunicorn |

Conventions: views stay thin; write workflows live in `services.py`, read-only queries in `selectors.py`.
Each app keeps its tests next to it (`tests.py`, `test_<area>.py` or `tests/`).

## Frontend (`frontend/`)

| Path | Responsibility |
|---|---|
| `src/main.jsx` | Router (all routes), global stylesheet order, lazy-loaded pages |
| `src/layouts/` | `ResRefPublicLayout` (header, footer, consent, scroll-in motion) and `DashboardLayout` (sidebar, top bar, command palette) |
| `src/pages/site/` | Public pages (home, database, learn, tools hub, tool pages, about, contact, FAQ, legal, 404) |
| `src/pages/public/` | CMS-driven pages: articles, managed pages, author profiles |
| `src/pages/account/` | Sign-in/register, account hub, password reset, email confirmation |
| `src/pages/dashboard/<domain>/` | Dashboard screens (posts, media, users, contacts, services, settings, reports, tools, home) |
| `src/components/common/` | App-wide pieces: `LoadingState`, `RouteErrorBoundary` |
| `src/components/public/` | Public site components (header, footer, page hero, cards, forms, search, consent) |
| `src/components/account/`, `dashboard/`, `home/` | Components for those areas (dashboard UI kit: `DashboardPrimitives`, `ActionMenu`, `ChipPicker`, `MediaPicker`) |
| `src/features/` | Self-contained tool logic: `journalFinder/`, `referenceGenerator/`, `sampleSizeCalculator/`, `researchAnalyzer/` |
| `src/api/` | `apiClient.js` (CSRF, timeouts, 401 event) and one module per API area |
| `src/hooks/` | Shared hooks (`useToolWorkspace`, `useToolUsage`) |
| `src/contexts/` | Account and site-settings providers |
| `src/config/` | Site paths, content structure, editable-settings schema, hero images, image catalog |
| `src/data/` | Static data (Journal Finder list as fetched JSON, keyword maps) |
| `src/utils/` | SEO meta, analytics/consent, safe links, article HTML clean-up, image helpers |
| `src/styles/global/` | Global stylesheets loaded in a fixed order from `main.jsx` (`brand-ui.css` = the shared design system) |
| `src/styles/pages/` | Per-page styles imported by the page that uses them |
| `src/styles/tools/` | Research-tool styles |
| `src/styles/dashboard/` | Dashboard styles (loaded with the dashboard layout) |
| `public/` | Static files copied as-is: logos, hero images, optimised article images, social image |
| `tests/` | Node test runner checks (brand palette, SEO, routing helpers, performance guards) |

Design system: tokens and shared classes (`rh-*`) live in `src/styles/global/brand-ui.css`; headings use Georgia,
UI text Roboto; brand colours are navy `#062b80`, blue `#126ac6`, sky `#4fb9fc`. Gradients are reserved for hero
and feature backgrounds; buttons and badges use solid colours.

## Data and integrations

- PostgreSQL in production (`DATABASE_URL`), SQLite for local development and tests.
- Redis (`REDIS_URL`) is required in production for shared rate limits and lockouts.
- Email: Django SMTP backend via `DJANGO_EMAIL_*` (Brevo).
- Optional: Google sign-in, GA4 (`GA_MEASUREMENT_ID`), Search Console verification, Sentry (`SENTRY_DSN`),
  Stripe (test keys only until Premium launches), S3/R2 media storage.

## Security summary

Secrets come only from the environment. Production runs with DEBUG off, HTTPS-only cookies, HSTS, CSP, CSRF,
login/password/form rate limits (Redis-backed), a configurable admin path, safe-link checks for admin-entered URLs,
upload type/size validation, private CVs and analyzer data, log masking and a non-root runtime.
Details: [launch/security.md](launch/security.md).
