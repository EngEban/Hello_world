# Operations scripts

## Manual backup of the live site

`backup-live.ps1` downloads the live Railway database (`pg_dump` custom format)
and the uploaded-files volume (`/data/media`, as `.tar.gz`) into a folder you
choose, and checks each file against a checksum taken on the server. It needs
only the Railway CLI, logged in and linked to this project; it changes nothing
on Railway. Run it weekly and before risky deploys until Railway's own backups
are enabled (see `docs/launch/backup-and-recovery.md` for restoring):

```powershell
.\scripts\backup-live.ps1 -Destination 'E:\path\to\backups'
```

The files contain personal data (e-mails, password hashes): keep them private
and outside the repository. `-SkipMedia` backs up only the database.

## Public image optimization

`optimize_public_images.py` builds local WebP copies of images referenced by
published local content, active contributor portraits, site image settings,
and the built-in public-page assets. It never edits database records or deletes
source images. Use backend's Python environment and normal local Django settings:

```powershell
.\backend\.venv\Scripts\python.exe scripts/optimize_public_images.py
```

The generated catalog is `frontend/src/config/optimizedImages.json`; both the
catalog and `frontend/public/optimized-images/` must be committed together.
Only explicitly allowed public hosts are downloaded, with bounded sizes and
redirect checks. Missing or unavailable originals are reported and not mapped
to nonexistent derivatives. Rerunning reuses catalog entries that exist locally.
For new content added only in production, download that image through the
dashboard Media Library instead: new static uploads automatically receive a
WebP delivery copy, while the original remains available in storage.

`--heroes` also regenerates the bundled desktop/mobile hero versions. This is
an explicit lossy asset rebuild, not a database migration; use original source
photos when regenerating an already-compressed banner. SVG icons remain vector
assets, and animations retain their original format to avoid flattening frames.

`migrate-local-data-to-render.ps1` is an approval-gated, one-time tool that
copies the local `backend/db.sqlite3` application data into Render staging
PostgreSQL.

It deliberately replaces the target staging records. It does not change local
data, Git-tracked files, or an existing backup. It prompts locally for the
Render **External Database URL** and a replacement staging-admin password; do
not paste either into Git, issue trackers, or chat.

Open the `resref-staging-db` resource in Render and copy its **External
Database URL**. Then run this from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\migrate-local-data-to-render.ps1
```

The tool exports a temporary JSON fixture and small, ordered import batches
under the current user's temporary directory. This prevents a single dropped
Render connection from losing the entire import. They are sensitive data.
Retain them only until staging has been checked, then delete them manually.

Before importing, it clears only application data from the target PostgreSQL
database. Django migrations, content types, and permissions are deliberately
preserved, avoiding conflicts with Render's already-initialized schema.

The Render API service does not need a redeploy after the import; the data is
available immediately. Sign in again using the administrator credentials
entered in the script.
