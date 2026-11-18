// Journal Finder constants and pure helpers (moved out of JournalFinderPage, T-20).
import { categories_data } from '../../data/journalFinder/Category_to_keyword.js';
// `?url` makes Vite emit the journal list as a content-hashed static file
// (e.g. /static/assets/journals_db-<hash>.json) instead of bundling it, so it
// is downloaded only on the Journal Finder route and can be cached by the
// browser; WhiteNoise serves it compressed.
import journalsDatabaseUrl from '../../data/journalFinder/journals_db.json?url';
import * as journalMatchingLogic from '../../data/journalFinder/matching_logic.js';

export const TOOL_KEY = 'journal-finder';
export const STORAGE_KEY = 'resref_journal_finder_workspace_v2';
export const MAX_RAW_MATCHES = 1500;
export const PUBLISHER_PRIORITY_ORDER = ['BMC', 'BMJ', 'SAGE', 'Wiley', 'Elsevier', 'Oxford', 'Cambridge', 'Wolters Kluwer'];
export const PUBLISHER_PRIORITY_LIMIT = 3;
export const PUBLISHER_PRIORITY_MIN_SCORE_RATIO = 0.2;

export const emptyForm = {
  title: '',
  abstract: '',
  keywords: '',
  articleType: '',
  studyDesign: '',
  targetAudience: '',
  category: '',
  publisher: '',
  quartile: '',
  openAccess: '',
  diamond: '',
  apcBudget: '',
  maxReviewWeeks: '',
  minHIndex: '',
  maxHIndex: '',
  resultSearch: '',
  sortBy: 'best',
  maxResults: '30',
};

export const filterDefaults = {
  category: '',
  publisher: '',
  quartile: '',
  openAccess: '',
  diamond: '',
  apcBudget: '',
  maxReviewWeeks: '',
  minHIndex: '',
  maxHIndex: '',
  resultSearch: '',
  sortBy: 'best',
  maxResults: '30',
};

export const articleTypes = [
  ['', 'Any article type'],
  ['original research', 'Original research'],
  ['systematic review meta analysis', 'Systematic review / meta-analysis'],
  ['scoping review evidence map', 'Scoping review'],
  ['case report clinical case', 'Case report'],
  ['clinical trial randomized trial', 'Clinical trial'],
  ['protocol pilot feasibility', 'Protocol / pilot study'],
  ['short communication brief report', 'Short communication'],
];

export const studyDesigns = [
  ['', 'Any study design'],
  ['cross sectional survey prevalence', 'Cross-sectional / survey'],
  ['cohort prospective retrospective', 'Cohort study'],
  ['case control odds ratio', 'Case-control study'],
  ['randomized trial intervention', 'Interventional trial'],
  ['qualitative interview focus group', 'Qualitative research'],
  ['diagnostic accuracy sensitivity specificity', 'Diagnostic accuracy'],
  ['machine learning prediction model artificial intelligence', 'AI / prediction model'],
  ['laboratory molecular experimental', 'Laboratory / experimental'],
];

export const targetAudiences = [
  ['', 'Any audience'],
  ['clinical medicine hospital patient care', 'Clinical medicine'],
  ['public health epidemiology policy population', 'Public health'],
  ['medical students education curriculum training', 'Medical education'],
  ['nursing care quality patient safety', 'Nursing / care quality'],
  ['basic science molecular cellular genetics', 'Basic science'],
  ['surgery procedure perioperative trauma', 'Surgery / procedures'],
];

export const syncLabels = {
  local: 'Local only',
  loading: 'Connecting',
  syncing: 'Saving',
  synced: 'Synced',
  error: 'Sync paused',
};

export function makeId() {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 9)}`;
}

export function safeExternalUrl(url) {
  return /^https?:\/\//i.test(url || '') ? url : '';
}

export function normalizeWorkspace(workspace = {}) {
  return {
    favorites: Array.isArray(workspace.favorites) ? workspace.favorites.slice(0, 80) : [],
    searches: Array.isArray(workspace.searches) ? workspace.searches.slice(0, 12) : [],
    lastForm: { ...emptyForm, ...(workspace.lastForm || {}) },
  };
}

export function loadWorkspace() {
  try {
    return normalizeWorkspace(JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}'));
  } catch {
    return normalizeWorkspace();
  }
}

export function saveWorkspace(workspace) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(normalizeWorkspace(workspace)));
}

export function workspaceHasContent(workspace) {
  return Boolean(workspace?.favorites?.length || workspace?.searches?.length || workspace?.lastForm?.title || workspace?.lastForm?.abstract);
}

export function cleanText(value) {
  return String(value || '').toLowerCase().replace(/[^a-z0-9\s]+/g, ' ').replace(/\s+/g, ' ').trim();
}

export function normalizePublisherName(publisher) {
  const normalized = cleanText(publisher);
  if (!normalized) return 'Other';
  if (normalized.includes('biomed central') || normalized.includes('bmc')) return 'BMC';
  if (normalized.includes('bmj')) return 'BMJ';
  if (normalized.includes('sage')) return 'SAGE';
  if (normalized.includes('wiley')) return 'Wiley';
  if (normalized.includes('elsevier') || normalized.includes('saunders') || normalized.includes('cell press')) return 'Elsevier';
  if (normalized.includes('oxford')) return 'Oxford';
  if (normalized.includes('cambridge')) return 'Cambridge';
  if (normalized.includes('wolters') || normalized.includes('lippincott')) return 'Wolters Kluwer';
  return 'Other';
}

export function isCaseReportRequest(form) {
  const normalized = cleanText(`${form.articleType} ${form.title} ${form.abstract} ${form.keywords}`);
  if (normalized.includes('case control') && !normalized.includes('case report')) return false;
  return normalized.includes('case report')
    || normalized.includes('case reports')
    || normalized.includes('clinical case')
    || normalized.includes('case series');
}

export function isCaseReportJournal(journal) {
  const normalized = cleanText(`${journal.title} ${journal.publisher} ${(journal.categories || []).join(' ')}`);
  return normalized.includes('case report')
    || normalized.includes('case reports')
    || normalized.includes('case studies')
    || normalized.includes('medical cases')
    || normalized.includes('case lessons');
}

export function parseNumber(value) {
  if (value === '' || value === null || value === undefined) return null;
  const match = String(value).replace(/,/g, '').match(/\d+(\.\d+)?/);
  if (!match) return null;
  const number = Number(match[0]);
  return Number.isFinite(number) ? number : null;
}

export function parseApcValue(value) {
  const text = String(value || '').toLowerCase();
  if (!text || text === 'n/a') return null;
  if (text.includes('free')) return 0;
  const values = [...text.matchAll(/\d+(?:,\d{3})*(?:\.\d+)?/g)].map(match => Number(match[0].replace(/,/g, ''))).filter(Number.isFinite);
  return values.length ? Math.min(...values) : null;
}

// Approximate USD value of one unit of each currency listed in the dataset.
// Used only to place fees into budget bands and to sort by cost.
const USD_PER_UNIT = {
  USD: 1, EUR: 1.1, GBP: 1.3, CHF: 1.15, AUD: 0.65, CAD: 0.72, SEK: 0.095, PLN: 0.26, CZK: 0.044, RON: 0.22,
  RSD: 0.0094, BAM: 0.56, UAH: 0.024, JPY: 0.0068, KRW: 0.00072, CNY: 0.14, INR: 0.0115, PKR: 0.0036,
  IDR: 0.000061, IRR: 0.000024, IQD: 0.00076, EGP: 0.02, NGN: 0.00065, ZAR: 0.055, BRL: 0.18,
};

function apcAmounts(journal) {
  return [...String(journal.APC || '').matchAll(/(\d+(?:[.,]\d+)*)\s*([A-Z]{3})/g)]
    .map(match => ({ amount: Number(match[1].replace(/,/g, '')), currency: match[2] }))
    .filter(item => Number.isFinite(item.amount));
}

// Publication fee in approximate US dollars: 0 when the journal charges
// nothing, null when the fee is not listed.
export function apcUsd(journal) {
  const text = String(journal.APC || '').trim().toLowerCase();
  if (text === 'free') return 0;
  const amounts = apcAmounts(journal);
  if (!amounts.length) return journal.is_diamond ? 0 : null;
  const usd = amounts.find(item => item.currency === 'USD');
  if (usd) return usd.amount;
  const known = amounts.find(item => USD_PER_UNIT[item.currency]);
  return known ? Math.round(known.amount * USD_PER_UNIT[known.currency]) : null;
}

export function isRanked(journal) {
  return /^Q[1-4]$/.test(String(journal.quartile || ''));
}

export function quartileLabel(journal) {
  return isRanked(journal) ? journal.quartile : 'Unranked';
}

export function apcLabel(journal) {
  const text = String(journal.APC || '').trim();
  if (text.toLowerCase() === 'free') return journal.is_oa ? 'No publication fee' : 'No fee (subscription)';
  const amounts = apcAmounts(journal);
  if (!amounts.length) return journal.is_diamond ? 'No publication fee' : 'Fee not listed';
  const first = amounts.find(item => item.currency === 'USD') || amounts[0];
  return `${first.amount.toLocaleString('en-US')} ${first.currency}`;
}

export function apcTitle(journal) {
  return apcAmounts(journal).length > 1 ? `Publication fee: ${String(journal.APC).trim()}` : '';
}

// Weeks to first decision when listed; otherwise DOAJ's weeks from
// submission to publication. Null when neither is known.
export function speedWeeks(journal) {
  const review = parseNumber(journal.review_period);
  if (review !== null) return review;
  const publication = Number(journal.publication_weeks);
  return Number.isFinite(publication) && publication > 0 ? publication : null;
}

export function reviewLabel(journal) {
  const review = parseNumber(journal.review_period);
  if (review !== null) return `~${review} weeks to decision`;
  const publication = speedWeeks(journal);
  return publication === null ? 'Time not listed' : `~${publication} weeks to publication`;
}

export function formatIssn(issn) {
  const value = String(issn || '').replace(/[^0-9Xx]/g, '').toUpperCase();
  return value.length === 8 ? `${value.slice(0, 4)}-${value.slice(4)}` : String(issn || '');
}

// Most journal links in the dataset are a web search for the title; only some
// are the journal's own site, so the button says which one it is.
export function journalLink(journal) {
  const url = safeExternalUrl(journal.url);
  if (!url) return null;
  const isSearch = /^https?:\/\/(www\.)?google\.[a-z.]+\/search/i.test(url);
  return { url, label: isSearch ? 'Search online' : 'Journal website', isSearch };
}

export function formatSyncTime(date) {
  if (!date) return 'Ready when you are';
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

export function journalKey(journal) {
  return `${journal.issn || ''}-${journal.title || ''}`.toLowerCase();
}

export function journalSnapshot(journal) {
  return {
    title: journal.title || '',
    issn: journal.issn || '',
    publisher: journal.publisher || '',
    quartile: journal.quartile || '',
    h_index: journal.h_index || '',
    is_oa: Boolean(journal.is_oa),
    is_diamond: Boolean(journal.is_diamond),
    APC: journal.APC || '',
    review_period: journal.review_period || '',
    url: journal.url || '',
    guidelines_url: journal.guidelines_url || '',
    publication_weeks: journal.publication_weeks || '',
    peer_review: journal.peer_review || '',
    categories: Array.isArray(journal.categories) ? journal.categories.slice(0, 8) : [],
  };
}

export function categoryPercent(categories, index) {
  if (!categories.length) return 0;
  const highest = Math.max(categories[0]?.[1] || 1, 1);
  return Math.max(8, Math.round(((categories[index]?.[1] || 0) / highest) * 100));
}

export function buildMatchOptions(form) {
  return {
    abstract: form.abstract,
    keywords: [
      ...form.keywords.split(',').map(keyword => keyword.trim()).filter(Boolean),
      form.articleType,
      form.studyDesign,
      form.targetAudience,
    ].filter(Boolean),
    articleType: form.articleType,
    studyDesign: form.studyDesign,
    targetAudience: form.targetAudience,
    // Publisher, quartile, access and H-index are applied in the browser by
    // passesExpandedFilters, so changing them updates results without a new
    // search. Empty values here also override the engine's DOM fallback.
    publisher: '',
    quartile: '',
    openAccess: null,
    minHIndex: '',
    maxResults: MAX_RAW_MATCHES,
  };
}

export function passesExpandedFilters(journal, form) {
  if (form.publisher && journal.publisher !== form.publisher) return false;
  const quartiles = String(form.quartile || '').split(',').filter(Boolean);
  if (quartiles.length && !quartiles.includes(String(journal.quartile || '').toUpperCase())) return false;
  if (form.openAccess === 'open' && !journal.is_oa) return false;
  if (form.openAccess === 'subscription' && journal.is_oa) return false;
  const minHIndex = parseNumber(form.minHIndex);
  if (minHIndex !== null && (Number(journal.h_index) || 0) < minHIndex) return false;
  const maxHIndex = parseNumber(form.maxHIndex);
  if (maxHIndex !== null && (Number(journal.h_index) || 0) > maxHIndex) return false;
  if (form.category && !(journal.categories || []).includes(form.category)) return false;
  if (form.diamond === 'diamond' && !journal.is_diamond) return false;
  if (form.diamond === 'non-diamond' && journal.is_diamond) return false;

  const apc = apcUsd(journal);
  if (form.apcBudget === 'free' && apc !== 0) return false;
  if (form.apcBudget === 'known' && apc === null) return false;
  if (form.apcBudget === 'under1000' && (apc === null || apc > 1000)) return false;
  if (form.apcBudget === 'under2500' && (apc === null || apc > 2500)) return false;
  if (form.apcBudget === 'under5000' && (apc === null || apc > 5000)) return false;

  const maxReviewWeeks = parseNumber(form.maxReviewWeeks);
  const reviewWeeks = speedWeeks(journal);
  if (maxReviewWeeks !== null && (reviewWeeks === null || reviewWeeks > maxReviewWeeks)) return false;

  const query = cleanText(form.resultSearch);
  if (query) {
    const haystack = cleanText(`${journal.title} ${journal.publisher} ${(journal.categories || []).join(' ')} ${journal.issn}`);
    if (!haystack.includes(query)) return false;
  }

  return true;
}

export function compareMatchQuality(a, b, form, caseReportRequested) {
  const apcA = apcUsd(a.journal);
  const apcB = apcUsd(b.journal);
  const reviewA = speedWeeks(a.journal) ?? 999;
  const reviewB = speedWeeks(b.journal) ?? 999;
  const hA = Number(a.journal.h_index) || 0;
  const hB = Number(b.journal.h_index) || 0;
  const caseDelta = caseReportRequested ? Number(isCaseReportJournal(b.journal)) - Number(isCaseReportJournal(a.journal)) : 0;
  if (caseDelta !== 0) return caseDelta;

  if (form.sortBy === 'impact') return hB - hA || b.rawScore - a.rawScore;
  if (form.sortBy === 'fast') return reviewA - reviewB || b.rawScore - a.rawScore;
  if (form.sortBy === 'open') return Number(b.journal.is_oa) - Number(a.journal.is_oa) || b.rawScore - a.rawScore;
  if (form.sortBy === 'affordable') return (apcA ?? 999999) - (apcB ?? 999999) || b.rawScore - a.rawScore;
  if (form.sortBy === 'balanced') {
    const balanceA = a.score + Math.min(hA / 8, 18) + (a.journal.is_oa ? 4 : 0) - Math.min(reviewA / 6, 8);
    const balanceB = b.score + Math.min(hB / 8, 18) + (b.journal.is_oa ? 4 : 0) - Math.min(reviewB / 6, 8);
    return balanceB - balanceA;
  }
  return b.rawScore - a.rawScore;
}

export function sortMatches(matches, form) {
  const caseReportRequested = isCaseReportRequest(form);
  const qualitySorted = [...matches].sort((a, b) => compareMatchQuality(a, b, form, caseReportRequested));
  // Priority publishers are listed first only for the default "Best subject match" order;
  // any other sort the user picks is applied as it says.
  if (form.sortBy && form.sortBy !== 'best') return qualitySorted;
  const highestScore = qualitySorted.reduce((max, row) => Math.max(max, row.rawScore), 0);
  const priorityScoreCutoff = highestScore * PUBLISHER_PRIORITY_MIN_SCORE_RATIO;
  const pickedIndexes = new Set();
  const prioritized = [];

  for (const publisher of PUBLISHER_PRIORITY_ORDER) {
    let pickedForPublisher = 0;

    for (let index = 0; index < qualitySorted.length && pickedForPublisher < PUBLISHER_PRIORITY_LIMIT; index += 1) {
      if (pickedIndexes.has(index)) continue;
      if (qualitySorted[index].rawScore < priorityScoreCutoff) continue;
      if (normalizePublisherName(qualitySorted[index].journal.publisher) !== publisher) continue;

      prioritized.push({ ...qualitySorted[index], priority: true });
      pickedIndexes.add(index);
      pickedForPublisher += 1;
    }
  }

  return [
    ...prioritized,
    ...qualitySorted.filter((_, index) => !pickedIndexes.has(index)),
  ];
}

let journalsRequest = null;

function fetchJournalDatabase() {
  // One request per page session; a failed request is forgotten so that a
  // retry (or revisiting the route) tries again.
  if (!journalsRequest) {
    journalsRequest = fetch(journalsDatabaseUrl, { credentials: 'same-origin' })
      .then(response => {
        if (!response.ok) throw new Error(`Journal database request failed (${response.status})`);
        return response.json();
      })
      .then(journals => {
        if (!Array.isArray(journals)) throw new Error('Journal database has an unexpected format');
        journalMatchingLogic.setJournalDatabase(journals);
        return journals;
      })
      .catch(error => {
        journalsRequest = null;
        throw error;
      });
  }
  return journalsRequest;
}

export async function loadJournalFinderModules() {
  const journals_data = await fetchJournalDatabase();
  return {
    categoriesModule: { categories_data },
    database: { journals_data },
    logic: journalMatchingLogic,
    release: () => {},
  };
}

export function matchedCategories(journal, topCategories) {
  const categoryNames = new Set(topCategories.slice(0, 8).map(([category]) => category));
  return (journal.categories || []).filter(category => categoryNames.has(category));
}

// Why a journal fits, in plain words. Facts shown elsewhere on the card
// (quartile, H-index, access) are not repeated here.
export function explainMatch(journal, topCategories) {
  const direct = matchedCategories(journal, topCategories);
  const reasons = [];
  if (isCaseReportJournal(journal)) reasons.push('Publishes case reports');
  if (direct.length) reasons.push(`Covers your field: ${direct.slice(0, 3).join(', ')}`);
  const review = parseNumber(journal.review_period);
  if (review !== null && review <= 8) reasons.push(`Fast first decision (~${review} weeks)`);
  else if (review === null && speedWeeks(journal) !== null && speedWeeks(journal) <= 8) reasons.push(`Fast publication (~${speedWeeks(journal)} weeks)`);
  if (apcUsd(journal) === 0 && journal.is_oa) reasons.push('Open access with no publication fee');
  return reasons.slice(0, 3);
}

export function toCsv(rows) {
  const headers = ['Rank', 'Match', 'Title', 'Publisher', 'ISSN', 'Quartile', 'H-index', 'Open Access', 'Diamond', 'APC', 'Review Period (weeks)', 'Weeks to Publication', 'Peer Review', 'URL', 'Author Guidelines', 'Categories'];
  const escape = value => `"${String(value ?? '').replace(/"/g, '""')}"`;
  return [
    headers.map(escape).join(','),
    ...rows.map((row, index) => [
      index + 1,
      row.score === undefined ? '' : `${row.score}%`,
      row.journal.title,
      row.journal.publisher,
      formatIssn(row.journal.issn),
      quartileLabel(row.journal),
      row.journal.h_index,
      row.journal.is_oa ? 'Yes' : 'No',
      row.journal.is_diamond ? 'Yes' : 'No',
      row.journal.APC,
      row.journal.review_period,
      row.journal.publication_weeks,
      row.journal.peer_review,
      row.journal.url,
      row.journal.guidelines_url,
      (row.journal.categories || []).join('; '),
    ].map(escape).join(',')),
  ].join('\n');
}

export function downloadCsv(rows, filename = 'resref-journal-finder-results.csv') {
  const blob = new Blob(['\ufeff', toCsv(rows)], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
