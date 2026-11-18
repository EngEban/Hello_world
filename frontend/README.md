# ResRef frontend (React + Vite)

Single-page app for the public website, member area, research tools and admin dashboard.
In production Django serves the built files; locally Vite proxies `/api` to Django.

```powershell
npm ci
npm run dev        # http://127.0.0.1:5173 (API proxy target: VITE_API_PROXY_TARGET, default http://127.0.0.1:8000)
npm run lint       # must report 0 errors
node --test tests/*.test.mjs
npm run build      # output in dist/ (the Dockerfile builds with VITE_ASSET_BASE_PATH=/static/)
```

Source layout (details in [`../docs/architecture.md`](../docs/architecture.md)):

```text
src/
  main.jsx        routes + global stylesheet order
  layouts/        public and dashboard shells
  pages/          site/, public/, account/, dashboard/<domain>/
  components/     common/, public/, account/, dashboard/, home/
  features/       journalFinder/, referenceGenerator/, sampleSizeCalculator/, researchAnalyzer/
  api/  hooks/  contexts/  config/  data/  utils/
  styles/         global/ (brand-ui.css = design system), pages/, tools/, dashboard/
public/           logos, hero images, optimised images, social image
tests/            node:test checks
```

Rules: never use the retired brand hex values (a test enforces this); keep gradients for hero/feature
backgrounds only; new page styles go in `src/styles/pages/` and are imported by that page.
