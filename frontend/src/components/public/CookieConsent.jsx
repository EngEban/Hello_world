import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { analyticsAvailable, OPEN_SETTINGS_EVENT, readConsent, saveConsent } from '../../utils/analytics';
import '../../styles/global/cookie-consent.css';

// Small, non-blocking consent banner. It only appears when analytics is
// configured; "Accept" and "Reject" carry equal weight, and the choice can be
// changed at any time from the Cookie Policy page.
export default function CookieConsent() {
  const [open, setOpen] = useState(() => analyticsAvailable() && readConsent() === null);
  const returnFocus = useRef(null);
  const panel = useRef(null);

  useEffect(() => {
    const reopen = () => {
      if (!analyticsAvailable()) return;
      returnFocus.current = document.activeElement;
      setOpen(true);
    };
    window.addEventListener(OPEN_SETTINGS_EVENT, reopen);
    return () => window.removeEventListener(OPEN_SETTINGS_EVENT, reopen);
  }, []);

  useEffect(() => {
    // Move focus only when the visitor asked to change settings.
    if (open && returnFocus.current) panel.current?.querySelector('button')?.focus();
  }, [open]);

  if (!open) return null;
  const choose = value => {
    saveConsent(value);
    setOpen(false);
    returnFocus.current?.focus?.();
    returnFocus.current = null;
  };

  return (
    <section ref={panel} className="rr-consent" role="region" aria-labelledby="rr-consent-title" aria-describedby="rr-consent-text">
      <div className="rr-consent-copy">
        <h2 id="rr-consent-title">Analytics cookies</h2>
        <p id="rr-consent-text">
          With your permission we use Google Analytics cookies to count visits and see which pages help researchers.
          No advertising, and nothing loads unless you accept. <Link to="/cookie-policy">Cookie Policy</Link>
        </p>
      </div>
      <div className="rr-consent-actions">
        <button type="button" className="rr-consent-button" onClick={() => choose('denied')}>Reject</button>
        <button type="button" className="rr-consent-button rr-consent-button-primary" onClick={() => choose('granted')}>Accept</button>
      </div>
    </section>
  );
}
