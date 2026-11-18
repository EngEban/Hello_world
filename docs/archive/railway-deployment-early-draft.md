# Railway deployment

## Architecture

Deploy exactly three Railway services in the same environment:

1. `resref-staging-api` — the only public service. The repository Dockerfile
   builds React, copies it into Django, and serves both the website and API
   from one origin.
2. `resref-staging-db` — Railway PostgreSQL. Keep it private.
3. `resref-staging-cache` — Railway Redis. Keep it private.

Do not deploy a separate Railway frontend service. It duplicates the compiled
frontend already included in the API image and causes avoidable cross-origin
session, CSRF, and environment-variable failures.

## API service configuration

Connect `resref-staging-api` to this repository at its root (do not set a
service root directory such as `frontend` or `backend`). Railway detects the
root `Dockerfile` and `railway.json` automatically.

Do not set a custom build command or start command in the Railway dashboard.
`railway.json` owns the Docker build, pre-deploy migrations, health check,
restart policy, and Gunicorn command. Migrations run over Railway private
networking before the new deployment receives traffic.

Add these service variables in Railway's Raw Editor. Values in angle brackets
must be replaced; do not add quote characters around values.

```text
DATABASE_URL=${{resref-staging-db.DATABASE_URL}}
DJANGO_CACHE_BACKEND=django.core.cache.backends.redis.RedisCache
REDIS_URL=${{resref-staging-cache.REDIS_URL}}
DJANGO_SECRET_KEY=<a newly generated Django secret>
RESREF_ENV=production
DJANGO_DEBUG=false
DJANGO_DB_CONN_MAX_AGE=600
DJANGO_DB_SSL_REQUIRE=true
DJANGO_CSP_ENABLED=true
DJANGO_SECURE_SSL_REDIRECT=true
DJANGO_SECURE_HSTS_SECONDS=31536000
DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS=true
DJANGO_CSRF_COOKIE_SECURE=true
DJANGO_CSRF_COOKIE_SAMESITE=Lax
DJANGO_SESSION_COOKIE_SECURE=true
DJANGO_SESSION_COOKIE_SAMESITE=Lax
DJANGO_SESSION_COOKIE_AGE=604800
DJANGO_SESSION_EXPIRE_AT_BROWSER_CLOSE=false
DJANGO_SESSION_SAVE_EVERY_REQUEST=true
RESREF_TRUST_PROXY=true
RESREF_TRUSTED_PROXY_HOPS=1
SERVE_FRONTEND_FROM_DJANGO=true
WEB_CONCURRENCY=2
```

`RAILWAY_PUBLIC_DOMAIN`, `DJANGO_ALLOWED_HOSTS`, and `FRONTEND_BASE_URL` do
not need to be set for Railway's generated domain: Django now derives the
public host and first-party frontend URL from `RAILWAY_PUBLIC_DOMAIN`, and
allows Railway's health-check host only on Railway. Set `FRONTEND_BASE_URL` to
your canonical `https://` custom domain only after that domain is attached. For
a custom domain, also set `DJANGO_ALLOWED_HOSTS` to that hostname (and include
the Railway generated hostname only if it must remain publicly reachable).

Keep PostgreSQL and Redis private. Reference `DATABASE_URL` and `REDIS_URL`;
do not use public TCP URLs for application-to-database traffic.

If a blank `DATABASE_URL`, `REDIS_URL`, or `DJANGO_CACHE_LOCATION` variable was
previously created in the API service, delete only that blank API variable
before adding the corresponding Railway reference. A duplicate blank service
variable prevents Railway's reference-variable picker from replacing it.

### Fallback when Railway renders a `DATABASE_URL` reference empty

If Railway continues to render the database URL reference as empty, do not add
an empty `DATABASE_URL` variable. Instead add these five direct references to
the API service from `resref-staging-db`: `PGHOST`, `PGPORT`, `PGUSER`,
`PGPASSWORD`, and `PGDATABASE`. Django constructs the PostgreSQL URL safely
from them. This is compatible with Railway's PostgreSQL variables and avoids
putting a credential literal in the dashboard.

## First deployment verification

The deployment must show all of the following:

1. The pre-deploy migration command completes successfully.
2. Gunicorn starts and binds to Railway's injected `PORT`.
3. `GET /api/health/` returns HTTP 200.
4. Opening the public service domain renders the React website from Django.

An empty PostgreSQL database is expected before data migration. Git contains
migrations and configuration, never database files or credentials.

## Importing the verified SQLite data

The verified legacy data is held locally and must not be committed. Railway
PostgreSQL is private by default, so temporarily enable its TCP proxy only for
the controlled one-time import, then disable public access afterward.

Run the existing import script from the repository root, passing Railway's
temporary `DATABASE_PUBLIC_URL` to the clipboard before running it. The script
reads that clipboard value without printing the credential. It exports a temporary
fixture outside the repository, validates the PostgreSQL target, migrates the
schema, clears only the chosen staging target after confirmation, and imports
the local SQLite data in batches:

```powershell
.\scripts\migrate-local-data-to-render.ps1
```

The script uses `RailwayDatabaseUrl` (and accepts the old `RenderDatabaseUrl`
parameter for backwards compatibility).
it accepts any PostgreSQL URL. Never put that URL in Git, a source file, or a
chat message. After import, validate the record totals and disable the TCP
proxy. The application itself continues using the private `DATABASE_URL`.
