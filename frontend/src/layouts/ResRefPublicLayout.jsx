import { Suspense } from 'react';
import { Outlet } from 'react-router-dom';
import LoadingState from '../components/common/LoadingState';
import ArabicTextEnhancer from '../components/public/ArabicTextEnhancer';
import CookieConsent from '../components/public/CookieConsent';
import VerifyEmailBanner from '../components/account/VerifyEmailBanner';
import RouteDiscoverability from '../components/public/RouteDiscoverability';
import ScrollToTop from '../components/public/ScrollToTop';
import SiteFooter from '../components/public/SiteFooter';
import SiteHeader from '../components/public/SiteHeader';
import { useReveal } from '../components/home/HomePrimitives';
import { AccountProvider } from '../contexts/AccountContext';
import { SiteSettingsProvider } from '../contexts/SiteSettingsContext';

export default function ResRefPublicLayout() {
  // Scroll-in motion for any `[data-reveal]` block on public pages.
  const revealRef = useReveal();
  return (
    <AccountProvider>
      <SiteSettingsProvider>
        <ScrollToTop />
        <RouteDiscoverability />
        <ArabicTextEnhancer />
        <div className="resref-app-shell">
          <SiteHeader />
          <VerifyEmailBanner />
          <div className="resref-app-main">
            <main className="resref-page" id="public-content" tabIndex={-1} ref={revealRef}>
              <Suspense fallback={<div className="site-container route-loading"><LoadingState /></div>}>
                <Outlet />
              </Suspense>
            </main>
            <SiteFooter />
          </div>
        </div>
        <CookieConsent />
      </SiteSettingsProvider>
    </AccountProvider>
  );
}
