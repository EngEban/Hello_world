import { AlertCircle, ArchiveRestore, ArrowLeft, CalendarClock, CheckCircle2, Circle, Code2, ExternalLink, Eye, FileText, Globe2, History, ImageIcon, Palette, RefreshCw, Save, Search, Send, Star, Tags, Trash2, UserRound, Wand2, X } from 'lucide-react';
import { useDeferredValue, useEffect, useMemo, useRef, useState } from 'react';
import { DashboardApi } from '../../../api/dashboardApi';
import AdminNotice from '../../../components/dashboard/AdminNotice';
import MediaPicker from '../../../components/dashboard/MediaPicker';
import StatusBadge from '../../../components/dashboard/StatusBadge';
import VisualContentEditor from '../../../components/dashboard/VisualContentEditor';
import ArticlePreview from './ArticlePreview';
import { AuthorSectionFields, DesignFields, EditorSection, MediaFields, SourceInfo, TaxonomyFields } from './EditorSections';
import OptimizationPanel, { OptimizationSummary } from './OptimizationPanel';
import { analysisInput, analyzeArticle, BAND_LABELS, scoreBand } from './seoAnalysis';
import { buildChecklist, currentDatetimeLocal, displayStatus, emptyContributor, normalizePost, payloadForSave, publicPreviewPath, publishVisibilityIssues, tomorrowMorningLocal } from './editorModel';
import { clearBackup, isFuturePublication, readBackup, readMinutes, slugify, wordCount, writeBackup } from './workspace';

const SECTION_LINKS = [['article-section-seo', 'SEO, AEO & GEO'], ['article-section-media', 'Media & files'], ['article-section-taxonomy', 'Taxonomy & credits'], ['article-section-author', 'Author section'], ['article-section-design', 'Design'], ['article-section-source', 'Source']];

function focusTarget(id) {
  const element = document.getElementById(id);
  if (!element) return;
  const details = element.tagName === 'DETAILS' ? element : element.closest('details');
  if (details) details.open = true;
  element.scrollIntoView({ behavior: 'smooth', block: element.tagName === 'DETAILS' ? 'start' : 'center' });
  const focusable = element.matches('input, textarea, select') ? element : element.querySelector('input:not([type=hidden]), textarea, select, [contenteditable=true]');
  setTimeout(() => focusable?.focus({ preventScroll: true }), 350);
}

// Internal links are judged against the public site, not the dashboard host.
const siteHost = () => { try { return new URL(document.querySelector('meta[name="resref:site-url"]')?.content || 'https://resref.com').host; } catch { return 'resref.com'; } };

function ScoreRing({ score }) {
  const radius = 26; const circumference = 2 * Math.PI * radius;
  return <svg className="dart-score-ring" viewBox="0 0 64 64" aria-hidden="true"><circle cx="32" cy="32" r={radius} /><circle cx="32" cy="32" r={radius} className="is-value" strokeDasharray={circumference} strokeDashoffset={circumference * (1 - score / 100)} /></svg>;
}

export default function ArticleEditor({ initialPost, categories, tags, authors, setAuthors, setTags, canWrite, canDelete, canUploadMedia, userId, onClose, onSaved, onTrashed, onDeleted, onNotice, onError }) {
  const [editing, setEditing] = useState(initialPost);
  const [cleanSnapshot, setCleanSnapshot] = useState(() => JSON.stringify(initialPost));
  const [backup, setBackup] = useState(() => { const saved = readBackup(userId, initialPost); return saved && JSON.stringify(saved.post) !== JSON.stringify(initialPost) ? saved : null; });
  const [saving, setSaving] = useState(false);
  const [pdfUploading, setPdfUploading] = useState(false);
  const [showContributorDraft, setShowContributorDraft] = useState(false);
  const [contributorDraft, setContributorDraft] = useState({ ...emptyContributor });
  const [contributorSaving, setContributorSaving] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [scheduleOpen, setScheduleOpen] = useState(false);
  const [scheduleValue, setScheduleValue] = useState('');
  const [analysisGroup, setAnalysisGroup] = useState('seo');
  const scheduleDialog = useRef(null);
  const editorForm = useRef(null);
  const slugTouched = useRef(Boolean(initialPost.id || initialPost.slug));
  const cleanPost = useMemo(() => JSON.parse(cleanSnapshot), [cleanSnapshot]);
  const dirty = JSON.stringify(editing) !== cleanSnapshot;
  const isPage = editing.post_type === 'page';
  const noun = isPage ? 'page' : 'article';
  const status = displayStatus(editing);
  const isLive = Boolean(editing.id && cleanPost.status === 'publish' && cleanPost.published_at && !isFuturePublication(cleanPost.published_at));
  const publicPath = publicPreviewPath(editing, categories);
  const publicUrl = `${window.location.origin}${publicPath}`;
  const checklist = buildChecklist(editing);
  const score = checklist.length ? Math.round((checklist.filter(item => item.done).length / checklist.length) * 100) : 0;
  const visibilityIssues = publishVisibilityIssues(editing, categories);
  const words = wordCount(editing.content);
  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  // Real-time SEO / AEO / GEO analysis; deferred so typing in long articles stays smooth.
  const analysisSource = useDeferredValue(editing);
  const analysis = useMemo(() => analyzeArticle(analysisInput(analysisSource, { siteHost: siteHost() })), [analysisSource]);
  const overallBand = scoreBand(analysis.scores.overall);

  useEffect(() => { const frame = requestAnimationFrame(() => window.scrollTo({ top: 0, behavior: 'instant' })); return () => cancelAnimationFrame(frame); }, []);
  // Local, per-browser safety net for unsaved edits (cleared on successful save).
  useEffect(() => {
    if (!dirty || !canWrite) return undefined;
    const timer = setTimeout(() => writeBackup(userId, editing, editing.updated_at), 800);
    return () => clearTimeout(timer);
  }, [editing, dirty, canWrite, userId]);
  useEffect(() => {
    const leave = event => { if (dirty) { event.preventDefault(); event.returnValue = ''; } };
    const shortcut = event => { if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') { event.preventDefault(); if (canWrite && !saving) editorForm.current?.requestSubmit(); } };
    const navigate = event => { const link = event.target.closest?.('a[href]'); if (dirty && link && link.target !== '_blank' && link.origin === location.origin && link.pathname !== location.pathname && !window.confirm('Leave this page and discard unsaved changes?')) { event.preventDefault(); event.stopPropagation(); } };
    window.addEventListener('beforeunload', leave); document.addEventListener('keydown', shortcut); document.addEventListener('click', navigate, true);
    return () => { window.removeEventListener('beforeunload', leave); document.removeEventListener('keydown', shortcut); document.removeEventListener('click', navigate, true); };
  }, [dirty, canWrite, saving]);
  useEffect(() => { const dialog = scheduleDialog.current; if (scheduleOpen && !dialog?.open) dialog?.showModal(); if (!scheduleOpen && dialog?.open) dialog.close(); }, [scheduleOpen]);

  const acceptEditing = post => { setEditing(post); setCleanSnapshot(JSON.stringify(post)); };
  const acceptPdf = post => {
    const attachment = { pdf_url: post.pdf_url || '', pdf_title: post.pdf_title || '', updated_at: post.updated_at };
    setEditing(current => ({ ...current, ...attachment }));
    setCleanSnapshot(current => JSON.stringify({ ...JSON.parse(current || '{}'), ...attachment }));
  };
  const requestClose = () => {
    if (dirty && !window.confirm('Leave the editor and discard unsaved changes?')) return;
    if (dirty) clearBackup(userId, editing);
    onClose();
  };
  const update = event => {
    const { name, value } = event.target;
    if (name === 'slug') slugTouched.current = true;
    setEditing(current => ({
      ...current,
      [name]: value,
      ...(name === 'status' && value === 'publish' && !current.published_at ? { published_at: currentDatetimeLocal() } : {}),
      ...(name === 'title' && !current.id && !slugTouched.current ? { slug: slugify(value) } : {}),
    }));
  };
  const setField = (name, value) => setEditing(current => ({ ...current, [name]: value }));
  const setSeoSetting = (name, value) => setEditing(current => ({ ...current, seo_settings: { ...(current.seo_settings || {}), [name]: value } }));
  const openAnalysis = group => { setAnalysisGroup(group); focusTarget('article-section-seo'); };
  const fixCheck = check => { setAnalysisGroup(check.group); focusTarget(check.target || 'article-section-seo'); };
  const updateDesign = event => setEditing(current => ({ ...current, design_settings: { ...current.design_settings, [event.target.name]: event.target.value } }));
  const regenerateSlug = () => { slugTouched.current = true; setField('slug', slugify(editing.title)); };

  /* ---------- backup prompt ---------- */
  const restoreBackup = () => {
    // Keep server-owned values (id, version stamp, uploaded PDF) from the loaded record.
    setEditing(current => ({ ...backup.post, id: current.id, updated_at: current.updated_at, pdf_url: current.pdf_url }));
    setBackup(null);
    onNotice('Unsaved changes restored. Review them, then save.');
  };
  const discardBackup = () => { clearBackup(userId, initialPost); setBackup(null); };

  /* ---------- contributors ---------- */
  const resetContributorDraft = () => { setShowContributorDraft(false); setContributorDraft({ ...emptyContributor }); };
  const updateContributorDraft = event => { const { name, value } = event.target; setContributorDraft(current => ({ ...current, [name]: value })); };
  const saveContributor = async event => {
    event.preventDefault();
    if (!contributorDraft.display_name.trim()) { onError('Enter a display name for the new contributor profile.'); return; }
    setContributorSaving(true); onError('');
    try {
      const fallbackLogin = slugify(contributorDraft.display_name || contributorDraft.email.split('@')[0] || '');
      const data = await DashboardApi.saveAuthor({ ...contributorDraft, login: fallbackLogin });
      const authorData = await DashboardApi.getAuthors();
      setAuthors(authorData.results || []);
      setEditing(current => ({ ...current, author_ids: Array.from(new Set([...(current.author_ids || []), data.author.id])), contributors: [...(current.contributors || []), { contributor_id: data.author.id, role: 'author', contribution_note: '' }] }));
      resetContributorDraft();
      onNotice('Contributor profile saved and selected for this article.');
    } catch (err) { onError(err.message); } finally { setContributorSaving(false); }
  };
  const contributor = {
    showDraft: showContributorDraft, setShowDraft: setShowContributorDraft, draft: contributorDraft, updateDraft: updateContributorDraft,
    saving: contributorSaving, saveDraft: saveContributor, resetDraft: resetContributorDraft,
    add: contributorId => setEditing(current => (current.contributors || []).some(item => Number(item.contributor_id) === Number(contributorId)) ? current : { ...current, contributors: [...(current.contributors || []), { contributor_id: Number(contributorId), role: 'author', contribution_note: '' }] }),
    updateCredit: (index, field, value) => setEditing(current => ({ ...current, contributors: current.contributors.map((item, itemIndex) => itemIndex === index ? { ...item, [field]: value } : item) })),
    removeCredit: index => setEditing(current => ({ ...current, contributors: current.contributors.filter((_, itemIndex) => itemIndex !== index) })),
    moveCredit: (index, direction) => setEditing(current => { const next = [...current.contributors]; const destination = index + direction; if (destination < 0 || destination >= next.length) return current; [next[index], next[destination]] = [next[destination], next[index]]; return { ...current, contributors: next }; }),
  };
  const createTag = async name => {
    try {
      const data = await DashboardApi.saveTag({ name });
      if (!data.tag?.id) return null;
      setTags(current => [...current, data.tag].sort((a, b) => a.name.localeCompare(b.name)));
      onNotice(`Tag “${data.tag.name}” created.`);
      return data.tag.id;
    } catch (err) { onError(err.message); return null; }
  };

  /* ---------- saving and workflow ---------- */
  const persist = async (post, extra = {}, message = 'Content saved successfully.') => {
    if (!canWrite || saving) return false;
    setSaving(true); onError('');
    try {
      const data = await DashboardApi.savePost({ ...payloadForSave(post), ...extra }, post.id);
      const next = normalizePost(data.post);
      clearBackup(userId, post); clearBackup(userId, next);
      setBackup(null);
      acceptEditing(next);
      onNotice(message);
      onSaved(next, !post.id);
      return true;
    } catch (err) { onError(err.message); return false; } finally { setSaving(false); }
  };
  const save = event => { event.preventDefault(); persist(editing); };
  const publishNow = () => persist(editing, { status: 'publish', publish_now: true }, 'Content published now.');
  const openSchedule = () => { setScheduleValue(isFuturePublication(editing.published_at) ? editing.published_at : tomorrowMorningLocal()); setScheduleOpen(true); };
  const confirmSchedule = async event => {
    event.preventDefault();
    if (!isFuturePublication(scheduleValue)) { onError('Choose a publication date and time in the future.'); return; }
    const value = scheduleValue;
    setScheduleOpen(false);
    await persist({ ...editing, status: 'publish', published_at: value }, {}, `Scheduled for ${new Date(value).toLocaleString()}. It publishes automatically.`);
  };
  const reloadRecord = async () => {
    const data = await DashboardApi.getPosts({ type: editing.post_type, id: editing.id });
    if (data.results?.[0]) { const next = normalizePost(data.results[0]); acceptEditing(next); onSaved(next, false); }
  };
  const moveToTrash = async () => {
    if (!editing.id || !window.confirm(`Move "${editing.title}" to Trash? It can be restored later.`)) return;
    try { await DashboardApi.bulkPosts({ ids: [editing.id], action: 'trash' }); clearBackup(userId, editing); onTrashed(); }
    catch (err) { onError(err.message); }
  };
  const restore = async () => {
    try { await DashboardApi.bulkPosts({ ids: [editing.id], action: 'restore' }); await reloadRecord(); onNotice('Restored as a draft.'); }
    catch (err) { onError(err.message); }
  };
  const permanentlyRemove = async () => {
    if (!editing?.id || editing.status !== 'trash' || !canDelete || window.prompt('This permanently deletes the trashed record. Type DELETE to confirm.') !== 'DELETE') return;
    try { await DashboardApi.deletePost(editing.id); clearBackup(userId, editing); onDeleted(); }
    catch (err) { onError(err.message); }
  };
  const uploadPdf = async event => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file || !editing?.id) return;
    const formData = new FormData();
    formData.append('file', file);
    if (editing.pdf_title) formData.append('title', editing.pdf_title);
    setPdfUploading(true); onError('');
    try { const data = await DashboardApi.uploadPostPdf(editing.id, formData); acceptPdf(data.post); onNotice('PDF attachment updated.'); onSaved(null, false); }
    catch (err) { onError(err.message); } finally { setPdfUploading(false); }
  };
  const removePdf = async () => {
    if (!editing?.id || !editing.pdf_url || !window.confirm('Remove this PDF attachment from the article?')) return;
    const formData = new FormData();
    formData.append('remove', '1');
    setPdfUploading(true); onError('');
    try { const data = await DashboardApi.uploadPostPdf(editing.id, formData); acceptPdf(data.post); onNotice('PDF attachment removed.'); onSaved(null, false); }
    catch (err) { onError(err.message); } finally { setPdfUploading(false); }
  };

  const credits = (editing.contributors || []).length;
  const slugChanged = Boolean(editing.id && isLive && cleanPost.slug && editing.slug !== cleanPost.slug);
  const saveState = saving ? 'Saving…' : dirty ? 'Unsaved changes' : editing.id ? 'All changes saved' : 'Not saved yet';

  return <div className="dart-editor">
    <header className="dart-editor-head">
      <div className="dart-editor-head-main">
        <button className="article-back-button dart-back" type="button" onClick={requestClose}><ArrowLeft size={16} /> All {isPage ? 'pages' : 'articles'}</button>
        <div className="dart-editor-heading">
          <h1>{editing.id ? 'Edit' : 'New'} {noun}</h1>
          <span className={`dart-save-state ${dirty ? 'has-changes' : ''}`} role="status">{saveState}</span>
        </div>
      </div>
      <div className="dart-editor-head-actions">
        <button type="button" className="admin-button admin-button-secondary" onClick={() => setPreviewOpen(true)}><Eye size={16} /> Preview {noun}</button>
        {isLive && <a className="admin-button admin-button-secondary dart-hide-sm" href={publicPath} target="_blank" rel="noreferrer"><ExternalLink size={16} /> View published</a>}
        {canWrite && <button className="admin-button" type="submit" form="article-editor-form" disabled={saving} title="Ctrl / ⌘ S"><Save size={16} />{saving ? 'Saving…' : 'Save changes'}</button>}
      </div>
    </header>

    <form ref={editorForm} id="article-editor-form" className="admin-editor dart-editor-form" onSubmit={save}>
      {!canWrite && <AdminNotice type="info">Read-only access. You can inspect content, but your role cannot save or publish changes.</AdminNotice>}
      {backup && canWrite && <div className="dart-backup" role="alert">
        <History size={18} aria-hidden="true" />
        <div><strong>Restore unsaved changes from {new Date(backup.savedAt).toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}?</strong>
          <p>This browser kept a copy of edits that were never saved.{backup.baseUpdatedAt && editing.updated_at && backup.baseUpdatedAt !== editing.updated_at ? ' The article was saved again after this copy; restoring replaces those newer changes when you save.' : ''}</p></div>
        <span><button type="button" className="admin-button" onClick={restoreBackup}>Restore changes</button><button type="button" className="admin-button admin-button-secondary" onClick={discardBackup}>Discard</button></span>
      </div>}
      {editing.status === 'trash' && <div className="article-trash-notice dart-trash-notice"><Trash2 size={18} aria-hidden="true" /><p>This record is in Trash and hidden everywhere. Restore it as a draft, or permanently delete it.</p><span>{canWrite && <button className="admin-button admin-button-secondary" type="button" onClick={restore}><ArchiveRestore size={15} /> Restore as draft</button>}{canDelete && <button className="admin-button admin-button-danger" type="button" onClick={permanentlyRemove}><Trash2 size={15} /> Delete permanently</button>}</span></div>}

      <fieldset className="editorial-readonly-fields dart-editor-fieldset" disabled={!canWrite}>
        <div className="dart-editor-grid">
          <div className="dart-editor-main">
            <section className="dart-card dart-writing" aria-label="Title and summary">
              <label className="dart-title-field"><span>Title</span><input id="article-field-title" required name="title" value={editing.title} onChange={update} placeholder={`${isPage ? 'Page' : 'Article'} title`} dir="auto" /></label>
              <div className="dart-slug">
                <label htmlFor="article-field-slug">URL Slug</label>
                <div className="dart-slug-row">
                  <span className="dart-slug-prefix" aria-hidden="true">{publicPath.slice(0, publicPath.length - editing.slug.length) || '/'}</span>
                  <input id="article-field-slug" required name="slug" value={editing.slug} onChange={update} spellCheck="false" />
                  <button type="button" className="dash-icon-button" onClick={regenerateSlug} disabled={!editing.title.trim()} aria-label="Regenerate slug from title" title="Regenerate from title"><Wand2 size={15} /></button>
                </div>
                <small className="dart-slug-url"><Globe2 size={13} aria-hidden="true" />{isLive ? <a href={publicPath} target="_blank" rel="noreferrer">{publicUrl}</a> : <span>{publicUrl}</span>}</small>
                {slugChanged && <small className="dart-warning-text"><AlertCircle size={13} aria-hidden="true" /> Changing the slug of a published {noun} changes its public URL; existing links will stop working.</small>}
              </div>
              <label>Short Excerpt<textarea id="article-field-excerpt" name="excerpt" aria-label="Short Excerpt" value={editing.excerpt} onChange={update} rows="3" placeholder="Short summary shown in cards and search results" dir="auto" /><small className={`dart-counter ${editing.excerpt.trim().length >= 70 ? 'is-good' : editing.excerpt ? 'is-short' : 'is-empty'}`}>{editing.excerpt.length} characters · 70+ recommended for cards and search</small></label>
            </section>

            <section className="dart-card dart-body-card" id="article-section-body" aria-label="Visual Content Editor">
              <header className="dart-card-head"><h2><FileText size={16} /> Visual Content Editor</h2><span>{words.toLocaleString()} words · {readMinutes(editing.content)} min read</span></header>
              <VisualContentEditor readOnly={!canWrite} value={editing.content} onChange={content => setEditing(current => ({ ...current, content }))} />
            </section>

            <nav className="dart-section-nav" aria-label="Article settings sections">
              {SECTION_LINKS.filter(([id]) => id !== 'article-section-source' || editing.wordpress_id).map(([id, label]) => <button type="button" key={id} onClick={() => focusTarget(id)}>{label}</button>)}
            </nav>

            <EditorSection id="article-section-seo" icon={Search} title="SEO, AEO & GEO optimization" hint={`${analysis.scores.overall ?? '–'}/100 · ${BAND_LABELS[overallBand]}`} tone={overallBand === 'good' ? 'is-good' : 'is-warn'} defaultOpen>
              <OptimizationPanel editing={editing} update={update} setSeoSetting={setSeoSetting} publicUrl={publicUrl} analysis={analysis} group={analysisGroup} onGroup={setAnalysisGroup} onFix={fixCheck} />
            </EditorSection>
            <EditorSection id="article-section-media" icon={ImageIcon} title="Media & files" hint={[editing.featured_image ? 'Image set' : 'No image', editing.pdf_url ? 'PDF attached' : ''].filter(Boolean).join(' · ')} tone={editing.featured_image ? 'is-good' : 'is-warn'} defaultOpen>
              <MediaFields editing={editing} update={update} setField={setField} onPickImage={() => setPickerOpen(true)} pdfUploading={pdfUploading} uploadPdf={uploadPdf} removePdf={removePdf} />
            </EditorSection>
            <EditorSection id="article-section-taxonomy" icon={Tags} title="Categories, Contributors, and Tags" hint={`${editing.categories.length} ${editing.categories.length === 1 ? 'category' : 'categories'} · ${editing.tags.length} tags · ${credits} ${credits === 1 ? 'credit' : 'credits'}`} tone={!isPage && (!editing.categories.length || !credits) ? 'is-warn' : 'is-good'} defaultOpen>
              <TaxonomyFields editing={editing} categories={categories} tags={tags} authors={authors} canWrite={canWrite} setField={setField} onCreateTag={createTag} contributor={contributor} />
            </EditorSection>
            <EditorSection id="article-section-author" icon={UserRound} title="Author Section" hint={editing.design_settings.author_section_enabled === 'auto' ? 'Cards shown' : 'Cards hidden'}>
              <AuthorSectionFields editing={editing} updateDesign={updateDesign} />
            </EditorSection>
            <EditorSection id="article-section-design" icon={Palette} title="Typography and Page Design">
              <DesignFields editing={editing} updateDesign={updateDesign} />
            </EditorSection>
            {editing.wordpress_id && <EditorSection id="article-section-source" icon={Code2} title="WordPress source" hint={`#${editing.wordpress_id}`}>
              <SourceInfo editing={editing} />
            </EditorSection>}
          </div>

          <aside className="dart-editor-side" aria-label="Publishing">
            <section className="dart-card dart-publish">
              <header className="dart-card-head"><h2><Send size={16} /> Publish</h2><StatusBadge value={status} /></header>
              <label>Workflow Status<select name="status" aria-label="Workflow Status" value={editing.status} onChange={update}><option value="draft">Draft</option><option value="pending">Pending Review</option><option value="private">Private</option><option value="publish">Published / scheduled</option><option value="trash">Trash</option></select></label>
              <label>Publication Date<input id="article-field-date" type="datetime-local" name="published_at" value={editing.published_at || ''} onChange={update} /><small>Timezone: {timezone}. Set Published with a future date to schedule automatically.</small></label>
              <label>Content Type<select name="post_type" value={editing.post_type} onChange={update}><option value="post">Blog Post / Database Resource</option><option value="page">Backend Page</option></select></label>
              <label className="admin-check dart-switch"><input type="checkbox" checked={editing.design_settings.is_featured === true} onChange={event => updateDesign({ target: { name: 'is_featured', value: event.target.checked } })} /><span className="dart-switch-track" aria-hidden="true" /><Star size={14} aria-hidden="true" /> Feature on homepage</label>
              <p className="editor-hint">Only published articles are shown publicly. Featured articles are prioritized on the homepage.</p>
              {editing.status === 'publish' && <div className={visibilityIssues.length ? 'dart-visibility warning' : 'dart-visibility ready'}>
                <strong>{visibilityIssues.length ? <AlertCircle size={16} /> : <CheckCircle2 size={16} />}{visibilityIssues.length ? 'Check public visibility' : 'Ready for public database'}</strong>
                {visibilityIssues.length ? <ul>{visibilityIssues.map(issue => <li key={issue}>{issue}</li>)}</ul> : <p>This {noun} should appear publicly after saving.</p>}
              </div>}
              {editing.status !== 'trash' && canWrite && <div className="dart-publish-actions">
                {!isLive || isFuturePublication(editing.published_at) ? <button className="admin-button" type="button" disabled={saving} onClick={publishNow}>{isFuturePublication(editing.published_at) ? <RefreshCw size={15} /> : <Send size={15} />} Publish now</button> : null}
                <button className="admin-button admin-button-secondary" type="button" disabled={saving} onClick={openSchedule}><CalendarClock size={15} /> {status === 'scheduled' ? 'Reschedule' : 'Schedule'}</button>
              </div>}
              {isLive && <a className="dart-live-link" href={publicPath} target="_blank" rel="noreferrer"><ExternalLink size={14} /> View published {noun}</a>}
              <footer className="dart-publish-foot">
                <span className="editor-save-state">{dirty ? 'Changes not saved' : editing.id ? 'All changes saved' : 'Not saved yet'} · {status}<small>Ctrl / ⌘ S to save</small></span>
                {editing.id && canDelete && editing.status !== 'trash' && <button className="dart-trash-link" type="button" onClick={moveToTrash}><Trash2 size={14} /> Move to trash</button>}
              </footer>
            </section>

            <OptimizationSummary analysis={analysis} onOpenGroup={openAnalysis} onFix={fixCheck} />

            <section className="dart-card dart-readiness" aria-label="Publishing completeness">
              <div className="dart-readiness-head">
                <div className="dart-score"><ScoreRing score={score} /><strong>{score}%</strong></div>
                <div><h2>Publishing completeness</h2><p>{words.toLocaleString()} words / {readMinutes(editing.content)} min read</p></div>
              </div>
              <ul className="dart-checklist" aria-label="Publish checklist">
                {checklist.map(item => <li key={item.label}><button type="button" className={item.done ? 'is-done' : ''} onClick={() => focusTarget(item.target)}>{item.done ? <CheckCircle2 size={15} /> : <Circle size={15} />}<span>{item.label}</span></button></li>)}
              </ul>
            </section>
          </aside>
        </div>
      </fieldset>
    </form>

    <MediaPicker open={pickerOpen} onClose={() => setPickerOpen(false)} onSelect={asset => setField('featured_image', asset.url)} title="Choose a featured image" canUpload={canUploadMedia} />
    <ArticlePreview open={previewOpen} onClose={() => setPreviewOpen(false)} post={editing} categories={categories} tags={tags} authors={authors} />
    <dialog ref={scheduleDialog} className="article-action-dialog dart-dialog" aria-labelledby="dart-schedule-title" onCancel={() => setScheduleOpen(false)} onClose={() => setScheduleOpen(false)}>
      {scheduleOpen && <form onSubmit={confirmSchedule}>
        <header><h2 id="dart-schedule-title">Schedule publication</h2><button type="button" className="dash-icon-button" onClick={() => setScheduleOpen(false)} aria-label="Cancel scheduling"><X size={18} /></button></header>
        <p>“<strong>{editing.title || 'Untitled draft'}</strong>” will be saved with any current changes and published automatically at this time.</p>
        <label>Publication date and time<input type="datetime-local" required value={scheduleValue} onChange={event => setScheduleValue(event.target.value)} /><small>Your timezone: {timezone}.</small></label>
        <footer><button type="button" className="admin-button admin-button-secondary" onClick={() => setScheduleOpen(false)}>Cancel</button><button className="admin-button" disabled={saving}><CalendarClock size={15} /> Schedule publication</button></footer>
      </form>}
    </dialog>
  </div>;
}
