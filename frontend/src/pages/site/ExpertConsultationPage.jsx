import {
  ArrowRight,
  BarChart3,
  BookOpenCheck,
  CheckCircle2,
  ClipboardCheck,
  FileText,
  Microscope,
  PenLine,
  Route,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import GoogleFormDialog, { googleFormEmbedUrl } from '../../components/public/GoogleFormDialog';
import PageHero from '../../components/public/PageHero';
import SectionHeading from '../../components/public/SectionHeading';
import { useSiteSettings } from '../../contexts/SiteSettingsContext';
import { ASSETS } from '../../siteData';
import { SEO } from '../../config/contentStructure';
import { usePageMeta } from '../../utils/seo';
import { safeHref } from '../../utils/safeHref';
import '../../styles/pages/consultation.css';

const serviceAreas = [
  [Microscope, 'Research planning', 'Clarify research questions, study direction, variables, and practical project structure.'],
  [Route, 'Methodology review', 'Improve study design, sampling logic, workflow, and alignment with research objectives.'],
  [BarChart3, 'Statistical guidance', 'Discuss sample size, analysis planning, assumptions, and reporting expectations.'],
  [PenLine, 'Scientific writing', 'Strengthen abstracts, manuscripts, proposals, discussion sections, and academic tone.'],
  [FileText, 'Reference and journal support', 'Prepare references, journal targeting, submission readiness, and formatting checks.'],
  [ClipboardCheck, 'Project readiness', 'Identify missing pieces before analysis, submission, presentation, or collaboration.'],
];

const process = [
  ['01', 'Submit your context', 'Share your topic, stage, goal, and the type of support you need.'],
  ['02', 'Scope the request', 'The team reviews whether the request is methodological, statistical, writing, or publication-related.'],
  ['03', 'Clarify next steps', 'You receive a practical pathway for the most useful next action.'],
  ['04', 'Move with confidence', 'Use the guidance to continue planning, writing, analyzing, or preparing submission.'],
];

const proofPoints = [
  'Designed for students, doctors, and research teams',
  'Useful for early ideas and advanced manuscripts',
  'Focused on practical next steps, not generic advice',
];

export default function ExpertConsultationPage() {
  usePageMeta(SEO.consultation);
  const settings = useSiteSettings();
  const [openForm, setOpenForm] = useState(null);
  const formUrl = (settings.consultation_form_url || '').trim();
  const requestLabel = settings.consultation_form_button_label || 'Request consultation';
  const openRequest = event => {
    const embedUrl = googleFormEmbedUrl(formUrl);
    // A modified click still opens a new tab, as with any link.
    if (embedUrl && !event.ctrlKey && !event.metaKey && !event.shiftKey) {
      event.preventDefault();
      setOpenForm({ title: requestLabel, href: formUrl, embedUrl });
    }
  };
  return (
    <div className="rh-page rp-consult">
      <PageHero title="Free Expert Research Consultation" text="Get personalised guidance for your research idea, protocol, analysis plan, manuscript, or publication pathway." settingPrefix="consultation" breadcrumb="Expert consultation">
        <a className="rh-button rh-button-light" href={formUrl ? safeHref(formUrl) : '#consultation-request'} target={formUrl ? '_blank' : undefined} rel={formUrl ? 'noopener noreferrer' : undefined} onClick={openRequest}><span>{requestLabel}</span><ArrowRight className="rh-button-icon" size={17} aria-hidden="true" /></a>
      </PageHero>

      <section className="rh-section rp-consult-overview" aria-labelledby="consult-overview-title">
        <div className="rh-container rp-consult-overview-layout">
          <div className="rp-consult-overview-copy">
            <SectionHeading id="consult-overview-title" eyebrow={settings.consultation_overview_eyebrow} title={settings.consultation_overview_title} text={settings.consultation_overview_text} />
            <ul className="rh-check-list rp-consult-proof" data-reveal>
              {proofPoints.map(point => <li key={point}><CheckCircle2 size={19} aria-hidden="true" />{point}</li>)}
            </ul>
          </div>

          <div className="rp-consult-visual" data-reveal>
            <figure className="rh-media rp-consult-media">
              <img src={settings.consultation_overview_image_url || ASSETS.consultation} alt="Research consultation" loading="lazy" decoding="async" />
              <figcaption className="rh-media-caption">
                <Sparkles size={20} aria-hidden="true" />
                <span>
                  <strong>Guidance built around your research stage</strong>
                  <small className="rp-consult-caption-note">Idea, protocol, analysis, writing, or submission.</small>
                </span>
              </figcaption>
            </figure>
          </div>
        </div>
      </section>

      <section className="rh-section rh-surface-mist rp-consult-services" aria-labelledby="consult-services-title">
        <div className="rh-container">
          <SectionHeading id="consult-services-title" eyebrow="Consultation areas" title="Choose Support That Matches the Research Problem" text="The service is organized around the decisions researchers actually need to make." align="center" />
          <div className="rh-card-grid rh-card-grid-3">
            {serviceAreas.map(([Icon, title, text], index) => (
              <article className="rh-card" key={title} data-reveal style={{ '--rh-delay': `${(index % 3) * 80}ms` }}>
                <span className="rh-card-icon" aria-hidden="true"><Icon size={23} /></span>
                <h3>{title}</h3>
                <p>{text}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="rh-section rp-consult-process" aria-labelledby="consult-process-title">
        <div className="rh-container rp-consult-process-layout">
          <div className="rp-consult-process-lead">
            <SectionHeading id="consult-process-title" eyebrow="How it works" title="A Clear Process Before Advice Is Given" text="A premium consultation experience starts by understanding the research context, not by guessing from incomplete details." />
            <div className="rp-consult-assurance" data-reveal>
              <ShieldCheck size={24} aria-hidden="true" />
              <span>ResRef guidance supports your research preparation. It does not replace institutional supervision, ethics review, or clinical judgment.</span>
            </div>
          </div>

          <ol className="rh-steps rp-consult-steps">
            {process.map(([step, title, text], index) => (
              <li className="rh-step" key={title} data-reveal style={{ '--rh-delay': `${index * 80}ms` }}>
                <span className="rh-step-number" aria-hidden="true">{step}</span>
                <div>
                  <h3>{title}</h3>
                  <p>{text}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="rh-section rh-surface-fade rp-consult-request" id="consultation-request" aria-labelledby="consult-request-title">
        <div className="rh-container">
          <div className="rp-consult-request-panel" data-reveal>
            <div className="rp-consult-request-copy">
              <span className="rp-consult-request-icon" aria-hidden="true"><BookOpenCheck size={26} /></span>
              <span className="rh-label rh-label-light">Request consultation</span>
              <h2 id="consult-request-title">Tell us where your project is stuck.</h2>
              <p>Good consultation starts with context. Share your research area, current stage, and the decision you need help making.</p>
              <ul className="rp-consult-request-list">
                <li><CheckCircle2 size={17} aria-hidden="true" /> Topic and research stage</li>
                <li><CheckCircle2 size={17} aria-hidden="true" /> Method, writing, statistics, or journal need</li>
                <li><CheckCircle2 size={17} aria-hidden="true" /> Timeline or urgency if relevant</li>
              </ul>
            </div>
            <div className="rp-consult-request-actions">
              {formUrl
                ? <a className="rh-button rh-button-light" href={safeHref(formUrl)} target="_blank" rel="noopener noreferrer" onClick={openRequest}><span>{requestLabel}</span><ArrowRight className="rh-button-icon" size={17} aria-hidden="true" /></a>
                : <Link className="rh-button rh-button-light" to="/contact"><span>Contact us to request</span><ArrowRight className="rh-button-icon" size={17} aria-hidden="true" /></Link>}
            </div>
          </div>
        </div>
      </section>
      <GoogleFormDialog form={openForm} onClose={() => setOpenForm(null)} />
    </div>
  );
}
