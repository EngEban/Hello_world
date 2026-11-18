import { useEffect, useMemo, useRef, useState } from 'react';
import ToolGuide from '../../components/public/ToolGuide';
import { Link } from 'react-router-dom';
import {
  Activity,
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  ChevronDown,
  Clipboard,
  Cloud,
  CloudOff,
  Copy,
  Download,
  Edit3,
  ExternalLink,
  FilePlus2,
  FolderInput,
  GripVertical,
  ListPlus,
  Lock,
  Search,
  ShieldCheck,
  Sparkles,
  Trash2,
  Undo2,
  Upload,
  UserRound,
  Wand2,
  X,
} from 'lucide-react';
import useToolWorkspace from '../../hooks/useToolWorkspace';
import { PublicWebsiteApi } from '../../api/publicWebsiteApi';
import useToolUsage from '../../hooks/useToolUsage';
import { useAccount } from '../../contexts/AccountContext';
import {
  CITATION_STYLES,
  FIELDS_BY_TYPE,
  NUMERIC_STYLES,
  SOURCE_TYPES,
  authorsToText,
  bibliographyEntries,
  citationHtml,
  createBlankReference,
  formatCitation,
  formatInText,
  parseAuthors,
  referenceWarnings,
  validateReference,
} from '../../features/referenceGenerator/citationStyles';
import { downloadText, parseReferenceFile, toBibTeX, toCslJson, toRIS } from '../../features/referenceGenerator/referenceFiles';
import {
  compactWorkspace,
  duplicateGroups,
  fillMissing,
  findDuplicate,
  loadWorkspace,
  makeList,
  mergeReferences,
  normalizeReference,
  normalizeWorkspace,
  saveWorkspace,
  workspaceHasContent,
} from '../../features/referenceGenerator/referenceStorage';
import '../../styles/tools/tool-workspace.css';
import { trackEvent } from '../../utils/analytics';

const REFERENCE_TOOL_KEY = 'reference-generator';
const SYNC_LABELS = {
  local: 'Local only',
  loading: 'Connecting',
  syncing: 'Saving',
  synced: 'Synced',
  error: 'Sync paused',
};
const FIELD_LABELS = { title: 'title', journal: 'journal', journal_abbrev: 'journal abbreviation', publisher: 'publisher', booktitle: 'book title', editors: 'editors', org: 'organization', site: 'website', year: 'year', volume: 'volume', issue: 'issue', pages: 'pages', doi: 'DOI', pmid: 'PMID', isbn: 'ISBN', url: 'link', edition: 'edition', number: 'report number', accessed: 'date accessed', authors: 'authors' };

const move = (items, from, to) => {
  const next = [...items];
  const [item] = next.splice(from, 1);
  next.splice(to, 0, item);
  return next;
};

const safeExternalUrl = url => /^https?:\/\//i.test(url || '') ? url : '';
const hasText = value => String(value || '').trim().length > 0;
const completeField = (reference, field) => field === 'authors_text' ? Boolean(reference.authors?.length) : hasText(reference[field]);
const today = () => {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
};
const normalTitle = value => String(value || '').toLowerCase().normalize('NFKD').replace(/[̀-ͯ]/g, '').replace(/<[^>]+>/g, '').replace(/[^a-z0-9]+/g, ' ').trim();
const slugify = name => name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'references';
const sourceLabel = source => ({ crossref: 'Crossref', openalex: 'OpenAlex', pubmed: 'PubMed', openlibrary: 'Open Library', 'doi.org': 'DOI', 'manual-url': 'Link', manual: 'Added by hand' }[source] || source || 'Added by hand');

function referenceQuality(reference) {
  if (!reference) return 0;
  const fields = FIELDS_BY_TYPE[reference.type] || FIELDS_BY_TYPE.journal;
  const required = fields.filter(([, , isRequired]) => isRequired).map(([field]) => field);
  const optional = fields.filter(([, , isRequired]) => !isRequired).map(([field]) => field);
  const requiredScore = required.length ? required.filter(field => completeField(reference, field)).length / required.length : 1;
  const optionalScore = optional.length ? optional.filter(field => completeField(reference, field)).length / optional.length : 0.8;
  return Math.max(5, Math.round(((requiredScore * 0.78) + (optionalScore * 0.22)) * 100));
}

function qualityClass(score) {
  if (score >= 85) return 'good';
  if (score >= 60) return 'warning';
  return 'danger';
}

function formatSyncTime(date) {
  if (!date) return 'Ready when you are';
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

// The best identifier to look a reference up again.
function lookupQuery(reference) {
  if (reference.doi) return reference.doi;
  if (reference.pmid) return `PMID: ${reference.pmid}`;
  if (reference.isbn) return `ISBN ${reference.isbn}`;
  return reference.title;
}

export default function ReferenceGeneratorPage() {
  const { account, loading: accountLoading } = useAccount();
  const [workspace, setWorkspace] = useState(loadWorkspace);
  const [query, setQuery] = useState('');
  const [sourceType, setSourceType] = useState('');
  const [filter, setFilter] = useState('');
  const [onlyIssues, setOnlyIssues] = useState(false);
  const [selectedId, setSelectedId] = useState('');
  const [checked, setChecked] = useState(() => new Set());
  const [lookupResults, setLookupResults] = useState([]);
  const [editor, setEditor] = useState(null);
  const [editingId, setEditingId] = useState('');
  const [notice, setNotice] = useState(null);
  const [undo, setUndo] = useState(null);
  const [loading, setLoading] = useState(false);
  const [filling, setFilling] = useState(false);
  const [duplicates, setDuplicates] = useState(null);
  const [listForm, setListForm] = useState(null);
  const toolUsage = useToolUsage('reference_generator', account?.email || '');
  const [actionsOpen, setActionsOpen] = useState(false);
  const [moveOpen, setMoveOpen] = useState(false);
  const [dragListIndex, setDragListIndex] = useState(null);
  const [dragReferenceIndex, setDragReferenceIndex] = useState(null);
  const fileInput = useRef(null);
  const menuRef = useRef(null);

  const { syncStatus, syncError, lastSynced } = useToolWorkspace({
    toolKey: REFERENCE_TOOL_KEY,
    account,
    accountLoading,
    workspace,
    setWorkspace,
    normalize: normalizeWorkspace,
    serialize: compactWorkspace,
    hasContent: workspaceHasContent,
    persistLocal: saveWorkspace,
    adoptEmptyRemote: true,
    markSyncingImmediately: true,
  });
  const activeList = workspace.lists.find(list => list.id === workspace.activeListId) || workspace.lists[0];
  const style = workspace.style;
  const numericStyle = NUMERIC_STYLES.includes(style);
  const styleLabel = CITATION_STYLES.find(([value]) => value === style)?.[1] || 'Selected style';

  // Checks for every reference, computed once per change of the library.
  const checks = useMemo(() => {
    const map = new Map();
    workspace.lists.forEach(list => list.references.forEach(reference => {
      const missing = validateReference(reference);
      const warnings = referenceWarnings(reference);
      map.set(reference.id, { missing, warnings, quality: referenceQuality(reference), needsWork: missing.length > 0 || warnings.length > 0 });
    }));
    return map;
  }, [workspace.lists]);
  const listHtml = useMemo(() => new Map(activeList.references.map(reference => [reference.id, citationHtml(reference, style)])), [activeList.references, style]);

  const totalReferences = workspace.lists.reduce((total, list) => total + list.references.length, 0);
  const listIssues = activeList.references.filter(reference => checks.get(reference.id)?.needsWork).length;
  const readyReferences = [...checks.values()].filter(check => !check.missing.length).length;
  const selected = activeList.references.find(reference => reference.id === selectedId);
  const selectedIndex = activeList.references.findIndex(reference => reference.id === selectedId);
  const selectedCheck = selected ? checks.get(selected.id) : null;
  const selectedDuplicate = selected ? findDuplicate(selected, activeList.references) : null;
  const shownReferences = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    return activeList.references.filter(reference => {
      if (onlyIssues && !checks.get(reference.id)?.needsWork) return false;
      if (!needle) return true;
      const text = `${reference.title} ${reference.journal} ${reference.booktitle} ${reference.site} ${reference.publisher} ${reference.year} ${reference.doi} ${reference.pmid} ${reference.url} ${authorsToText(reference.authors)}`.toLowerCase();
      return text.includes(needle);
    });
  }, [activeList.references, filter, onlyIssues, checks]);
  const checkedInList = activeList.references.filter(reference => checked.has(reference.id));
  const allShownChecked = shownReferences.length > 0 && shownReferences.every(reference => checked.has(reference.id));

  useEffect(() => {
    if (!editor && !lookupResults.length && !duplicates && !actionsOpen && !moveOpen) return undefined;
    const onKey = event => {
      if (event.key !== 'Escape') return;
      if (editor) setEditor(null);
      else if (duplicates) setDuplicates(null);
      else if (lookupResults.length) setLookupResults([]);
      setActionsOpen(false);
      setMoveOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [editor, lookupResults.length, duplicates, actionsOpen, moveOpen]);

  // Close the Actions menu when clicking elsewhere.
  useEffect(() => {
    if (!actionsOpen && !moveOpen) return undefined;
    const onClick = event => {
      if (menuRef.current && !menuRef.current.contains(event.target)) setActionsOpen(false);
      if (!event.target.closest?.('.rp-rg-move')) setMoveOpen(false);
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, [actionsOpen, moveOpen]);

  useEffect(() => {
    if (selectedId && !activeList.references.some(reference => reference.id === selectedId)) setSelectedId('');
  }, [activeList.references, selectedId]);

  useEffect(() => {
    if (!undo) return undefined;
    const timeout = window.setTimeout(() => setUndo(null), 12000);
    return () => window.clearTimeout(timeout);
  }, [undo]);

  const updateActiveList = update => setWorkspace(current => ({
    ...current,
    lists: current.lists.map(list => list.id === current.activeListId ? update(list) : list),
  }));

  const showNotice = (message, type = 'success') => setNotice({ message, type });

  const copyText = async (text, message, html = '') => {
    if (!text) return showNotice('There is nothing to copy yet.', 'error');
    try {
      // Rich copy keeps italics when pasting into Word or Google Docs.
      if (html && window.ClipboardItem && navigator.clipboard?.write) {
        await navigator.clipboard.write([new window.ClipboardItem({
          'text/html': new Blob([html], { type: 'text/html' }),
          'text/plain': new Blob([text], { type: 'text/plain' }),
        })]);
      } else {
        await navigator.clipboard.writeText(text);
      }
    } catch {
      const area = document.createElement('textarea');
      area.value = text;
      document.body.appendChild(area);
      area.select();
      document.execCommand('copy');
      area.remove();
    }
    showNotice(message);
  };

  const selectList = id => {
    setWorkspace(current => ({ ...current, activeListId: id }));
    setSelectedId('');
    setChecked(new Set());
    setOnlyIssues(false);
  };

  // Adds references to the active list, skipping ones already in it.
  const addReferences = rawReferences => {
    const existing = [...activeList.references];
    const added = [];
    let skipped = 0;
    rawReferences.forEach(raw => {
      const reference = normalizeReference({ ...raw, id: undefined, accessed: raw.accessed || (raw.type === 'website' ? today() : '') });
      if (findDuplicate(reference, existing)) { skipped += 1; return; }
      existing.push(reference);
      added.push(reference);
    });
    if (added.length) {
      updateActiveList(list => ({ ...list, references: [...list.references, ...added] }));
      setSelectedId(added.at(-1).id);
    }
    return { added, skipped };
  };

  const addReference = raw => {
    const { added } = addReferences([raw]);
    if (!added.length) return showNotice('That reference is already in this list.', 'warning');
    const missing = validateReference(added[0]);
    showNotice(missing.length ? `Reference added. Still missing: ${missing.join(', ').toLowerCase()}.` : 'Reference added to your list.', missing.length ? 'warning' : 'success');
    return added[0];
  };

  const addAllResults = () => {
    const { added, skipped } = addReferences(lookupResults);
    setLookupResults([]);
    showNotice(`${added.length} reference${added.length === 1 ? '' : 's'} added${skipped ? `; ${skipped} already in the list` : ''}.`, added.length ? 'success' : 'warning');
  };

  const search = async event => {
    event.preventDefault();
    if (!query.trim()) return showNotice('Paste a DOI, PubMed ID, ISBN, link or title first.', 'error');
    setLoading(true);
    setNotice(null);
    try {
      const data = await PublicWebsiteApi.searchReferences(query, sourceType);
      trackEvent('tool_use', { tool_name: 'reference_generator' });
      if (data.usage) toolUsage.setUsage(data.usage);
      const results = data.results || [];
      // One exact identifier: add it straight away.
      const lines = query.trim().split(/\n/).filter(line => line.trim());
      if (results.length === 1 && lines.length === 1 && results[0].source !== 'manual-url' && results[0].source !== 'openalex' && /^(10\.\d|doi:|https?:\/\/(dx\.)?doi\.org\/|https?:\/\/pubmed\.|pmid|isbn|\d[\d\- ]{4,16}[\dXx]$)/i.test(lines[0].trim())) {
        if (addReference(results[0])) setQuery('');
      } else {
        setLookupResults(results);
      }
    } catch (error) {
      if (error.data?.usage) toolUsage.setUsage(error.data.usage);
      showNotice(error.status === 404 ? 'Nothing was found. Check the DOI, PubMed ID or ISBN, try the exact title, or add the reference by hand.' : error.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  const fillSelected = async () => {
    if (!selected) return;
    setFilling(true);
    try {
      const data = await PublicWebsiteApi.searchReferences(lookupQuery(selected), '');
      if (data.usage) toolUsage.setUsage(data.usage);
      const results = data.results || [];
      const byIdentifier = Boolean(selected.doi || selected.pmid || selected.isbn);
      const sameTitle = item => normalTitle(item.title) === normalTitle(selected.title);
      // Without an identifier, only a result with the same title is used, so
      // details of a different paper are never copied in.
      const match = results.find(item => selected.doi && item.doi && item.doi.toLowerCase() === selected.doi.toLowerCase())
        || (byIdentifier ? results[0] : results.find(sameTitle));
      if (!match) return showNotice(byIdentifier ? 'No details were found for this reference.' : 'No source with exactly this title was found, so nothing was changed. Add a DOI or PubMed ID and try again.', 'warning');
      const { reference, filled } = fillMissing(selected, match);
      if (!filled.length) return showNotice('Nothing new was found. All available details are already filled in.', 'success');
      updateActiveList(list => ({ ...list, references: list.references.map(item => item.id === selected.id ? { ...reference, id: selected.id } : item) }));
      showNotice(`Filled in: ${filled.map(field => FIELD_LABELS[field] || field).join(', ')}. Existing details were not changed.`);
    } catch (error) {
      if (error.data?.usage) toolUsage.setUsage(error.data.usage);
      showNotice(error.status === 404 ? 'No details were found for this reference.' : error.message, 'error');
    } finally {
      setFilling(false);
    }
  };

  const submitListForm = event => {
    event.preventDefault();
    const name = listForm.name.trim().slice(0, 120);
    if (!name) return;
    if (listForm.mode === 'rename') updateActiveList(list => ({ ...list, name }));
    else {
      const list = makeList(name);
      setWorkspace(current => ({ ...current, lists: [...current.lists, list], activeListId: list.id }));
      setSelectedId('');
      setChecked(new Set());
    }
    setListForm(null);
  };

  const deleteList = () => {
    if (workspace.lists.length === 1) return showNotice('You need at least one list. Rename this one or delete its references instead.', 'error');
    if (activeList.references.length && !window.confirm(`Delete the list "${activeList.name}" and its ${activeList.references.length} references? You can undo this for a few seconds.`)) return;
    const index = workspace.lists.findIndex(list => list.id === activeList.id);
    const removed = activeList;
    setWorkspace(current => {
      const lists = current.lists.filter(list => list.id !== current.activeListId);
      return { ...current, lists, activeListId: lists[Math.max(0, index - 1)].id };
    });
    setSelectedId('');
    setChecked(new Set());
    setUndo({
      message: `List "${removed.name}" deleted.`,
      restore: () => setWorkspace(current => {
        const lists = [...current.lists];
        lists.splice(index, 0, removed);
        return { ...current, lists, activeListId: removed.id };
      }),
    });
  };

  // Removes references and offers an undo that puts them back where they were.
  const removeReferences = ids => {
    const listId = activeList.id;
    const removed = activeList.references.map((reference, index) => ({ reference, index })).filter(entry => ids.has(entry.reference.id));
    if (!removed.length) return;
    updateActiveList(list => ({ ...list, references: list.references.filter(item => !ids.has(item.id)) }));
    setChecked(current => new Set([...current].filter(id => !ids.has(id))));
    setUndo({
      message: removed.length === 1 ? `Deleted "${removed[0].reference.title || 'reference'}".` : `${removed.length} references deleted.`,
      restore: () => setWorkspace(current => ({
        ...current,
        lists: current.lists.map(list => {
          if (list.id !== listId) return list;
          const references = [...list.references];
          removed.forEach(({ reference, index }) => references.splice(Math.min(index, references.length), 0, reference));
          return { ...list, references };
        }),
      })),
    });
  };

  const moveChecked = (targetId, keepCopy) => {
    const target = workspace.lists.find(list => list.id === targetId);
    if (!target || !checkedInList.length) return;
    const incoming = [];
    let skipped = 0;
    checkedInList.forEach(reference => {
      if (findDuplicate(reference, [...target.references, ...incoming])) skipped += 1;
      else incoming.push(keepCopy ? { ...reference, id: normalizeReference({}).id } : reference);
    });
    const movedIds = new Set(checkedInList.map(reference => reference.id));
    setWorkspace(current => ({
      ...current,
      lists: current.lists.map(list => {
        if (list.id === targetId) return { ...list, references: [...list.references, ...incoming] };
        if (list.id === current.activeListId && !keepCopy) return { ...list, references: list.references.filter(item => !movedIds.has(item.id)) };
        return list;
      }),
    }));
    setChecked(new Set());
    setMoveOpen(false);
    showNotice(`${incoming.length} reference${incoming.length === 1 ? '' : 's'} ${keepCopy ? 'copied' : 'moved'} to "${target.name}"${skipped ? `; ${skipped} ${keepCopy ? 'were' : 'stayed here because they were'} already there` : ''}.`);
  };

  const toggleChecked = id => setChecked(current => {
    const next = new Set(current);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    return next;
  });

  const toggleAllShown = () => setChecked(current => {
    const next = new Set(current);
    shownReferences.forEach(reference => (allShownChecked ? next.delete(reference.id) : next.add(reference.id)));
    return next;
  });

  const openEditor = (reference = createBlankReference(sourceType || 'journal')) => {
    setEditingId(reference.id || '');
    setEditor({ ...reference, accessed: reference.accessed || (reference.type === 'website' && !reference.id ? today() : ''), authors_text: authorsToText(reference.authors) });
  };

  // Changing the source type keeps everything already typed.
  const changeEditorType = type => setEditor(current => ({ ...createBlankReference(type), ...current, type, accessed: current.accessed || (type === 'website' ? today() : '') }));

  const editorReference = editor ? normalizeReference({ ...editor, authors: parseAuthors(editor.authors_text) }) : null;
  const editorMissing = editorReference ? validateReference(editorReference) : [];
  const editorWarnings = editorReference ? referenceWarnings(editorReference) : [];

  const saveEditor = event => {
    event.preventDefault();
    const reference = editorReference;
    if (editorMissing.length) return showNotice(`Complete the required fields: ${editorMissing.join(', ').toLowerCase()}.`, 'error');
    if (editingId) {
      updateActiveList(list => ({ ...list, references: list.references.map(item => item.id === editingId ? { ...reference, id: editingId } : item) }));
      setSelectedId(editingId);
      showNotice('Reference updated.');
    } else if (!addReference(reference)) {
      return;
    }
    setEditor(null);
    setEditingId('');
  };

  const bibliography = (references = activeList.references) => bibliographyEntries(references, style);
  const copyBibliography = (references = activeList.references) => {
    const entries = bibliography(references);
    setActionsOpen(false);
    return copyText(entries.map(entry => entry.text).join('\n'), `${entries.length} formatted reference${entries.length === 1 ? '' : 's'} copied in ${styleLabel}.`, entries.map(entry => `<p>${entry.html}</p>`).join(''));
  };

  const exportReferences = (type, references = activeList.references) => {
    if (!references.length) return showNotice('Add a reference before exporting.', 'error');
    const slug = slugify(activeList.name);
    if (type === 'bib') downloadText(`${slug}.bib`, references.map(toBibTeX).join('\n\n'), 'application/x-bibtex');
    if (type === 'ris') downloadText(`${slug}.ris`, references.map(toRIS).join('\n'), 'application/x-research-info-systems');
    if (type === 'json') downloadText(`${slug}.json`, toCslJson(references), 'application/json');
    if (type === 'txt') downloadText(`${slug}.txt`, bibliography(references).map(entry => entry.text).join('\n'));
    if (type === 'html') downloadText(`${slug}.html`, `<!doctype html><meta charset="utf-8"><title>${activeList.name}</title><body style="font-family:Georgia,serif;line-height:1.6">${bibliography(references).map(entry => `<p style="padding-left:2em;text-indent:-2em">${entry.html}</p>`).join('')}</body>`, 'text/html');
    setActionsOpen(false);
  };

  const importFile = async event => {
    const file = event.target.files?.[0];
    event.target.value = '';
    setActionsOpen(false);
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) return showNotice('That file is larger than 5 MB. Split it into smaller files and import them one at a time.', 'error');
    let parsed = [];
    try {
      parsed = parseReferenceFile(file.name, await file.text());
    } catch {
      parsed = [];
    }
    if (!parsed.length) return showNotice('No references were found in that file. Supported formats: BibTeX (.bib), RIS (.ris), PubMed (.nbib) and CSL JSON (.json).', 'error');
    const unique = [];
    parsed.map(normalizeReference).forEach(reference => { if (!findDuplicate(reference, unique)) unique.push(reference); });
    const skipped = parsed.length - unique.length;
    const list = makeList(file.name.replace(/\.[^.]+$/, '').slice(0, 120) || 'Imported references', unique);
    setWorkspace(current => ({ ...current, lists: [...current.lists, list], activeListId: list.id }));
    setSelectedId('');
    setChecked(new Set());
    const incomplete = unique.filter(reference => validateReference(reference).length).length;
    showNotice(`${unique.length} references imported into the new list "${list.name}".${skipped ? ` ${skipped} duplicate${skipped === 1 ? ' in the file was' : 's in the file were'} skipped.` : ''}${incomplete ? ` ${incomplete} ${incomplete === 1 ? 'needs' : 'need'} more details; select "Needs attention" to review ${incomplete === 1 ? 'it' : 'them'}.` : ''}`, incomplete ? 'warning' : 'success');
  };

  const openDuplicates = () => {
    setActionsOpen(false);
    const groups = duplicateGroups(activeList.references);
    if (!groups.length) return showNotice('No duplicates found in this list.');
    setDuplicates(groups);
  };

  const mergeGroup = group => {
    const merged = mergeReferences(group);
    const ids = new Set(group.map(reference => reference.id));
    const before = activeList.references;
    updateActiveList(list => {
      const firstIndex = list.references.findIndex(reference => ids.has(reference.id));
      const rest = list.references.filter(reference => !ids.has(reference.id));
      rest.splice(firstIndex, 0, merged);
      return { ...list, references: rest };
    });
    const listId = activeList.id;
    setDuplicates(current => {
      const next = (current || []).filter(item => item !== group);
      return next.length ? next : null;
    });
    setSelectedId(merged.id);
    setUndo({ message: `${group.length} copies merged into one reference.`, restore: () => setWorkspace(current => ({ ...current, lists: current.lists.map(list => list.id === listId ? { ...list, references: before } : list) })) });
  };

  const SyncIcon = account ? (syncStatus === 'error' ? CloudOff : Cloud) : Lock;
  const syncDescription = accountLoading
    ? 'Checking your ResRef account...'
    : account
      ? syncStatus === 'synced'
        ? `Last saved ${formatSyncTime(lastSynced)}`
        : syncStatus === 'syncing'
          ? 'Saving your latest changes'
          : syncStatus === 'loading'
            ? 'Loading your saved workspace'
            : syncError || 'Your local copy is still available'
      : 'Sign in once, then all ResRef tools can share the same authenticated workspace.';
  const otherLists = workspace.lists.filter(list => list.id !== activeList.id);

  return <>
    <section className="rp-tool rp-tool--reference citation-section" aria-labelledby="reference-generator-title">
      <div className="rp-tool-container">
        <header className="rp-tool-header">
          <div className="rp-tool-header-main">
            <span className="rp-tool-badge" aria-hidden="true"><BookOpen size={30} strokeWidth={1.6} /></span>
            <div className="rp-tool-heading">
              <span className="rh-label rh-label-light">Citation Workspace</span>
              <h1 id="reference-generator-title">Reference Generator</h1>
              <p>Add references by DOI, PubMed ID, ISBN, link or title, keep them in lists, and copy a ready bibliography in your journal's style. Work as a guest, or sign in to keep your lists on every device.</p>
              <ul className="rp-tool-header-chips" aria-label="Workspace features">
                <li><CheckCircle2 size={14} aria-hidden="true" />DOI, PMID, ISBN, link or title</li>
                <li><CheckCircle2 size={14} aria-hidden="true" />{CITATION_STYLES.length} citation styles</li>
                <li><CheckCircle2 size={14} aria-hidden="true" />BibTeX, RIS, PubMed and CSL JSON</li>
              </ul>
            </div>
          </div>
          <div className={`rp-tool-sync is-${account ? syncStatus : 'guest'}`}>
            <div className="rp-tool-sync-top">
              <span className="rp-tool-sync-icon" aria-hidden="true"><SyncIcon size={18} /></span>
              <div className="rp-tool-sync-copy">
                <span className="rp-tool-sync-state">{account ? SYNC_LABELS[syncStatus] : 'Guest workspace'}</span>
                <strong>{account ? (account.display_name || account.email) : 'Local browser storage'}</strong>
              </div>
            </div>
            <p>{syncDescription}</p>
            {account ? <Link className="rp-tool-sync-link" to="/account"><UserRound size={15} aria-hidden="true" /> Account</Link> : <Link className="rp-tool-sync-link is-primary" to="/sign-in?next=/tools/reference-generator"><Cloud size={15} aria-hidden="true" /> Sign in to sync</Link>}
          </div>
        </header>

        <div className="rp-tool-stats" aria-label="Reference workspace summary">
          <div className="rp-tool-stat citation-command-card"><span className="rp-tool-stat-icon" aria-hidden="true"><Activity size={19} /></span><span className="rp-tool-stat-label">References</span><strong>{totalReferences}</strong><small>{workspace.lists.length} list{workspace.lists.length === 1 ? '' : 's'} in this workspace</small></div>
          <div className="rp-tool-stat citation-command-card"><span className="rp-tool-stat-icon" aria-hidden="true"><ShieldCheck size={19} /></span><span className="rp-tool-stat-label">Complete</span><strong>{readyReferences}</strong><small>{totalReferences ? `of ${totalReferences} have every required detail` : 'Add a reference to begin'}</small></div>
          <button type="button" className={`rp-tool-stat citation-command-card rp-rg-stat-button${onlyIssues ? ' is-active' : ''}`} onClick={() => setOnlyIssues(value => !value)} disabled={!listIssues && !onlyIssues} aria-pressed={onlyIssues}><span className="rp-tool-stat-icon" aria-hidden="true"><AlertTriangle size={19} /></span><span className="rp-tool-stat-label">Needs attention</span><strong>{listIssues}</strong><small>{listIssues ? (onlyIssues ? 'Showing these only. Select to show all.' : 'Select to show them in this list') : 'Nothing to fix in this list'}</small></button>
          <div className="rp-tool-stat citation-command-card"><span className="rp-tool-stat-icon" aria-hidden="true"><Sparkles size={19} /></span><span className="rp-tool-stat-label">Style</span><strong>{styleLabel}</strong><small>{numericStyle ? 'Numbered in list order' : 'Sorted A–Z by author when copied'}</small></div>
        </div>

        {!notice && toolUsage.summary && <p className="rp-tool-notice is-warning tool-usage-summary" role="status">{toolUsage.summary}</p>}
        {notice && <div className={`rp-tool-notice is-${notice.type}`} role={notice.type === 'error' ? 'alert' : 'status'} aria-live="polite">{notice.type === 'success' ? <CheckCircle2 size={17} aria-hidden="true" /> : <AlertTriangle size={17} aria-hidden="true" />}<span>{notice.message}</span><button type="button" onClick={() => setNotice(null)} aria-label="Dismiss message"><X size={16} /></button></div>}

        <div className="rp-rg-shell">
          <aside className="rp-tool-panel rp-rg-lists">
            <div className="rp-tool-panel-head">
              <div><span className="rp-tool-kicker">Library</span><h2>Your Lists</h2></div>
              <button type="button" className="rp-tool-icon-button is-primary" onClick={() => setListForm({ mode: 'create', name: '' })} aria-label="Create list" title="New list"><ListPlus size={17} /></button>
            </div>
            {listForm && <form className="rp-rg-list-form" onSubmit={submitListForm}>
              <label><span className="rh-visually-hidden">{listForm.mode === 'rename' ? 'New list name' : 'List name'}</span><input autoFocus value={listForm.name} maxLength={120} onChange={event => setListForm(current => ({ ...current, name: event.target.value }))} placeholder={listForm.mode === 'rename' ? 'New name' : 'e.g. Thesis chapter 2'} onKeyDown={event => { if (event.key === 'Escape') setListForm(null); }} /></label>
              <button type="submit" className="rp-tool-mini-button is-primary">{listForm.mode === 'rename' ? 'Save' : 'Create'}</button>
              <button type="button" className="rp-tool-mini-button" onClick={() => setListForm(null)}>Cancel</button>
            </form>}
            <div className="rp-rg-list-items">
              {workspace.lists.map((list, index) => <button type="button" draggable key={list.id} className={list.id === activeList.id ? 'rp-rg-list is-active' : 'rp-rg-list'} aria-current={list.id === activeList.id ? 'true' : undefined} onDragStart={() => setDragListIndex(index)} onDragOver={event => event.preventDefault()} onDrop={() => { if (dragListIndex === null || dragListIndex === index) return; const lists = move(workspace.lists, dragListIndex, index); setWorkspace(current => ({ ...current, lists, activeListId: lists[index].id })); setDragListIndex(null); }} onClick={() => selectList(list.id)}>
                <GripVertical size={15} aria-hidden="true" /><span>{list.name}</span><small>{list.references.length}</small>
              </button>)}
            </div>
            <div className="rp-rg-list-actions"><button type="button" className="rp-tool-mini-button" onClick={() => setListForm({ mode: 'rename', name: activeList.name })}><Edit3 size={13} aria-hidden="true" /> Rename</button><button type="button" className="rp-tool-mini-button is-danger" onClick={deleteList}><Trash2 size={13} aria-hidden="true" /> Delete</button></div>
            <p className="rp-tool-muted rp-rg-help">{account ? 'Drag lists to reorder. Changes sync after a short pause.' : 'Drag lists to reorder. Saved in this browser until you sign in.'}</p>
          </aside>

          <div className="rp-tool-panel rp-rg-main">
            <div className="rp-tool-toolbar">
              <div><span className="rp-tool-kicker">Active list</span><h3>{activeList.name}</h3></div>
              <div className="rp-tool-toolbar-actions">
                <span className={`rp-rg-sync-pill is-${account ? syncStatus : 'local'}`}><SyncIcon size={13} aria-hidden="true" />{account ? SYNC_LABELS[syncStatus] : 'Local only'}</span>
                <select className="rp-tool-select" value={style} onChange={event => setWorkspace(current => ({ ...current, style: event.target.value }))} aria-label="Citation style">{CITATION_STYLES.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select>
                <div className="rp-rg-menu" ref={menuRef}>
                  <button type="button" className="button button-outline" aria-expanded={actionsOpen} aria-haspopup="true" onClick={() => setActionsOpen(open => !open)}>Actions <ChevronDown size={15} aria-hidden="true" /></button>
                  {actionsOpen && <div className="rp-rg-menu-dropdown" role="menu">
                    <span className="rp-rg-menu-label">Bibliography</span>
                    <button type="button" role="menuitem" onClick={() => copyBibliography()} disabled={!activeList.references.length}><Clipboard size={15} aria-hidden="true" /> Copy all ({styleLabel})</button>
                    <button type="button" role="menuitem" onClick={() => exportReferences('html')} disabled={!activeList.references.length}><Download size={15} aria-hidden="true" /> Download for Word (.html)</button>
                    <button type="button" role="menuitem" onClick={() => exportReferences('txt')} disabled={!activeList.references.length}><Download size={15} aria-hidden="true" /> Download text (.txt)</button>
                    <span className="rp-rg-menu-label">Reference managers</span>
                    <button type="button" role="menuitem" onClick={() => exportReferences('ris')} disabled={!activeList.references.length}><Download size={15} aria-hidden="true" /> Export RIS (EndNote, Zotero)</button>
                    <button type="button" role="menuitem" onClick={() => exportReferences('bib')} disabled={!activeList.references.length}><Download size={15} aria-hidden="true" /> Export BibTeX (LaTeX)</button>
                    <button type="button" role="menuitem" onClick={() => exportReferences('json')} disabled={!activeList.references.length}><Download size={15} aria-hidden="true" /> Export CSL JSON</button>
                    <button type="button" role="menuitem" onClick={() => fileInput.current?.click()}><Upload size={15} aria-hidden="true" /> Import file (BIB, RIS, NBIB, JSON)</button>
                    <span className="rp-rg-menu-label">Tidy up</span>
                    <button type="button" role="menuitem" onClick={openDuplicates} disabled={activeList.references.length < 2}><Copy size={15} aria-hidden="true" /> Find duplicates</button>
                    <button type="button" role="menuitem" onClick={() => { setActionsOpen(false); setOnlyIssues(true); if (!listIssues) showNotice('Every reference in this list has its required details.'); }} disabled={!activeList.references.length}><CheckCircle2 size={15} aria-hidden="true" /> Show references to fix</button>
                  </div>}
                </div>
                <input ref={fileInput} hidden type="file" accept=".bib,.ris,.nbib,.json,.txt,text/plain,application/json,application/x-bibtex,application/x-research-info-systems" onChange={importFile} />
              </div>
            </div>
            <form className="citation-search rp-rg-search" onSubmit={search}>
              <label className="rp-rg-search-field"><span className="rh-visually-hidden">DOI, PubMed ID, ISBN, link or title</span><Search size={18} aria-hidden="true" /><textarea value={query} onChange={event => setQuery(event.target.value)} onKeyDown={event => { if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) search(event); }} placeholder="Paste a DOI, PubMed ID, ISBN, link or article title. Add up to 5, one per line." rows="2" /></label>
              <div className="rp-rg-search-controls">
                <select className="rp-tool-select" value={sourceType} onChange={event => setSourceType(event.target.value)} aria-label="Source type"><option value="">Any source type</option>{SOURCE_TYPES.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select>
                <button className="button rp-tool-primary" disabled={loading}><Search size={16} aria-hidden="true" /> {loading ? 'Searching...' : 'Find'}</button>
              </div>
            </form>
            <div className="rp-rg-tools">
              <button type="button" className="button button-outline" onClick={() => openEditor()}><FilePlus2 size={16} aria-hidden="true" /> Add by hand</button>
              <label className="rp-tool-search"><Search size={15} aria-hidden="true" /><span className="rh-visually-hidden">Filter references</span><input value={filter} onChange={event => setFilter(event.target.value)} placeholder="Filter by title, author, year, journal or DOI" /></label>
            </div>
            <div className="rp-rg-ref-head">
              <label className="rp-rg-check-all"><input type="checkbox" checked={allShownChecked} onChange={toggleAllShown} disabled={!shownReferences.length} /> <strong>References ({onlyIssues || filter ? `${shownReferences.length} of ${activeList.references.length}` : activeList.references.length})</strong></label>
              {onlyIssues ? <button type="button" className="rp-rg-filter-chip" onClick={() => setOnlyIssues(false)}>Needs attention <X size={13} aria-hidden="true" /></button> : <small>{numericStyle ? 'Drag to change the numbering.' : `${styleLabel} sorts the bibliography by author when you copy or download it.`}</small>}
            </div>
            {checkedInList.length > 0 && <div className="rp-rg-bulk" role="region" aria-label="Selected references">
              <strong>{checkedInList.length} selected</strong>
              <button type="button" className="rp-tool-mini-button" onClick={() => copyBibliography(checkedInList)}><Clipboard size={13} aria-hidden="true" /> Copy</button>
              <button type="button" className="rp-tool-mini-button" onClick={() => exportReferences('ris', checkedInList)}><Download size={13} aria-hidden="true" /> RIS</button>
              <div className="rp-rg-move">
                <button type="button" className="rp-tool-mini-button" onClick={() => setMoveOpen(open => !open)} aria-expanded={moveOpen} disabled={!otherLists.length} title={otherLists.length ? '' : 'Create another list first'}><FolderInput size={13} aria-hidden="true" /> Move or copy</button>
                {moveOpen && <div className="rp-rg-menu-dropdown rp-rg-move-menu" role="menu">
                  {otherLists.map(list => <div className="rp-rg-move-row" key={list.id}><span>{list.name}</span><button type="button" onClick={() => moveChecked(list.id, false)}>Move</button><button type="button" onClick={() => moveChecked(list.id, true)}>Copy</button></div>)}
                </div>}
              </div>
              <button type="button" className="rp-tool-mini-button is-danger" onClick={() => removeReferences(new Set(checkedInList.map(reference => reference.id)))}><Trash2 size={13} aria-hidden="true" /> Delete</button>
              <button type="button" className="rp-rg-bulk-clear" onClick={() => setChecked(new Set())}>Clear selection</button>
            </div>}
            <div className="rp-rg-ref-list">
              {!shownReferences.length && <div className="rp-tool-empty is-compact"><span className="rp-tool-empty-icon" aria-hidden="true">{activeList.references.length ? <Search size={24} /> : <FilePlus2 size={24} />}</span><strong>{activeList.references.length ? 'No matches' : 'No references yet'}</strong><p>{activeList.references.length ? (onlyIssues ? 'Every reference here has its required details.' : 'No references in this list match your filter.') : 'Paste a DOI, PubMed ID, ISBN or title above, import a file from Actions, or add a reference by hand.'}</p></div>}
              {shownReferences.map(reference => {
                const index = activeList.references.findIndex(item => item.id === reference.id);
                const check = checks.get(reference.id) || { quality: 0, missing: [], warnings: [] };
                return <article draggable className={`rp-rg-ref${reference.id === selectedId ? ' is-selected' : ''}${checked.has(reference.id) ? ' is-checked' : ''}`} key={reference.id} onDragStart={() => setDragReferenceIndex(index)} onDragOver={event => event.preventDefault()} onDrop={() => { if (dragReferenceIndex === null || dragReferenceIndex === index) return; updateActiveList(list => ({ ...list, references: move(list.references, dragReferenceIndex, index) })); setDragReferenceIndex(null); }} onClick={() => setSelectedId(reference.id)}>
                  <GripVertical size={16} className="rp-rg-grip" aria-hidden="true" />
                  <input type="checkbox" className="rp-rg-check" checked={checked.has(reference.id)} onChange={() => toggleChecked(reference.id)} onClick={event => event.stopPropagation()} aria-label={`Select ${reference.title || 'reference'}`} />
                  <span className="rp-rg-ref-index">{index + 1}</span>
                  <div className="rp-rg-ref-body">
                    <h4>{reference.title || 'Untitled reference'}</h4>
                    <p dangerouslySetInnerHTML={{ __html: listHtml.get(reference.id) || '' }} />
                    <div className="rp-rg-ref-meta">
                      <small>{SOURCE_TYPES.find(([value]) => value === reference.type)?.[1]} · {sourceLabel(reference.source)}{reference.doi && ` · DOI ${reference.doi}`}</small>
                      {check.missing.length ? <span className="rp-rg-quality is-danger">Missing {check.missing.join(', ').toLowerCase()}</span> : check.warnings.length ? <span className="rp-rg-quality is-warning">{check.warnings.length} to check</span> : <span className="rp-rg-quality is-good">Complete</span>}
                    </div>
                  </div>
                  <div className="rp-rg-row-actions">
                    <button type="button" onClick={event => { event.stopPropagation(); copyText(formatCitation(reference, style), 'Citation copied.', citationHtml(reference, style)); }} aria-label={`Copy citation: ${reference.title || 'reference'}`} title="Copy citation"><Clipboard size={15} /></button>
                    <button type="button" onClick={event => { event.stopPropagation(); openEditor(reference); }} aria-label={`Edit ${reference.title || 'reference'}`} title="Edit"><Edit3 size={15} /></button>
                    <button type="button" className="is-danger" onClick={event => { event.stopPropagation(); removeReferences(new Set([reference.id])); }} aria-label={`Delete ${reference.title || 'reference'}`} title="Delete"><Trash2 size={15} /></button>
                  </div>
                </article>;
              })}
            </div>
          </div>

          <aside className="rp-tool-panel rp-rg-detail">
            {!selected && <div className="rp-tool-empty is-compact"><span className="rp-tool-empty-icon" aria-hidden="true"><BookOpen size={24} /></span><strong>Select a reference</strong><p>Choose an entry to copy its citation, check its details, and fill in anything missing.</p></div>}
            {selected && selectedCheck && <div className="rp-rg-detail-body">
              <div className="rp-tool-panel-head"><div><span className="rp-tool-kicker">{SOURCE_TYPES.find(([value]) => value === selected.type)?.[1]}</span><h2>Citation Tools</h2></div><button type="button" className="rp-tool-icon-button" onClick={() => openEditor(selected)} aria-label="Edit selected reference"><Edit3 size={16} /></button></div>
              <h3 className="rp-rg-detail-title">{selected.title || 'Untitled reference'}</h3>
              <div className="rp-rg-insight">
                <div className={`rp-rg-ring is-${qualityClass(selectedCheck.quality)}`} style={{ '--rp-q': `${selectedCheck.quality}%` }}><span>{selectedCheck.quality}%</span></div>
                <div><strong>{selectedCheck.missing.length ? 'Details missing' : selectedCheck.warnings.length ? 'Worth a check' : 'Ready to cite'}</strong><p>{selectedCheck.missing.length ? `Add the ${selectedCheck.missing.join(', ').toLowerCase()}.` : selectedCheck.warnings.length ? 'Required details are complete. See the notes below.' : 'All required details are filled in.'}</p></div>
              </div>
              {selectedCheck.warnings.length > 0 && <ul className="rp-rg-warnings">{selectedCheck.warnings.map(warning => <li key={warning}><AlertTriangle size={13} aria-hidden="true" /> {warning}</li>)}</ul>}
              {selectedDuplicate && <p className="rp-rg-dup-note"><Copy size={13} aria-hidden="true" /> This looks like a duplicate of “{selectedDuplicate.title || 'another reference'}”. Use Actions, then Find duplicates, to merge them.</p>}
              {(selectedCheck.missing.length > 0 || selectedCheck.warnings.length > 0) && (selected.doi || selected.pmid || selected.isbn || selected.title) && <button type="button" className="button button-outline rp-rg-wide" onClick={fillSelected} disabled={filling}><Wand2 size={16} aria-hidden="true" /> {filling ? 'Looking up details...' : `Fill missing details from ${selected.doi ? 'the DOI' : selected.pmid ? 'PubMed' : selected.isbn ? 'the ISBN' : 'the title'}`}</button>}
              <div className="rp-rg-output"><small>{styleLabel}</small><p dangerouslySetInnerHTML={{ __html: citationHtml(selected, style) }} /></div>
              <button type="button" className="button rp-tool-primary rp-rg-wide" onClick={() => copyText(formatCitation(selected, style), 'Formatted citation copied.', citationHtml(selected, style))}><Clipboard size={16} aria-hidden="true" /> Copy citation</button>
              <div className="rp-rg-output"><small>In-text citation</small><p>{formatInText(selected, style, selectedIndex)}</p></div>
              <button type="button" className="button button-outline rp-rg-wide" onClick={() => copyText(formatInText(selected, style, selectedIndex), 'In-text citation copied.')}><Clipboard size={16} aria-hidden="true" /> Copy in-text</button>
              <dl className="rp-rg-meta-grid">
                <div><dt>Found via</dt><dd>{sourceLabel(selected.source)}</dd></div>
                <div><dt>Year</dt><dd>{selected.year || 'Missing'}</dd></div>
                <div><dt>DOI</dt><dd title={selected.doi}>{selected.doi || 'Not set'}</dd></div>
                <div><dt>{selected.type === 'book' || selected.type === 'chapter' ? 'ISBN' : 'PMID'}</dt><dd>{(selected.type === 'book' || selected.type === 'chapter' ? selected.isbn : selected.pmid) || 'Not set'}</dd></div>
              </dl>
              {safeExternalUrl(selected.url) && <a className="rp-rg-open" href={safeExternalUrl(selected.url)} target="_blank" rel="noopener noreferrer"><ExternalLink size={15} aria-hidden="true" /> Open source</a>}
            </div>}
          </aside>
        </div>
      </div>

    {undo && <div className="rp-rg-undo" role="status" aria-live="polite"><span>{undo.message}</span><button type="button" onClick={() => { undo.restore(); setUndo(null); }}><Undo2 size={15} aria-hidden="true" /> Undo</button><button type="button" className="rp-rg-undo-close" onClick={() => setUndo(null)} aria-label="Dismiss"><X size={15} /></button></div>}

    {lookupResults.length > 0 && <div className="rp-tool-modal-backdrop" role="dialog" aria-modal="true" aria-label="Select search result">
      <div className="rp-tool-modal">
        <div className="rp-tool-modal-head"><div><span className="rp-tool-kicker">{lookupResults.length} result{lookupResults.length === 1 ? '' : 's'}</span><h3>Choose what to add</h3></div><button type="button" className="rp-tool-icon-button" onClick={() => setLookupResults([])} aria-label="Close results"><X size={18} /></button></div>
        <div className="rp-rg-result-list">{lookupResults.map((reference, index) => {
          const inList = Boolean(findDuplicate(normalizeReference({ ...reference, id: `lookup-${index}` }), activeList.references));
          const missing = validateReference(normalizeReference(reference));
          return <article className="rp-rg-result" key={`${reference.doi}-${reference.title}-${index}`}><div><small><span>{sourceLabel(reference.source)}</span><span>{SOURCE_TYPES.find(([value]) => value === reference.type)?.[1] || reference.type}</span>{missing.length ? <span className="rp-rg-quality is-warning">Missing {missing.join(', ').toLowerCase()}</span> : <span className="rp-rg-quality is-good">Complete</span>}</small><h4>{reference.title || 'Untitled result'}</h4><p dangerouslySetInnerHTML={{ __html: citationHtml(reference, style) }} /></div>{inList ? <span className="rp-rg-in-list"><CheckCircle2 size={15} aria-hidden="true" /> In list</span> : <button type="button" className="button rp-tool-primary" onClick={() => addReference(reference)}><ListPlus size={15} aria-hidden="true" /> Add</button>}</article>;
        })}</div>
        <div className="rp-tool-modal-actions">
          <button type="button" className="button button-outline" onClick={() => setLookupResults([])}>Done</button>
          {lookupResults.length > 1 && <button type="button" className="button rp-tool-primary" onClick={addAllResults}><ListPlus size={15} aria-hidden="true" /> Add all</button>}
        </div>
      </div>
    </div>}

    {duplicates && <div className="rp-tool-modal-backdrop" role="dialog" aria-modal="true" aria-label="Duplicate references">
      <div className="rp-tool-modal">
        <div className="rp-tool-modal-head"><div><span className="rp-tool-kicker">{duplicates.length} group{duplicates.length === 1 ? '' : 's'} found</span><h3>Possible duplicates</h3></div><button type="button" className="rp-tool-icon-button" onClick={() => setDuplicates(null)} aria-label="Close"><X size={18} /></button></div>
        <p className="rp-tool-muted">These share a DOI, PubMed ID, ISBN, link, or the same title and year. Merging keeps the most complete copy and fills its empty fields from the others. Nothing is merged unless you choose to.</p>
        <div className="rp-rg-result-list">{duplicates.map(group => <article className="rp-rg-dup-group" key={group.map(reference => reference.id).join('-')}>
          <ul>{group.map(reference => <li key={reference.id}><strong>{reference.title || 'Untitled'}</strong><span>{[authorsToText(reference.authors).split(';')[0], reference.year, reference.journal || reference.publisher || reference.site, reference.doi && `DOI ${reference.doi}`].filter(Boolean).join(' · ')}</span></li>)}</ul>
          <div className="rp-rg-dup-actions"><button type="button" className="button button-outline" onClick={() => setDuplicates(current => { const next = current.filter(item => item !== group); return next.length ? next : null; })}>Keep separate</button><button type="button" className="button rp-tool-primary" onClick={() => mergeGroup(group)}>Merge {group.length} into one</button></div>
        </article>)}</div>
      </div>
    </div>}

    {editor && <div className="rp-tool-modal-backdrop" role="dialog" aria-modal="true" aria-label="Reference editor">
      <form className="rp-tool-modal rp-rg-editor rp-tool-form" onSubmit={saveEditor}>
        <div className="rp-tool-modal-head"><div><span className="rp-tool-kicker">{editingId ? 'Edit reference' : 'Add by hand'}</span><h3>{SOURCE_TYPES.find(([value]) => value === editor.type)?.[1]}</h3></div><button type="button" className="rp-tool-icon-button" onClick={() => setEditor(null)} aria-label="Close editor"><X size={18} /></button></div>
        <label className="rp-rg-editor-type">Source type<select value={editor.type} onChange={event => changeEditorType(event.target.value)}>{SOURCE_TYPES.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
        <div className="rp-rg-editor-grid">{(FIELDS_BY_TYPE[editor.type] || FIELDS_BY_TYPE.journal).map(([field, label, required]) => <label className={['title', 'url', 'authors_text', 'booktitle'].includes(field) ? 'is-wide' : ''} key={field}>{label}{required && ' *'}{field === 'authors_text'
          ? <><textarea rows="3" value={editor[field] || ''} onChange={event => setEditor(current => ({ ...current, [field]: event.target.value }))} placeholder={'One per line or separated by semicolons:\nAda Lovelace; Smith JA; World Health Organization'} /><small className="rp-rg-field-hint">{editorReference.authors.length ? `${editorReference.authors.length} author${editorReference.authors.length === 1 ? '' : 's'} read: ${editorReference.authors.slice(0, 3).map(author => author.first || author.middle ? `${author.last}, ${[author.first, author.middle].filter(Boolean).join(' ')}` : author.last).join(' · ')}${editorReference.authors.length > 3 ? ' …' : ''}` : 'Organisations such as "World Health Organization" are kept whole.'}</small></>
          : <input value={editor[field] || ''} onChange={event => setEditor(current => ({ ...current, [field]: event.target.value }))} type={field === 'url' ? 'url' : field === 'accessed' ? 'date' : 'text'} inputMode={['year', 'volume', 'issue', 'pmid'].includes(field) ? 'numeric' : undefined} placeholder={{ doi: '10.1000/xyz123', pages: '101–109', year: '2024', pmid: '31452104', isbn: '978-0-19-852999-6' }[field] || ''} />}</label>)}</div>
        {(editorWarnings.length > 0 || editorMissing.length > 0) && <ul className="rp-rg-warnings rp-rg-editor-warnings">
          {editorMissing.length > 0 && <li><AlertTriangle size={13} aria-hidden="true" /> Still needed: {editorMissing.join(', ').toLowerCase()}.</li>}
          {editorWarnings.map(warning => <li key={warning}><AlertTriangle size={13} aria-hidden="true" /> {warning}</li>)}
        </ul>}
        {editorReference && editorReference.title && <div className="rp-rg-output rp-rg-preview"><small>Preview · {styleLabel}</small><p dangerouslySetInnerHTML={{ __html: citationHtml(editorReference, style) }} /></div>}
        <div className="rp-tool-modal-actions"><button type="button" className="button button-outline" onClick={() => setEditor(null)}>Cancel</button><button className="button rp-tool-primary">{editingId ? 'Save changes' : 'Add reference'}</button></div>
      </form>
    </div>}
      <ToolGuide path="/tools/reference-generator" />
    </section>
  </>;
}
