// Google Analytics 4 with Consent Mode v2.
//
// Nothing is loaded and no analytics cookie is set unless BOTH a measurement ID
// is configured (GA_MEASUREMENT_ID on the server, written into the page as
// <meta name="resref:ga-id">, or VITE_GA_MEASUREMENT_ID at build time) AND the
// visitor accepted analytics in the cookie banner. Only page paths are sent:
// query strings (which can hold search terms or one-time tokens) are dropped
// except for a short allowlist of non-personal listing filters.

const CONSENT_KEY = 'resref_cookie_consent';
const CONSENT_VERSION = 1;
const ID_PATTERN = /^G-[A-Z0-9]{4,20}$/;
const SAFE_QUERY_KEYS = ['cat', 'tag', 'page', 'sort'];
export const CONSENT_EVENT = 'resref:consent-change';
export const OPEN_SETTINGS_EVENT = 'resref:open-cookie-settings';

let scriptLoaded = false;

export function measurementId() {
  if (typeof document === 'undefined') return '';
  const fromServer = document.querySelector('meta[name="resref:ga-id"]')?.getAttribute('content') || '';
  const value = (fromServer || import.meta.env.VITE_GA_MEASUREMENT_ID || '').trim().toUpperCase();
  return ID_PATTERN.test(value) ? value : '';
}

export const analyticsAvailable = () => Boolean(measurementId());

/** 'granted' | 'denied' | null (not asked yet). */
export function readConsent() {
  try {
    const stored = JSON.parse(window.localStorage.getItem(CONSENT_KEY) || 'null');
    if (stored?.version === CONSENT_VERSION && ['granted', 'denied'].includes(stored.analytics)) return stored.analytics;
  } catch { /* storage unavailable or malformed: ask again */ }
  return null;
}

function gtag() {
  // gtag.js expects the Arguments object itself, not an array.
  window.dataLayer.push(arguments);
}

function ensureGtag() {
  window.dataLayer = window.dataLayer || [];
  if (!window.gtag) {
    window.gtag = gtag;
    // Consent Mode v2: everything denied until the visitor opts in. Advertising
    // signals are never enabled by ResRef.
    window.gtag('consent', 'default', {
      ad_storage: 'denied', ad_user_data: 'denied', ad_personalization: 'denied',
      analytics_storage: 'denied', functionality_storage: 'denied', personalization_storage: 'denied',
      security_storage: 'granted', wait_for_update: 500,
    });
  }
}

function enable(id) {
  ensureGtag();
  window[`ga-disable-${id}`] = false;
  window.gtag('consent', 'update', { analytics_storage: 'granted' });
  if (scriptLoaded) return;
  scriptLoaded = true;
  window.gtag('js', new Date());
  const path = safePagePath(window.location);
  window.gtag('config', id, {
    send_page_view: false, // page views are sent on every route change instead
    page_location: `${window.location.origin}${path}`, // never the raw URL (it may hold tokens)
    page_path: path,
    allow_google_signals: false,
    allow_ad_personalization_signals: false,
  });
  const script = document.createElement('script');
  script.async = true;
  script.src = `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(id)}`;
  document.head.appendChild(script);
}

function removeAnalyticsCookies() {
  const host = window.location.hostname;
  const domains = ['', host, `.${host}`, `.${host.split('.').slice(-2).join('.')}`];
  document.cookie.split('; ').map(row => row.split('=')[0]).filter(name => /^_ga(_|$)|^_gid$|^_gat/.test(name)).forEach(name => {
    domains.forEach(domain => {
      document.cookie = `${name}=; Max-Age=0; path=/${domain ? `; domain=${domain}` : ''}; SameSite=Lax`;
    });
  });
}

function disable(id) {
  if (window.gtag) window.gtag('consent', 'update', { analytics_storage: 'denied' });
  window[`ga-disable-${id}`] = true;
  removeAnalyticsCookies();
}

/** Apply the stored choice; call once on start-up. */
export function applyStoredConsent() {
  const id = measurementId();
  if (id && readConsent() === 'granted') enable(id);
}

export function saveConsent(choice) {
  const analytics = choice === 'granted' ? 'granted' : 'denied';
  try {
    window.localStorage.setItem(CONSENT_KEY, JSON.stringify({ version: CONSENT_VERSION, analytics, savedAt: new Date().toISOString() }));
  } catch { /* the choice still applies for this visit */ }
  const id = measurementId();
  if (id) (analytics === 'granted' ? enable : disable)(id);
  window.dispatchEvent(new CustomEvent(CONSENT_EVENT, { detail: { analytics } }));
}

export function openCookieSettings() {
  window.dispatchEvent(new Event(OPEN_SETTINGS_EVENT));
}

export function safePagePath(location) {
  const params = new URLSearchParams(location.search || '');
  const kept = new URLSearchParams();
  SAFE_QUERY_KEYS.forEach(key => { const value = params.get(key); if (value) kept.set(key, value.slice(0, 80)); });
  const query = kept.toString();
  return `${location.pathname}${query ? `?${query}` : ''}`;
}

/**
 * Records one action, only for visitors who accepted analytics. Pass labels
 * like a form or tool name, never anything a visitor typed or personal details.
 */
export function trackEvent(name, params = {}) {
  if (!measurementId() || !scriptLoaded || readConsent() !== 'granted' || !window.gtag) return;
  window.gtag('event', name, params);
}

export function trackPageView(location) {
  const id = measurementId();
  if (!id || !scriptLoaded || readConsent() !== 'granted' || !window.gtag) return;
  const path = safePagePath(location);
  const page = { page_path: path, page_location: `${window.location.origin}${path}`, page_title: document.title };
  // Later automatic events (engagement, scrolls) reuse these sanitised values.
  window.gtag('set', page);
  window.gtag('event', 'page_view', page);
}
