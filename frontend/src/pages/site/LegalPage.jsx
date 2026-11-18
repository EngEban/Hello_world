import { useEffect, useMemo, useState } from 'react';
import { ArrowRight, CalendarDays, ChevronDown, Cookie, FileText, ListOrdered, Mail, ShieldCheck } from 'lucide-react';
import { Link } from 'react-router-dom';
import PageHero from '../../components/public/PageHero';
import { analyticsAvailable, CONSENT_EVENT, openCookieSettings, readConsent } from '../../utils/analytics';
import { usePageMeta } from '../../utils/seo';
import '../../styles/pages/legal.css';

// Effective date per policy (update the matching one when its text changes).
const UPDATED_AT = { terms: 'June 5, 2026', privacy: 'October 22, 2026', cookies: 'October 22, 2026' };
const META_DESCRIPTION = {
  terms: 'The terms that apply to using ResRef, its research resources, tools and support services.',
  privacy: 'What information ResRef collects, why it is collected, how it is used and the choices you have.',
  cookies: 'How ResRef uses essential cookies and, only with your consent, Google Analytics cookies.',
};

const CONTENT = {
  terms: {
    title: 'Terms of Use',
    intro: 'These terms explain how visitors, students, doctors, researchers, collaborators, and service clients may use ResRef.com and its research-support resources.',
    sections: [
      {
        title: '1. Acceptance of Terms',
        body: [
          'By accessing or using ResRef.com, you agree to follow these Terms of Use and all applicable laws and professional standards.',
          'If you do not agree with these terms, you should not use the website, submit forms, request services, or rely on platform materials.',
        ],
      },
      {
        title: '2. Platform Purpose',
        body: [
          'ResRef provides educational resources, research references, research tools, questionnaire access, consultation requests, opportunities, and academic support workflows.',
          'The platform is designed to support learning and research preparation. It does not replace formal supervision, institutional review, clinical judgment, legal advice, or independent statistical review.',
        ],
      },
      {
        title: '3. Responsible Use',
        body: [
          'You agree to use ResRef in a lawful, respectful, and academically honest manner.',
          'You must not misuse forms, interfere with website operation, attempt unauthorized access, upload harmful files, impersonate another person, or submit false or misleading information.',
        ],
      },
      {
        title: '4. Research and Medical Information',
        body: [
          'Any research, medical, statistical, or academic information on ResRef is provided for general support and education.',
          'Users remain responsible for verifying methods, references, calculations, journal requirements, ethical approvals, and institutional policies before using outputs in academic or clinical work.',
        ],
      },
      {
        title: '5. Expert Support and Services',
        body: [
          'Consultation and support requests are reviewed based on availability, scope, and the information provided by the requester.',
          'Submission of a request does not guarantee acceptance, timeline, outcome, publication, admission, job placement, or research approval.',
        ],
      },
      {
        title: '6. Intellectual Property',
        body: [
          'Website design, platform content, text, graphics, tools, structure, brand assets, and original materials belong to ResRef or its licensors unless otherwise stated.',
          'You may use public educational material for personal learning and research preparation, but you may not copy, resell, scrape, redistribute, or present ResRef materials as your own.',
        ],
      },
      {
        title: '7. User Submissions',
        body: [
          'When you submit messages, applications, service requests, files, or other information, you confirm that you have the right to share that content with ResRef.',
          'You grant ResRef permission to review, process, store, and respond to the submission for the purpose of providing the requested service or communication.',
        ],
      },
      {
        title: '8. External Links',
        body: [
          'ResRef may link to journals, databases, social platforms, partners, or third-party resources for convenience.',
          'ResRef is not responsible for the accuracy, availability, policies, or practices of third-party websites.',
        ],
      },
      {
        title: '9. Limitation of Liability',
        body: [
          'ResRef aims to provide reliable information and useful tools, but the platform is provided on an as-available basis.',
          'To the maximum extent permitted by law, ResRef is not liable for decisions, losses, missed opportunities, research errors, publication outcomes, or damages arising from use of the website or reliance on its materials.',
        ],
      },
      {
        title: '10. Changes to Terms',
        body: [
          'ResRef may update these Terms of Use as the platform grows, services change, or legal and operational requirements evolve.',
          'The updated version will be posted on this page with the latest effective date.',
        ],
      },
    ],
  },
  privacy: {
    title: 'Privacy Policy',
    intro: 'This policy explains what information ResRef collects, why it is collected, how it is used, and the choices users have when interacting with the platform.',
    sections: [
      {
        title: '1. Information We Collect',
        body: [
          'ResRef may collect information you provide through contact forms, newsletter forms, consultation requests, applications, account forms, dashboard workflows, and uploaded files.',
          'This may include your name, email address, phone or WhatsApp number, organization, specialization, message content, service details, CV or application files, and other information you choose to submit.',
        ],
      },
      {
        title: '2. How We Use Information',
        body: [
          'We use submitted information to respond to inquiries, process service requests, manage opportunities and applications, deliver newsletters, improve platform content, and maintain website security.',
          'We may also use aggregated or non-identifying information to understand platform usage and improve research-support services.',
          'Only if you accept analytics cookies, we use Google Analytics 4 to count page visits and understand which content is useful. Analytics never receives your name, email address, form contents or search terms. The Cookie Policy explains the details and how to change your choice.',
        ],
      },
      {
        title: '3. Research and Sensitive Information',
        body: [
          'Users should avoid submitting unnecessary sensitive personal, medical, patient, institutional, or confidential research data through public forms.',
          'If a service requires sensitive information, ResRef may provide additional instructions or a more appropriate communication channel.',
        ],
      },
      {
        title: '4. Accounts and Dashboard Access',
        body: [
          'If you use account or dashboard features, ResRef may process login details, profile information, role information, content edits, and activity required to operate the platform.',
          'Access permissions are managed to protect administrative workflows and user data.',
        ],
      },
      {
        title: '5. Data Sharing',
        body: [
          'ResRef does not sell personal information.',
          'Information may be shared with authorized team members, service providers, technical vendors, or collaborators only when needed to operate the website, respond to requests, deliver services, or comply with legal obligations.',
          'If you accept analytics cookies, usage data is processed by Google (Google Analytics) on our behalf. Advertising features and Google signals are switched off.',
        ],
      },
      {
        title: '6. Data Security',
        body: [
          'ResRef uses reasonable technical and organizational measures to protect submitted information from unauthorized access, misuse, loss, or alteration.',
          'No online system can be guaranteed completely secure, so users should submit only information that is necessary for the requested purpose.',
        ],
      },
      {
        title: '7. Data Retention',
        body: [
          'ResRef keeps information for as long as needed to respond to requests, provide services, maintain records, comply with obligations, resolve disputes, and improve platform operations.',
          'Newsletter subscriptions and account records may be retained until deleted, deactivated, or no longer needed.',
        ],
      },
      {
        title: '8. Your Choices',
        body: [
          'You may contact ResRef to request correction, update, or deletion of information where applicable.',
          'You may unsubscribe from newsletter communication or ask ResRef to stop non-essential communication.',
        ],
      },
      {
        title: '9. International Users',
        body: [
          'ResRef is intended for an international research and academic community.',
          'By using the platform, you understand that submitted information may be processed where ResRef, its team, or service providers operate.',
        ],
      },
      {
        title: '10. Updates to This Policy',
        body: [
          'This Privacy Policy may be updated as the platform, services, legal requirements, or data practices change.',
          'The latest version will be posted on this page with the effective date.',
        ],
      },
    ],
  },
  cookies: {
    title: 'Cookie Policy',
    intro: 'This policy explains which cookies and similar browser storage ResRef uses, why, and how you can control them. Analytics cookies are only used if you accept them.',
    sections: [
      {
        title: '1. What Cookies Are',
        body: [
          'Cookies are small text files stored by your browser when you visit a website. Similar technologies, such as local storage, keep small pieces of information in your browser.',
          'They help websites keep you signed in, protect forms, remember choices, and, with your permission, measure how pages are used.',
        ],
      },
      {
        title: '2. Essential Cookies',
        body: [
          'sessionid keeps you signed in to your ResRef account or dashboard. It is set only when you sign in and expires after 7 days or when you sign out.',
          'csrftoken protects forms and account actions against cross-site request forgery. It lasts up to one year.',
          'Both are first-party cookies set by ResRef, are needed for the website to work, and are never used for tracking or advertising, so they do not require consent.',
        ],
      },
      {
        title: '3. Storage in Your Browser',
        body: [
          'ResRef keeps some preferences in your browser’s local storage instead of cookies: your cookie choice, articles you save for later, drafts in research tools, and dashboard display preferences.',
          'This information stays on your device and is not sent to ResRef or anyone else. You can remove it at any time by clearing site data in your browser.',
        ],
      },
      {
        title: '4. Analytics Cookies (Only With Your Consent)',
        body: [
          'If you select Accept in the cookie banner, ResRef uses Google Analytics 4, a service of Google, to count visits and understand which pages are useful. Nothing from Google Analytics is loaded before you accept, and choosing Reject keeps it switched off.',
          'Google Analytics sets two cookies: _ga, which distinguishes visitors, and _ga_<ID>, which keeps the state of a visit. Both last up to 2 years.',
          'We send the address of the page you view (without search terms or private links), the page title and the referring website. Google adds approximate location, device and browser information; Google Analytics 4 does not store IP addresses. Advertising features, ad personalisation and Google signals are switched off, and analytics data is kept for up to 14 months.',
          'Google may process this data outside your country. See Google’s privacy policy at policies.google.com/privacy.',
        ],
        action: 'cookie-settings',
      },
      {
        title: '5. Third-Party Services',
        body: [
          'Some features use other providers that may set their own cookies when you use them: Google sign-in when you choose to sign in with Google, and Stripe when you open a payment page. Fonts are loaded from Google Fonts, which does not set cookies.',
          'External links, journals, social platforms and partner websites are governed by their own privacy and cookie policies.',
        ],
      },
      {
        title: '6. Managing Cookies',
        body: [
          'You can change your analytics choice at any time with the Cookie settings button in section 4. Withdrawing consent stops analytics immediately and removes the Google Analytics cookies from this site.',
          'You can also block or delete cookies in your browser settings. Blocking essential cookies will stop sign-in, forms and dashboard features from working.',
        ],
      },
      {
        title: '7. Updates to This Policy',
        body: [
          'ResRef may update this Cookie Policy when platform features, analytics tools, security measures, or legal requirements change.',
          'The latest version will be posted on this page with the effective date.',
        ],
      },
    ],
  },
};

const RELATED = [
  ['terms', '/terms-of-use', FileText],
  ['privacy', '/privacy-policy', ShieldCheck],
  ['cookies', '/cookie-policy', Cookie],
];

// "1. Acceptance of Terms" -> ['1', 'Acceptance of Terms'] so the number can sit in its own badge.
function splitTitle(title) {
  const match = /^(\d+)\.\s*(.*)$/.exec(title);
  return match ? [match[1], match[2]] : ['', title];
}

const legalSectionId = (pageKey, index) => `legal-${pageKey}-${index + 1}`;

function CookieSettingsControl() {
  const [choice, setChoice] = useState(readConsent);
  useEffect(() => {
    const update = () => setChoice(readConsent());
    window.addEventListener(CONSENT_EVENT, update);
    return () => window.removeEventListener(CONSENT_EVENT, update);
  }, []);
  if (!analyticsAvailable()) return <p className="rp-legal-cookie-status"><strong>Current status:</strong> analytics is switched off on this website, so no analytics cookies are used.</p>;
  const status = { granted: 'accepted', denied: 'rejected' }[choice] || 'not chosen yet (analytics stays off)';
  return (
    <p className="rp-legal-cookie-status">
      <strong>Your current choice:</strong> analytics {status}.{' '}
      <button type="button" className="rh-button rh-button-outline" onClick={openCookieSettings}>Cookie settings</button>
    </p>
  );
}

export default function LegalPage({ type }) {
  const page = CONTENT[type] || CONTENT.terms;
  const pageKey = CONTENT[type] ? type : 'terms';
  const sectionId = index => legalSectionId(pageKey, index);
  const [active, setActive] = useState(0);
  const [tocOpen, setTocOpen] = useState(false);
  const updatedAt = UPDATED_AT[pageKey];
  const meta = useMemo(() => ({
    title: `${page.title} | ResRef`, description: META_DESCRIPTION[pageKey],
    canonical: new URL(RELATED.find(([key]) => key === pageKey)[1], window.location.origin).href,
  }), [page.title, pageKey]);
  usePageMeta(meta);

  useEffect(() => {
    setActive(0);
    if (typeof IntersectionObserver === 'undefined') return undefined;
    const nodes = CONTENT[pageKey].sections.map((_, index) => document.getElementById(legalSectionId(pageKey, index))).filter(Boolean);
    const observer = new IntersectionObserver(entries => {
      const visible = entries.filter(entry => entry.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
      if (visible.length) setActive(nodes.indexOf(visible[0].target));
    }, { rootMargin: '-20% 0px -65% 0px', threshold: 0 });
    nodes.forEach(node => observer.observe(node));
    return () => observer.disconnect();
  }, [pageKey]);

  const jumpTo = (event, index) => {
    const target = document.getElementById(sectionId(index));
    if (!target) return;
    event.preventDefault();
    const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    target.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'start' });
    target.focus({ preventScroll: true });
    setActive(index);
    setTocOpen(false);
  };

  return (
    <div className="rh-page rp-legal">
      <PageHero title={page.title} text="Clear policies for using ResRef as a trusted research and academic support platform." kicker={`Effective ${updatedAt}`} />
      <section className="rh-section-tight rp-legal-section">
        <div className="rh-container rp-legal-layout">
          <aside className="rp-legal-aside">
            <nav className={`rp-legal-toc${tocOpen ? ' is-open' : ''}`} aria-label={`${page.title} contents`}>
              <span className="rp-legal-toc-title rp-legal-toc-label"><ListOrdered size={16} aria-hidden="true" /> On this page</span>
              <button type="button" className="rp-legal-toc-toggle" aria-expanded={tocOpen} aria-controls={`legal-${pageKey}-toc`} onClick={() => setTocOpen(value => !value)}>
                <ListOrdered size={16} aria-hidden="true" /> On this page <span>{page.sections.length} sections</span><ChevronDown size={18} aria-hidden="true" />
              </button>
              <ol id={`legal-${pageKey}-toc`}>
                {page.sections.map((section, index) => {
                  const [number, label] = splitTitle(section.title);
                  return (
                    <li key={section.title}>
                      <a href={`#${sectionId(index)}`} className={active === index ? 'is-active' : undefined} aria-current={active === index ? 'location' : undefined} onClick={event => jumpTo(event, index)}>
                        {number && <span aria-hidden="true">{number}</span>}{label}
                      </a>
                    </li>
                  );
                })}
              </ol>
            </nav>
            <nav className="rp-legal-related" aria-label="Related policies">
              <span className="rp-legal-toc-title">Policies</span>
              {RELATED.map(([key, to, Icon]) => (
                <Link key={key} to={to} className={key === pageKey ? 'is-current' : undefined} aria-current={key === pageKey ? 'page' : undefined}>
                  <Icon size={16} aria-hidden="true" />{CONTENT[key].title}
                </Link>
              ))}
            </nav>
          </aside>

          <article className="rp-legal-document">
            <header className="rp-legal-intro">
              <span className="rp-legal-date"><CalendarDays size={15} aria-hidden="true" /> Effective date: {updatedAt}</span>
              <h2>{page.title}</h2>
              <p>{page.intro}</p>
            </header>

            <div className="rp-legal-body">
              {page.sections.map((section, index) => {
                const [number, label] = splitTitle(section.title);
                return (
                  <section className="rp-legal-block" id={sectionId(index)} key={section.title} tabIndex={-1} aria-labelledby={`${sectionId(index)}-title`}>
                    <h3 id={`${sectionId(index)}-title`}>
                      {number && <span className="rp-legal-number" aria-hidden="true">{number}</span>}
                      <span>{number && <span className="rh-visually-hidden">{number}. </span>}{label}</span>
                    </h3>
                    {section.body.map(paragraph => <p key={paragraph}>{paragraph}</p>)}
                    {section.action === 'cookie-settings' && <CookieSettingsControl />}
                  </section>
                );
              })}
            </div>

            <aside className="rp-legal-contact">
              <span className="rp-legal-contact-icon" aria-hidden="true"><Mail size={22} /></span>
              <div>
                <strong>Questions about this policy?</strong>
                <p>Contact ResRef at <a href="mailto:info@resref.com">info@resref.com</a> or visit the <Link to="/contact">Contact Us</Link> page.</p>
              </div>
              <Link className="rh-button rh-button-primary" to="/contact"><span>Contact us</span><ArrowRight className="rh-button-icon" size={17} aria-hidden="true" /></Link>
            </aside>
          </article>
        </div>
      </section>
    </div>
  );
}
