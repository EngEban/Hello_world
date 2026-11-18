# WordPress → ResRef migration

**Status:** the tooling is ready and tested. The final WordPress data has not arrived yet, so nothing has been imported into
any shared database. Everything below is additive: the importer **never deletes** rows, files, or category/tag links.

## 1. What to send (owner)

**Preferred (complete):**
1. **A full SQL dump of the WordPress database.** Use one of:
   - hosting panel → phpMyAdmin → *Export* → *Quick* → format *SQL*, or
   - WP-CLI: `wp db export resref-final.sql`, or
   - `mysqldump --single-transaction --default-character-set=utf8mb4 DBNAME > resref-final.sql`.
   Send the plain `.sql` file (zip it if large). Include **all tables**. No MySQL server is needed on our side.
2. **The `wp-content/uploads/` folder** (zip of the folder, via the hosting file manager, SFTP, or a backup plugin). It
   contains every image *and* the resized copies (`photo-300x200.jpg`) that article HTML links to.

**Alternative (lighter):** WordPress admin → *Tools → Export → All content* (a WXR `.xml` file) **plus** the uploads folder.
A WXR file has no user accounts, no password hashes, no author biographies and no redirect-plugin rules; everything else is
covered.

Also tell us: the date WordPress will be frozen (no more edits), and whether old member accounts should move over.

**Tables and plugins that matter** (all read from the SQL dump; prefix is usually `wp_`, detected automatically):

| WordPress source | Used for |
|---|---|
| `wp_posts` (post, page, attachment) | articles, pages, media records. Revisions, menu items, auto-drafts are ignored |
| `wp_postmeta` | featured image (`_thumbnail_id`), image alt text, Elementor (`_elementor_data`), page template |
| Rank Math (`rank_math_title`, `rank_math_description`) / Yoast (`_yoast_wpseo_title`, `_yoast_wpseo_metadesc`) | SEO title and description (template tokens like `%title% %sep% %sitename%` are resolved; a title that is only the default pattern stays empty so the site's default is used) |
| Rank Math / Yoast *primary category* | which category builds the old dated permalink |
| `wp_terms`, `wp_term_taxonomy`, `wp_term_relationships` | categories (with parents) and tags |
| `wp_users`, `wp_usermeta` | authors (name, email, website, biography), member accounts, roles |
| `wp_options` (`home`, `permalink_structure`, `category_base`) | rebuilding the old URLs |
| `wp_redirection_items` (Redirection plugin), `wp_rank_math_redirections` | existing redirects |
| ACF and other custom fields | **not mapped** (no matching fields in the new app). The dry-run report lists the most common unmapped keys so we can decide |
| Comments, WooCommerce, forms plugins | not imported (no equivalent in the new app) |
| Yoast Premium redirects | not read automatically: export them as CSV in Yoast and add them in Django admin → Redirects |

## 2. How WordPress maps to the new app

| WordPress | New app | Match order (first hit wins) |
|---|---|---|
| Post / page | `blog.Post` (`post_type` post/page) | ledger → `Post.wordpress_id` → same slug *and* type with no WordPress ID (adopted) |
| Author (`post_author`) | `blog.Author` (`Post.author`) | ledger → `Author.wordpress_id` → `login` |
| Category | `blog.Category` (+ parent) | ledger (WordPress term ID) → slug |
| Tag | `blog.Tag` | ledger → slug |
| Attachment | `blog.MediaAsset` (+ file) | ledger → `MediaAsset.wordpress_id` → same URL |
| Featured image | `Post.featured_image` (URL of the media file) | via `_thumbnail_id` |
| Status `publish/draft/pending/private/trash` | same | `future` → `publish` (the public API already hides future dates) |
| User account | Django `User` + `MembershipProfile` | ledger → email (Gmail dot rules as on sign-up) |
| Redirect rules | `resref_redirects.Redirect` | old path |

Credits: the WordPress uploader is only stored as `Post.author`; article credits (`PostContributor`) are never invented
from it. Named credits inside article HTML can still be recovered with `manage.py import_legacy_contributors --all`
(preview) and `--apply`.

**The import ledger** (`WordPressImportRecord`, new table) remembers, for every imported object, which WordPress ID it came
from and a fingerprint of each field as last imported. That is what makes re-imports safe (section 4). Category, Tag
and User have no `wordpress_id` column, so the ledger is their only link to WordPress.

### Passwords
WordPress hashes **can be kept**. `blog/wordpress/hashers.py` adds a verify-only Django hasher:
- `$P$…` phpass (WordPress ≤ 6.7, the usual case): works in pure Python.
- `$wp$2y$…` (WordPress 6.8+, bcrypt): needs the `bcrypt` package, which is **not installed** (no new dependencies were
  allowed). Without it, those members simply use "Forgot password". To enable: add `bcrypt==4.2.1` to requirements.
- At the member's first successful sign-in Django re-hashes the password with PBKDF2, so WordPress hashes disappear.

To turn it on, one settings change is needed (requested from the settings owner, see the report): add
`'blog.wordpress.hashers.WordPressPasswordHasher'` as the **last** entry of `PASSWORD_HASHERS`. Then run the import with
`--only=users --import-password-hashes`. Without the hasher, imported members get no password and use "Forgot password".

User import rules: it only runs when asked for (`--only=users`); members are created as normal free members, never
staff or admin (WordPress administrator/editor roles are listed in the report for manual review); an existing account
with the same email is only linked — its password, roles and status are never touched.

## 3. Old URLs and 301 redirects

New addresses: articles `/database/<first-category>/<slug>` (canonical), pages `/<slug>`. The React app also serves any
article or page at `/<slug>`, so WordPress's `/%postname%/` links keep working with no redirect.

New app `backend/redirects/` (middleware + `Redirect` table, editable in Django admin → *Redirects*; has hit counters):

| Old address | Goes to | How |
|---|---|---|
| `/2024/05/my-article/` (dated or other permalink formats), hierarchical pages `/about-us/team/` | canonical new address | rows created by the importer |
| Redirection plugin / Rank Math rules | same targets (old WordPress targets are translated to new addresses) | rows created by the importer; regex rules are listed, not imported |
| `/?p=123`, `/?page_id=123` | the published post with that WordPress ID | built in |
| `/category/<slug>/` (also nested and `/page/2/`) | `/database/<slug>` | built in |
| `/author/<login>/` | `/authors/<profile>` | built in |
| `/wp-content/uploads/2024/05/x.jpg` | the copied file in media storage | built in (only if the file was copied) |
| anything else | handled by hand in admin (exact or prefix redirects) | |

Safety: only GET/HEAD; never `/api/`, `/static/`, `/media/`, admin or dashboard; targets must be a local path or an
`http(s)://` URL (no `//evil.com`); the importer never creates a redirect for an address that is a live article/page or
one of the new site's own routes (e.g. `/journal-finder`); staff-made redirects are never overwritten.

**Important – images:** article HTML and featured images currently point to `https://resref.com/wp-content/uploads/…`.
When the domain moves to the new app those requests arrive at the new app, so **the uploads folder must be imported**
(`--uploads-dir`); the uploads redirect then serves every old image link without rewriting any article.

## 4. Content created in the new app meanwhile (merge rules)

1. Records are matched by WordPress ID (ledger or `wordpress_id`), then by slug/login/email/URL. A post written in the new
   app with the same slug as a WordPress post is **adopted** (linked), not duplicated, and its text is kept.
2. Per field, three-way:
   - changed in WordPress, untouched in the new app → updated;
   - edited in the new app, unchanged in WordPress → new-app value kept, silently;
   - changed in both → **conflict**: new-app value kept and listed in the report. `--overwrite` takes WordPress's value.
3. Rows from the first import (before the ledger existed) have no fingerprint. They count as "unedited" when they were
   not saved again more than 10 minutes after they were created (an untouched import row); otherwise each differing
   field is a conflict. Override with `--trust-unedited-before=YYYY-MM-DD` or disable with `--no-assume-unedited`.
4. An empty WordPress value never clears a filled field. Categories/tags are only added to a post, never removed.
   Nothing is deleted: posts deleted in WordPress stay in the new app (set them to draft/trash in the dashboard).
5. Media files: same name + same bytes → skipped; same name + different bytes → conflict, existing file kept
   (`--overwrite` stores the new file beside it). Only jpg/jpeg/png/gif/webp/avif/pdf/doc/docx files are copied
   (never `.php`, `.svg`, scripts).
6. Slugs WordPress allowed twice (a post and a page) keep their numbered slug (`journal-finder-2`) without noise.

## 5. Runbook

Commands run from `backend/` with the production environment (Railway shell: `railway run` or the service shell).
`$PGURL` = the database URL. Allow ~1 minute per 400 posts plus file copying.

1. **Freeze WordPress** (no more edits) and get the SQL dump + uploads zip (section 1). Unzip uploads to e.g. `/tmp/uploads`.
2. **Back up the production database** (see also `backup-and-recovery.md`):
   `pg_dump "$PGURL" -Fc --no-owner --no-privileges -f resref-before-wp-$(date +%Y%m%d-%H%M).dump` and check it with
   `pg_restore --list <file> | head`. Also take a Railway backup and note the media volume/bucket state.
3. **Restore that dump into a throw-away copy** (temporary Postgres service or local):
   `createdb resref_wp_test && pg_restore --no-owner --no-privileges -d resref_wp_test <file>`, then
   `DATABASE_URL=postgres://…/resref_wp_test MEDIA_ROOT=/tmp/wp-test-media python manage.py migrate`.
4. **Dry run on the copy** (changes nothing, copies nothing):
   `python manage.py import_wordpress resref-final.sql --uploads-dir /tmp/uploads --dry-run --report dry-run.json`
5. **Review the report**: the table (created / updated / linked / unchanged / conflict / skipped / error per entity),
   every CONFLICT and ERROR line, notes, unmapped custom fields. `-v 2` lists every created/updated record and field.
   Decide on conflicts (keep new-app values, or rerun with `--overwrite`, optionally `--only=posts`).
6. **Real run on the copy**, then check the site against it: counts, a few articles, images, old URLs (`curl -I
   http://…/2024/05/old-article/` → 301). Run the dry run again: it must show 0 created/updated (idempotent).
7. **Real run on production** (the command asks you to type `import`; `--no-input` skips that in scripts):
   `python manage.py import_wordpress resref-final.sql --uploads-dir /tmp/uploads --optimize-images --report import.json`
   Users (only if decided): `python manage.py import_wordpress resref-final.sql --only=users --import-password-hashes`.
8. **Verify**: compare counts with WordPress (`Posts`, `Pages`, `Media`, categories); open 10 old URLs from Google Search
   Console; check Django admin → Redirects; run `import_legacy_contributors --all` (preview) if credits are missing.
9. **Rollback**, if needed: stop the app, restore the step-2 dump into a fresh database
   (`pg_restore --clean --if-exists --no-owner -d "$PGURL" <file>` only with explicit owner approval, or restore into a new
   database and switch `DATABASE_URL`). Copied files live under `wp-content/uploads/` in media storage and can stay (nothing
   references them after a database rollback).

Useful options: `--only=authors,categories,tags,media,posts,redirects,users` (default: all except users),
`--format=wxr|sql`, `--table-prefix=wp_`, `--media-base-url=https://old-host/wp-content/uploads/` (download files that are
missing from the folder), `--published-only`, `--skip-trash`, `--report=file.json`.

Each entity is imported in its own transaction (a failure rolls back that entity and stops); a single bad record is
reported as an error and skipped. Multisite (`wp_2_posts`) is not supported automatically: pass `--table-prefix=wp_2_`.

## 6. Verified so far

- 29 automated tests (`blog/test_wordpress_import.py`, `redirects/tests.py`): WXR and SQL parsing (escapes, hierarchical
  pages, dated permalinks, PHP-serialized roles), dry run, idempotence, local edits kept, adoption by slug, no deletions,
  media checksum/conflict, unsafe files skipped, users + phpass hashes (upgraded to PBKDF2 at sign-in), redirects.
- The original WordPress export (`wp_database2.xml`, 329 posts, 701 media) was dry-run and then imported into a
  **throw-away copy** of the developer database: 0 conflicts, 12 empty SEO fields filled from Yoast, 4 duplicate slugs
  recognised, and a second run reported everything unchanged.
