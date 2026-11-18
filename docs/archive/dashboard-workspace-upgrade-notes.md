# Dashboard workspace upgrade

## Scope and safeguards

Existing Django, React/Vite, session authentication, CSRF, role permissions, public article URLs, models, and all dashboard routes remain. No CMS or dependencies were added. A local SQLite backup was taken before implementation; it is ignored by Git. Workflow browser tests run against a disposable database copy, not production or the working content database.

## Review findings and implementation

- The old split-pane content manager squeezed both list and editor. Articles now have a full-width editorial table and a focused editor.
- Page-local status counts were misleading. Status totals now cover all records of the selected content type; live and scheduled publication are distinct.
- Overview and topbar search links did not initialize article filters. Query-string filters now work, remain shareable, and support queue deep links.
- The sidebar mixed content, people, settings, and reports. Workspace, Library, Operations, and Administration groups retain all existing destinations.
- Duplicate header branding, decorative overview hero, and demonstration-only state examples were removed. The original ResRef logo is retained once in the sidebar; the header provides location and search instead.
- Existing service/content charts, user/media counts, audit activity, pending tasks, and quick actions remain available in a more task-oriented overview.

## Article workflows

- All content, published, drafts, in review, scheduled, private, and Trash views.
- Title/body/excerpt search; category, tag, contributor-role, updated-date, featured, and missing-metadata filters; allowlisted sorting; 20/50/100-row pagination.
- Named filtered views saved **per user in the current browser**, not server-wide.
- Current-page selection, explicit confirmation, bounded atomic bulk operations, and audit entries. Trash requires existing `content.delete` permission; other mutations require `content.write`. Original permanent deletion remains available only when inspecting a trashed record, with a typed DELETE confirmation.
- Draft, review, private, publish-now, schedule, feature/unfeature, Trash, restore-as-draft, and duplicate-as-draft operations.
- Duplicates receive a unique slug, remain unpublished, and preserve content, taxonomy, media URLs, and contributor roles. Uploaded PDFs are deliberately not shared: attach a separate PDF to the copy so removing it cannot delete the original file.
- Scheduled content reuses the existing `publish` status plus a future `published_at`; public queries already enforce the due timestamp. No scheduler service or new model is required.
- Explicit homepage featuring uses `design_settings.is_featured`. Only live articles are eligible; normal newest-content fallback remains.
- Full HTML/legacy editor metadata loads on demand. Existing list API clients still receive full content unless they request `summary_only=true`.

## Editor

The existing visual/HTML/preview editor, block tools, SEO, media/PDF controls, categories/tags, assigned authors and contribution roles, optional author cards, source metadata, and design settings remain. Account/uploading identity is never inferred as authorship.

Publication is grouped in the settings rail. A future local datetime is converted to UTC before saving. Browser timezone is displayed. Publishing completeness measures metadata checks, not medical quality or SEO performance.

Unsaved edits warn on closing the editor, internal text-link navigation, and browser unload. Ctrl/Cmd+S saves. Stored `updated_at` is submitted as `expected_updated_at`; a stale save receives HTTP 409 instead of overwriting newer content. PDF attachment updates no longer replace unsaved text edits.

No automatic background server saving, version-history UI, article view analytics, or fake engagement metrics are introduced. Existing audit logs record actions, not full historical article bodies. Actual analytic event collection and full revision history would be separate work.

## API additions

`POST /api/dashboard/posts/bulk/` accepts `ids` (1–100 integer IDs), `action`, and `published_at` for scheduling. It never permanently deletes records.

`GET /api/dashboard/posts/` adds global `summary`, `status=scheduled`, `id`, `summary_only`, `featured=true`, `needs=seo|image|contributors`, `date_from`, `date_to`, and `sort=updated|published|oldest|title|scheduled`. An unfiltered view excludes Trash. Public routes are not migrated or renamed.

## Validation

Automated coverage includes workflow permissions, request validation, atomicity, counts, publication times, Trash/restore, duplication/contributor preservation, featured visibility, save conflicts, link/filter utilities, and existing dashboard/blog regressions. Browser checks use real API requests against a disposable database and verify desktop/mobile layout and the create → save → review → schedule → Trash → restore flow. No live deployment/content mutation is needed to validate these operations.

Final verification: 102 Django dashboard/blog tests and 20 frontend tests passed, alongside a production build. The real-browser smoke pass opened all 22 dashboard destinations and checked that they render without runtime exceptions, API 5xx failures, or desktop overflow. Desktop 1440×1000 and mobile 390×844 checks covered the article table, editor, command palette, mobile menu, metadata filters, browser-saved views, duplication, homepage featuring, Ctrl/Cmd+S, unsaved-close cancellation, and recoverable publishing operations.

Visual review compared the generated table/editor/overview concepts against rendered screenshots: navy sidebar and original logo, restrained breadcrumb header, open page heading, status summary/tabs, full-width table anatomy, and writing/settings columns. Intentional differences are real application records rather than sample copy, retention of every existing navigation destination, a compact bulk-action selector that fits all supported operations, and preserving the existing advanced editor controls instead of replacing their functionality. The mobile status tabs were corrected to scroll horizontally; opening an editor now resets the viewport to its heading.
