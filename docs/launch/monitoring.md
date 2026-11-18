# Monitoring — launch notes

## Health check

`GET /api/health/` returns `{"status": "ok", "database": "ok"}` (HTTP 200) or
HTTP 503 when PostgreSQL is unreachable. Railway uses it for deploy health
checks (`railway.json`, 180 s). Point an external uptime monitor (for example
UptimeRobot or Better Stack, free tier) at `https://<domain>/api/health/`
every 5 minutes and alert by e-mail.

## Error reporting (optional, Sentry)

Off by default. To turn on: create a free Sentry project (platform: Django),
then set on the **web** and **cron** services:

| Variable | Purpose | Example |
|---|---|---|
| `SENTRY_DSN` | Enables reporting. Empty = off. | `https://<key>@o0.ingest.sentry.io/0` |
| `SENTRY_ENVIRONMENT` | Label in Sentry (default: `RESREF_ENV`). | `production` |
| `SENTRY_RELEASE` | Version label (default: Railway's `RAILWAY_GIT_COMMIT_SHA`). | `2026-10-launch` |
| `SENTRY_TRACES_SAMPLE_RATE` | Performance tracing share 0–1 (default 0 = off). | `0.05` |

Privacy: no cookies, request bodies, query strings, auth headers, e-mail
addresses or IPs are sent — only the error, stack trace, URL path and the
numeric user id (`core/monitoring.py`). Bad-Host-header noise is ignored.

Test after enabling: in a Railway shell run
`python -c "import django,os;os.environ.setdefault('DJANGO_SETTINGS_MODULE','resref.settings');django.setup();import sentry_sdk;sentry_sdk.capture_message('ResRef Sentry test')"`
and confirm the event appears.

## Logs

- Railway → service → *Logs*. App logs and gunicorn access logs go to stdout.
- `DJANGO_LOG_FORMAT=json` makes each line a JSON object (searchable by
  `level`, `logger`).
- Passwords, tokens, API keys and `?token=` URL values are masked; the access
  log shows the path without the query string.
- Things to watch in the first week: `level=ERROR`, `Rate-limit cache is
  unavailable` (Redis down — public forms then refuse requests), `email
  connection failed` (Brevo SMTP), HTTP 429 spikes, HTTP 413 (uploads too large).
- The dashboard's *Activity* log is the audit trail for staff actions
  (sign-ins, exports, CV downloads, settings changes).

## Cron

`railway.cron.json` runs `process_outbox` every 5 minutes (newsletter
sending). If newsletters stay "queued", check that service's logs.
