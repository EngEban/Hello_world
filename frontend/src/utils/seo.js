import { useEffect } from 'react';

// Keep identical to ORGANIZATION_DESCRIPTION in backend/resref/seo.py: one
// consistent "about" statement for search and answer engines.
export const SITE_NAME = 'ResRef';
export const ORGANIZATION_DESCRIPTION = 'ResRef is a research reference platform for students, clinicians and researchers. It offers a searchable database of research resources and validated questionnaires, learning articles on research methods, practical research tools, research opportunities and expert research consultation.';

// Django writes per-URL metadata into index.html (marked data-seo="server")
// for crawlers that do not run JavaScript. In the browser those tags stay valid
// only for the URL they were rendered for.
const SERVER = '[data-seo="server"]';

function headMeta(name) {
  if (typeof document === 'undefined') return '';
  return document.querySelector(`meta[name="${name}"]`)?.getAttribute('content') || '';
}

export const serverSeoPath = () => headMeta('resref:seo-path');
const onServerRenderedPath = () => typeof window !== 'undefined' && serverSeoPath() === window.location.pathname;

/** Remove server-rendered tags once the visitor has navigated to another URL. */
export function dropStaleServerMeta() {
  if (typeof document === 'undefined' || onServerRenderedPath()) return;
  document.querySelectorAll(`${SERVER}:not(title)`).forEach(node => node.remove());
}

/** Use the configured public origin (custom domain) for canonical URLs. */
export function canonicalUrl(value) {
  const site = headMeta('resref:site-url');
  if (!value || !site) return value;
  try {
    const url = new URL(value, window.location.origin);
    const origin = new URL(site).origin;
    return new URL(`${url.pathname}${url.search}`, origin).href;
  } catch {
    return value;
  }
}

function selectorFor(kind, key) {
  if (kind === 'link') return `link[rel="${key}"]`;
  return `meta[${kind}="${key}"]`;
}

// Update the existing tag instead of adding a duplicate.
// Returns the element when this page owns it (and must remove it on cleanup).
function upsert(kind, key, value) {
  if (!value) return null;
  const existing = document.head.querySelector(selectorFor(kind, key));
  const attr = kind === 'link' ? 'href' : 'content';
  if (existing) {
    if (existing.dataset.seo === 'server') {
      // Server tags are authoritative for the URL they were rendered for.
      if (onServerRenderedPath()) return null;
      delete existing.dataset.seo; // claimed: now belongs to this page
    }
    existing.setAttribute(attr, value);
    return existing;
  }
  const tag = document.createElement(kind === 'link' ? 'link' : 'meta');
  if (kind === 'link') tag.rel = key; else tag.setAttribute(kind, key);
  tag.setAttribute(attr, value);
  document.head.appendChild(tag);
  return tag;
}

export function setRobots(value) {
  if (typeof document === 'undefined') return;
  const existing = document.head.querySelector('meta[name="robots"]');
  if (existing?.dataset.seo === 'server' && onServerRenderedPath()) return;
  if (!value) { existing?.remove(); return; }
  upsert('name', 'robots', value);
}

export function usePageMeta(meta) {
  useEffect(() => {
    if (!meta) return undefined;
    if (meta.title) document.title = meta.title;
    // Description persists between pages (every page sets its own).
    upsert('name', 'description', meta.description);
    const canonical = canonicalUrl(meta.canonical);
    const owned = [
      upsert('link', 'canonical', canonical),
      upsert('property', 'og:url', canonical),
      upsert('property', 'og:title', meta.title),
      upsert('property', 'og:description', meta.description),
      upsert('property', 'og:type', meta.type || 'website'),
      upsert('property', 'og:image', meta.image),
      upsert('name', 'twitter:title', meta.title),
      upsert('name', 'twitter:description', meta.description),
      upsert('name', 'twitter:image', meta.image),
    ];
    if (meta.robots) setRobots(meta.robots);
    // Server JSON-LD for this exact URL is authoritative; add client data only
    // after in-app navigation.
    const serverJsonLd = document.head.querySelector(`script[type="application/ld+json"]${SERVER}`);
    if (meta.structuredData && !(serverJsonLd && onServerRenderedPath())) {
      const script = document.createElement('script'); script.type = 'application/ld+json';
      script.textContent = JSON.stringify(meta.structuredData).replace(/</g, '\\u003c');
      document.head.appendChild(script); owned.push(script);
    }
    return () => owned.forEach(node => node?.remove());
  }, [meta]);
}
