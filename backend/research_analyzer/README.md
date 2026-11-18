# Research Analyzer Backend

Isolated Django API module for the ResRef Research Analyzer add-on.

## Endpoints

All routes are mounted under `/api/research-analyzer/`.

- `POST upload/` accepts one dataset file and returns an ephemeral analyzer session.
- `POST variables/` updates confirmed variable types and roles.
- `POST prepare/` applies safe data-preparation options.
- `POST analyze/` runs one selected statistical test.
- `GET analysis-plan/` returns a conservative role-led analysis plan.
- `POST report/generate/` runs the guided report analyses.
- `GET report/` returns the accumulated master report.
- `POST session/<session_id>/clear/` clears the active analyzer session.

## Security Notes

Each upload becomes an `AnalyzerSession` row plus a private, HMAC-signed dataset file under `ANALYZER_STORAGE_DIR` (default `MEDIA_ROOT/private/analyzer`, never served). Sessions expire after `ANALYZER_SESSION_TTL_SECONDS` (2 h) of inactivity, are capped per user (`ANALYZER_MAX_SESSIONS_PER_USER`) and are removed on upload, at container start and by `manage.py cleanup_analyzer_sessions`. XLSX files are checked for size, parts, rows and columns before parsing. Test runs and master reports count toward the premium usage limit; uploads do not. Every mutating endpoint uses Django CSRF protection through the shared frontend API client.
