#!/bin/sh
# Container entrypoint for Railway (and any Docker host).
set -e

# Railway volumes are mounted root-owned, so docs/deployment.md sets
# RAILWAY_RUN_UID=0 to make the media volume writable. In that case only this
# step runs as root: it hands the media directory to the unprivileged `app`
# user and re-executes this script as `app`, so the web server never runs as root.
if [ "$(id -u)" = "0" ] && id app >/dev/null 2>&1; then
  media_root="${MEDIA_ROOT:-/app/backend/media}"
  mkdir -p "$media_root"
  find "$media_root" ! -user app -exec chown app:app {} + 2>/dev/null || true
  if command -v setpriv >/dev/null 2>&1; then
    export HOME=/app
    exec setpriv --reuid=app --regid=app --init-groups "$0" "$@"
  fi
  echo "WARNING: setpriv not found; continuing as root."
fi

# On Railway, migrations run once per deploy as the pre-deploy command
# (railway.json) before any new container starts; running them again in every
# replica would race. Plain `docker run` (no RAILWAY_ENVIRONMENT) still
# migrates here. RUN_MIGRATIONS_ON_START=true/false overrides either default.
if [ -n "${RAILWAY_ENVIRONMENT:-}" ]; then
  default_migrate=false
else
  default_migrate=true
fi
if [ "${RUN_MIGRATIONS_ON_START:-$default_migrate}" = "true" ]; then
  python manage.py migrate --noinput
fi

# Idempotent: adds missing default roles/plans and syncs Stripe price ids from env.
python manage.py seed_reference_data || echo "WARNING: seed_reference_data failed; continuing."

# Analyzer datasets are on this container's disk, so expired ones are removed here.
python manage.py cleanup_analyzer_sessions || echo "WARNING: analyzer cleanup failed; continuing."

# exec makes gunicorn PID 1 so it receives SIGTERM and shuts down gracefully.
# The access log records the path WITHOUT the query string (%(U)s), and no
# referrer or user agent, so password-reset / confirmation tokens and other
# personal data in URLs never reach the platform logs.
exec gunicorn resref.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --worker-class gthread \
  --threads "${GUNICORN_THREADS:-4}" \
  --timeout "${GUNICORN_TIMEOUT:-120}" \
  --graceful-timeout "${GUNICORN_GRACEFUL_TIMEOUT:-30}" \
  --keep-alive "${GUNICORN_KEEPALIVE:-5}" \
  --max-requests "${GUNICORN_MAX_REQUESTS:-300}" \
  --max-requests-jitter 50 \
  --worker-tmp-dir /dev/shm \
  --access-logfile - \
  --access-logformat '%(t)s "%(m)s %(U)s %(H)s" %(s)s %(B)s %(M)sms' \
  --error-logfile -
