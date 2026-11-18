# Search, AI discoverability and analytics

What is built, what you need to set up, and how to check it after the first deploy.

## What the site now does

**Every page is readable without JavaScript.** Django writes each page's title, description, canonical address,
robots rule, social preview tags (Open Graph and Twitter) and structured data into the HTML before it is sent.
Google, Bing, social previews (WhatsApp, LinkedIn, X, Facebook) and AI crawlers all see the correct page. Articles,
pages, topics, author profiles and the FAQ also include a plain-text copy of their content inside `<noscript>`.
The code is in `backend/resref/seo.py`.

| URL | What it does |
| --- | --- |
| `/robots.txt` | Lets search engines crawl public pages. Blocks `/dashboard`, `/account` and `/api/`, except the read-only APIs that pages need to load (Google runs JavaScript and must be able to fetch them). Points to the sitemap. The admin address is not listed. |
| `/sitemap.xml` | Lists the public pages, topics that have articles, published articles (with last-updated date), published pages, and authors with published work. Drafts, pending, private, trashed and scheduled posts are never listed. Cached for 15 minutes. |
| `/llms.txt` | A short summary of ResRef for AI assistants: what it is, key pages, database topics and the latest 30 articles. |
| `/llms-full.txt` | Every published article with its URL, authors, dates, summary and section headings. |

**Structured data (schema.org):** Organization and WebSite (with site search) on every page. Breadcrumbs on inner
pages. `Article` on articles, with named authors linked to their profile pages, dates, image and publisher.
`ProfilePage` + `Person` on author pages (with ORCID, Google Scholar and similar links). `FAQPage` on `/faq`, built
from the dashboard FAQ.

**Duplicate addresses:**
- Old aliases such as `/about-us`, `/home` and `/contact-us` permanently redirect (301) to their main address.
- A trailing slash also redirects: `/about/` goes to `/about`.
- An old `/<article-slug>` link redirects to `/database/<topic>/<article-slug>`.
- Unknown addresses, and drafts or private posts, return a real 404. The page shown to visitors is unchanged.

**Hidden from search (noindex):**
- Sign-in, register, account and newsletter-confirmation pages.
- The dashboard.
- Search-result and tag-filter listings.
- The four tool pages that need sign-in. The public `/tools` page describes these tools and is indexed.
- Author profiles with no published work yet.

**Staging is never indexed.** Unless `RESREF_ENV=production` (or `SEO_ALLOW_INDEXING=true`), `robots.txt` blocks
everything and every page says `noindex`.

**Google Analytics 4 with consent:** Analytics only runs when `GA_MEASUREMENT_ID` is set. Visitors then see a small
banner with equal **Accept** and **Reject** buttons. Nothing from Google loads until a visitor accepts. Consent Mode v2
starts with everything denied, and advertising stays off.
- Page views are sent on every in-app page change.
- Only the page path is sent. Search terms, reset links and other query strings are removed. Only listing filters
  (`cat`, `tag`, `page`, `sort`) are kept.
- Visitors can change their choice on the Cookie Policy page under "Cookie settings". Withdrawing consent deletes the
  `_ga` cookies.
- The Cookie Policy and Privacy Policy now describe this accurately.

## Accounts you need to create (owner)

You need a Google account that will own these, ideally a shared team account such as `web@resref.com`, not a
personal one.

1. **Google Analytics 4 property** (analytics.google.com)
   - Admin → Create → Property "ResRef", your time zone and currency → Web data stream, URL `https://resref.com`.
   - In the stream, open **Enhanced measurement** → gear on *Page views* → turn **off** "Page changes based on
     browser history events". ResRef sends these page views itself; leaving this on counts them twice.
   - Admin → Data collection and modification → Data retention → **14 months**. The Cookie Policy states this.
   - Admin → Data collection → leave **Google signals off**.
   - **Give us:** the Measurement ID, which looks like `G-XXXXXXXXXX`. It is not a secret.
2. **Google Search Console** (search.google.com/search-console)
   - Recommended: add a **Domain property** for `resref.com`. Google gives you a TXT record; add it at your DNS
     provider (where resref.com's DNS is managed). This covers http/https and all subdomains, and no code is needed.
   - Alternative: a **URL-prefix property** for `https://resref.com/` with the **HTML tag** method. Copy only the
     `content` value from the tag Google shows and **give us** that value for `GOOGLE_SITE_VERIFICATION`.
   - After verifying: Sitemaps → submit `https://resref.com/sitemap.xml`.
   - Optional: Settings → Associations → link the GA4 property.
3. **Bing Webmaster Tools** (optional; also feeds ChatGPT search and Copilot) (bing.com/webmasters)
   - Easiest: "Import from Google Search Console". Otherwise choose the meta-tag method and **give us** the
     `msvalidate.01` content value for `BING_SITE_VERIFICATION`. Then submit the sitemap.

## Environment variables (Railway, web service)

| Name | Purpose | Example |
| --- | --- | --- |
| `GA_MEASUREMENT_ID` | Turns on GA4 and the consent banner. Not set means no analytics and no banner. | `G-AB12CD34EF` |
| `GOOGLE_SITE_VERIFICATION` | Search Console HTML-tag token. Not needed with DNS verification. | `aBcD1234...` |
| `BING_SITE_VERIFICATION` | Bing `msvalidate.01` token (optional). | `0123ABCD...` |
| `SEO_SITE_URL` | Canonical origin, if it should differ from `FRONTEND_BASE_URL`. Set it to the final custom domain. | `https://resref.com` |
| `SEO_ALLOW_INDEXING` | Override for indexing. The default is on only in production. Set `false` on any staging service. | `true` |
| `SEO_AI_CRAWLERS` | `allow` (default): AI search and training crawlers may read public pages. `search-only`: blocks training crawlers (GPTBot, ClaudeBot, Google-Extended, CCBot…) but allows AI answer engines (ChatGPT search, Perplexity, Claude search). `block`: blocks both. | `allow` |

Optional build-time alternative: `VITE_GA_MEASUREMENT_ID`. The runtime `GA_MEASUREMENT_ID` is preferred because it
needs no rebuild.

Canonical links use `SEO_SITE_URL`, then `FRONTEND_BASE_URL`, then `https://PUBLIC_HOSTNAME`. Before launch, make
sure one of these is the **final public domain**. If it is the `*.up.railway.app` address, search engines will
index that address instead.

## Content guidance (for editors)

- Fill in the **SEO title** (under about 60 characters) and **SEO description** (about 150–160 characters) for each
  article. If they are empty, the title and excerpt are used.
- Give each article a **featured image**. It becomes the social preview; without one, the ResRef card is used. A
  1200×630 image works best.
- Structure articles with real **H2/H3 headings**. They become the table of contents and the outline that AI tools
  and llms-full.txt use. Start with a one or two sentence direct answer or summary, then the detail.
- Credit **named contributors** with complete profiles (position, institution, short bio, ORCID). This builds
  expertise signals (E-E-A-T) for medical and research topics.
- Put each article's **main topic first** in its categories. The first category decides the article's address.
- Keep FAQ answers short and factual. They are published as FAQPage structured data.

## Checks after the first deploy

1. Open `https://resref.com/robots.txt`, `/sitemap.xml` and `/llms.txt`.
2. View the page source of an article and confirm the `<title>`, `canonical`, `og:` tags and the JSON-LD block.
3. Run Google's Rich Results Test (search.google.com/test/rich-results) on an article and on `/faq`.
4. Paste an article link into the LinkedIn Post Inspector or a WhatsApp chat to see the preview.
5. Open the site in a private window and check the banner. Accept, then confirm the visit appears in GA4 →
   Reports → Realtime. Reject in another private window and confirm nothing is sent.
6. In Search Console, use URL Inspection → "Test live URL" on the home page and on one article.

## Performance notes (Core Web Vitals)

Fixed in this round:
- Google Fonts are now requested from the HTML head with `preconnect`, instead of being discovered late from inside
  the CSS bundle.
- The page shell is served with `Cache-Control: no-cache`, so a new deploy is seen immediately.
- The home hero image already uses `fetchpriority="high"` with width and height set.

Still to do (other files):
- WhiteNoise serves Vite's content-hashed files in `/static/assets/` with `max-age=60`. They can be cached for a year
  (see the request in the audit report).
- The `@import` of Google Fonts in `styles/base.css` and `styles/resref.css` can be removed now that `index.html`
  loads the fonts. That removes a render-blocking request chain.
- Article, page and card images have no `width`/`height`, which can shift the layout while they load (CLS). The
  article hero image should load eagerly; it currently has `fetchpriority="high"` with no size.
