const STORAGE_KEY = 'resref_reference_workspace_v6';
const LEGACY_STORAGE_KEY = 'resref_simple_lists_v5';

export const makeId = () => `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 9)}`;
export const makeList = (name = 'References', references = []) => ({ id: makeId(), name, references: references.map(normalizeReference) });

const TEXT_FIELDS = ['source', 'type', 'title', 'journal', 'journal_abbrev', 'publisher', 'site', 'booktitle', 'editors', 'org', 'number', 'edition', 'year', 'volume', 'issue', 'pages', 'doi', 'pmid', 'isbn', 'url', 'accessed'];

const cleanAuthor = author => ({
  first: String(author?.first || '').trim(),
  middle: String(author?.middle || '').trim(),
  last: String(author?.last || '').trim(),
});

export function normalizeReference(reference = {}) {
  return {
    id: reference.id || makeId(),
    source: reference.source || 'manual',
    type: reference.type || 'journal',
    title: reference.title || '',
    journal: reference.journal || '',
    journal_abbrev: reference.journal_abbrev || '',
    publisher: reference.publisher || '',
    site: reference.site || '',
    booktitle: reference.booktitle || '',
    editors: reference.editors || '',
    org: reference.org || '',
    number: reference.number || '',
    edition: reference.edition || '',
    year: String(reference.year || ''),
    volume: reference.volume || '',
    issue: reference.issue || '',
    pages: reference.pages || '',
    doi: cleanDoi(reference.doi),
    pmid: String(reference.pmid || '').trim(),
    isbn: String(reference.isbn || '').trim(),
    url: reference.url || '',
    accessed: reference.accessed || '',
    authors: Array.isArray(reference.authors) ? reference.authors.map(cleanAuthor).filter(author => author.last || author.first) : [],
  };
}

export function emptyWorkspace() {
  const list = makeList();
  return { lists: [list], activeListId: list.id, style: 'vancouver' };
}

function migrateLegacy(legacy) {
  const lists = (legacy.lists || []).map(list => makeList(list.name, (list.items || []).map(item => item.raw || item)));
  return lists.length ? { lists, activeListId: lists[legacy.active || 0]?.id || lists[0].id, style: legacy.style || 'vancouver' } : emptyWorkspace();
}

export function loadWorkspace() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
    if (saved?.lists?.length) return normalizeWorkspace(saved);
    const legacy = JSON.parse(localStorage.getItem(LEGACY_STORAGE_KEY) || 'null');
    if (legacy?.lists?.length) return migrateLegacy(legacy);
  } catch {
    return emptyWorkspace();
  }
  return emptyWorkspace();
}

export function normalizeWorkspace(workspace) {
  if (!workspace || !Array.isArray(workspace.lists) || !workspace.lists.length) return emptyWorkspace();
  const lists = workspace.lists.map(list => ({
    id: typeof list.id === 'string' && list.id ? list.id : makeId(),
    name: String(list.name || 'References').slice(0, 120),
    references: Array.isArray(list.references) ? list.references.map(normalizeReference) : [],
  }));
  const activeListId = lists.some(list => list.id === workspace.activeListId) ? workspace.activeListId : lists[0].id;
  return { lists, activeListId, style: typeof workspace.style === 'string' && workspace.style ? workspace.style : 'vancouver' };
}

export function workspaceHasContent(workspace) {
  return Array.isArray(workspace?.lists) && workspace.lists.some(list => Array.isArray(list.references) && list.references.length);
}

// Empty fields are left out of the stored copy (normalizeReference restores
// them on load), which lets larger libraries fit the account storage limit.
export function compactWorkspace(workspace) {
  return {
    ...workspace,
    lists: (workspace.lists || []).map(list => ({
      ...list,
      references: (list.references || []).map(reference => {
        const compact = { id: reference.id };
        TEXT_FIELDS.forEach(field => { if (reference[field]) compact[field] = reference[field]; });
        if (reference.authors?.length) {
          compact.authors = reference.authors.map(author => {
            const entry = { last: author.last };
            if (author.first) entry.first = author.first;
            if (author.middle) entry.middle = author.middle;
            return entry;
          });
        }
        return compact;
      }),
    })),
  };
}

export function saveWorkspace(workspace) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(compactWorkspace(workspace)));
  } catch {
    // Storage full or blocked: the in-memory copy (and account sync) still work.
  }
}

// Duplicates ----------------------------------------------------------------

export function cleanDoi(value) {
  return String(value || '').trim().replace(/^https?:\/\/(?:dx\.)?doi\.org\//i, '').replace(/^doi:\s*/i, '').replace(/[.,;]+$/, '');
}

const normalTitle = value => String(value || '').toLowerCase().normalize('NFKD').replace(/[̀-ͯ]/g, '').replace(/<[^>]+>/g, '').replace(/[^a-z0-9]+/g, ' ').trim();
const normalUrl = value => String(value || '').trim().toLowerCase().replace(/^https?:\/\/(www\.)?/, '').replace(/[?#].*$/, '').replace(/\/+$/, '');

// Keys that identify the same work: DOI, PMID, ISBN, link, or title + year.
export function duplicateKeys(reference) {
  const keys = [];
  const doi = cleanDoi(reference.doi).toLowerCase();
  if (doi) keys.push(`doi:${doi}`);
  if (String(reference.pmid || '').trim()) keys.push(`pmid:${String(reference.pmid).trim()}`);
  const isbn = String(reference.isbn || '').replace(/[^0-9xX]/g, '');
  if (isbn.length >= 10 && reference.type === 'book') keys.push(`isbn:${isbn}`);
  const url = normalUrl(reference.url);
  if (url && !/^doi\.org\//.test(url)) keys.push(`url:${url}`);
  const title = normalTitle(reference.title);
  if (title.length >= 12) keys.push(`title:${title}|${String(reference.year || '').slice(0, 4)}`);
  return keys;
}

// Kept for older callers: one key per reference.
export function referenceFingerprint(reference) {
  return duplicateKeys(reference)[0] || String(reference.id || '').toLowerCase();
}

export function findDuplicate(reference, references) {
  const keys = new Set(duplicateKeys(reference));
  if (!keys.size) return null;
  return references.find(item => item.id !== reference.id && duplicateKeys(item).some(key => keys.has(key))) || null;
}

// Groups of references in one list that look like the same work.
export function duplicateGroups(references) {
  const parent = references.map((_, index) => index);
  const find = index => (parent[index] === index ? index : (parent[index] = find(parent[index])));
  const seen = new Map();
  references.forEach((reference, index) => {
    duplicateKeys(reference).forEach(key => {
      if (seen.has(key)) parent[find(index)] = find(seen.get(key));
      else seen.set(key, index);
    });
  });
  const groups = new Map();
  references.forEach((reference, index) => {
    const root = find(index);
    if (!groups.has(root)) groups.set(root, []);
    groups.get(root).push(reference);
  });
  return [...groups.values()].filter(group => group.length > 1);
}

const filledCount = reference => TEXT_FIELDS.filter(field => !['source', 'type'].includes(field) && reference[field]).length + (reference.authors?.length ? 2 : 0);

// Merge into the most complete record; empty fields are filled from the
// others and nothing that is already filled is overwritten.
export function mergeReferences(group) {
  const [primary, ...rest] = [...group].sort((a, b) => filledCount(b) - filledCount(a));
  const merged = { ...primary };
  rest.forEach(other => {
    TEXT_FIELDS.forEach(field => { if (!merged[field] && other[field]) merged[field] = other[field]; });
    if (!merged.authors?.length && other.authors?.length) merged.authors = other.authors;
  });
  return normalizeReference(merged);
}

// Fill only the empty fields of a reference from looked-up metadata.
export function fillMissing(reference, found) {
  const next = { ...reference };
  const filled = [];
  TEXT_FIELDS.filter(field => !['source', 'type'].includes(field)).forEach(field => {
    if (!String(next[field] || '').trim() && String(found[field] || '').trim()) {
      next[field] = found[field];
      filled.push(field);
    }
  });
  if (!next.authors?.length && found.authors?.length) {
    next.authors = found.authors;
    filled.push('authors');
  }
  return { reference: normalizeReference(next), filled };
}
