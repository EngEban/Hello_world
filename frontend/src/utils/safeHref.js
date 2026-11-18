// Links typed by administrators (site settings, notifications) are rendered on
// public pages. React still renders `javascript:` URLs, so every such link goes
// through this helper: anything that is not a same-site path or an allowed
// scheme is replaced by the fallback.
const SAFE_SCHEMES = new Set(['http:', 'https:', 'mailto:', 'tel:']);

export function safeHref(value, fallback = '#') {
  if (typeof value !== 'string') return fallback;
  const href = value.trim();
  if (!href) return fallback;
  if (/[\u0000-\u001f]/.test(href)) return fallback;
  if (href.startsWith('#')) return href;
  if (href.startsWith('/')) return href.startsWith('//') || href.startsWith('/\\') ? fallback : href;
  try {
    const url = new URL(href);
    return SAFE_SCHEMES.has(url.protocol) ? href : fallback;
  } catch {
    return fallback;
  }
}
