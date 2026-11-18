import React, { lazy, Suspense } from 'react';
import { createRoot } from 'react-dom/client';
import { createBrowserRouter, createRoutesFromElements, Navigate, Route, RouterProvider } from 'react-router-dom';
// Global stylesheets: order matters (later files intentionally override earlier ones).
import './styles/global/design-system.css';
import './styles/global/base.css';
import './styles/global/resref.css';
import './styles/global/upgrades.css';
import './styles/global/platform-redesign.css';
import './styles/tools/reference-generator.css';
import './styles/tools/journal-finder.css';
import './styles/global/stitch-app.css';
import './styles/dashboard/admin.css';
import './styles/global/experience-polish.css';
import './styles/dashboard/dashboard-polish.css';
import './styles/global/resilience.css';
// Shared brand design language (homepage redesign) for every public page.
import './styles/global/brand-ui.css';
// The shared page grid, type scale and interaction rules; keep this last.
import './styles/global/layout-system.css';
import ResRefPublicLayout from './layouts/ResRefPublicLayout.jsx';
import LoadingState from './components/common/LoadingState.jsx';
import RouteErrorBoundary from './components/common/RouteErrorBoundary.jsx';

const HomePage = lazy(() => import('./pages/site/HomePage.jsx'));
const DatabasePage = lazy(() => import('./pages/site/DatabasePage.jsx'));
const LearningArticlesPage = lazy(() => import('./pages/site/LearningArticlesPage.jsx'));
const QuestionnairesPage = lazy(() => import('./pages/site/QuestionnairesPage.jsx'));
const JournalFinderPage = lazy(() => import('./pages/site/JournalFinderPage.jsx'));
const ResearchToolsPage = lazy(() => import('./pages/site/ResearchToolsPage.jsx'));
const ExpertConsultationPage = lazy(() => import('./pages/site/ExpertConsultationPage.jsx'));
const SampleSizeCalculatorPage = lazy(() => import('./pages/site/SampleSizeCalculatorPage.jsx'));
const ReferenceGeneratorPage = lazy(() => import('./pages/site/ReferenceGeneratorPage.jsx'));
const ResearchAnalyzerPage = lazy(() => import('./pages/site/ResearchAnalyzerPage.jsx'));
const ResearchOpportunitiesPage = lazy(() => import('./pages/site/ResearchOpportunitiesPage.jsx'));
const JoinOurTeamPage = lazy(() => import('./pages/site/JoinOurTeamPage.jsx'));
const AboutUsPage = lazy(() => import('./pages/site/AboutUsPage.jsx'));
const TeamPage = lazy(() => import('./pages/site/TeamPage.jsx'));
const ContactUsPage = lazy(() => import('./pages/site/ContactUsPage.jsx'));
const FaqPage = lazy(() => import('./pages/site/FaqPage.jsx'));
const LegalPage = lazy(() => import('./pages/site/LegalPage.jsx'));
const NotFoundPage = lazy(() => import('./pages/site/NotFoundPage.jsx'));
const DynamicContentPage = lazy(() => import('./pages/public/DynamicContentPage.jsx'));
const AuthorProfilePage = lazy(() => import('./pages/public/AuthorProfilePage.jsx'));
const StaticContentPage = lazy(() => import('./pages/public/StaticContentPage.jsx'));
const AccountAuthPage = lazy(() => import('./pages/account/AccountAuthPage.jsx'));
const AccountPage = lazy(() => import('./pages/account/AccountPage.jsx'));
const AccountResetPasswordPage = lazy(() => import('./pages/account/AccountResetPasswordPage.jsx'));
const ConfirmEmailPage = lazy(() => import('./pages/account/ConfirmEmailPage.jsx'));
// The dashboard shell and its stylesheet load only when /dashboard is opened.
const DashboardLayout = lazy(() => import('./layouts/DashboardLayout.jsx'));
const DashboardLoginPage = lazy(() => import('./pages/dashboard/auth/LoginPage.jsx'));
const DashboardHomePage = lazy(() => import('./pages/dashboard/home/index.jsx'));
const DashboardUsersPage = lazy(() => import('./pages/dashboard/users/index.jsx'));
const DashboardPostsPage = lazy(() => import('./pages/dashboard/posts/index.jsx'));
const DashboardTaxonomyPage = lazy(() => import('./pages/dashboard/posts/TaxonomyPage.jsx'));
const DashboardAuthorsPage = lazy(() => import('./pages/dashboard/posts/AuthorsPage.jsx'));
const DashboardFaqPage = lazy(() => import('./pages/dashboard/posts/FaqManagerPage.jsx'));
const DashboardMediaPage = lazy(() => import('./pages/dashboard/media/index.jsx'));
const DashboardContactsPage = lazy(() => import('./pages/dashboard/contacts/index.jsx'));
const DashboardApplicationsPage = lazy(() => import('./pages/dashboard/contacts/ApplicationsPage.jsx'));
const DashboardTeamPage = lazy(() => import('./pages/dashboard/users/TeamPage.jsx'));
const DashboardTeamPageManager = lazy(() => import('./pages/dashboard/team-page/index.jsx'));
const DashboardRolesPage = lazy(() => import('./pages/dashboard/users/RolesPage.jsx'));
const DashboardOpportunitiesPage = lazy(() => import('./pages/dashboard/services/OpportunitiesPage.jsx'));
const DashboardServicesPage = lazy(() => import('./pages/dashboard/services/index.jsx'));
const DashboardFormsPage = lazy(() => import('./pages/dashboard/contacts/FormsPage.jsx'));
const DashboardReportsPage = lazy(() => import('./pages/dashboard/reports/index.jsx'));
const DashboardSettingsPage = lazy(() => import('./pages/dashboard/settings/index.jsx'));
const DashboardPremiumControlsPage = lazy(() => import('./pages/dashboard/settings/PremiumControlsPage.jsx'));
const DashboardResearchAnalyzerPage = lazy(() => import('./pages/dashboard/tools/ResearchAnalyzerAdminPage.jsx'));
const DashboardContentStudioPage = lazy(() => import('./pages/dashboard/settings/ContentStudioPage.jsx'));
const DashboardGuidePage = lazy(() => import('./pages/dashboard/home/GuidePage.jsx'));
const DashboardNotificationsPage = lazy(() => import('./pages/dashboard/settings/NotificationsPage.jsx'));

function redirectStandaloneFrontendToApp() {
  const fullStackAppUrl = import.meta.env.VITE_FULLSTACK_APP_URL?.trim();
  if (!fullStackAppUrl || typeof window === 'undefined') return false;

  try {
    // Build the target from the configured origin only. Resolving the current
    // path against it would turn a path like //evil.example into another site.
    const appOrigin = new URL(fullStackAppUrl).origin;
    const destination = new URL(appOrigin);
    destination.pathname = `/${window.location.pathname.replace(/^[/\\]+/, '')}`;
    destination.search = window.location.search;
    destination.hash = window.location.hash;
    if (destination.origin !== appOrigin) return false;
    if (destination.origin === window.location.origin) return false;
    window.location.replace(destination.href);
    return true;
  } catch {
    // An invalid optional deployment URL must never prevent the standalone
    // frontend from loading.
    return false;
  }
}

function RouteFallback() { return <section className="section"><div className="site-container"><LoadingState /></div></section>; }
// Data router: errorElement catches render errors and stale-chunk failures
// after a deploy (RouteErrorBoundary reloads once). Each layout has its own
// Suspense around <Outlet />, so the header/sidebar stay while a page loads.
const router = createBrowserRouter(createRoutesFromElements(<><Route element={<ResRefPublicLayout />} errorElement={<RouteErrorBoundary />}><Route errorElement={<RouteErrorBoundary />}><Route path="/" element={<HomePage />} /><Route path="/home" element={<HomePage />} /><Route path="/homepage" element={<HomePage />} /><Route path="/database" element={<DatabasePage />} /><Route path="/database/:category" element={<DatabasePage />} /><Route path="/database/:category/:slug" element={<DynamicContentPage />} /><Route path="/articles" element={<LearningArticlesPage />} /><Route path="/advanced-search" element={<Navigate to="/database?focus=search" replace />} /><Route path="/questionnaires" element={<QuestionnairesPage />} /><Route path="/questionnaires-2" element={<QuestionnairesPage />} /><Route path="/journal-finder" element={<Navigate to="/tools/journal-finder" replace />} /><Route path="/tools" element={<ResearchToolsPage />} /><Route path="/tools/sample-size-calculator" element={<SampleSizeCalculatorPage />} /><Route path="/tools/reference-generator" element={<ReferenceGeneratorPage />} /><Route path="/tools/journal-finder" element={<JournalFinderPage />} /><Route path="/tools/research-analyzer" element={<ResearchAnalyzerPage />} /><Route path="/sample-size-calculator" element={<Navigate to="/tools/sample-size-calculator" replace />} /><Route path="/reference-generator" element={<Navigate to="/tools/reference-generator" replace />} /><Route path="/research-analyzer" element={<Navigate to="/tools/research-analyzer" replace />} /><Route path="/consultation" element={<ExpertConsultationPage />} /><Route path="/expert-consultation" element={<Navigate to="/consultation" replace />} /><Route path="/opportunities" element={<ResearchOpportunitiesPage />} /><Route path="/research-opportunities" element={<Navigate to="/opportunities" replace />} /><Route path="/join" element={<JoinOurTeamPage />} /><Route path="/join-our-team" element={<Navigate to="/join" replace />} /><Route path="/about" element={<AboutUsPage />} /><Route path="/team" element={<TeamPage />} /><Route path="/team/preview" element={<TeamPage preview />} /><Route path="/about-us" element={<Navigate to="/about" replace />} /><Route path="/contact" element={<ContactUsPage />} /><Route path="/contact-us" element={<Navigate to="/contact" replace />} /><Route path="/faq" element={<FaqPage />} /><Route path="/terms-of-use" element={<LegalPage type="terms" />} /><Route path="/privacy-policy" element={<LegalPage type="privacy" />} /><Route path="/cookie-policy" element={<LegalPage type="cookies" />} /><Route path="/sign-in" element={<AccountAuthPage />} /><Route path="/auth" element={<AccountAuthPage />} /><Route path="/register" element={<AccountAuthPage mode="register" />} /><Route path="/account" element={<AccountPage />} /><Route path="/account/reset-password" element={<AccountResetPasswordPage />} /><Route path="/account/confirm-email" element={<ConfirmEmailPage />} /><Route path="/authors/:slug" element={<AuthorProfilePage />} /><Route path="/page/:slug" element={<StaticContentPage />} /><Route path="/:slug" element={<DynamicContentPage />} /><Route path="*" element={<NotFoundPage />} /></Route></Route><Route path="/dashboard/login" element={<DashboardLoginPage />} errorElement={<RouteErrorBoundary />} /><Route path="/dashboard" element={<DashboardLayout />} errorElement={<RouteErrorBoundary />}><Route errorElement={<RouteErrorBoundary />}><Route index element={<DashboardHomePage />} /><Route path="content-studio" element={<DashboardContentStudioPage />} /><Route path="users" element={<DashboardUsersPage />} /><Route path="posts" element={<DashboardPostsPage />} /><Route path="media" element={<DashboardMediaPage />} /><Route path="categories" element={<DashboardTaxonomyPage type="categories" />} /><Route path="tags" element={<DashboardTaxonomyPage type="tags" />} /><Route path="authors" element={<DashboardAuthorsPage />} /><Route path="faq" element={<DashboardFaqPage />} /><Route path="contacts" element={<DashboardContactsPage />} /><Route path="applications" element={<DashboardApplicationsPage />} /><Route path="opportunities" element={<DashboardOpportunitiesPage />} /><Route path="services" element={<DashboardServicesPage />} /><Route path="forms" element={<DashboardFormsPage />} /><Route path="team" element={<DashboardTeamPage />} /><Route path="team-page" element={<DashboardTeamPageManager />} /><Route path="roles" element={<DashboardRolesPage />} /><Route path="reports" element={<DashboardReportsPage />} /><Route path="research-analyzer" element={<DashboardResearchAnalyzerPage />} /><Route path="premium-controls" element={<DashboardPremiumControlsPage />} /><Route path="settings" element={<DashboardSettingsPage />} /><Route path="notifications" element={<DashboardNotificationsPage />} /><Route path="guide" element={<DashboardGuidePage />} /></Route></Route></>));
function App() { return <Suspense fallback={<RouteFallback />}><RouterProvider router={router} /></Suspense>; }
if (!redirectStandaloneFrontendToApp()) {
  createRoot(document.getElementById('root')).render(<App />);
}
