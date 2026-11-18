import {
  ArrowRight,
  ArrowUpRight,
  CheckCircle2,
  HelpCircle,
  Mail,
  MessageCircle,
  Microscope,
  Network,
  Send,
  Users,
} from 'lucide-react';
import { useState } from 'react';
import ContactForm from '../../components/public/ContactForm';
import PageHero from '../../components/public/PageHero';
import SectionHeading from '../../components/public/SectionHeading';
import { useSiteSettings } from '../../contexts/SiteSettingsContext';
import { SEO } from '../../config/contentStructure';
import { usePageMeta } from '../../utils/seo';
import { SOCIAL_LINKS } from '../../siteData';
import '../../styles/pages/contact.css';

const contactPaths = [
  [Microscope, 'Research consultation', 'Methods, statistics, manuscripts, study planning, and publication support.'],
  [HelpCircle, 'Platform support', 'Database, questionnaires, calculators, references, and account access.'],
  [Network, 'Partnerships', 'Institutional collaboration, research networks, training, and ecosystem work.'],
  [Users, 'Careers and teams', 'Volunteer roles, contributors, mentors, and research opportunities.'],
];

const processSteps = [
  ['Submit context', 'You send the main details once.'],
  ['Classify request', 'We identify the best support path.'],
  ['Route to team', 'The right person reviews it.'],
  ['Confirm next step', 'You receive a clear action or reply.'],
];

export default function ContactUsPage() {
  usePageMeta(SEO.contact);
  const settings = useSiteSettings();
  const [selectedRoute, setSelectedRoute] = useState(null);

  const chooseRoute = title => {
    setSelectedRoute({
      specialization: title,
      message: `Request type: ${title}\n\n`,
    });
    window.requestAnimationFrame(() => {
      document.getElementById('contact-request-form')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
  };

  const channels = [
    { href: `mailto:${settings.contact_email}`, Icon: Mail, label: 'Email', value: settings.contact_email },
    { href: settings.whatsapp_url, Icon: MessageCircle, label: 'WhatsApp', value: settings.whatsapp_label },
    { href: SOCIAL_LINKS.telegram, Icon: Send, label: 'ResRef Telegram Bot', value: 'Message, find resources, or request support', external: true },
  ];

  return (
    <div className="rh-page rp-contact">
      <PageHero title="Contact Us" text="Have a question, suggestion, or partnership enquiry? We're here to help." settingPrefix="contact" />

      <section className="rh-section rp-contact-main" aria-labelledby="contact-command-title">
        <div className="rh-container rp-contact-layout">
          <div className="rp-contact-routes">
            <SectionHeading id="contact-command-title" eyebrow={settings.contact_command_eyebrow} title={settings.contact_command_title} text={settings.contact_command_text} />

            <div className="rp-contact-route-grid">
              {contactPaths.map(([Icon, title, text], index) => {
                const active = selectedRoute?.specialization === title;
                return (
                  <button
                    className={`rp-contact-route${active ? ' is-active' : ''}`}
                    type="button"
                    onClick={() => chooseRoute(title)}
                    aria-pressed={active}
                    key={title}
                    data-reveal
                    style={{ '--rh-delay': `${index * 70}ms` }}
                  >
                    <span className="rh-card-icon" aria-hidden="true"><Icon size={21} /></span>
                    <h3>{title}</h3>
                    <p>{text}</p>
                    <small>{active ? <CheckCircle2 size={14} aria-hidden="true" /> : null}{settings.contact_route_action_label} <ArrowRight size={13} aria-hidden="true" /></small>
                  </button>
                );
              })}
            </div>
          </div>

          <aside className="rp-form-panel rp-contact-form-panel" id="contact-request-form" aria-label="Contact form">
            <ContactForm
              title={settings.contact_form_title}
              text={settings.contact_form_text}
              submitLabel={settings.contact_form_submit_label}
              messagePlaceholder={settings.contact_form_message_placeholder}
              className="contact-form-elevated"
              initialValues={selectedRoute || {}}
            />
          </aside>

        </div>
      </section>

      <section className="rh-band rp-contact-direct" aria-labelledby="contact-direct-title">
        <div className="rh-container">
          <div className="rh-band-panel rp-contact-direct-panel">
            <div className="rp-contact-direct-copy" data-reveal>
              <span className="rh-label rh-label-light">{settings.contact_direct_label}</span>
              <h2 id="contact-direct-title">{settings.contact_direct_title}</h2>
              <p>{settings.contact_direct_text}</p>
            </div>
            <div className="rp-contact-channels" data-reveal>
              {channels.map(({ href, Icon, label, value, external }) => (
                <a className="rp-contact-channel" href={href} key={label} target={external ? '_blank' : undefined} rel={external ? 'noreferrer' : undefined}>
                  <span className="rp-contact-channel-icon" aria-hidden="true"><Icon size={19} /></span>
                  <span className="rp-contact-channel-copy"><small>{label}</small>{value}</span>
                  <ArrowUpRight className="rp-contact-channel-arrow" size={18} aria-hidden="true" />
                </a>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="rh-section rp-contact-process" aria-labelledby="contact-process-title">
        <div className="rh-container">
          <SectionHeading id="contact-process-title" eyebrow={settings.contact_process_eyebrow} title={settings.contact_process_title} text={settings.contact_process_text} align="center" />
          <ol className="rp-contact-rail">
            {processSteps.map(([item, text], index) => (
              <li key={item} data-reveal style={{ '--rh-delay': `${index * 90}ms` }}>
                <span className="rh-step-number" aria-hidden="true">{String(index + 1).padStart(2, '0')}</span>
                <strong>{item}</strong>
                <p>{text}</p>
                {index < 3 && <CheckCircle2 className="rp-contact-rail-mark" size={18} aria-hidden="true" />}
              </li>
            ))}
          </ol>
        </div>
      </section>
    </div>
  );
}
