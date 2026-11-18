import { ArrowRight, BarChart3, BookOpenCheck, Calculator, FileSearch, FileText, ShieldCheck } from 'lucide-react';
import { Link } from 'react-router-dom';
import PageHero from '../../components/public/PageHero';
import SectionHeading from '../../components/public/SectionHeading';
import { HomeLink } from '../../components/home/HomePrimitives';
import { SEO, TOOL_HUB_ITEMS } from '../../config/contentStructure';
import { useSiteSettings } from '../../contexts/SiteSettingsContext';
import { usePageMeta } from '../../utils/seo';
import '../../styles/pages/tools-hub.css';

const icons = {
  'Sample Size Calculator': Calculator,
  'Reference Generator': FileText,
  'Journal Finder': FileSearch,
  'ResRef Analyzer': BarChart3,
};

export default function ResearchToolsPage() {
  usePageMeta(SEO.tools);
  const settings = useSiteSettings();
  const workflow = [1, 2, 3].map(index => [
    settings[`tools_workflow_${index}_title`],
    settings[`tools_workflow_${index}_text`],
  ]);
  const availableCount = TOOL_HUB_ITEMS.filter(item => item.status === 'available').length;

  return (
    <div className="rh-page rp-tools">
      <PageHero
        title="Research Tools"
        text="Free, interactive tools designed to support every stage of your research — from planning to publication."
        settingPrefix="tools"
        kicker={`${availableCount} tools available`}
      />

      <section className="rh-section rp-tools-hub" aria-label="ResRef research tools hub">
        <div className="rh-container">
          <div className="rh-split-heading">
            <SectionHeading
              eyebrow={settings.tools_hub_eyebrow}
              title={settings.tools_hub_title}
            />
            <div className="rh-split-aside" data-reveal>
              {settings.tools_hub_text && <p>{settings.tools_hub_text}</p>}
              <HomeLink to={settings.tools_guidance_cta_url || '/consultation'} variant="outline">{settings.tools_guidance_cta_label}</HomeLink>
            </div>
          </div>

          <div className="rp-tools-grid" aria-label="ResRef research tools">
            {TOOL_HUB_ITEMS.map((item, index) => {
              const Icon = icons[item.title] || BookOpenCheck;
              const available = item.status === 'available';
              const content = (
                <>
                  <span className="rp-tools-card-top">
                    <span className="rh-card-icon rp-tools-card-icon" aria-hidden="true"><Icon size={26} /></span>
                    <span className={available ? 'rh-status rh-status-live' : 'rh-status'}>{available ? 'Available' : 'Coming Soon'}</span>
                  </span>
                  <span className="rp-tools-card-index" aria-hidden="true">{String(index + 1).padStart(2, '0')}</span>
                  <h2>{item.title}</h2>
                  <p>{item.description}</p>
                  <strong className="rp-tools-card-cta"><span>{item.cta}</span> <ArrowRight size={17} aria-hidden="true" /></strong>
                </>
              );
              return available ? (
                <Link className="rh-card rp-tools-card" to={item.path} key={item.title} data-reveal style={{ '--rh-delay': `${index * 80}ms` }}>{content}</Link>
              ) : (
                <article className="rh-card rp-tools-card rp-tools-card-muted" key={item.title} data-reveal style={{ '--rh-delay': `${index * 80}ms` }}>{content}</article>
              );
            })}
          </div>
        </div>
      </section>

      <section className="rh-section-tight rh-surface-mist rp-tools-workflow" aria-labelledby="tools-workflow-title">
        <div className="rh-container rp-tools-workflow-layout">
          <header className="rh-intro" data-reveal>
            <span className="rh-label">Research workflow</span>
            <h2 id="tools-workflow-title">One connected path from plan to publication.</h2>
          </header>
          <ol className="rp-tools-steps">
            {workflow.map(([title, text], index) => (
              <li className="rp-tools-step" key={title || index} data-reveal style={{ '--rh-delay': `${index * 90}ms` }}>
                <span className="rh-step-number" aria-hidden="true">{String(index + 1).padStart(2, '0')}</span>
                <div>
                  <strong>{title}</strong>
                  <p>{text}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="rh-section-tight rp-tools-cta">
        <div className="rh-container">
          <div className="rh-cta-band" data-reveal>
            <div className="rh-cta-band-copy">
              <span className="rh-cta-band-icon" aria-hidden="true"><ShieldCheck size={24} /></span>
              <div>
                <h2>{settings.tools_bottom_cta_title}</h2>
                <p>{settings.tools_bottom_cta_text}</p>
              </div>
            </div>
            <HomeLink to={settings.tools_bottom_cta_url || '/consultation'} variant="light">{settings.tools_bottom_cta_label}</HomeLink>
          </div>
        </div>
      </section>
    </div>
  );
}
