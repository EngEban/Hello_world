import { AlertTriangle, ArrowRight, ChevronDown, Layers3, Search, SearchX, SlidersHorizontal, X } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { PublicWebsiteApi } from '../../api/publicWebsiteApi';
import CategoryExplorer from '../../components/public/CategoryExplorer';
import PublicPagination from '../../components/public/PublicPagination';
import ResourceCard from '../../components/public/ResourceCard';
import PageHero from '../../components/public/PageHero';
import { useSiteSettings } from '../../contexts/SiteSettingsContext';
import { plainText } from '../../utils/articleContent';
import { flattenTopics, publishedTopics, researchCategory, researchTopics } from '../../utils/libraryTopics';
import { usePageMeta } from '../../utils/seo';
import '../../styles/pages/database-library.css';

function DatabaseLibrary({ learning = false }) {
  const { category } = useParams();
  const navigate = useNavigate();
  const settings = useSiteSettings();
  const [params] = useSearchParams();
  const searchRef = useRef(null);
  const query = params.get('q') || '';
  const researchSlug = settings.learn_category_slug || 'mastering-research';
  const requestedCategory = params.get('cat') || category || '';
  const tag = params.get('tag') || '';
  const sort = ['latest', 'oldest', 'updated', 'title'].includes(params.get('sort')) ? params.get('sort') : 'latest';
  const page = Math.max(1, Number.parseInt(params.get('page'), 10) || 1);
  const [categories, setCategories] = useState([]);
  const [categoriesError, setCategoriesError] = useState('');
  const [data, setData] = useState({ results: [], pagination: null });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  const [topicsOpen, setTopicsOpen] = useState(() => window.matchMedia('(min-width: 901px)').matches);
  const flat = useMemo(() => learning ? researchTopics(categories, researchSlug) : flattenTopics(categories), [categories, learning, researchSlug]);
  const published = useMemo(() => publishedTopics(categories), [categories]);
  const navTopics = useMemo(() => learning ? researchTopics(published, researchSlug) : flattenTopics(published), [published, learning, researchSlug]);
  const cat = learning ? researchCategory(requestedCategory, flat, researchSlug) : requestedCategory;
  const libraryHome = learning ? '/articles' : '/database';
  const topic = flat.find(item => item.slug === cat);
  const title = learning ? settings.learn_hero_title || settings.learn_page_title || 'Mastering Research' : topic ? plainText(topic.name) : cat ? plainText(cat.replace(/-/g, ' ').replace(/\b[a-z]/g, char => char.toUpperCase())) : settings.database_hero_title || 'Research Database';
  const description = learning ? settings.learn_hero_text || settings.learn_page_text || 'Practical resources for planning, writing, publishing, and progressing through research.' : cat ? topic?.description || `Explore published articles, research tools, and resources in ${title}.` : settings.database_hero_text || 'Medical knowledge and research resources, organised for discovery.';
  const canonical = new URL(learning ? '/articles' : cat ? `/database/${cat}` : '/database', window.location.origin).href;
  const meta = useMemo(() => ({ title: `${title} | ResRef`, description, canonical }), [title, description, canonical]);
  usePageMeta(meta);
  useEffect(() => { if (params.get('focus') === 'search') searchRef.current?.focus(); }, [params]);

  useEffect(() => {
    let active = true;
    PublicWebsiteApi.getCategories().then(result => { if (active) { setCategories(result.categories || []); setCategoriesError(''); } })
      .catch(() => { if (active) setCategoriesError('Topics could not be loaded. You can still search articles.'); });
    return () => { active = false; };
  }, [retry]);
  useEffect(() => {
    let active = true; setLoading(true); setError('');
    PublicWebsiteApi.getPosts({ q: query, cat, tag, sort, page, per_page: 12 }).then(result => {
      if (active) setData({ results: result.results || [], pagination: result.pagination });
    }).catch(err => { if (active) setError(err.message); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [query, cat, tag, sort, page, retry]);
  useEffect(() => {
    const media = window.matchMedia('(min-width: 901px)');
    const change = event => setTopicsOpen(event.matches);
    media.addEventListener('change', change);
    return () => media.removeEventListener('change', change);
  }, []);
  const urlFor = changes => {
    const next = new URLSearchParams(params);
    Object.entries(changes).forEach(([key, value]) => value ? next.set(key, value) : next.delete(key));
    return `${learning ? '/articles' : category ? `/database/${category}` : '/database'}${next.size ? `?${next}` : ''}`;
  };
  const topicHref = item => learning ? item.slug === researchSlug ? '/articles' : `/articles?cat=${encodeURIComponent(item.slug)}` : `/database/${item.slug}`;
  const filtered = Boolean(query || tag || cat);
  const highlighted = !query && !tag && page === 1 && sort === 'latest' && !loading && !error ? data.results.find(post => post.featured_image && post.excerpt) : null;
  const remaining = highlighted ? data.results.filter(post => post.id !== highlighted.id) : data.results;
  const pagination = data.pagination;
  const popular = useMemo(() => flat.filter(item => item.depth === (learning ? 1 : 0) && (item.count || item.post_count)).sort((a, b) => (b.count || b.post_count || 0) - (a.count || a.post_count || 0)).slice(0, 6), [flat, learning]);
  const crumbs = learning ? [['Learn']] : cat ? [['Database', '/database'], [title]] : [['Database']];
  const resultsTitle = query ? `Results for “${query}”` : tag ? 'Articles by topic' : sort === 'updated' ? 'Recently updated' : sort === 'title' ? 'Articles A–Z' : sort === 'oldest' ? 'Articles by publication date' : (learning ? settings.learn_results_title : settings.database_results_title) || 'Latest articles';

  return <div className="rp-db">
    <PageHero title={title} text={description} settingPrefix={learning ? 'learn' : cat ? '' : 'database'} imageUrl={topic?.hero_image} breadcrumb={crumbs} />
    <div className="rh-container">
      <section className="rp-db-searchcard rh-hero-follow" aria-label={learning ? 'Search research articles' : 'Search the research database'}>
        <div className="rp-db-searchcard-head">
          <span className="rh-label">{learning ? 'Research library' : 'Research database'}</span>
          <p>{loading && !pagination ? 'Search every published article, guide and questionnaire.' : `Search ${pagination?.total_items ?? data.results.length} ${settings.database_count_label || 'published articles'}${cat ? ` in ${title}` : ''} by title, topic or keyword.`}</p>
        </div>
        <form className="publication-search rp-db-search" onSubmit={event => { event.preventDefault(); navigate(urlFor({ q: String(new FormData(event.currentTarget).get('q') || '').trim(), page: '' })); }} role="search">
          <Search className="rp-db-search-icon" size={21} aria-hidden="true" /><input ref={searchRef} key={query} name="q" type="search" defaultValue={query} placeholder={(learning ? settings.learn_search_placeholder : settings.database_search_placeholder) || 'Search articles, topics, or keywords'} aria-label="Search the research database" />
          {params.get('cat') && <input type="hidden" name="cat" value={cat} />}{tag && <input type="hidden" name="tag" value={tag} />}
          <button type="submit"><span>{(learning ? settings.learn_search_button_label : settings.database_search_button_label) || 'Search'}</span><ArrowRight size={17} aria-hidden="true" /></button>
        </form>
        {!learning && !filtered && page === 1 && <CategoryExplorer categories={published} featuredSlug={researchSlug} featuredText={settings.learn_hero_text || settings.learn_page_text || 'Practical resources for planning, writing, publishing, and progressing through research.'} hrefFor={topicHref} />}
        {learning && popular.length > 0 && <div className="rp-db-popular"><span>Popular topics</span>{popular.map(item => <Link key={item.id} to={topicHref(item)} aria-current={cat === item.slug ? 'page' : undefined}>{plainText(item.name)}<small>{item.count || item.post_count}</small></Link>)}</div>}
      </section>

      <div className="rp-db-layout">
        <aside className="rp-db-aside">
          <details open={topicsOpen} onToggle={event => setTopicsOpen(event.currentTarget.open)} className="publication-topic-browser rp-db-topics">
            <summary><span className="rp-db-topics-icon" aria-hidden="true"><Layers3 size={18} /></span><span>{learning ? 'Research topics' : settings.database_categories_label || 'Browse topics'}</span><ChevronDown className="rp-db-topics-chevron" size={18} aria-hidden="true" /></summary>
            {categoriesError && <p className="rp-db-topics-error" role="status">{categoriesError}</p>}
            <nav aria-label={learning ? 'Browse research topics' : 'Browse database topics'}>
              {!learning && <Link className="rp-db-topic is-all" to="/database" aria-current={!cat ? 'page' : undefined}><span>All articles</span></Link>}
              {navTopics.map(item => <Link key={item.id} className={`rp-db-topic depth-${Math.min(item.depth, 3)}`} to={topicHref(item)} aria-current={cat === item.slug ? 'page' : undefined} style={{ paddingInlineStart: `${14 + Math.min(item.depth, 3) * 14}px` }}><span>{plainText(item.name)}</span><small>{item.count || item.post_count || 0}</small></Link>)}
              {!navTopics.length && !categoriesError && Array.from({ length: 7 }, (_, i) => <span className="rp-db-topic-skeleton" key={i} aria-hidden="true" />)}
            </nav>
          </details>
        </aside>

        <section className="publication-library-main rp-db-main" aria-label="Articles" aria-busy={loading}>
          <div className="publication-results-header rp-db-results-head">
            <div><h2>{resultsTitle}</h2><p role="status">{loading ? 'Loading articles…' : error ? 'Articles unavailable' : `${pagination?.total_items ?? data.results.length} ${settings.database_count_label || 'published articles'}`}</p></div>
            <label className="publication-sort rp-db-sort"><SlidersHorizontal size={16} aria-hidden="true" /><span>Sort by</span><select value={sort} onChange={event => navigate(urlFor({ sort: event.target.value, page: '' }))}><option value="latest">Latest published</option><option value="updated">Recently updated</option><option value="oldest">Oldest published</option><option value="title">Title A–Z</option></select></label>
          </div>
          {filtered && <div className="publication-filter-note rp-db-filters">{cat && <span className="rp-db-filter">Topic: {plainText(topic?.name || title)}</span>}{tag && <span className="rp-db-filter">Tag: {plainText(tag.replace(/-/g, ' '))}</span>}{query && <span className="rp-db-filter">Search: {query}</span>}<Link className="rp-db-clear" to={libraryHome}><X size={14} aria-hidden="true" />Clear filters</Link></div>}

          {error ? <div className="rp-db-state is-error" role="alert"><span className="rp-db-state-icon"><AlertTriangle size={24} aria-hidden="true" /></span><h2>Unable to load articles</h2><p>{error}</p><button className="publication-primary-button" onClick={() => setRetry(value => value + 1)}>Try again</button></div>
            : loading ? <div className="rp-card-list" aria-label="Loading articles">{Array.from({ length: 6 }, (_, i) => <div className="rp-card-skeleton" key={i}><span /><span /><span /><span /></div>)}</div>
              : !data.results.length ? <div className="rp-db-state"><span className="rp-db-state-icon"><SearchX size={24} aria-hidden="true" /></span><h2>{(learning ? settings.learn_empty_title : settings.database_empty_title) || 'No matching articles'}</h2><p>{(learning ? settings.learn_empty_text : settings.database_empty_text) || 'Try a different keyword or explore another topic.'}</p><Link className="rh-button rh-button-outline" to={libraryHome}>{learning ? 'Browse research articles' : 'Browse all articles'} <ArrowRight size={15} /></Link></div>
                : <>
                  {highlighted && <div className="rp-db-featured"><p className="rh-label">Latest in {topic ? title : 'the database'}</p><ResourceCard variant="feature" post={highlighted} /></div>}
                  <div className="rp-card-list rp-db-list">{remaining.map(post => <ResourceCard variant="publication" key={post.id} post={post} />)}</div>
                  <PublicPagination pagination={pagination} hrefFor={n => urlFor({ page: n > 1 ? n : '' })} label="Article pagination" className="publication-pagination" />
                </>}
        </section>
      </div>
    </div>
  </div>;
}

export default function DatabasePage() {
  const location = useLocation();
  return <DatabaseLibrary key={location.pathname === '/articles' ? 'learning' : 'database'} learning={location.pathname === '/articles'} />;
}
