import {
  ArrowDown,
  ArrowRight,
  ArrowUp,
  BarChart3,
  BookMarked,
  BookOpen,
  BriefcaseBusiness,
  Command,
  CornerDownLeft,
  Database,
  FileQuestion,
  FileSearch,
  FileText,
  HelpCircle,
  Home,
  Loader2,
  Mail,
  Search,
  SearchX,
  ShieldCheck,
  Sparkles,
  X,
} from 'lucide-react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { PublicWebsiteApi } from '../../api/publicWebsiteApi';
import { DATABASE_CATEGORY_GROUPS, GUIDE_FAQS, TOOL_HUB_ITEMS, slugifyCategory } from '../../config/contentStructure';
import { NAV_ITEMS, PATHS } from '../../config/site';
import '../../styles/pages/universal-search.css';

const PAGE_DESCRIPTIONS = {
  '/': 'Start from the ResRef research platform homepage.',
  '/database': 'Browse questionnaires, articles, resources, and categories.',
  '/tools': 'Open calculators, generators, and research workflow tools.',
  '/consultation': 'Request free expert support for methods, writing, and planning.',
  '/opportunities': 'Explore research projects, roles, and collaborations.',
  '/join': 'Join ResRef teams in education, media, design, data, or technology.',
  '/about': 'Learn the ResRef mission, platform story, and research community.',
  '/contact': 'Send a message to the right ResRef support pathway.',
  '/faq': 'Find answers about ResRef tools, database, accounts, and support.',
};

const PAGE_ICONS = {
  '/': Home,
  '/database': Database,
  '/tools': BookMarked,
  '/consultation': ShieldCheck,
  '/opportunities': BriefcaseBusiness,
  '/join': Sparkles,
  '/about': BookOpen,
  '/contact': Mail,
  '/faq': HelpCircle,
};

const TOOL_ICONS = {
  'Sample Size Calculator': FileQuestion,
  'Reference Generator': FileText,
  'Journal Finder': FileSearch,
  'ResRef Analyzer': BarChart3,
  'Research Analyzer': BarChart3,
};

const REMOTE_GROUPS = {
  posts: ['Research content', Database],
  pages: ['Website pages', BookOpen],
  opportunities: ['Research opportunities', BriefcaseBusiness],
  tools: ['Saved tools', BookMarked],
  users: ['Users', Sparkles],
  media: ['Media library', FileSearch],
};

function normalize(value) {
  return String(value || '').toLowerCase().trim();
}

function buildText(item) {
  return normalize([item.title, item.description, item.subtitle, item.group, item.keywords].filter(Boolean).join(' '));
}

function scoreItem(item, query) {
  const q = normalize(query);
  if (!q) return item.priority || 0;
  const title = normalize(item.title);
  const text = buildText(item);
  if (title === q) return 100;
  if (title.startsWith(q)) return 80;
  if (title.includes(q)) return 60;
  if (text.includes(q)) return 35;
  return 0;
}

function staticSearch(items, query, limit = 5) {
  const q = normalize(query);
  return items
    .map(item => ({ ...item, score: scoreItem(item, q) }))
    .filter(item => (q ? item.score > 0 : item.priority > 0))
    .sort((a, b) => b.score - a.score)
    .slice(0, limit);
}

function localResultGroups(query) {
  const pages = NAV_ITEMS.map((item, index) => ({
    ...item,
    title: item.label,
    subtitle: PAGE_DESCRIPTIONS[item.path],
    url: item.path,
    type: 'Page',
    Icon: PAGE_ICONS[item.path] || BookOpen,
    priority: 90 - index,
  }));

  const tools = TOOL_HUB_ITEMS.map((item, index) => ({
    title: item.title,
    subtitle: item.description,
    url: item.path,
    type: 'Research tool',
    Icon: TOOL_ICONS[item.title] || BookMarked,
    keywords: item.cta,
    priority: 75 - index,
  }));

  const categories = DATABASE_CATEGORY_GROUPS.flatMap(group => (
    group.categories.map(category => ({
      title: category,
      subtitle: group.title,
      url: `/database/${slugifyCategory(category)}`,
      type: 'Database category',
      Icon: Database,
      group: group.title,
      keywords: `${category} questionnaire scale article guide`,
      priority: 40,
    }))
  ));

  const faqs = GUIDE_FAQS.map(([group, question, answer]) => ({
    title: question,
    subtitle: answer,
    url: PATHS.faq,
    type: `FAQ · ${group}`,
    Icon: HelpCircle,
    group,
    keywords: `${question} ${answer}`,
    priority: 25,
  }));

  return [
    { id: 'pages', label: query ? 'Best website matches' : 'Start here', results: staticSearch(pages, query, 4) },
    { id: 'tools', label: 'Research tools', results: staticSearch(tools, query, 4) },
    { id: 'categories', label: 'Database categories', results: staticSearch(categories, query, 4) },
    { id: 'faq', label: 'FAQ answers', results: staticSearch(faqs, query, 3) },
  ].filter(group => group.results.length > 0);
}

function mapRemoteResult(groupKey, item) {
  const [label, Icon] = REMOTE_GROUPS[groupKey] || ['Results', Search];
  return {
    title: item.title || item.metadata?.display_name || item.metadata?.username || 'Untitled result',
    subtitle: item.excerpt || item.metadata?.seo_description || item.metadata?.specialization || label,
    url: item.url || PATHS.database,
    type: item.type ? `${label} · ${item.type}` : label,
    Icon,
    source: 'api',
  };
}

function remoteResultGroups(data) {
  return Object.entries(data?.results || {})
    .map(([key, items]) => ({
      id: `api-${key}`,
      label: REMOTE_GROUPS[key]?.[0] || key,
      results: (items || []).map(item => mapRemoteResult(key, item)).slice(0, 4),
    }))
    .filter(group => group.results.length > 0);
}

function ResultLink({ result, active, id, onSelect, onHover }) {
  const Icon = result.Icon || Search;
  const isExternal = /^https?:\/\//i.test(result.url);
  const className = active ? 'universal-search-result rp-search-result is-active' : 'universal-search-result rp-search-result';
  const content = (
    <>
      <span className="rp-search-result-icon" aria-hidden="true"><Icon size={18} /></span>
      <span className="rp-search-result-copy">
        <strong dir="auto">{result.title}</strong>
        <small>{result.type}</small>
        {result.subtitle && <span dir="auto">{result.subtitle}</span>}
      </span>
      <span className="rp-search-result-enter" aria-hidden="true"><CornerDownLeft size={14} /></span>
      <ArrowRight className="rp-search-result-arrow" size={16} aria-hidden="true" />
    </>
  );
  const shared = { id, className, role: 'option', 'aria-selected': active, onClick: onSelect, onMouseEnter: onHover };

  if (isExternal) return <a href={result.url} {...shared}>{content}</a>;
  return <Link to={result.url} {...shared}>{content}</Link>;
}

export default function UniversalSearch() {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [remoteData, setRemoteData] = useState(null);
  const [error, setError] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);
  const navigate = useNavigate();
  const location = useLocation();
  const shellRef = useRef(null);
  const panelRef = useRef(null);
  const inputRef = useRef(null);
  const mobileInputRef = useRef(null);
  const returnFocusRef = useRef(null);

  const trimmedQuery = query.trim();
  const localGroups = useMemo(() => localResultGroups(trimmedQuery), [trimmedQuery]);
  const remoteGroups = useMemo(() => remoteResultGroups(remoteData), [remoteData]);
  // Keep search focused when first opened. Results appear only after the user
  // provides a query, rather than presenting a navigation directory as a default.
  const groups = trimmedQuery.length >= 2 ? [...localGroups, ...remoteGroups] : [];
  const flatResults = groups.flatMap(group => group.results);
  const fullSearchUrl = trimmedQuery ? `/database?focus=search&q=${encodeURIComponent(trimmedQuery)}` : PATHS.database;

  const openSearch = () => {
    if (!panelRef.current) returnFocusRef.current = document.activeElement;
    setOpen(true);
    window.setTimeout(() => {
      const target = mobileInputRef.current || inputRef.current;
      target?.focus();
    }, 0);
  };

  // Explicit close (Esc, backdrop, close button) hands focus back to whatever opened the panel.
  const closeSearch = () => {
    setOpen(false);
    const target = returnFocusRef.current;
    returnFocusRef.current = null;
    if (target && typeof target.focus === 'function' && document.contains(target)) window.setTimeout(() => target.focus(), 0);
  };

  useEffect(() => {
    setOpen(false);
  }, [location.pathname, location.search]);

  useEffect(() => {
    const onOpenSearch = () => openSearch();
    const onKeyDown = event => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        openSearch();
      }
    };
    window.addEventListener('resref:open-search', onOpenSearch);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      window.removeEventListener('resref:open-search', onOpenSearch);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, []);

  useEffect(() => {
    if (!open) return undefined;
    const closeOnOutside = event => {
      const inside = [shellRef.current, panelRef.current].some(node => node && node.contains(event.target));
      if (!inside) setOpen(false);
    };
    const closeOnEscape = event => { if (event.key === 'Escape') closeSearch(); };
    const { overflow } = document.body.style;
    document.body.style.overflow = 'hidden';
    document.addEventListener('mousedown', closeOnOutside);
    document.addEventListener('keydown', closeOnEscape);
    return () => {
      document.body.style.overflow = overflow;
      document.removeEventListener('mousedown', closeOnOutside);
      document.removeEventListener('keydown', closeOnEscape);
    };
  }, [open]);

  useEffect(() => {
    if (trimmedQuery.length < 2) {
      setRemoteData(null);
      setError('');
      setLoading(false);
      return undefined;
    }

    let active = true;
    const timer = window.setTimeout(() => {
      setLoading(true);
      setError('');
      PublicWebsiteApi.universalSearch({ q: trimmedQuery, content_type: 'all', per_type: 4 })
        .then(data => {
          if (active) setRemoteData(data);
        })
        .catch(() => {
          if (active) {
            setRemoteData(null);
            setError('Live content results are temporarily unavailable.');
          }
        })
        .finally(() => {
          if (active) setLoading(false);
        });
    }, 220);

    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [trimmedQuery]);

  useEffect(() => {
    setActiveIndex(0);
  }, [trimmedQuery, remoteData]);

  useEffect(() => {
    if (open) document.getElementById(`rp-search-option-${activeIndex}`)?.scrollIntoView({ block: 'nearest' });
  }, [activeIndex, open]);

  const goToResult = result => {
    if (!result) {
      navigate(fullSearchUrl);
      setOpen(false);
      return;
    }
    if (/^https?:\/\//i.test(result.url)) {
      window.location.href = result.url;
      return;
    }
    navigate(result.url);
    setOpen(false);
  };

  const submitSearch = event => {
    event.preventDefault();
    goToResult(flatResults[activeIndex] || null);
  };

  const handleKeyDown = event => {
    if (event.key === 'Escape') {
      event.stopPropagation();
      closeSearch();
      inputRef.current?.blur();
      return;
    }
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setOpen(true);
      setActiveIndex(index => Math.min(index + 1, Math.max(flatResults.length - 1, 0)));
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault();
      setActiveIndex(index => Math.max(index - 1, 0));
    }
  };

  // Keep keyboard focus inside the dialog while it is open.
  const trapFocus = event => {
    if (event.key !== 'Tab' || !panelRef.current) return;
    const focusable = [...panelRef.current.querySelectorAll('input, button:not(:disabled), a[href]')].filter(node => node.offsetParent !== null);
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  };

  const clearSearch = () => {
    setQuery('');
    setRemoteData(null);
    setError('');
    openSearch();
  };

  let renderedIndex = -1;
  const hasQuery = trimmedQuery.length >= 2;
  const activeId = hasQuery && flatResults.length ? `rp-search-option-${activeIndex}` : undefined;

  const panel = (
    <div className="rh-tokens rp-search">
      <div className="rp-search-backdrop" aria-hidden="true" onMouseDown={closeSearch} />
      <div className="rp-search-dialog" role="dialog" aria-modal="true" aria-label="Universal search results" ref={panelRef} onKeyDown={trapFocus}>
        <form className="rp-search-field" onSubmit={submitSearch} role="search">
          <Search className="rp-search-field-icon" size={20} aria-hidden="true" />
          <input
            ref={mobileInputRef}
            value={query}
            onChange={event => setQuery(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search ResRef"
            aria-label="Search ResRef"
            role="combobox"
            aria-expanded={hasQuery && flatResults.length > 0}
            aria-controls="rp-search-results"
            aria-activedescendant={activeId}
            aria-autocomplete="list"
            autoComplete="off"
            spellCheck="false"
          />
          {loading && <Loader2 className="rp-search-loader" size={18} aria-label="Loading results" />}
          {query && <button type="button" className="rp-search-clear" onClick={clearSearch} aria-label="Clear search"><X size={15} /></button>}
          <button type="button" className="rp-search-close" onClick={closeSearch} aria-label="Close search"><kbd>Esc</kbd><X size={18} /></button>
        </form>

        <div className="rp-search-body">
          {!hasQuery && <div className="rp-search-intro">
            <span className="rp-search-intro-icon" aria-hidden="true"><Sparkles size={22} /></span>
            <strong>Search across ResRef</strong>
            <span>Pages, tools, database categories, FAQ answers, articles, opportunities, and permitted account content.</span>
            <small>Type at least two characters to see results.</small>
          </div>}

          {hasQuery && <div className="rp-search-head">
            <strong>{trimmedQuery ? `Search results for "${trimmedQuery}"` : 'Search across ResRef'}</strong>
            <span>Pages, tools, database categories, FAQ answers, articles, opportunities, and permitted account content.</span>
          </div>}

          {hasQuery && groups.length === 0 ? (
            loading ? <div className="rp-search-skeleton" aria-hidden="true"><span /><span /><span /></div> : <div className="rp-search-empty">
              <span className="rp-search-intro-icon" aria-hidden="true"><SearchX size={22} /></span>
              <strong>No quick match found</strong>
              <span>Try a specialty, tool name, questionnaire topic, or research keyword.</span>
            </div>
          ) : hasQuery ? (
            <div className="rp-search-groups" id="rp-search-results" role="listbox" aria-label="Search results">
              {groups.map(group => (
                <div className="rp-search-group" role="group" aria-labelledby={`rp-search-group-${group.id}`} key={group.id}>
                  <p className="rp-search-group-label" id={`rp-search-group-${group.id}`}>{group.label}<span>{group.results.length}</span></p>
                  <div className="rp-search-result-list">
                    {group.results.map(result => {
                      renderedIndex += 1;
                      const itemIndex = renderedIndex;
                      return (
                        <ResultLink
                          key={`${group.id}-${result.url}-${result.title}`}
                          id={`rp-search-option-${itemIndex}`}
                          result={result}
                          active={itemIndex === activeIndex}
                          onHover={() => setActiveIndex(itemIndex)}
                          onSelect={() => setOpen(false)}
                        />
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          ) : null}

          {hasQuery && error && <p className="rp-search-note" role="status">{error} Showing built-in site results.</p>}
        </div>

        <div className="rp-search-footer">
          {hasQuery ? <button type="button" className="rp-search-all" onClick={() => goToResult(null)}>
            <Database size={16} aria-hidden="true" />
            <span>Search database for {trimmedQuery ? `"${trimmedQuery}"` : 'all resources'}</span>
            <ArrowRight size={15} aria-hidden="true" />
          </button> : <span className="rp-search-tip">Use Ctrl/⌘ + K anytime</span>}
          <span className="rp-search-keys" aria-hidden="true"><kbd><ArrowUp size={12} /></kbd><kbd><ArrowDown size={12} /></kbd> navigate <kbd><CornerDownLeft size={12} /></kbd> open <kbd>Esc</kbd> close</span>
        </div>
      </div>
    </div>
  );

  return (
    <div className="universal-search" ref={shellRef}>
      <form className={open ? 'universal-search-control is-open' : 'universal-search-control'} onSubmit={submitSearch} role="search">
        <Search size={18} />
        <input
          ref={inputRef}
          value={query}
          onChange={event => setQuery(event.target.value)}
          onFocus={() => setOpen(true)}
          onKeyDown={handleKeyDown}
          placeholder="Search all ResRef pages, tools, categories, and resources"
          aria-label="Search all ResRef"
        />
        <span className="universal-search-shortcut"><Command size={13} /> K</span>
        {query && (
          <button className="universal-search-clear" type="button" onClick={clearSearch} aria-label="Clear search">
            <X size={15} />
          </button>
        )}
      </form>

      {open && createPortal(panel, document.body)}
    </div>
  );
}
