# Security and platform — launch notes

Owner summary: the site was already well protected. This audit closed a few
gaps (oversized uploads, a trash-permission bypass, unthrottled endpoints,
tokens in access logs, an outdated image library) and added optional error
reporting. Nothing here needs a decision before launch except the items
marked **Owner decision**.

## What is in place (checked)

| Area | Status |
|---|---|
| HTTPS | `SECURE_SSL_REDIRECT`, HSTS 1 year, secure session/CSRF cookies — all on automatically when `RESREF_ENV=production`. `/api/health/` is exempt from the redirect so Railway's probe works. |
| Proxy | `X-Forwarded-Proto` / `X-Forwarded-For` are trusted only on Railway (`RESREF_TRUST_PROXY`), one hop. |
| Hosts | Railway domain + `PUBLIC_HOSTNAME` added automatically. `*` is now refused in production. |
| Secret key | Required; production now refuses keys shorter than 50 characters or placeholders. |
| CSRF / CORS | Same-origin deployment; CORS only for listed origins; JSON CSRF errors. |
| Headers | CSP (no inline scripts), `X-Frame-Options: DENY`, `nosniff`, Referrer-Policy, Permissions-Policy, COOP. |
| Uploads | Images verified with Pillow (type, size 8 MB, pixel limit); article PDFs checked by signature (12 MB); CVs PDF/DOCX by signature (5 MB), never served from `/media/`, downloaded only by staff with `forms.read`; analyzer datasets private (20 MB). **New:** every request over 25 MB is rejected up front (`DJANGO_MAX_REQUEST_BYTES`). |
| Dashboard permissions | Every dashboard endpoint has a role check (`api_permission_required`); exports need both `reports.export` and read access to that module; privilege/billing changes on users need a super-admin. **Fixed:** moving an article to Trash through the editor's status field now needs `content.delete`, like the bulk action already did. |
| Rate limits (Redis, shared by all workers) | Logins, contact, newsletter subscribe, applications, service requests, unified search, site settings, reference lookup, newsletter send. **New:** newsletter confirmation (30/h per IP) and article search with a query (120/min per IP). |
| Errors | `/api/` always answers JSON; no stack traces (DEBUG is refused in production). |
| Logs | **New:** passwords, tokens, keys and URL `?token=` values are masked in all log lines; gunicorn access log no longer records query strings, referrers or user agents. Optional JSON logs (`DJANGO_LOG_FORMAT=json`). |
| Containers | Non-root `app` user, `.dockerignore` excludes `.env`, databases and media. **New:** on Railway, migrations run only once (pre-deploy), not again in every container; graceful shutdown and keep-alive timeouts set. |
| Database | TLS required in production (`DJANGO_DB_SSL_REQUIRE`, default on); **new** 10 s connect timeout; optional `statement_timeout`. |
| Dependencies | `pip-audit`: Pillow 12.3.0 had 24 known CVEs → upgraded to **13.0.0**; now 0 known. `npm audit --omit=dev`: 0. Dev-only: Vite 8.0–8.1.5 has a high advisory (dev server only, not in the production build) — see requests below. CI runs both audits on every push. |

## Environment variables added

| Name | Purpose | Example |
|---|---|---|
| `DJANGO_MAX_REQUEST_BYTES` | Largest accepted request body (bytes). | `26214400` (25 MB, default) |
| `DJANGO_LOG_FORMAT` | `text` (default) or `json`. | `json` |
| `DJANGO_DB_CONNECT_TIMEOUT` | Seconds to wait for PostgreSQL. | `10` (default) |
| `DJANGO_DB_STATEMENT_TIMEOUT_MS` | Optional per-query time limit; 0 = off. | `30000` |
| `RUN_MIGRATIONS_ON_START` | Force (`true`) or skip (`false`) migrations in `start.sh`. Default: skip on Railway, run elsewhere. | `false` |
| `GUNICORN_GRACEFUL_TIMEOUT`, `GUNICORN_KEEPALIVE` | Gunicorn tuning. | `30`, `5` |
| `SENTRY_DSN` etc. | See `monitoring.md`. | — |

## Database least privilege (recommended, needs Railway)

Railway's default user owns the database. For launch this is acceptable. Later,
create a separate role for the web app that can read/write tables but not
create roles or databases, and keep the owner role only for migrations
(pre-deploy). Never expose the Postgres TCP proxy publicly unless needed; the web
service reaches Postgres on the private network (`postgres.railway.internal`).
If the private connection refuses TLS, set `DJANGO_DB_SSL_REQUIRE=false`
only for that private URL.

## Media storage choice (important)

Use the **Railway volume** (`MEDIA_STORAGE=local`) for launch. With
`MEDIA_STORAGE=s3` (R2) every upload — including applicants' CVs — goes to the
public bucket, so a leaked CV link would open without sign-in. If R2 is wanted
later, CVs first need their own private storage (a model change in
`dashboard/models.py`, `JobApplication.cv_file`).

The start script now lets `RAILWAY_RUN_UID=0` (needed for a root-owned volume)
be used safely: it fixes the media folder's owner and then drops to the
unprivileged `app` user before starting gunicorn.

## Open items

- **Owner decision:** the *contributor* role can publish articles directly
  (it has `content.write`). If contributors should only submit for review,
  the save/bulk endpoints need a `content.publish` permission.
- **Owner decision:** `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS` / `..._PRELOAD`
  — turn on only after the final custom domain and all subdomains use HTTPS.
- After deploy: check headers with `curl -sI https://<domain>/` and
  https://securityheaders.com; run `python manage.py check --deploy` in a
  Railway shell.
