import { Link } from 'react-router-dom';
import { ArrowUpRight, Bot, Mail, MessageCircle } from 'lucide-react';
import { useSiteSettings } from '../../contexts/SiteSettingsContext';
import { ASSETS } from '../../siteData';
import SocialLinks from './SocialLinks';
import { safeHref } from '../../utils/safeHref';
import { openCookieSettings } from '../../utils/analytics';

const footerColumns = [
  {
    title: 'Quick Links',
    links: [
      ['Home', '/'],
      ['Research Database', '/database'],
      ['Research Tools', '/tools'],
      ['Expert Consultation', '/consultation'],
    ],
  },
  {
    title: 'Resources',
    links: [
      ['Medical Specialties', '/database'],
      ['Methodology Articles', '/database/mastering-research'],
      ['Research Opportunities', '/opportunities'],
      ['FAQ', '/faq'],
    ],
  },
  {
    title: 'Tools',
    links: [
      ['Sample Size Calculator', '/tools/sample-size-calculator'],
      ['Reference Generator', '/tools/reference-generator'],
      ['Journal Finder', '/tools/journal-finder'],
      ['ResRef Analyzer', '/tools/research-analyzer'],
    ],
  },
  {
    title: 'Community',
    links: [
      ['Join Our Team', '/join'],
      ['About ResRef', '/about'],
      ['Contact Us', '/contact'],
      ['Privacy Policy', '/privacy-policy'],
    ],
  },
];

export default function SiteFooter() {
  const settings = useSiteSettings();
  const contacts = [
    { Icon: Mail, label: 'Email', value: settings.contact_email, href: `mailto:${settings.contact_email}` },
    { Icon: MessageCircle, label: 'WhatsApp', value: settings.whatsapp_label, href: safeHref(settings.whatsapp_url) },
    { Icon: Bot, label: 'ResRef Telegram Bot', value: settings.telegram_bot_label || '@resrefbot', href: safeHref(settings.telegram_bot_url, 'https://t.me/resrefbot'), external: true },
  ];

  return (
    <footer className="rh-footer">
      <div className="rh-footer-dark">
      <div className="rh-footer-texture" aria-hidden="true" />
      <div className="rh-container">

        <div className="rh-footer-main">
          <section className="rh-footer-brand" aria-label="ResRef platform summary">
            <Link className="rh-footer-logo" to="/" aria-label="ResRef home">
              <img src={settings.footer_logo_url || ASSETS.whiteLogo} alt={settings.site_name} loading="lazy" />
            </Link>
            <p>{settings.footer_description}</p>
            <SocialLinks light />
          </section>

          <nav className="rh-footer-nav" aria-label="Footer navigation">
            {footerColumns.map(column => (
              <div className="rh-footer-column" key={column.title}>
                <h3>{column.title}</h3>
                <ul>
                  {column.links.map(([label, path]) => <li key={`${column.title}-${label}`}><Link to={path}>{label}</Link></li>)}
                </ul>
              </div>
            ))}
          </nav>

          <section className="rh-footer-contact" aria-label="Contact ResRef">
            <h3>Get in touch</h3>
            {contacts.map(({ Icon, label, value, href, external }) => (
              <a className="rh-footer-contact-card" href={href} key={label} target={external ? '_blank' : undefined} rel={external ? 'noopener noreferrer' : undefined}>
                <span className="rh-footer-contact-icon" aria-hidden="true"><Icon size={17} /></span>
                <span className="rh-footer-contact-copy"><strong>{label}</strong><small>{value}</small></span>
                <ArrowUpRight className="rh-footer-contact-arrow" size={15} aria-hidden="true" />
              </a>
            ))}
          </section>
        </div>

        <div className="rh-footer-bottom">
          <span>Copyright &copy; 2026 {settings.site_name}. All rights reserved.</span>
          <div>
            <Link to="/terms-of-use">Terms of Use</Link>
            <Link to="/cookie-policy">Cookie Policy</Link>
            <Link to="/privacy-policy">Privacy Policy</Link>
            <button type="button" className="rh-footer-cookie-button" onClick={openCookieSettings}>Cookie settings</button>
          </div>
        </div>
      </div>
      </div>
    </footer>
  );
}
