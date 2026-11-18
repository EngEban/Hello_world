# ResRef launch checklist

Prepared 22 Oct 2026 while Railway deployments were paused. Detailed notes for each area are in this folder:
[security](security.md) · [backup-and-recovery](backup-and-recovery.md) · [monitoring](monitoring.md) ·
[accounts-and-email](accounts-and-email.md) · [premium-and-limits](premium-and-limits.md) ·
[seo-analytics](seo-analytics.md) · [wordpress-migration](wordpress-migration.md) · [frontend-quality](frontend-quality.md)

Verification at the time of writing: all backend tests pass on PostgreSQL (the same database GitHub CI uses),
`check --deploy` clean, `pip-audit` 0 known vulnerabilities, `npm audit --omit=dev` 0, frontend lint 0 errors,
frontend tests pass, production build OK, 70/70 click-test steps with no browser console errors,
0 automated accessibility (axe WCAG 2.2 AA) violations on the checked pages.

---

## 1. Already complete
- New design across the website and admin dashboard; mobile, tablet and desktop checked.
- Security hardening: HTTPS-only cookies and HSTS in production, CSP, upload checks, per-endpoint permissions,
  request-size limit, rate limits on every public form and login/reset/password endpoints, secrets masked in logs,
  app runs as a non-root user, dependency vulnerabilities fixed (Pillow upgrade).
- Accounts: sign-up with email verification, login lockout, password reset, sessions invalidated on password change,
  "keep me signed in", security emails (password changed, new sign-in, email changed, account deleted),
  safe email change, download-my-data, delete-my-account (deactivate + anonymise; nothing hard-deleted).
- Sign-up and profile: country (required on the form) and international phone number (optional, stored as +E.164),
  using the maintained `react-phone-number-input` and `phonenumbers` libraries. Visible to admins in the user editor.
- Free/Premium: one server-side usage engine with daily/monthly limits per tool and per plan, editable in
  Dashboard → Premium Controls → Enforcement. Race-safe counters; refreshing or calling the API directly is still counted.
  Launch limits are generous (see table in premium-and-limits.md); nothing restrictive is switched on.
- SEO/GEO/AEO foundation: server-rendered titles, descriptions, canonicals, Open Graph/Twitter cards and structured data
  (Organization, WebSite search, Breadcrumbs, Article, Person, FAQPage) for every public page; real 404s; 301 redirects for
  duplicate URLs; `/robots.txt`, `/sitemap.xml`, `/llms.txt`, `/llms-full.txt`; staging is never indexed.
- Google Analytics 4 ready behind a cookie-consent banner (Consent Mode v2, off until an ID is set); cookie and privacy
  policies updated; "Cookie settings" link in the footer.
- Performance: Journal Finder data split out of the main bundle (JavaScript output 4.4 MB → 1.9 MB), long-term caching for
  built files, image sizes to prevent layout shift, one font request instead of three.
- WordPress migration tooling: safe, re-runnable importer with dry-run report (WXR XML or SQL dump), media copy,
  redirects for old URLs and image links, WordPress passwords accepted and upgraded on first sign-in.
- Optional error reporting (Sentry) and JSON logs, both switched on by environment variables only.
- Backup and restore runbook written; the app-level export/restore was tested on a copy of the data.

## 2. Issues found (and status)
| Severity | Issue | Status |
|---|---|---|
| Critical | Search engines, social previews and AI crawlers saw an empty page titled "ResRef" for every URL | Fixed |
| High | Image library (Pillow) had 24 known vulnerabilities | Fixed (13.0.0) |
| High | Password-reset tokens were written to the server access log | Fixed |
| High | Old WordPress image links would break at the domain switch | Fixed (copy + 301) |
| High | Old importer overwrote dashboard edits and had no dry run | Fixed (rewritten) |
| High | No rate limit on password change | Fixed |
| High | Journal Finder downloaded 2.5 MB of JavaScript on first visit | Fixed |
| Medium | Editors without delete rights could trash articles from the editor | Fixed |
| Medium | Sign-up timing revealed whether an email had an account | Fixed |
| Medium | No account deletion / data export; no safe email change | Fixed |
| Medium | Usage limits not race-safe; no master switch; Sample Size not metered | Fixed |
| Medium | Low colour contrast across the dashboard | Fixed |
| Medium | Migrations ran twice on Railway; app ran as root with the media volume | Fixed |
| Medium | Imported articles carry wrong SEO titles (e.g. another article's title) | Needs final WordPress data, then review |
| Low | Several smaller items (see each area's notes) | Fixed |

## 3. Fix now (done in this round)
Everything marked "Fixed" above. Nothing destructive was run; database changes are additive only
(new fields and tables: accounts 0013, usage 0001–0002, redirects 0001).

## 4. Requires Railway (once deployments work)
1. In the API service **Variables**, make sure `DATABASE_URL = ${{Postgres.DATABASE_URL}}` and
   `REDIS_URL = ${{<redis service>.REDIS_URL}}` are references (they pick up the rotated passwords), same for the cron service.
2. Deploy the API service (pre-deploy `migrate` adds the new tables/fields; no data is removed), then the cron service.
3. Check `/api/health/` shows `"database": "ok"`; open the site, sign in, open the dashboard.
4. Turn on Railway **backups** for Postgres (daily) and the media volume; do one restore drill (backup-and-recovery.md).
5. After deploy, check Dashboard → Premium Controls → Features: Research Analyzer access for Free users (owner decision below).
6. Run the full click test against the live site (I can do this once it is up).

## 5. Requires credentials / accounts from you
| Service | What to create | What to set (Railway variables) — never paste secrets in chat |
|---|---|---|
| **Brevo** (email) | Verify the `resref.com` domain (done), create a sender, create an **API key** (SMTP & API → API Keys, starts `xkeysib-`) | `BREVO_API_KEY=xkeysib-…` and `DJANGO_DEFAULT_FROM_EMAIL=ResRef <no-reply@resref.com>`. The API is used because Railway blocks SMTP ports on Trial/Hobby plans. New members get in at once and have `ACCOUNT_EMAIL_VERIFICATION_GRACE_DAYS` (default 2) to confirm. |
| **Domain** | Point `resref.com` to Railway (custom domain in the API service) | `PUBLIC_HOSTNAME=resref.com`, `FRONTEND_BASE_URL=https://resref.com`, `SEO_SITE_URL=https://resref.com` |
| **Google Analytics 4** | A GA4 property + web stream for resref.com | `GA_MEASUREMENT_ID=G-…` (send me the ID; it is not secret) |
| **Google Search Console** | Domain property, verified by DNS TXT (no code needed) — or HTML tag | optional `GOOGLE_SITE_VERIFICATION=…`; then submit `https://resref.com/sitemap.xml` |
| Bing Webmaster Tools (optional) | Import from Search Console | optional `BING_SITE_VERIFICATION` |
| Sentry (optional) | Free project for error alerts | `SENTRY_DSN`, `SENTRY_ENVIRONMENT=production` |
| Google sign-in (optional) | OAuth client ID for resref.com | `GOOGLE_OAUTH_CLIENT_ID` |
| Stripe (later) | Only when Premium payments start; live keys are entered by you | see [deployment](../deployment.md) |
| Supabase | Not needed — Railway Postgres is used. Only consider later for a specific reason | — |

## 6. Requires the final WordPress database
- Provide: the full **SQL dump** of the WordPress database (preferred) or a WXR XML export, plus the
  **`wp-content/uploads`** folder (zip).
- Then: backup (pg_dump) → import with `--dry-run` on a copy → review report (conflicts, wrong SEO titles, users) →
  real import on the copy → re-run shows "unchanged" → production → verify counts. Roll back by restoring the dump.
- Decide: whether member accounts move over (passwords keep working); how to resolve reported conflicts.

## 7. Owner decisions
1. **Research Analyzer for Free users**: a fresh database starts it as Premium-only; the dev data has it Free. Choose in Premium Controls → Features.
2. **Research Analyzer limits**: Premium is capped at 25/month while Free is unlimited — raise or remove the Premium cap.
3. **Contributors can publish directly** — keep, or add a review step (needs a new permission).
4. **Deleted accounts**: tool workspaces/notifications are kept with the anonymised account; approve a purge step if you want them erased.
5. **HSTS preload/subdomains** — only after the final domain works on HTTPS.
6. **AI crawlers** — allowed by default (`SEO_AI_CRAWLERS=allow`); `search-only` blocks training crawlers but keeps AI answer engines.
7. **Default social image** (`frontend/public/og-default.png`) is generated from the wordmark — replace with a designed 1200×630 image if you like.

## 8. Cloudflare — not needed for launch
Railway already provides HTTPS certificates, a global edge, and basic DDoS protection; the app has its own rate limits,
login lockout and security headers, and built files are cached by browsers for a year. Cloudflare would add a second
proxy layer (DNS, SSL modes, caching rules, real-IP headers for rate limits) that is easy to misconfigure and can break
sign-in or rate limiting if done wrong. **Recommendation: launch without it.**
Add it later (the free plan is enough) if you see bot/spam attacks, want a WAF, or want your DNS at one place. If so, use:
DNS + proxy, SSL "Full (strict)", Always Use HTTPS, Bot Fight Mode, and caching for `/static/` and `/media/` only.
Do **not** use: caching of HTML or `/api/`, Rocket Loader, Email Obfuscation, auto-minify, or "Flexible" SSL. We would also
need to trust Cloudflare's `CF-Connecting-IP` header for per-IP rate limits — tell me before turning it on.

## 9. Optional after launch
- Submit the sitemap in Search Console and Bing; watch the "Pages" and "Core Web Vitals" reports for 2–4 weeks.
- Replace the generated social image; write short, unique SEO descriptions for the top articles.
- Split dashboard-only CSS out of the global stylesheet (performance, low priority).
- Move Journal Finder/Sample Size calculations to the server if Premium limits ever need to be strict for them.
- Bump `vite` to ≥ 8.3.5 (affects the local dev server only, not production).
- Uptime monitor (e.g. Better Stack or UptimeRobot, free) on `/api/health/`.
- Open the pull request from `resref-workspace` to `main`.
