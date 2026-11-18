import { useEffect, useMemo, useRef, useState } from 'react';
import ToolGuide from '../../components/public/ToolGuide';
import { Link } from 'react-router-dom';
import {
  ArrowLeft,
  ArrowRight,
  BarChart3,
  Bookmark,
  BookmarkCheck,
  Brain,
  CheckCircle2,
  ChevronDown,
  Cloud,
  CloudOff,
  Compass,
  Download,
  ExternalLink,
  Filter,
  Gauge,
  Info,
  Lock,
  RotateCcw,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Star,
  UserRound,
  X,
} from 'lucide-react';
import { UsageApi, isUsageRefusal } from '../../api/usageApi';
import useToolUsage from '../../hooks/useToolUsage';
import useToolWorkspace from '../../hooks/useToolWorkspace';
import { useAccount } from '../../contexts/AccountContext';
import { useSiteSettings } from '../../contexts/SiteSettingsContext';
import { pageHeroImage } from '../../config/heroImages';
import {
  TOOL_KEY,
  MAX_RAW_MATCHES,
  PUBLISHER_PRIORITY_ORDER,
  emptyForm,
  filterDefaults,
  articleTypes,
  studyDesigns,
  targetAudiences,
  syncLabels,
  makeId,
  normalizeWorkspace,
  loadWorkspace,
  saveWorkspace,
  workspaceHasContent,
  apcLabel,
  apcTitle,
  reviewLabel,
  quartileLabel,
  formatIssn,
  journalLink,
  formatSyncTime,
  journalKey,
  journalSnapshot,
  categoryPercent,
  buildMatchOptions,
  passesExpandedFilters,
  sortMatches,
  explainMatch,
  matchedCategories,
  downloadCsv,
  loadJournalFinderModules,
} from '../../features/journalFinder/journalFinderModel.js';
import '../../styles/tools/tool-workspace.css';

const PAGE_SIZE = 30;
const SORT_OPTIONS = [
  ['best', 'Best subject match'],
  ['balanced', 'Balanced (fit, impact, speed)'],
  ['impact', 'Highest H-index'],
  ['fast', 'Fastest decision or publication'],
  ['open', 'Open access first'],
  ['affordable', 'Lowest publication fee'],
];
const ACCESS_LABELS = { open: 'Open access only', subscription: 'Subscription only' };
const DIAMOND_LABELS = { diamond: 'Diamond OA only', 'non-diamond': 'No diamond OA' };
const FEE_LABELS = { free: 'No publication fee', known: 'Fee listed', under1000: 'Fee under $1,000', under2500: 'Fee under $2,500', under5000: 'Fee under $5,000' };

function fitLabel(score) {
  if (score >= 75) return 'Strong fit';
  if (score >= 45) return 'Good fit';
  return 'Possible fit';
}

// The text a search was run on. Results only stay open while it is unchanged.
function manuscriptKey(form) {
  return JSON.stringify([form.title, form.abstract, form.keywords, form.articleType, form.studyDesign, form.targetAudience].map(value => String(value || '').trim()));
}

function wordCount(text) {
  return String(text || '').trim().split(/\s+/).filter(Boolean).length;
}

// One removable chip per active filter, shown above the results.
function activeFilterChips(form) {
  const chips = [];
  if (form.category) chips.push(['category', form.category]);
  if (form.publisher) chips.push(['publisher', form.publisher]);
  if (form.quartile) chips.push(['quartile', form.quartile.split(',').join(', ')]);
  if (form.openAccess) chips.push(['openAccess', ACCESS_LABELS[form.openAccess]]);
  if (form.diamond) chips.push(['diamond', DIAMOND_LABELS[form.diamond]]);
  if (form.apcBudget) chips.push(['apcBudget', FEE_LABELS[form.apcBudget]]);
  if (form.minHIndex) chips.push(['minHIndex', `H-index ≥ ${form.minHIndex}`]);
  if (form.maxHIndex) chips.push(['maxHIndex', `H-index ≤ ${form.maxHIndex}`]);
  if (form.maxReviewWeeks) chips.push(['maxReviewWeeks', `≤ ${form.maxReviewWeeks} weeks`]);
  if (form.resultSearch) chips.push(['resultSearch', `“${form.resultSearch}”`]);
  return chips;
}

export default function JournalFinderPage() {
  const settings = useSiteSettings();
  const { account, loading: accountLoading } = useAccount();
  const [finder, setFinder] = useState(null);
  const [journals, setJournals] = useState([]);
  const [categoriesData, setCategoriesData] = useState({});
  const [workspace, setWorkspace] = useState(loadWorkspace);
  // Bring back the manuscript typed on an earlier visit (results are not kept).
  const [form, setForm] = useState(() => ({ ...emptyForm, ...workspace.lastForm, maxResults: filterDefaults.maxResults }));
  const [results, setResults] = useState([]);
  const [detectedCategories, setDetectedCategories] = useState([]);
  const [status, setStatus] = useState('loading');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [filtersOpen, setFiltersOpen] = useState(true);
  const [step, setStep] = useState(1);
  const [searchedKey, setSearchedKey] = useState(null);
  const stepsRef = useRef(null);
  const firstStepRender = useRef(true);
  const toolUsage = useToolUsage('journal_finder', account?.email || '');

  const { syncStatus, syncError, lastSynced } = useToolWorkspace({
    toolKey: TOOL_KEY,
    account,
    accountLoading,
    workspace,
    setWorkspace,
    normalize: normalizeWorkspace,
    hasContent: workspaceHasContent,
    persistLocal: saveWorkspace,
    onRemoteLoaded: remote => setForm({ ...emptyForm, ...remote.lastForm }),
    debounceMs: 900,
  });
  const favoriteKeys = useMemo(() => new Set(workspace.favorites.map(journalKey)), [workspace.favorites]);
  const categories = useMemo(() => Object.keys(categoriesData).sort(), [categoriesData]);
  const detectedNames = useMemo(() => detectedCategories.slice(0, 8).map(([category]) => category), [detectedCategories]);
  const publishers = useMemo(() => [...new Set(journals.map(journal => journal.publisher).filter(Boolean))].sort(), [journals]);
  const filteredResults = useMemo(
    () => sortMatches(results.filter(row => passesExpandedFilters(row.journal, form)), form),
    [results, form],
  );
  const shownCount = Math.max(Number(form.maxResults) || PAGE_SIZE, 1);
  const visibleResults = useMemo(() => filteredResults.slice(0, shownCount), [filteredResults, shownCount]);
  const filterChips = useMemo(() => activeFilterChips(form), [form]);
  const activeFilterCount = filterChips.length;
  const datasetStats = useMemo(() => {
    const open = journals.filter(journal => journal.is_oa).length;
    const diamond = journals.filter(journal => journal.is_diamond).length;
    return { open, diamond, publishers: publishers.length, categories: categories.length };
  }, [journals, publishers.length, categories.length]);
  const abstractWords = wordCount(form.abstract);
  const manuscriptReady = Boolean(form.title.trim() && form.abstract.trim());
  const resultsReady = manuscriptReady && searchedKey === manuscriptKey(form);
  // A step that is no longer open (the abstract was cleared or edited) falls back to the last open one.
  const activeStep = step === 3 && (resultsReady || status === 'searching') ? 3 : step >= 2 && manuscriptReady ? 2 : 1;
  const stepOpen = { 1: true, 2: manuscriptReady, 3: resultsReady };

  useEffect(() => {
    let active = true;
    let releaseModules = null;
    loadJournalFinderModules().then(({ logic, database, categoriesModule, release }) => {
      if (!active) {
        release();
        return;
      }
      releaseModules = release;
      setFinder(logic);
      setJournals(database.journals_data || []);
      setCategoriesData(categoriesModule.categories_data || {});
      setStatus('ready');
    }).catch(() => {
      if (!active) return;
      setStatus('error');
      setError('The journal database could not be loaded. Please refresh the page and try again.');
    });
    return () => {
      active = false;
      if (releaseModules) releaseModules();
    };
  }, []);

  // Each step starts at the top of the step bar, under the sticky navigation.
  useEffect(() => {
    if (firstStepRender.current) {
      firstStepRender.current = false;
      return;
    }
    const node = stepsRef.current;
    if (node) window.scrollTo({ top: window.scrollY + node.getBoundingClientRect().top - 88, behavior: 'instant' });
  }, [activeStep]);

  const applyForm = next => {
    setForm(next);
    setWorkspace(current => ({ ...current, lastForm: next }));
  };

  // Changing a filter or the sort order starts the list again from the top.
  const update = event => {
    const { name, value } = event.target;
    const listChange = name in filterDefaults && name !== 'maxResults';
    applyForm({ ...form, [name]: value, ...(listChange ? { maxResults: filterDefaults.maxResults } : {}) });
  };

  const setField = (name, value) => applyForm({ ...form, [name]: value, maxResults: filterDefaults.maxResults });

  const setQuartile = quartile => {
    const values = new Set(form.quartile.split(',').filter(Boolean));
    if (values.has(quartile)) values.delete(quartile);
    else values.add(quartile);
    setField('quartile', [...values].sort().join(','));
  };

  const showMore = () => applyForm({ ...form, maxResults: String(shownCount + PAGE_SIZE) });

  const reset = () => {
    setResults([]);
    setDetectedCategories([]);
    setError('');
    setNotice('');
    setSearchedKey(null);
    setStep(1);
    applyForm(emptyForm);
  };

  const resetFilters = () => {
    applyForm({ ...form, ...filterDefaults });
    setNotice('Filters cleared. Your manuscript text was kept.');
  };

  const goToFilters = event => {
    event?.preventDefault();
    if (!manuscriptReady) {
      setError('Please enter at least a title and abstract so the matching engine has enough context.');
      return;
    }
    setError('');
    setStep(2);
  };

  const runSearch = async () => {
    if (!finder || !manuscriptReady) {
      setError('Please enter at least a title and abstract so the matching engine has enough context.');
      return;
    }
    setStatus('searching');
    setError('');
    setNotice('');
    // The server counts the search (and refuses it when the allowance is
    // used up) before results are shown. Only a real limit or access decision
    // stops the search; a network hiccup must not block a browser-side tool.
    try {
      const data = await UsageApi.consume('journal_finder');
      if (data.usage) toolUsage.setUsage(data.usage);
    } catch (usageError) {
      if (isUsageRefusal(usageError)) {
        if (usageError.data?.usage) toolUsage.setUsage(usageError.data.usage);
        setError(usageError.message);
        setStatus('ready');
        return;
      }
    }

    setStep(3);
    window.setTimeout(() => {
      try {
        const options = buildMatchOptions(form);
        const categories = typeof finder.analyze_manuscript_categories === 'function'
          ? finder.analyze_manuscript_categories(form.title, options)
          : finder.match_tokens_to_keywords(`${form.title} ${form.abstract} ${form.keywords}`.split(/\s+/));
        const rawMatches = finder.match_categories_to_journals(form.title, options);
        const highest = rawMatches.reduce((max, [, score]) => Math.max(max, score), 1);
        const nextResults = rawMatches.map(([journal, rawScore]) => ({
          journal,
          rawScore,
          score: Math.max(1, Math.round((rawScore / highest) * 100)),
          reasons: explainMatch(journal, categories),
          matched: matchedCategories(journal, categories),
        }));
        const nextCategories = categories.slice(0, 12);
        const nextForm = { ...form, maxResults: filterDefaults.maxResults };
        setForm(nextForm);
        setDetectedCategories(nextCategories);
        setResults(nextResults);
        setSearchedKey(manuscriptKey(nextForm));
        setStatus('ready');
        setWorkspace(current => ({
          ...current,
          lastForm: nextForm,
          searches: [{
            id: makeId(),
            title: form.title.slice(0, 180),
            form: { ...nextForm, abstract: form.abstract.slice(0, 5000) },
            categories: nextCategories.slice(0, 5).map(([category]) => category),
            resultCount: nextResults.length,
            createdAt: new Date().toISOString(),
          }, ...current.searches.filter(item => item.title !== form.title)].slice(0, 12),
        }));
      } catch (error) {
        setError(error.message || 'Could not complete the journal search. Try broader keywords or remove a filter.');
        setStatus('ready');
      }
    }, 0);
  };

  const toggleFavorite = journal => {
    const key = journalKey(journal);
    setWorkspace(current => {
      const exists = current.favorites.some(item => journalKey(item) === key);
      return {
        ...current,
        favorites: exists
          ? current.favorites.filter(item => journalKey(item) !== key)
          : [journalSnapshot(journal), ...current.favorites].slice(0, 80),
      };
    });
    setNotice(favoriteKeys.has(key) ? 'Journal removed from your shortlist.' : 'Journal added to your shortlist.');
  };

  const restoreSearch = saved => {
    applyForm({ ...emptyForm, ...(saved.form || {}) });
    setStep(1);
    setNotice('Saved search restored. Continue through the steps to see its matches again.');
  };

  const removeSavedSearch = id => {
    setWorkspace(current => ({ ...current, searches: current.searches.filter(search => search.id !== id) }));
  };

  const clearShortlist = () => {
    setWorkspace(current => ({ ...current, favorites: [] }));
    setNotice('Shortlist cleared.');
  };

  const SyncIcon = account ? (syncStatus === 'error' ? CloudOff : Cloud) : Lock;
  const syncDescription = accountLoading
    ? 'Checking your ResRef account...'
    : account
      ? syncStatus === 'synced'
        ? `Saved ${formatSyncTime(lastSynced)}`
        : syncStatus === 'syncing'
          ? 'Saving your shortlist and searches'
          : syncStatus === 'loading'
            ? 'Loading your saved Journal Finder workspace'
            : syncError || 'Your local copy is still available'
      : 'Sign in to sync saved searches and favorite journals across ResRef tools.';
  const heroImage = pageHeroImage(settings, 'journal_finder');
  const otherCategories = categories.filter(category => !detectedNames.includes(category));

  return (
    <section className="rp-tool rp-tool--journal journal-finder-section" aria-labelledby="journal-finder-title">
      <div className="rp-tool-container">
        <header className="rp-tool-header" style={{ '--rp-tool-image': `url(${heroImage})` }}>
          <div className="rp-tool-header-main">
            <span className="rp-tool-badge" aria-hidden="true"><Compass size={30} strokeWidth={1.6} /></span>
            <div className="rp-tool-heading">
              <span className="rh-label rh-label-light">Manuscript workspace</span>
              <h1 id="journal-finder-title">{settings.journal_finder_hero_title}</h1>
              <p>{settings.journal_finder_hero_text}</p>
              <ul className="rp-tool-header-chips" aria-label="What the Journal Finder does">
                <li><CheckCircle2 size={14} aria-hidden="true" />Matched to your subject</li>
                <li><CheckCircle2 size={14} aria-hidden="true" />Quartile, fees and review time</li>
                <li><CheckCircle2 size={14} aria-hidden="true" />Shortlist, compare and export</li>
              </ul>
            </div>
          </div>
          <div className={`rp-tool-sync is-${account ? syncStatus : 'guest'}`}>
            <div className="rp-tool-sync-top">
              <span className="rp-tool-sync-icon" aria-hidden="true"><SyncIcon size={18} /></span>
              <div className="rp-tool-sync-copy">
                <span className="rp-tool-sync-state">{account ? syncLabels[syncStatus] : 'Guest workspace'}</span>
                <strong>{account ? (account.display_name || account.email) : 'Local browser storage'}</strong>
              </div>
            </div>
            <p>{syncDescription}</p>
            {account ? <Link className="rp-tool-sync-link" to="/account"><UserRound size={15} aria-hidden="true" /> Account</Link> : <Link className="rp-tool-sync-link is-primary" to="/sign-in?next=/tools/journal-finder"><Cloud size={15} aria-hidden="true" /> Sign in to sync</Link>}
          </div>
        </header>

        <div className="rp-tool-stats" aria-label="Journal Finder summary">
          <div className="rp-tool-stat journal-command-card"><span className="rp-tool-stat-icon" aria-hidden="true"><BarChart3 size={19} /></span><span className="rp-tool-stat-label">Dataset</span><strong>{journals.length.toLocaleString()} journals</strong><small>{datasetStats.categories} categories and {datasetStats.publishers.toLocaleString()} publishers</small></div>
          <div className="rp-tool-stat journal-command-card"><span className="rp-tool-stat-icon" aria-hidden="true"><Sparkles size={19} /></span><span className="rp-tool-stat-label">Your top field</span><strong>{detectedCategories[0]?.[0] || '--'}</strong><small>{detectedCategories.length ? `${detectedCategories.length} related fields detected` : 'Run a search to detect your fields'}</small></div>
          <div className="rp-tool-stat journal-command-card"><span className="rp-tool-stat-icon" aria-hidden="true"><ShieldCheck size={19} /></span><span className="rp-tool-stat-label">Open access</span><strong>{datasetStats.open.toLocaleString()} journals</strong><small>{datasetStats.diamond.toLocaleString()} diamond (free to publish and read)</small></div>
          <div className="rp-tool-stat journal-command-card"><span className="rp-tool-stat-icon" aria-hidden="true"><BookmarkCheck size={19} /></span><span className="rp-tool-stat-label">Shortlist</span><strong>{workspace.favorites.length}</strong><small>{account ? 'Synced with your account' : 'Saved locally until sign-in'}</small></div>
        </div>

        {notice && <div className="rp-tool-notice is-success" role="status" aria-live="polite"><CheckCircle2 size={17} aria-hidden="true" /><span>{notice}</span><button type="button" onClick={() => setNotice('')} aria-label="Dismiss"><X size={15} /></button></div>}
        {error && <p className="rp-tool-notice is-error error tool-message" role="alert">{error}</p>}
        {!error && toolUsage.summary && <p className="rp-tool-notice is-warning tool-usage-summary" role="status">{toolUsage.summary}</p>}

        <nav className="rp-jf-steps" aria-label="Journal Finder steps" ref={stepsRef}>
          <ol>
            {[[1, 'Your manuscript', 'Title and abstract'], [2, 'Filters', 'Optional'], [3, 'Matches', 'Your journal list']].map(([number, label, hint]) => (
              <li key={number}>
                <button type="button" className={activeStep === number ? 'is-current' : stepOpen[number] ? 'is-open' : ''} disabled={!stepOpen[number]} aria-current={activeStep === number ? 'step' : undefined} onClick={() => setStep(number)}>
                  <span className="rp-jf-step-number" aria-hidden="true">{stepOpen[number] ? number : <Lock size={14} />}</span>
                  <span className="rp-jf-step-text"><strong>{label}</strong><small>{hint}</small></span>
                </button>
              </li>
            ))}
          </ol>
        </nav>

        <div className="rp-jf-shell">
          <div className="rp-jf-side">
            {activeStep === 1 && <div className="rp-tool-panel rp-jf-manuscript">
              <div className="rp-tool-panel-head">
                <div><span className="rp-tool-kicker">Step 1</span><h2>Your manuscript</h2></div>
                <span className="rp-tool-panel-icon" aria-hidden="true"><Brain size={19} /></span>
              </div>
              <p className="rp-tool-muted rp-jf-step-intro">ResRef first detects the fields your manuscript belongs to, then ranks journals by how well they fit. You can filter and sort the results without searching again.</p>
              <form className="journal-finder-form rp-tool-form" onSubmit={goToFilters}>
                <label>Manuscript title *<input required name="title" value={form.title} onChange={update} placeholder="Example: Knowledge of first aid among medical students in Syria" /></label>
                <label>Abstract *<textarea required name="abstract" value={form.abstract} onChange={update} placeholder="Paste your full abstract or a detailed summary. More context gives better journal matches." />
                  <small className={`rp-jf-hint${form.abstract && abstractWords < 100 ? ' is-warn' : ''}`}>{abstractWords} words{abstractWords < 100 ? ' · 150 or more words give the best matches' : ''}</small>
                </label>
                <label>Keywords<input name="keywords" value={form.keywords} onChange={update} placeholder="diabetes, public health, screening" /><small className="rp-jf-hint">Separate keywords with commas.</small></label>
                <details className="rp-jf-more" open={Boolean(form.articleType || form.studyDesign || form.targetAudience)}>
                  <summary><ChevronDown size={15} aria-hidden="true" /> Article type, design and audience <small>optional</small></summary>
                  <div className="rp-jf-more-body">
                    <label>Article type<select name="articleType" value={form.articleType} onChange={update}>{articleTypes.map(([value, label]) => <option value={value} key={label}>{label}</option>)}</select></label>
                    <label>Study design<select name="studyDesign" value={form.studyDesign} onChange={update}>{studyDesigns.map(([value, label]) => <option value={value} key={label}>{label}</option>)}</select></label>
                    <label>Target audience<select name="targetAudience" value={form.targetAudience} onChange={update}>{targetAudiences.map(([value, label]) => <option value={value} key={label}>{label}</option>)}</select></label>
                  </div>
                </details>
                <div className="rp-tool-form-actions">
                  <button className="button rp-tool-primary">Next: Filters<ArrowRight size={17} aria-hidden="true" /></button>
                  <button className="button button-outline" type="button" onClick={reset}><RotateCcw size={16} aria-hidden="true" /> Clear</button>
                </div>
              </form>
            </div>}

            {activeStep === 2 && <div className={`rp-tool-panel rp-jf-filters${filtersOpen ? ' is-open' : ''}`}>
              <div className="rp-tool-panel-head">
                <div><span className="rp-tool-kicker">Step 2</span><h2>Filters</h2></div>
                <div className="rp-jf-filter-tools">
                  <span className={`rp-jf-count${activeFilterCount ? ' is-active' : ''}`}>{activeFilterCount} active</span>
                  <button type="button" className="rp-tool-mini-button" onClick={resetFilters} disabled={!activeFilterCount && form.sortBy === filterDefaults.sortBy}><RotateCcw size={13} aria-hidden="true" /> Clear</button>
                </div>
              </div>
              <button type="button" className="rp-jf-filter-toggle" aria-expanded={filtersOpen} aria-controls="journal-filter-body" onClick={() => setFiltersOpen(open => !open)}>
                <SlidersHorizontal size={16} aria-hidden="true" />
                <span>{filtersOpen ? 'Hide filters' : `Show filters${activeFilterCount ? ` (${activeFilterCount})` : ''}`}</span>
                <ChevronDown size={16} aria-hidden="true" />
              </button>
              <div className="rp-jf-filter-body" id="journal-filter-body">
                <p className="rp-tool-muted rp-jf-filter-note">Filters update the results straight away. No new search is needed.</p>
                <div className="rp-tool-form rp-jf-filter-grid">
                  <label>Field<select name="category" value={form.category} onChange={update}>
                    <option value="">Any field</option>
                    {detectedNames.length > 0 && <optgroup label="Detected in your manuscript">{detectedNames.map(category => <option value={category} key={category}>{category}</option>)}</optgroup>}
                    <optgroup label={detectedNames.length ? 'All fields' : 'Fields'}>{otherCategories.map(category => <option value={category} key={category}>{category}</option>)}</optgroup>
                  </select></label>
                  <div className="rp-jf-quartiles" role="group" aria-label="Quartile"><span>Quartile <small>(Q1 = top 25% of its field)</small></span><div>{['Q1', 'Q2', 'Q3', 'Q4'].map(quartile => <button type="button" aria-pressed={form.quartile.split(',').includes(quartile)} className={form.quartile.split(',').includes(quartile) ? 'active' : ''} onClick={() => setQuartile(quartile)} key={quartile}>{quartile}</button>)}</div></div>
                  <div className="rp-tool-form-row">
                    <label>Access<select name="openAccess" value={form.openAccess} onChange={update}><option value="">Any</option><option value="open">Open access only</option><option value="subscription">Subscription only</option></select></label>
                    <label>Diamond OA<select name="diamond" value={form.diamond} onChange={update}><option value="">Any</option><option value="diamond">Diamond only</option><option value="non-diamond">Exclude diamond</option></select></label>
                  </div>
                  <label>Publication fee (APC)<select name="apcBudget" value={form.apcBudget} onChange={update}><option value="">Any fee</option><option value="free">No publication fee</option><option value="known">Fee listed</option><option value="under1000">Under $1,000</option><option value="under2500">Under $2,500</option><option value="under5000">Under $5,000</option></select><small className="rp-jf-hint">Other currencies are converted to US dollars approximately.</small></label>
                  <label>Publisher<select name="publisher" value={form.publisher} onChange={update}><option value="">Any publisher</option>{publishers.map(publisher => <option value={publisher} key={publisher}>{publisher}</option>)}</select></label>
                  <div className="rp-tool-form-row"><label>Min H-index<input type="number" min="0" inputMode="numeric" name="minHIndex" value={form.minHIndex} onChange={update} /></label><label>Max H-index<input type="number" min="0" inputMode="numeric" name="maxHIndex" value={form.maxHIndex} onChange={update} /></label></div>
                  <label>Max weeks (decision or publication)<input type="number" min="1" inputMode="numeric" name="maxReviewWeeks" value={form.maxReviewWeeks} onChange={update} /><small className="rp-jf-hint">Uses the time to first decision, or the time to publication when only that is listed. Journals with neither are hidden.</small></label>
                </div>
                <details className="rp-jf-rules">
                  <summary><Info size={14} aria-hidden="true" /> How results are ranked</summary>
                  <p>Journals are scored on how well their subject areas and titles match your manuscript. The match percentage is relative to the best match for your manuscript.</p>
                  <p><b>Priority publishers:</b> the best-fitting journals from {PUBLISHER_PRIORITY_ORDER.join(', ')} are listed first, up to three from each.</p>
                  <p><b>Case reports:</b> case-report journals come first when the article type or text describes a case report.</p>
                </details>
                <div className="rp-tool-form-actions rp-jf-step-actions">
                  <button type="button" className="button button-outline" onClick={() => setStep(1)}><ArrowLeft size={16} aria-hidden="true" /> Back</button>
                  {resultsReady
                    ? <button type="button" className="button rp-tool-primary" onClick={() => setStep(3)}>See {filteredResults.length.toLocaleString()} {filteredResults.length === 1 ? 'match' : 'matches'}<ArrowRight size={17} aria-hidden="true" /></button>
                    : <button type="button" className="button rp-tool-primary" disabled={status === 'loading' || status === 'searching'} onClick={runSearch}><Search size={17} aria-hidden="true" />{status === 'loading' ? 'Loading journals...' : status === 'searching' ? 'Finding journals...' : 'Find journals'}</button>}
                </div>
              </div>
            </div>}
          </div>

          <div className="rp-jf-main">
            {activeStep === 3 && <>
            {detectedCategories.length > 0 && status !== 'searching' && (
              <div className="rp-tool-panel">
                <div className="rp-jf-categories">
                  <div className="rp-tool-subhead"><div><span className="rp-tool-kicker">Detected fields</span><h3>What your manuscript is about</h3></div><Gauge size={18} aria-hidden="true" /></div>
                  <p className="rp-tool-muted rp-jf-categories-hint">Select a field to see only journals in it.</p>
                  {detectedCategories.slice(0, 6).map((item, index) => {
                    const selected = form.category === item[0];
                    return (
                      <button type="button" className={`rp-jf-meter${selected ? ' is-selected' : ''}`} key={item[0]} aria-pressed={selected} onClick={() => setField('category', selected ? '' : item[0])}>
                        <span><strong>{item[0]}</strong><em>{categoryPercent(detectedCategories, index)}%</em></span>
                        <i aria-hidden="true"><b style={{ width: `${categoryPercent(detectedCategories, index)}%` }} /></i>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            <div className="rp-tool-panel rp-jf-results journal-results">
              <div className="rp-tool-toolbar">
                <div>
                  <span className="rp-tool-kicker">Step 3 · Matches</span>
                  <h3>{results.length
                    ? (filteredResults.length ? `${filteredResults.length.toLocaleString()}${results.length >= MAX_RAW_MATCHES && filteredResults.length === results.length ? '+' : ''} matching journals` : 'No journals match these filters')
                    : status === 'searching' ? 'Finding journals...' : 'No matching journals'}</h3>
                  {results.length > 0 && <small className="rp-jf-subcount">
                    {filteredResults.length !== results.length ? `${(results.length - filteredResults.length).toLocaleString()} hidden by filters · ` : ''}
                    {form.sortBy === 'best' ? 'Best fit first; priority publishers are listed at the top' : `Sorted by ${SORT_OPTIONS.find(([value]) => value === form.sortBy)?.[1].toLowerCase()}`}
                  </small>}
                </div>
                <div className="rp-tool-toolbar-actions">
                  <label className="rp-jf-sort"><span>Sort</span><select name="sortBy" value={form.sortBy} onChange={update} disabled={!results.length}>{SORT_OPTIONS.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
                  <label className="rp-tool-search"><Search size={15} aria-hidden="true" /><span className="rh-visually-hidden">Search within results</span><input name="resultSearch" value={form.resultSearch} onChange={update} placeholder="Search within results" disabled={!results.length} /></label>
                  <button type="button" className="button button-outline" disabled={!filteredResults.length} onClick={() => downloadCsv(filteredResults)}><Download size={15} aria-hidden="true" /> Export CSV</button>
                </div>
              </div>

              {filterChips.length > 0 && (
                <div className="rp-jf-chips" aria-label="Active filters">
                  {filterChips.map(([name, label]) => <button type="button" key={name} onClick={() => setField(name, '')} aria-label={`Remove filter: ${label}`}>{label}<X size={13} aria-hidden="true" /></button>)}
                  <button type="button" className="rp-jf-chips-clear" onClick={resetFilters}>Clear all</button>
                </div>
              )}

              {status === 'ready' && results.length === 0 && <div className="rp-tool-empty"><span className="rp-tool-empty-icon" aria-hidden="true"><Sparkles size={26} /></span><strong>No journals matched this manuscript</strong><p>Go back to step 1 and add more detail to your title, abstract or keywords.</p></div>}
              {status === 'searching' && <div className="rp-tool-empty is-loading"><span className="rp-tool-empty-icon" aria-hidden="true"><Search size={26} /></span><strong>Finding journals...</strong><p>Scoring subject fit across the whole journal list.</p></div>}
              {status !== 'searching' && results.length > 0 && filteredResults.length === 0 && <div className="rp-tool-empty"><span className="rp-tool-empty-icon" aria-hidden="true"><Filter size={26} /></span><strong>No journals passed every filter</strong><p>Remove a filter above to see more journals.</p><button type="button" className="button button-outline" onClick={resetFilters}>Clear all filters</button></div>}

              {status !== 'searching' && (
                <ol className="rp-jf-result-list">
                  {visibleResults.map((row, index) => {
                    const { journal } = row;
                    const favorite = favoriteKeys.has(journalKey(journal));
                    const link = journalLink(journal);
                    const matched = new Set(row.matched || []);
                    const orderedCategories = [...(journal.categories || [])].sort((a, b) => Number(matched.has(b)) - Number(matched.has(a))).slice(0, 5);
                    return <li className="rp-jf-result" key={`${journal.issn}-${journal.title}`} style={{ '--rp-score': `${row.score}%` }}>
                      <div className="rp-jf-rank" title="Match relative to the best journal for your manuscript"><span>#{index + 1}</span><strong>{row.score}%</strong><small>{fitLabel(row.score)}</small><i aria-hidden="true"><b /></i></div>
                      <div className="rp-jf-result-body">
                        <div className="rp-jf-result-title">
                          <div>
                            <h3>{journal.title}</h3>
                            <p><span>{journal.publisher || 'Publisher not listed'}</span>{journal.issn && <span className="rp-jf-issn">ISSN {formatIssn(journal.issn)}</span>}</p>
                          </div>
                          <button type="button" className={favorite ? 'rp-jf-favorite active' : 'rp-jf-favorite'} onClick={() => toggleFavorite(journal)} aria-label={favorite ? `Remove ${journal.title} from shortlist` : `Add ${journal.title} to shortlist`} aria-pressed={favorite} title={favorite ? 'Remove from shortlist' : 'Add to shortlist'}>{favorite ? <BookmarkCheck size={18} /> : <Bookmark size={18} />}</button>
                        </div>
                        <dl className="rp-jf-facts">
                          <div className="is-strong"><dt>Quartile</dt><dd>{quartileLabel(journal)}</dd></div>
                          <div><dt>H-index</dt><dd>{journal.h_index || 'N/A'}</dd></div>
                          <div className={journal.is_oa ? 'is-open' : ''}><dt>Access</dt><dd>{journal.is_diamond ? 'Diamond OA' : journal.is_oa ? 'Open access' : 'Subscription'}</dd></div>
                          <div title={apcTitle(journal) || undefined}><dt>Fee</dt><dd>{apcLabel(journal)}</dd></div>
                          <div title={journal.peer_review || undefined}><dt>Speed</dt><dd>{reviewLabel(journal)}</dd>{journal.peer_review && <small>{journal.peer_review}</small>}</div>
                        </dl>
                        <div className="rp-jf-cats">{orderedCategories.map(category => <span key={category} className={matched.has(category) ? 'is-match' : ''}>{category}</span>)}</div>
                        {row.reasons.length > 0 && <div className="rp-jf-reasons">{row.reasons.map(reason => <small key={reason}><CheckCircle2 size={13} aria-hidden="true" /> {reason}</small>)}</div>}
                      </div>
                      {(link || journal.guidelines_url) && <div className="rp-jf-links">
                        {link && <a className="rp-jf-link" href={link.url} target="_blank" rel="noreferrer">{link.label} <ExternalLink size={14} aria-hidden="true" /></a>}
                        {/^https?:\/\//i.test(journal.guidelines_url || '') && <a className="rp-jf-link is-secondary" href={journal.guidelines_url} target="_blank" rel="noreferrer">Author guidelines <ExternalLink size={14} aria-hidden="true" /></a>}
                      </div>}
                    </li>;
                  })}
                </ol>
              )}
              {status !== 'searching' && filteredResults.length > visibleResults.length && (
                <div className="rp-jf-more-results">
                  <span>Showing {visibleResults.length} of {filteredResults.length.toLocaleString()}</span>
                  <button type="button" className="button button-outline" onClick={showMore}>Show {Math.min(PAGE_SIZE, filteredResults.length - visibleResults.length)} more</button>
                </div>
              )}
            </div>
            </>}

            <div className="rp-tool-panel rp-jf-workspace">
              <div className="rp-tool-panel-head">
                <div><span className="rp-tool-kicker">Workspace</span><h2>Shortlist &amp; compare</h2></div>
                <div className="rp-jf-filter-tools">
                  {workspace.favorites.length > 0 && <button type="button" className="rp-tool-mini-button" onClick={() => downloadCsv(workspace.favorites.map(journal => ({ journal })), 'resref-journal-shortlist.csv')}><Download size={13} aria-hidden="true" /> Export</button>}
                  {workspace.favorites.length > 0 && <button type="button" className="rp-tool-mini-button" onClick={clearShortlist}>Clear</button>}
                  <span className="rp-tool-panel-icon" aria-hidden="true"><Star size={18} /></span>
                </div>
              </div>
              {!workspace.favorites.length && <p className="rp-tool-muted">No saved journals yet. Use the bookmark button on a result to compare journals side by side here.</p>}
              {workspace.favorites.length > 0 && (
                <div className="rp-jf-compare" role="region" aria-label="Shortlist comparison" tabIndex={0}>
                  <table>
                    <thead><tr><th scope="col">Journal</th><th scope="col">Quartile</th><th scope="col">H-index</th><th scope="col">Access</th><th scope="col">Fee</th><th scope="col">Speed</th><th scope="col"><span className="rh-visually-hidden">Actions</span></th></tr></thead>
                    <tbody>
                      {workspace.favorites.map(journal => {
                        const link = journalLink(journal);
                        return <tr key={journalKey(journal)}>
                          <th scope="row"><strong>{journal.title}</strong><span>{journal.publisher || 'Publisher not listed'}</span></th>
                          <td>{quartileLabel(journal)}</td>
                          <td>{journal.h_index || 'N/A'}</td>
                          <td>{journal.is_diamond ? 'Diamond OA' : journal.is_oa ? 'Open access' : 'Subscription'}</td>
                          <td title={apcTitle(journal) || undefined}>{apcLabel(journal)}</td>
                          <td>{reviewLabel(journal).replace(' to decision', ' (decision)').replace(' to publication', ' (publication)')}</td>
                          <td><span className="rp-jf-row-actions">
                            {link && <a href={link.url} target="_blank" rel="noreferrer" aria-label={`${link.label}: ${journal.title}`} title={link.label}><ExternalLink size={14} /></a>}
                            <button type="button" className="rp-jf-remove" onClick={() => toggleFavorite(journal)} aria-label={`Remove ${journal.title} from shortlist`} title="Remove"><X size={14} /></button>
                          </span></td>
                        </tr>;
                      })}
                    </tbody>
                  </table>
                </div>
              )}
              <div className="rp-jf-list">
                <div className="rp-jf-list-head"><strong><RotateCcw size={15} aria-hidden="true" /> Recent searches</strong></div>
                {!workspace.searches.length && <p className="rp-tool-muted">Your searches will appear here{account ? ' and sync to your account' : ''}.</p>}
                {workspace.searches.slice(0, 6).map(search => <div className="rp-jf-saved is-search" key={search.id}><button type="button" onClick={() => restoreSearch(search)}><strong>{search.title}</strong><span>{search.categories?.slice(0, 2).join(', ') || 'No fields detected'} · {search.resultCount} matches</span></button><button type="button" className="rp-jf-remove" onClick={() => removeSavedSearch(search.id)} aria-label={`Remove search: ${search.title}`}><X size={14} /></button></div>)}
              </div>
            </div>
          </div>
        </div>
      </div>
      <ToolGuide path="/tools/journal-finder" />
    </section>
  );
}
