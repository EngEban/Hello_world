# Deploying ResRef on Railway

The repository builds one Docker image (React frontend + Django API) from the root `Dockerfile`.
`railway.json` tells Railway to use it and to health-check `/api/health/` (which also checks the database).
On every start the container runs migrations, `seed_reference_data`, analyzer-session cleanup, an optional admin bootstrap, then gunicorn (`backend/start.sh`).

## 1. Services in the Railway project

| Service | Why | Required |
|---|---|---|
| **Web** (this repo) | The site | Yes |
| **Postgres** | Real database. Without `DATABASE_URL` the app falls back to SQLite *inside the container*, which is wiped on every deploy | **Yes** |
| **Redis** | Shared rate limits / login lockouts | **Yes** (production refuses to start without it) |
| **Volume** on Web, *or* a Cloudflare R2 bucket | Uploaded images/PDFs survive deploys | **Yes**, one of them |
| **Cron** (same repo, see below) | Sends queued newsletters | Yes, if you send newsletters |

## 2. Variables on the Web service

Required:

```
RESREF_ENV=production
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=<new random value: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())">
DATABASE_URL=${{Postgres.DATABASE_URL}}
SERVE_FRONTEND_FROM_DJANGO=true
```

Set automatically by the code on Railway (no action needed): the `*.up.railway.app` host is added to
`ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`, Railway health checks are allowed, and the proxy is trusted
for HTTPS detection and client IPs. For a custom domain add `PUBLIC_HOSTNAME=resref.com` and also list
it in `DJANGO_ALLOWED_HOSTS`.

Also required: `REDIS_URL=${{Redis.REDIS_URL}}`. Recommended: `DJANGO_ADMIN_PATH=<something-hard-to-guess>/`.

### Email (required: sign-up confirmation, password reset, newsletter opt-in)

New accounts must confirm their email before they can sign in, and newsletter sign-ups are
double opt-in, so production needs working SMTP. Any SMTP provider works (Brevo, Resend,
Mailgun, Gmail with an app password). Example:

```
DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
DJANGO_EMAIL_HOST=smtp-relay.brevo.com
DJANGO_EMAIL_PORT=587
DJANGO_EMAIL_USE_TLS=true
DJANGO_EMAIL_HOST_USER=<smtp login>
DJANGO_EMAIL_HOST_PASSWORD=<smtp key>
DJANGO_DEFAULT_FROM_EMAIL=ResRef <no-reply@resref.com>
```

No email provider yet? Set `ACCOUNT_EMAIL_CONFIRMATION_REQUIRED=false` so new accounts are signed in
without the confirmation email, and delete that variable once SMTP works.

Set the same variables on the cron service (it sends the newsletter). Check after deploy: register a
test account and confirm that the "Confirm your ResRef account" email arrives.

### Uploaded files — option A: Cloudflare R2 (recommended, free tier)

1. Cloudflare → R2 → create bucket `resref-media`, enable public access (r2.dev URL or a custom domain).
2. Create an R2 API token with read/write on that bucket.
3. Variables:

```
MEDIA_STORAGE=s3
AWS_STORAGE_BUCKET_NAME=resref-media
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_S3_ENDPOINT_URL=https://<ACCOUNT_ID>.r2.cloudflarestorage.com
AWS_S3_REGION_NAME=auto
AWS_S3_CUSTOM_DOMAIN=<pub-xxxx.r2.dev or media.resref.com>
```

4. Copy existing files from your local `backend/media/` into the bucket under the `media/` prefix
   (e.g. with `rclone copy backend/media r2:resref-media/media`).

### Uploaded files — option B: Railway Volume

1. Web service → Volumes → mount path `/data`.
2. Variables: `MEDIA_STORAGE=local`, `MEDIA_ROOT=/data/media`, `RAILWAY_RUN_UID=0`
   (the image runs as a non-root user; Railway volumes are root-owned, this makes them writable).
3. Django serves only public images and PDFs from `/media/`; CV uploads are never served publicly.

### Newsletter cron service

Newsletters are queued by the dashboard and sent in the background (never inside a web request).
Add a second service from the same repo:

1. New service → GitHub repo (same repo/branch) → Settings → **Config-as-code file path**:
   `/railway.cron.json`. That file sets the start command (`python manage.py process_outbox`),
   the schedule (`*/5 * * * *`) and no health check, so the web settings in `railway.json` are not used.
2. Give it the same variables as Web (at least `RESREF_ENV`, `DJANGO_SECRET_KEY`, `DATABASE_URL`,
   `SERVE_FRONTEND_FROM_DJANGO`, and all `DJANGO_EMAIL_*` settings). Shared variables or
   `${{Web.VARIABLE}}` references keep them in sync.
3. Each run sends up to `NEWSLETTER_BATCH_SIZE` (default 200) emails per campaign and exits.

## 3. First admin account (once)

Production refuses to start if any `RESREF_STAGING_ADMIN_*` variable is set. Create the first
super administrator from a Railway shell on the Web service instead:

```
python manage.py createsuperuser
```

## 4. After each deploy

- `https://<domain>/api/health/` returns `{"status": "ok", "database": "ok"}`.
- Deploy logs show `Using worker: gthread` and no `RuntimeWarning` about the cache (if Redis is set).
- Upload an image in the dashboard, redeploy, and confirm it still loads.

## Notes

- Memory: pandas/scipy in the Research Analyzer need ~300 MB. If the service restarts under load, raise the
  memory limit on the paid plan before raising `WEB_CONCURRENCY`.
