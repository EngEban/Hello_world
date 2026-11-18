import {
  ArrowRight,
  BookOpen,
  Compass,
  Globe2,
  GraduationCap,
  Layers3,
  Lightbulb,
  Network,
  ShieldCheck,
  Stethoscope,
  Users,
} from 'lucide-react';
import PageHero from '../../components/public/PageHero';
import SectionHeading from '../../components/public/SectionHeading';
import { HomeLink } from '../../components/home/HomePrimitives';
import { useSiteSettings } from '../../contexts/SiteSettingsContext';
import { ASSETS } from '../../siteData';
import { SEO } from '../../config/contentStructure';
import { usePageMeta } from '../../utils/seo';
import { safeHref } from '../../utils/safeHref';
import '../../styles/pages/about.css';

const metrics = [
  ['Built for', 'Students, doctors, researchers'],
  ['Focus', 'Research tools and guidance'],
  ['Standard', 'Clear, practical, trustworthy'],
];

const values = [
  [BookOpen, 'Knowledge made usable', 'Research support should be easy to find, understand, and apply.'],
  [Users, 'Collaboration with purpose', 'Scientific progress grows when people can connect around clear workflows.'],
  [Lightbulb, 'Practical innovation', 'Tools should simplify the research process rather than add complexity.'],
  [Globe2, 'Accessible research culture', 'High-quality research guidance should be available to a wider community.'],
];

const audiences = [
  [GraduationCap, 'Students', 'A guided way to understand research, references, tools, and academic opportunities.'],
  [Stethoscope, 'Doctors and clinicians', 'Practical support for study planning, evidence work, and manuscript preparation.'],
  [Network, 'Research teams', 'Shared workflows for collaboration, resource discovery, and project organization.'],
];

const principles = [
  ['Research-first structure', 'Content and tools are organized around real research tasks, not generic website sections.'],
  ['Clinical and academic trust', 'The interface is designed for healthcare, education, and research audiences.'],
  ['Scalable ecosystem thinking', 'ResRef is built to grow from a website into a broader research platform.'],
];

export default function AboutUsPage() {
  usePageMeta(SEO.about);
  const settings = useSiteSettings();
  return (
    <div className="rh-page rp-about">
      <PageHero title="About ResRef" text="Learn why ResRef was created, what problem it solves, and how it supports the global research community." settingPrefix="about" />

      <section className="rh-section rp-about-identity" aria-labelledby="about-identity-title">
        <div className="rh-container rp-about-identity-layout">
          <div className="rp-about-identity-copy">
            <SectionHeading id="about-identity-title" eyebrow={settings.about_identity_eyebrow} title={settings.about_identity_title} text={settings.about_identity_text} />
            <p className="rp-about-body" data-reveal>{settings.about_identity_body}</p>
            <div className="rh-stat-row rp-about-metrics" data-reveal>
              {metrics.map(([label, value]) => (
                <article className="rh-stat-tile" key={label}>
                  <small>{label}</small>
                  <strong>{value}</strong>
                </article>
              ))}
            </div>
          </div>

          <div className="rp-about-visual" data-reveal>
            <figure className="rh-media rp-about-media">
              <img src={settings.about_identity_image_url || ASSETS.about} alt="Medical researcher" loading="lazy" decoding="async" />
              <figcaption className="rh-media-caption">
                <Compass size={21} aria-hidden="true" />
                <span>
                  <small>Platform direction</small>
                  <strong>From simple research support to a global academic ecosystem.</strong>
                </span>
              </figcaption>
            </figure>
          </div>
        </div>
      </section>

      <section className="rh-band rp-about-mission" aria-labelledby="about-mission-title">
        <div className="rh-container">
          <div className="rh-band-panel rp-about-mission-panel">
            <div className="rp-about-mission-copy" data-reveal>
              <span className="rp-about-mission-icon" aria-hidden="true"><Layers3 size={24} /></span>
              <span className="rh-label rh-label-light">Our mission</span>
              <h2 id="about-mission-title">{settings.about_mission_title}</h2>
              <p>{settings.about_mission_text}</p>
            </div>
            <ol className="rp-about-principles">
              {principles.map(([title, text], index) => (
                <li className="rp-about-principle" key={title} data-reveal style={{ '--rh-delay': `${index * 90}ms` }}>
                  <span className="rh-step-number" aria-hidden="true">{String(index + 1).padStart(2, '0')}</span>
                  <div>
                    <h3>{title}</h3>
                    <p>{text}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </div>
      </section>

      <section className="rh-section rp-about-values" aria-labelledby="about-values-title">
        <div className="rh-container">
          <SectionHeading id="about-values-title" eyebrow={settings.about_values_eyebrow} title={settings.about_values_title} text={settings.about_values_text} align="center" />
          <div className="rh-card-grid rh-card-grid-4">
            {values.map(([Icon, title, text], index) => (
              <article className="rh-card rh-card-compact" key={title} data-reveal style={{ '--rh-delay': `${index * 80}ms` }}>
                <span className="rh-card-icon" aria-hidden="true"><Icon size={24} /></span>
                <h3>{title}</h3>
                <p>{text}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="rh-section rh-surface-mist rp-about-audience" aria-labelledby="about-audience-title">
        <div className="rh-container">
          <div className="rh-split-heading">
            <SectionHeading id="about-audience-title" eyebrow={settings.about_audience_eyebrow} title={settings.about_audience_title} />
            <div className="rh-split-aside" data-reveal>
              <p>{settings.about_audience_text}</p>
              <a className="text-link" href={safeHref(settings.about_audience_link_url, '/database')}>{settings.about_audience_link_label} <ArrowRight size={14} aria-hidden="true" /></a>
            </div>
          </div>
          <div className="rh-card-grid rp-about-audience-grid">
            {audiences.map(([Icon, title, text], index) => (
              <article className="rh-card rp-about-audience-card" key={title} data-reveal style={{ '--rh-delay': `${index * 90}ms` }}>
                <span className="rh-card-icon" aria-hidden="true"><Icon size={23} /></span>
                <h3>{title}</h3>
                <p>{text}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="rh-section-tight rp-about-trust" aria-labelledby="about-trust-title">
        <div className="rh-container">
          <div className="rh-cta-band" data-reveal>
            <div className="rh-cta-band-copy">
              <span className="rh-cta-band-icon" aria-hidden="true"><ShieldCheck size={26} /></span>
              <div>
                <span className="rh-label rh-label-light">Platform standard</span>
                <h2 id="about-trust-title">Professional enough for institutions. Simple enough for everyday research work.</h2>
              </div>
            </div>
            <div className="rh-actions">
              <HomeLink to="/contact" variant="light">Contact ResRef</HomeLink>
              <HomeLink to="/join" variant="ghost">Join our team</HomeLink>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
