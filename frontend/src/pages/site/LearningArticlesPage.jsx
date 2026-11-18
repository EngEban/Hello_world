import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { AlertTriangle, ArrowRight, GraduationCap, Search, SearchX, X } from 'lucide-react';
import { PublicWebsiteApi } from '../../api/publicWebsiteApi';
import PublicPagination from '../../components/public/PublicPagination';
import ResourceCard from '../../components/public/ResourceCard';
import PageHero from '../../components/public/PageHero';
import { useSiteSettings } from '../../contexts/SiteSettingsContext';
import { usePageMeta } from '../../utils/seo';
import { plainText } from '../../utils/articleContent';
import { researchTopics } from '../../utils/libraryTopics';
import '../../styles/pages/database-library.css';

const valueOr = (value, fallback) => value || fallback;

export default function LearningArticlesPage() {
  const settings = useSiteSettings();
  const [searchParams, setSearchParams] = useSearchParams();
  const [posts, setPosts] = useState([]);
  const [pagination, setPagination] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const rootCategory = valueOr(settings.learn_category_slug, 'mastering-research');
  const [topics, setTopics] = useState([]);
  const query = searchParams.get('q') || '';
  // Subcategories of the learning category, shown as chips for quick switching.
  const subtopics = useMemo(() => topics.filter(item => item.depth === 1), [topics]);
  const requestedTopic = searchParams.get('topic') || '';
  const activeTopic = subtopics.find(item => item.slug === requestedTopic);
  const category = activeTopic ? activeTopic.slug : rootCategory;
  const page = Math.max(1, Number.parseInt(searchParams.get('page'), 10) || 1);
  usePageMeta({ title: `${valueOr(settings.learn_page_title, 'Mastering Research')} | ResRef`, description: valueOr(settings.learn_page_text, 'Research learning articles from ResRef.') });

  useEffect(() => {
    let active = true;
    PublicWebsiteApi.getCategories().then(result => { if (active) setTopics(researchTopics(result.categories || [], rootCategory)); }).catch(() => {});
    return () => { active = false; };
  }, [rootCategory]);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    PublicWebsiteApi.getPosts({ q: query, cat: category, page, per_page: 18 }, { signal: controller.signal }).then(data => {
      setPosts(data.results || []);
      setPagination(data.pagination || null);
      setLoading(false);
    }).catch(err => {
      if (err.name === 'AbortError') return;
      setError(err.message);
      setLoading(false);
    });
    return () => controller.abort();
  }, [category, query, page]);

  const goToPage = nextPage => {
    const next = new URLSearchParams(searchParams);
    if (nextPage > 1) next.set('page', String(nextPage));
    else next.delete('page');
    setSearchParams(next);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const submitSearch = event => {
    event.preventDefault();
    const value = new FormData(event.currentTarget).get('q')?.trim();
    setSearchParams({ ...(value ? { q: value } : {}), ...(activeTopic ? { topic: activeTopic.slug } : {}) });
  };

  const chooseTopic = slug => {
    setSearchParams({ ...(query ? { q: query } : {}), ...(slug ? { topic: slug } : {}) });
  };
  const rootTopic = topics.find(item => item.depth === 0);

  const total = pagination?.total_items ?? posts.length;

  return <div className="rp-db rp-learn">
    <PageHero title={valueOr(settings.learn_page_title, 'Mastering Research')} text={valueOr(settings.learn_page_text, 'A focused library of practical articles for planning, writing, publishing, and progressing through research with clarity.')} settingPrefix="learn" breadcrumb={[[valueOr(settings.nav_learn_label, 'Learn')]]} />
    <div className="rh-container">
      <section className="rp-db-searchcard rh-hero-follow" aria-label="Search Mastering Research articles">
        <div className="rp-db-searchcard-head">
          <span className="rh-label">{valueOr(settings.learn_category_label, 'Mastering Research')}</span>
          <p>{loading && !pagination ? 'Practical guides for every stage of your research.' : `${total} practical ${total === 1 ? 'guide' : 'guides'} for planning, writing and publishing research.`}</p>
        </div>
        <form className="rp-db-search" onSubmit={submitSearch} role="search">
          <Search className="rp-db-search-icon" size={21} aria-hidden="true" />
          <input name="q" type="search" key={query} defaultValue={query} placeholder={valueOr(settings.learn_search_placeholder, 'Search Mastering Research articles')} aria-label="Search Mastering Research articles" />
          <button className="button"><span>{valueOr(settings.learn_search_button_label, 'Search articles')}</span> <ArrowRight size={16} aria-hidden="true" /></button>
        </form>
      </section>

      {subtopics.length > 0 && (
        <nav className="rp-learn-topics" aria-label={`${valueOr(settings.learn_category_label, 'Mastering Research')} topics`}>
          <button type="button" className={!activeTopic ? 'is-active' : ''} aria-pressed={!activeTopic} onClick={() => chooseTopic('')}>
            All topics{rootTopic?.count ? <span>{rootTopic.count}</span> : null}
          </button>
          {subtopics.map(item => (
            <button type="button" key={item.slug} className={activeTopic?.slug === item.slug ? 'is-active' : ''} aria-pressed={activeTopic?.slug === item.slug} onClick={() => chooseTopic(item.slug)}>
              {plainText(item.name)}{item.count ? <span>{item.count}</span> : null}
            </button>
          ))}
        </nav>
      )}

      <section className="rp-learn-results" aria-busy={loading}>
        <div className="rp-db-results-head">
          <div className="rp-learn-heading">
            <span className="rp-learn-icon" aria-hidden="true"><GraduationCap size={22} /></span>
            <div><span className="rp-learn-kicker">{valueOr(settings.learn_category_label, 'Mastering Research')}</span><h2>{query ? `Results for “${query}”` : activeTopic ? plainText(activeTopic.name) : valueOr(settings.learn_results_title, 'Latest learning articles')}</h2></div>
          </div>
          {query && <button type="button" className="rp-db-clear" onClick={() => chooseTopic(activeTopic?.slug || '')}><X size={14} aria-hidden="true" />Clear search</button>}
        </div>
        {error && <div className="rp-db-state is-error" role="alert"><span className="rp-db-state-icon"><AlertTriangle size={24} aria-hidden="true" /></span><p className="error tool-message">{error}</p></div>}
        {loading ? <div className="rp-card-list rp-learn-list" aria-label="Loading articles">{Array.from({ length: 6 }).map((_, index) => <div className="rp-card-skeleton" key={index}><span /><span /><span /><span /></div>)}</div>
          : posts.length ? <><div className="rp-card-list rp-learn-list">{posts.map(post => <ResourceCard post={post} key={post.id} />)}</div><PublicPagination pagination={pagination} onPage={goToPage} label="Article pages" /></>
            : !error && <div className="rp-db-state"><span className="rp-db-state-icon"><SearchX size={24} aria-hidden="true" /></span><h2>{valueOr(settings.learn_empty_title, 'No articles match that search.')}</h2><p>{valueOr(settings.learn_empty_text, 'Try a different keyword or browse the latest Mastering Research articles.')}</p><button className="button button-secondary" type="button" onClick={() => setSearchParams({})}>Show latest articles</button></div>}
      </section>
    </div>
  </div>;
}
