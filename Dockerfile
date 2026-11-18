# Build the Vite frontend first, then bundle it with the Django service so the
# whole site is served from one origin (no third-party cookies).
FROM node:22-bookworm-slim AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN VITE_ASSET_BASE_PATH=/static/ npm run build

FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install -r /app/backend/requirements.txt

# Run as an unprivileged user.
RUN groupadd --system app && useradd --system --gid app --home /app app

COPY --chown=app:app backend/ /app/backend/
COPY --from=frontend-build --chown=app:app /app/frontend/dist /app/backend/frontend_dist
# The tool guides feed both the React pages and the server-rendered copy for crawlers.
COPY --chown=app:app frontend/src/data/toolGuides.json /app/backend/resref/tool_guides.json

WORKDIR /app/backend
# collectstatic needs a key to load settings; this build-only value is never
# used at runtime (the platform injects the real DJANGO_SECRET_KEY).
RUN DJANGO_SECRET_KEY=build-only-not-a-secret RESREF_ENV=development \
    python manage.py collectstatic --noinput \
    && mkdir -p /app/backend/media \
    && chown -R app:app /app/backend/staticfiles /app/backend/media \
    && chmod +x /app/backend/start.sh

USER app
EXPOSE 8000
CMD ["/app/backend/start.sh"]
