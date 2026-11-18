# Frontend quality, accessibility and performance

**Status:** audited on the production build (`npm run build`, served by `vite preview` against a local copy of the API).
Everything found that could be fixed safely has been fixed. Nothing here needs a new environment variable or service.

## What was checked

| Check | How | Result after fixes |
|---|---|---|
| Every public route + every internal link found on pages (400 pages, signed in as a member) and 40 pages anonymously | Playwright crawl (status, console errors, failed requests) | All 200, no JavaScript errors. Only expected 404s on deliberately wrong URLs (the "not found" pages render correctly) |
| All 22 dashboard routes + dashboard login (admin) | Playwright crawl | No console errors, no failed requests |
| Accessibility (WCAG 2.0/2.1/2.2 A + AA rules) | axe-core on every crawled page | **0 violations** on the re-checked public, tool and dashboard pages (was: low contrast on every dashboard page, unlabeled image links in articles, a non-valid `aria-label`, nested `<main>`) |
| Mobile layout (390 px wide) | Playwright, every public and dashboard route | No horizontal scrolling anywhere |
| End-to-end click test (`scratchpad/pw/vr/e2e.mjs`) | 70 steps: sign-in, tools, forms, dashboard create/publish/upload/export | **70/70 passed**, no console errors |
| Reduced motion, skip link, loading / error / empty states | Code review | Present: global `prefers-reduced-motion` rule, "Skip to content" link, `role="status"` loaders, retry buttons on load errors, error page that auto-reloads once after a deploy |
| Placeholder / unfinished text | Crawl text scan + code search | None in the app ("Coming Soon" badge only appears for tools switched off in the dashboard) |
| Unused stylesheet files | Import scan | None — every CSS file is imported |

## Performance

| Build output | Before | After |
|---|---|---|
| Journal Finder page code | 2,583 kB JavaScript (417 kB gzipped) | 79 kB JavaScript (24 kB gzipped) |
| Journal list (7,679 journals) | inside that JavaScript | separate `journals_db-<hash>.json`, 2,716 kB (400 kB gzipped), downloaded only when the Journal Finder opens |
| All JavaScript files together | 4.37 MB | 1.87 MB |
| First page load (home) | ~460 kB JS | ~460 kB JS, now split so React/router (`react-vendor-<hash>.js`, 237 kB) stays cached across most deploys |

- The journal list is never loaded on other pages (verified: the home page requests no journal file).
- It is fetched once per visit and parsed as JSON (faster than parsing 2.7 MB of JavaScript). The file name contains a
  content hash, so the browser can keep it until the list changes. WhiteNoise serves it compressed (gzip/brotli).
- Article images now get their real width/height from the image catalog, so text no longer jumps while images load.
- Remaining large chunk: the Research Analyzer page (532 kB, mostly the charts library). It already loads only on that page.
- Global CSS is one 489 kB file (85 kB gzipped). Dashboard-only and analyzer-only styles could be moved out of it later,
  but some of their classes are shared with public/account pages, so this was not changed before launch (risk of visual
  regressions). Low priority.

## Fixed (file — what)

- `src/data/journalFinder/journals_db.js` → `journals_db.json` — journal list moved out of the JavaScript bundle.
- `src/features/journalFinder/journalFinderModel.js` — `loadJournalFinderModules()` now fetches the JSON (same return shape, so the page did not need changes); a failed download can be retried.
- `src/data/journalFinder/matching_logic.js` — receives the list through `setJournalDatabase()` instead of a static import.
- `vite.config.js` — React/router vendor chunk for long-term caching.
- `src/utils/articleContent.js` — article links that pointed at e-mail addresses without `mailto:` (they opened broken ResRef pages, 9 found) now open the e-mail app; `www.` links get `https://`; links to old WordPress image uploads now open the self-hosted copy; image-only links get an accessible name; images get width/height.
- `src/utils/optimizedImages.js` — new `optimizedImageEntry()` helper (image size lookup).
- `src/pages/site/HomePage.jsx`, `src/components/RouteErrorBoundary.jsx` — removed a second `<main>` landmark nested inside the layout.
- `src/components/dashboard/DashboardPrimitives.jsx` — dashboard pop-up dialogs: focus moves into the dialog, Tab stays inside, Escape closes, focus returns to the button that opened it.
- `src/pages/dashboard/posts/ArticleLibrary.jsx` — readiness dots have a valid role for their label.
- Contrast (text was 2.3–4.4:1, now ≥ 4.5:1): `styles/pages/dashboard-brand.css` (dashboard muted text token), `dash-admin.css`, `dash-articles.css`, `dash-library.css`, `dashboard-ui.css`, `admin.css`, `stitch-app.css`, `upgrades.css`, `reference-generator.css`, `pages/tool-workspace.css` (green "synced" text), `pages/research-analyzer-studio.css` (locked steps), `pages/resource-card.css` (disabled pager buttons).
- `styles/pages/resource-card.css` — page-number buttons were squeezed to 20 px on phones by a global rule; restored to 44 px touch targets.
- Tests: `frontend/tests/frontend-quality.test.mjs` (journal list not bundled + matching works, image sizes, vendor chunk, no nested `<main>`).

## Not fixed / for others

- **Content data (WordPress import):** several imported articles have a wrong SEO title (e.g. "The Scientific Publication
  Process…" has the SEO title of a questionnaire guide, so the browser tab/Google title is wrong). Check the SEO titles
  after the final import (`seo_title` field; dashboard → Posts → SEO).
- **Content:** some articles contain links to `https://resref.com/wp-content/uploads/…` files that are not images (PDFs etc.);
  they keep working only while the old WordPress host exists — covered by the WordPress migration plan.
- **SEO agent:** legal pages, sign-in/register and account pages show the generic tab title "ResRef".
- **Deployment (optional):** Vite file names already contain a hash; setting WhiteNoise's
  `WHITENOISE_IMMUTABLE_FILE_TEST` to match `/assets/<name>-<hash>.<ext>` would let browsers cache them for a year
  instead of 60 seconds.
- Dashboard tables use 16–17 px checkboxes and 21 px-tall tree rows; they pass WCAG 2.5.8 through its spacing exception.

## How to re-run the checks

From `<scratchpad>/pw/vr` (needs the API on 8765/8776 and `vite preview --port 5176`):
`AUTH=member MODE=public node fq_crawl.mjs out.json`, `AUTH=admin MODE=dashboard node fq_crawl.mjs out.json`,
`AUTH=admin node fq_axe_detail.mjs /dashboard …` (axe details), `node e2e.mjs http://127.0.0.1:5176`.
