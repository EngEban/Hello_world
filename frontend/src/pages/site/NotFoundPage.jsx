import { ArrowRight, Compass, Database, HelpCircle, Home, Mail, Search, Wrench } from 'lucide-react';
import { Link } from 'react-router-dom';
import PageHero from '../../components/public/PageHero';
import { SEO } from '../../config/contentStructure';
import { usePageMeta } from '../../utils/seo';
import '../../styles/pages/not-found.css';

const destinations = [
  [Home, 'Home', 'Start again from the ResRef homepage.', '/'],
  [Database, 'Database', 'Questionnaires, scales, articles, and methods.', '/database'],
  [Wrench, 'Research tools', 'Calculators, generators, and journal matching.', '/tools'],
  [HelpCircle, 'FAQ', 'Answers about the platform and services.', '/faq'],
  [Mail, 'Contact', 'Ask the ResRef team for direct help.', '/contact'],
];

export default function NotFoundPage({ message = 'The requested page could not be found.' }) {
  usePageMeta(SEO.notFound);
  return (
    <div className="rh-page rp-404">
      <PageHero title="Page Not Found" text={message} settingPrefix="not_found" kicker="Error 404" />
      <section className="rh-section-tight rp-404-section">
        <div className="rh-container">
          <div className="rh-panel rh-panel-raised rp-404-panel">
            <div className="rp-404-copy">
              <span className="rp-404-mark" aria-hidden="true"><Compass size={30} /></span>
              <h2>Let us route you back to the right ResRef area.</h2>
              <p>Use database search for questionnaires and articles, open the tools hub for calculators and generators, or contact ResRef if you need help.</p>
              <form className="not-found-search rp-404-search" action="/database" role="search">
                <Search size={19} aria-hidden="true" />
                <input name="q" type="search" placeholder="Search ResRef database..." aria-label="Search ResRef database" />
                <button className="button" type="submit">Search</button>
              </form>
            </div>
            <span className="rp-404-number" aria-hidden="true">404</span>
          </div>

          <nav className="rp-404-links" aria-label="Helpful links">
            {destinations.map(([Icon, title, text, to], index) => (
              <Link className="rp-404-link" to={to} key={to} data-reveal style={{ '--rh-delay': `${index * 60}ms` }}>
                <span className="rp-404-link-icon" aria-hidden="true"><Icon size={20} /></span>
                <span className="rp-404-link-copy"><strong>{title}</strong><small>{text}</small></span>
                <ArrowRight className="rp-404-link-arrow" size={17} aria-hidden="true" />
              </Link>
            ))}
          </nav>
        </div>
      </section>
    </div>
  );
}
