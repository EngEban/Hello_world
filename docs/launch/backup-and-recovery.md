# Backup and recovery — launch runbook

What must be backed up:

1. **PostgreSQL** (Railway Postgres service) — accounts, articles, forms,
   settings, newsletter, usage data.
2. **Uploaded files** — the media volume (`MEDIA_ROOT=/data/media` on the Web
   service: images, article PDFs, CVs under `uploads/jobapplication/`, analyzer
   datasets under `private/analyzer/` — the analyzer files are temporary and
   need no backup), or the R2/S3 bucket if `MEDIA_STORAGE=s3`.
3. **Environment variables** — keep a copy of every Railway variable in a
   password manager (never in git). Without `DJANGO_SECRET_KEY` all sessions
   and e-mailed links stop working (data itself is not lost).

Targets: lose at most 24 hours of data (RPO), be back online within 2 hours (RTO).

## 1. Automatic backups on Railway (set up on launch day)

- Postgres service → **Backups** tab → enable a **daily** schedule (and weekly
  if offered); retention at least 7 days. Do the same on the Web service's
  media **volume**. (Railway volume backups need a paid plan.)
- Click **Backup now** once and confirm it appears in the list.
- Railway restores a backup **into the same volume** (it replaces current data).
  Before restoring, always take a manual backup of the current state first.

## 2. Off-platform copy with pg_dump (weekly, and before every risky deploy)

Railway backups live inside Railway; keep an independent copy too.

Prerequisites on the admin computer: PostgreSQL client tools **version 16 or
newer** (same major version as the Railway server or newer), Railway CLI.

```sh
# 1. Get the public connection URL: Postgres service → Variables → DATABASE_PUBLIC_URL
#    (enable the TCP proxy if it is not shown). Keep it out of shell history:
read -r -s PGURL     # paste the URL, press Enter

# 2. Dump (custom format, compressed, no ownership/privileges so it restores anywhere)
pg_dump "$PGURL" -Fc --no-owner --no-privileges -f "resref-$(date +%Y%m%d-%H%M).dump"

# 3. Check the file is readable and lists the tables
pg_restore --list resref-YYYYMMDD-HHMM.dump | head
```

Store the `.dump` file encrypted (it contains personal data: e-mails,
applications, password hashes). Delete copies older than 90 days.

### Restore (into a NEW, empty database — never over the live one first)

```sh
# a) Create a new Railway Postgres service (or a local one) and copy its URL into NEWURL
read -r -s NEWURL
pg_restore --no-owner --no-privileges -d "$NEWURL" resref-YYYYMMDD-HHMM.dump
# b) Sanity check
psql "$NEWURL" -c "select count(*) from auth_user;" -c "select count(*) from blog_post;"
```

Then point the Web **and** cron services' `DATABASE_URL` at the new database
(`${{NewPostgres.DATABASE_URL}}`), redeploy, and open `/api/health/`. The
pre-deploy `migrate` applies any migrations newer than the backup. Keep the old
database untouched until the site is confirmed working.

## 3. Application-level export (fallback, tested)

Works without PostgreSQL tools (from a Railway shell on the Web service) and
across database engines. Slower and larger than pg_dump.

```sh
python manage.py dumpdata --natural-foreign --natural-primary \
  -e contenttypes -e auth.permission -e sessions -e admin.logentry \
  --indent 0 -o /data/backup-$(date +%Y%m%d).json
```

Restore — **only into a brand-new empty database** (`flush` empties the
database it runs on, so check `DATABASE_URL` twice):

```sh
python manage.py migrate --noinput
python manage.py flush --noinput      # removes rows seeded by migrations, NEW database only
python manage.py loaddata /path/backup-YYYYMMDD.json
```

Tested on 2026-10-22 against a copy of the development database: 1,755
objects (6 users, 331 posts, 701 media records) exported in ~12 s, restored
into a fresh database in ~15 s; every table count matched except sessions and
the admin log, which are intentionally excluded (users simply sign in again).
Without the `flush` step the restore fails on rows seeded by migrations
(`UNIQUE constraint failed: accounts_featureentitlement.code`) — this is expected.

The pg_dump/pg_restore commands above could not be executed in the audit
environment (no PostgreSQL tools or Railway access); run sections 2 and 4 once
on Railway before launch and note the date here.

## 4. Uploaded files

- **Railway volume:** covered by volume backups (section 1). Off-platform copy:
  `railway ssh --service Web -- tar czf - -C /data media > media-$(date +%Y%m%d).tgz`
  Restore: upload the archive and `tar xzf` it into `/data` from a Railway shell,
  then make sure files are owned by `app` (the start script fixes ownership on boot).
- **R2/S3 bucket:** enable bucket versioning/lifecycle in the provider, and copy
  periodically with `rclone sync r2:resref-media backup-folder/`.

## 5. Restore drill (do once before launch, then every 3 months)

1. Take a manual Railway backup and a pg_dump.
2. Restore the pg_dump into a temporary Postgres service (section 2).
3. Temporarily point a staging Web service at it; sign in to the dashboard,
   open an article, an image and a CV download.
4. Delete the temporary services. Record date, duration and problems below.

| Date | Who | Method | Duration | Result |
|---|---|---|---|---|
| 2026-10-22 | audit | dumpdata/loaddata on local copy | ~30 s | OK (counts matched) |
