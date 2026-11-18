import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { applyStoredConsent, CONSENT_EVENT, trackPageView } from '../../utils/analytics';
import { dropStaleServerMeta, setRobots } from '../../utils/seo';

// Private or thin screens stay out of search results (the server sends the
// same directive on a direct visit; this keeps in-app navigation consistent).
const NOINDEX_PATHS = [/^\/(sign-in|auth|register)$/, /^\/account(\/|$)/, /^\/tools\/[^/]+$/];

export function robotsFor(location) {
  if (NOINDEX_PATHS.some(pattern => pattern.test(location.pathname))) return 'noindex, follow';
  const params = new URLSearchParams(location.search);
  if (params.get('q') || params.get('tag') || params.get('focus')) return 'noindex, follow';
  return '';
}

export default function RouteDiscoverability() {
  const location = useLocation();
  useEffect(() => { applyStoredConsent(); }, []);
  useEffect(() => {
    dropStaleServerMeta();
    setRobots(robotsFor(location));
    // Let the page set its title first so the page view is labelled correctly.
    const timer = window.setTimeout(() => trackPageView(location), 400);
    // Count the page the visitor is on when they accept analytics.
    const onConsent = event => { if (event.detail?.analytics === 'granted') trackPageView(location); };
    window.addEventListener(CONSENT_EVENT, onConsent);
    return () => { window.clearTimeout(timer); window.removeEventListener(CONSENT_EVENT, onConsent); };
  }, [location]);
  return null;
}
