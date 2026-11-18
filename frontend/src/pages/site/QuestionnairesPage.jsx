import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, ArrowRight, ClipboardList, SearchCheck } from 'lucide-react';
import { PublicWebsiteApi } from '../../api/publicWebsiteApi';
import PageHero from '../../components/public/PageHero';
import ResourceCard from '../../components/public/ResourceCard';
import SectionHeading from '../../components/public/SectionHeading';
import { usePageMeta } from '../../utils/seo';
import '../../styles/pages/questionnaires.css';

const META = { title: 'Research Questionnaires | ResRef', description: 'Validated questionnaires and scales with practical guides for researchers and clinicians.', canonical: '/questionnaires' };

const GUIDE_TOPICS = ['Purpose', 'Structure', 'Target audience', 'Scoring', 'Validation', 'Languages', 'Administration format'];

export default function QuestionnairesPage() {
  usePageMeta(META);
  const [posts, setPosts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    setLoading(true);
    PublicWebsiteApi.getPosts({ q: 'questionnaire', per_page: 12 })
      .then(data => {
        if (!active) return;
        setPosts(data.results || []);
        setError('');
      })
      .catch(err => {
        if (!active) return;
        setPosts([]);
        setError(err.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, []);

  return (
    <div className="rp-quest">
      <PageHero title="Research Questionnaires" text="Find the best scales and questionnaires for advancing your research." settingPrefix="questionnaires" breadcrumb={[['Database', '/database'], ['Questionnaires']]} />
      <section className="rh-section-tight">
        <div className="rh-container">
          <div className="rh-split-heading rp-quest-heading">
            <SectionHeading eyebrow="Curated Collection" title="Explore Scientific Questionnaires" text="Browse guides that explain purpose, structure, target audience, scoring, validation, languages, and administration format so you can identify the most relevant instruments for your study." />
            <aside className="rp-quest-search" data-reveal>
              <span className="rp-quest-search-icon" aria-hidden="true"><SearchCheck size={22} /></span>
              <p>Use advanced search when you need a questionnaire related to a specific specialization such as cardiology, dermatology, neurology, public health, and more.</p>
              <Link className="rh-button rh-button-primary" to="/database?q=questionnaire">Search questionnaires by category <ArrowRight className="rh-button-icon" size={16} aria-hidden="true" /></Link>
            </aside>
          </div>

          <div className="rp-quest-covers" data-reveal>
            <span className="rp-quest-covers-label"><ClipboardList size={18} aria-hidden="true" />Every guide covers</span>
            <ul>{GUIDE_TOPICS.map(topic => <li key={topic} className="rh-tag">{topic}</li>)}</ul>
          </div>

          {error && <div className="rp-quest-state is-error" role="alert"><span className="rp-quest-state-icon"><AlertTriangle size={24} aria-hidden="true" /></span><p className="error tool-message">{error}</p></div>}
          {loading && (
            <div className="rp-quest-loading" role="status" aria-live="polite">
              <div className="rp-quest-state">
                <span className="rp-quest-state-icon"><SearchCheck size={24} aria-hidden="true" /></span>
                <strong>Loading questionnaire resources...</strong>
                <p>ResRef is checking the latest available questionnaire guides.</p>
              </div>
              <div className="rp-card-grid" aria-hidden="true">{Array.from({ length: 3 }, (_, index) => <div className="rp-card-skeleton" key={index}><span /><span /><span /><span /></div>)}</div>
            </div>
          )}
          {!loading && !error && posts.length === 0 && (
            <div className="rp-quest-state">
              <span className="rp-quest-state-icon"><SearchCheck size={24} aria-hidden="true" /></span>
              <strong>No questionnaire guides found</strong>
              <p>Try database search for a specialty, disease area, questionnaire name, or scale title.</p>
            </div>
          )}
          {!loading && posts.length > 0 && <div className="rp-card-grid rp-quest-grid">{posts.map(post => <ResourceCard post={post} key={post.id} />)}</div>}
        </div>
      </section>
    </div>
  );
}
