import { useEffect, useRef, useState } from 'react';
import { ArrowRight, BookOpenCheck, BriefcaseBusiness, CalendarDays, FlaskConical, GraduationCap, MapPin, Network, RotateCcw, Search, SlidersHorizontal, Star, Tag, Users, X } from 'lucide-react';
import { Link, useSearchParams } from 'react-router-dom';
import { PublicWebsiteApi } from '../../api/publicWebsiteApi';
import PageHero from '../../components/public/PageHero';
import RequestForm from '../../components/public/RequestForm';
import SectionHeading from '../../components/public/SectionHeading';
import { SEO } from '../../config/contentStructure';
import { useSiteSettings } from '../../contexts/SiteSettingsContext';
import { usePageMeta } from '../../utils/seo';
import '../../styles/pages/opportunities.css';

const benefits = [
  [Users, 'Mentorship', 'Get guided by experienced researchers with a strong publication record.'],
  [BookOpenCheck, 'Publication Pathway', 'Strong contributors may receive opportunities to co-author published research papers.'],
  [GraduationCap, 'Skill Development', 'Build skills in data collection, statistics, writing, ethics, and teamwork.'],
  [FlaskConical, 'Hands-On Experience', 'Participate in real research projects from idea to publication.'],
  [CalendarDays, 'Quarterly Cycles', 'Join a structured cycle with selection followed by three months of mentorship.'],
  [Network, 'Global Network', 'Connect with an international community of mentors, peers, and researchers.'],
];

const typeOptions = ['', 'position', 'collaboration', 'programme'];
const typeLabel = type => (type ? type.charAt(0).toUpperCase() + type.slice(1) : 'All types');

function OpportunityCard({ item, onShowDetails, index }) {
  const isClosed = Boolean(item.is_closed || item.status === 'closed');
  const classes = ['rp-opps-card', item.is_featured && 'rp-opps-card-featured', isClosed && 'rp-opps-card-closed'].filter(Boolean).join(' ');
  return (
    <article className={classes} data-reveal style={{ '--rh-delay': `${(index % 3) * 70}ms` }}>
      <div className="rp-opps-card-meta">
        {item.is_featured && <span className="rp-opps-chip rp-opps-chip-featured"><Star size={13} fill="currentColor" aria-hidden="true" /> Featured</span>}
        {isClosed && <span className="rp-opps-chip rp-opps-chip-closed">Closed</span>}
        <span className="rh-chip">{item.type_label || item.type}</span>
        {item.deadline && <span className="rp-opps-deadline"><CalendarDays size={14} aria-hidden="true" /> Deadline {new Date(item.deadline).toLocaleDateString()}</span>}
      </div>
      <h3>{item.title}</h3>
      {item.organization && <p className="rp-opps-org">{item.organization}</p>}
      <p className="rp-opps-summary">{item.short_description || 'Open this opportunity to learn more about the research pathway.'}</p>
      <div className="rp-opps-card-details">
        <span className="rh-tag"><MapPin size={14} aria-hidden="true" /> {item.is_remote ? 'Remote' : item.location || 'Location TBA'}</span>
        <span className="rh-tag"><Tag size={14} aria-hidden="true" /> {item.specialty || 'General research'}</span>
        {(item.custom_fields || []).filter(field => field.value).slice(0, 2).map(field => <span className="rh-tag" key={field.label}>{field.label}: {field.value}</span>)}
      </div>
      <div className="rp-opps-card-actions">
        {!isClosed && item.application_url ? (
          <a className="button" href={item.application_url} target="_blank" rel="noreferrer">Apply Now <ArrowRight size={15} /></a>
        ) : !isClosed && item.contact_email ? (
          <a className="button" href={`mailto:${item.contact_email}`}>Contact Team <ArrowRight size={15} /></a>
        ) : !isClosed ? (
          <Link className="button" to="/contact">Ask ResRef <ArrowRight size={15} /></Link>
        ) : <span className="rp-opps-closed-note">Applications closed</span>}
        <button className="button button-outline" type="button" onClick={() => onShowDetails(item)}>View details <ArrowRight size={15} /></button>
      </div>
    </article>
  );
}

function OpportunityDetailsModal({ item, onClose, closeButtonRef }) {
  if (!item) return null;
  const isClosed = Boolean(item.is_closed || item.status === 'closed');
  const customFields = (item.custom_fields || []).filter(field => field.value);
  return (
    <div className="rp-opps-backdrop" role="presentation" onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}>
      <article className="rp-opps-modal" role="dialog" aria-modal="true" aria-labelledby="opportunity-details-title">
        <header className="rp-opps-modal-head">
          <div>
            <span className="rh-chip">{item.type_label || item.type || 'Research opportunity'}</span>
            <h2 id="opportunity-details-title">{item.title}</h2>
            <p className="rp-opps-modal-meta">
              <span><MapPin size={14} aria-hidden="true" /> {item.is_remote ? 'Remote' : item.location || 'Location TBA'}</span>
              {item.deadline && <span><CalendarDays size={14} aria-hidden="true" /> Deadline {new Date(item.deadline).toLocaleDateString()}</span>}
            </p>
          </div>
          <button ref={closeButtonRef} type="button" onClick={onClose} aria-label="Close opportunity details"><X size={20} /></button>
        </header>
        <div className="rp-opps-modal-body">
          {item.full_description && <section><h3>About this opportunity</h3><p>{item.full_description}</p></section>}
          {item.requirements && <section><h3>Requirements</h3><p>{item.requirements}</p></section>}
          {item.benefits && <section><h3>Benefits</h3><p>{item.benefits}</p></section>}
          {customFields.length > 0 && <section><h3>Additional information</h3><dl>{customFields.map(field => <div key={`${field.label}-${field.value}`}><dt>{field.label}{field.is_required && <em>Required</em>}</dt><dd>{field.value}{field.help_text && <small>{field.help_text}</small>}</dd></div>)}</dl></section>}
          {!item.full_description && !item.requirements && !item.benefits && !customFields.length && <p className="rp-opps-modal-empty">More information will be added soon. You can still contact ResRef about this opportunity.</p>}
        </div>
        <footer className="rp-opps-modal-foot">
          {!isClosed && (item.application_url ? <a className="button" href={item.application_url} target="_blank" rel="noreferrer">Apply Now <ArrowRight size={15} /></a> : item.contact_email ? <a className="button" href={`mailto:${item.contact_email}`}>Contact Team <ArrowRight size={15} /></a> : <Link className="button" to="/contact">Contact ResRef <ArrowRight size={15} /></Link>)}
          {isClosed && <span className="rp-opps-modal-closed">Applications for this opportunity are closed.</span>}
          <button type="button" className="button button-outline" onClick={onClose}>Close</button>
        </footer>
      </article>
    </div>
  );
}

export default function ResearchOpportunitiesPage() {
  usePageMeta(SEO.opportunities);
  const settings = useSiteSettings();
  const [searchParams, setSearchParams] = useSearchParams();
  const [filters, setFilters] = useState({
    search: searchParams.get('search') || '',
    type: searchParams.get('type') || '',
    category: searchParams.get('category') || '',
    location: searchParams.get('location') || '',
  });
  const [opportunities, setOpportunities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedOpportunity, setSelectedOpportunity] = useState(null);
  const modalCloseButtonRef = useRef(null);

  useEffect(() => {
    if (!selectedOpportunity) return undefined;
    const previousOverflow = document.body.style.overflow;
    const triggeringElement = document.activeElement;
    const onKeyDown = event => { if (event.key === 'Escape') setSelectedOpportunity(null); };
    document.body.style.overflow = 'hidden';
    modalCloseButtonRef.current?.focus();
    window.addEventListener('keydown', onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener('keydown', onKeyDown);
      triggeringElement?.focus?.();
    };
  }, [selectedOpportunity]);

  const load = async (next = filters) => {
    setLoading(true);
    setError('');
    try {
      const data = await PublicWebsiteApi.getOpportunities({ ...next, per_page: 24 });
      setOpportunities(data.results || []);
    } catch (err) {
      setError(err.message);
      setOpportunities([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const update = event => {
    const next = { ...filters, [event.target.name]: event.target.value };
    setFilters(next);
  };

  const submit = event => {
    event.preventDefault();
    const next = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value) next.set(key, value);
    });
    setSearchParams(next);
    load(filters);
  };
  const resetFilters = () => {
    const next = { search: '', type: '', category: '', location: '' };
    setFilters(next);
    setSearchParams(new URLSearchParams());
    load(next);
  };
  const hasActiveFilters = Object.values(filters).some(Boolean);

  return (
    <div className="rh-page rp-opps">
      <PageHero title="Research Opportunities" text="Explore open research projects, collaborations, mentorship pathways, and publication-focused opportunities." settingPrefix="opportunities">
        <a className="rh-button rh-button-light" href="#opportunities-list"><span>Browse opportunities</span><ArrowRight className="rh-button-icon" size={17} aria-hidden="true" /></a>
        <a className="rh-button rh-button-ghost" href="#opportunities-apply"><span>Apply to the program</span></a>
      </PageHero>

      <section className="rh-section rp-opps-pathways">
        <div className="rh-container">
          <SectionHeading eyebrow={settings.opportunities_benefits_eyebrow} title={settings.opportunities_benefits_title} text={settings.opportunities_benefits_text} align="center" />
          <div className="rh-card-grid rh-card-grid-3">
            {benefits.map(([Icon, title, text], index) => (
              <article className="rh-card rh-card-compact" key={title} data-reveal style={{ '--rh-delay': `${(index % 3) * 80}ms` }}>
                <span className="rh-card-icon" aria-hidden="true"><Icon size={24} /></span>
                <h3>{title}</h3>
                <p>{text}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="rh-section rh-surface-mist rp-opps-list" id="opportunities-list" aria-labelledby="opportunities-list-title">
        <div className="rh-container">
          <SectionHeading id="opportunities-list-title" eyebrow={settings.opportunities_list_eyebrow} title={settings.opportunities_list_title} text="Browse open research projects and roles. Featured opportunities are shown first." />

          <form className="rh-panel rp-opps-filter" onSubmit={submit} role="search" aria-label="Filter research opportunities">
            <div className="rp-opps-filter-field rp-opps-filter-search">
              <label htmlFor="opps-search">Search</label>
              <div className="rp-opps-input-wrap">
                <Search size={18} aria-hidden="true" />
                <input id="opps-search" name="search" value={filters.search} onChange={update} placeholder="Search by topic, organization, or specialty" aria-label="Search research opportunities" />
                {filters.search && <button type="button" className="rp-opps-clear" onClick={() => setFilters(current => ({ ...current, search: '' }))} aria-label="Clear opportunity search"><X size={16} /></button>}
              </div>
            </div>
            <div className="rp-opps-filter-field">
              <label htmlFor="opps-type">Type</label>
              <select id="opps-type" name="type" value={filters.type} onChange={update}>{typeOptions.map(type => <option value={type} key={type}>{typeLabel(type)}</option>)}</select>
            </div>
            <div className="rp-opps-filter-field">
              <label htmlFor="opps-category">Specialty</label>
              <input id="opps-category" name="category" value={filters.category} onChange={update} placeholder="Specialty" />
            </div>
            <div className="rp-opps-filter-field">
              <label htmlFor="opps-location">Location</label>
              <input id="opps-location" name="location" value={filters.location} onChange={update} placeholder="Location" />
            </div>
            <div className="rp-opps-filter-actions">
              <button className="button" type="submit"><SlidersHorizontal size={16} aria-hidden="true" /> Filter</button>
              {hasActiveFilters && <button className="rp-opps-reset" type="button" onClick={resetFilters}><RotateCcw size={14} aria-hidden="true" /> Reset filters</button>}
            </div>
          </form>

          {error && <p className="error rp-opps-error" role="alert">{error}</p>}
          {!loading && opportunities.length > 0 && (
            <p className="rp-opps-count" aria-live="polite"><strong>{opportunities.length}</strong> {opportunities.length === 1 ? 'opportunity' : 'opportunities'}{hasActiveFilters ? ' match your filters' : ' available'}</p>
          )}
          {loading ? (
            <div className="rp-opps-grid" aria-label="Loading research opportunities">{Array.from({ length: 6 }).map((_, index) => <span className="rp-opps-skeleton" key={index} />)}</div>
          ) : opportunities.length ? (
            <div className="rp-opps-grid">{opportunities.map((item, index) => <OpportunityCard item={item} key={item.id} index={index} onShowDetails={setSelectedOpportunity} />)}</div>
          ) : (
            <div className="rp-opps-empty">
              <span className="rp-opps-empty-icon" aria-hidden="true"><BriefcaseBusiness size={28} /></span>
              <h3>{settings.opportunities_empty_title}</h3>
              <p>{settings.opportunities_empty_text}</p>
              <div className="rh-actions">{hasActiveFilters && <button className="button button-outline" type="button" onClick={resetFilters}>Reset filters</button>}<Link className="button" to={settings.opportunities_empty_button_url || '/join'}>{settings.opportunities_empty_button_label} <ArrowRight size={15} /></Link></div>
            </div>
          )}
        </div>
      </section>
      <OpportunityDetailsModal item={selectedOpportunity} onClose={() => setSelectedOpportunity(null)} closeButtonRef={modalCloseButtonRef} />

      <section className="rh-section rp-opps-apply" id="opportunities-apply">
        <div className="rh-container rp-opps-apply-layout">
          <div className="rp-opps-apply-copy">
            <SectionHeading eyebrow={settings.opportunities_application_eyebrow} title={settings.opportunities_application_title} text={settings.opportunities_application_text} />
            <ul className="rh-check-list rp-opps-apply-points" data-reveal>
              {benefits.slice(0, 3).map(([Icon, title, text]) => <li key={title}><Icon size={18} aria-hidden="true" /><span><strong>{title}.</strong> {text}</span></li>)}
            </ul>
          </div>
          <div className="rh-panel rh-panel-raised rp-opps-apply-panel" data-reveal>
            <RequestForm id="opportunities-application" requestType="Research opportunities application" optionLabel="Research Interests" submitLabel={settings.opportunities_application_submit_label} successMessage="Your research opportunities application has been received." />
          </div>
        </div>
      </section>
    </div>
  );
}
