import { AlertTriangle, ArchiveRestore, BookOpen, CalendarClock, CheckCircle2, Copy, ExternalLink, Eye, EyeOff, FilePlus2, FileStack, FileText, Filter, Lock, Pencil, Plus, RefreshCw, Search, Send, Star, StarOff, Trash2, Undo2, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { DashboardApi } from '../../../api/dashboardApi';
import ActionMenu from '../../../components/dashboard/ActionMenu';
import AdminPagination from '../../../components/dashboard/AdminPagination';
import StatusBadge from '../../../components/dashboard/StatusBadge';
import { optimizedImageUrl } from '../../../utils/optimizedImages';
import { BAND_LABELS, CHECK_BY_ID, GROUPS, scoreBand } from './seoAnalysis';
import '../../../styles/dashboard/dash-optimization.css';
import { permissionsAllow } from '../users/adminShared';
import { articlePath, editorialStatus, localScheduleToISO, NEEDS_FILTERS, relativeTime, rowReadiness, SCORE_FILTERS, STATUS_VIEWS } from './workspace';

export const actionLabels = { draft:'Move to draft', pending:'Submit for review', private:'Make private', publish:'Publish now', schedule:'Schedule publication', feature:'Feature on homepage', unfeature:'Remove featured status', trash:'Move to trash', restore:'Restore as draft', duplicate:'Duplicate as draft' };
// Low-risk, easily reversible single-item actions run without a confirmation step.
const DIRECT_ACTIONS = new Set(['feature', 'unfeature', 'restore']);
const date = value => value ? new Date(value).toLocaleDateString(undefined,{day:'numeric',month:'short',year:'numeric'}) : 'Not set';
const FILTER_KEYS = ['q','category','tag','author','featured','needs','date_from','date_to'];

function Readiness({ post }) {
  const { results, done, total } = rowReadiness(post);
  const missing = results.filter(item => !item.done).map(item => item.label);
  const tone = done === total ? 'is-ready' : done >= total - 1 ? 'is-close' : 'is-low';
  return <span className={`dart-ready ${tone}`} role="img" tabIndex={0} aria-label={`Readiness ${done} of ${total}${missing.length ? `. Missing: ${missing.join(', ')}` : '. All checks complete'}`}>
    <span className="dart-ready-dots" aria-hidden="true">{results.map(item => <i key={item.key} className={item.done ? 'is-done' : ''}/>)}</span>
    <small aria-hidden="true">{done}/{total}</small>
    <span className="dart-ready-tip" role="tooltip">
      <strong>{done === total ? 'Ready to publish' : `${total - done} ${total - done === 1 ? 'check' : 'checks'} to review`}</strong>
      {results.map(item => <span key={item.key} className={item.done ? 'is-done' : ''}>{item.done ? <CheckCircle2 size={13}/> : <AlertTriangle size={13}/>}{item.label}</span>)}
    </span>
  </span>;
}

/** Stored SEO / AEO / GEO score for a row, with the lens scores and top issues on hover. */
function Optimization({ post }) {
  const summary = post.optimization || {};
  const scores = summary.scores;
  if (!scores) return <span className="dopt-pill is-none" title="Not analysed yet">–</span>;
  const band = scoreBand(scores.overall);
  const issues = (summary.issues || []).map(id => CHECK_BY_ID[id]?.label).filter(Boolean);
  return <span className={`dart-ready dopt-row is-${band}`} role="img" tabIndex={0} aria-label={`Optimization ${scores.overall} of 100, ${BAND_LABELS[band]}. ${GROUPS.map(group => `${group.short} ${scores[group.key] ?? 'n/a'}`).join(', ')}${issues.length ? `. Fix: ${issues.join(', ')}` : ''}`}>
    <span className={`dopt-pill is-${band}`} aria-hidden="true">{scores.overall}</span>
    <span className="dopt-row-lenses" aria-hidden="true">{GROUPS.map(group => <i key={group.key} className={`is-${scoreBand(scores[group.key])}`} title={`${group.label} ${scores[group.key] ?? '–'}`} />)}</span>
    <span className="dart-ready-tip" role="tooltip">
      <strong>{BAND_LABELS[band]} · {summary.problems || 0} problems, {summary.improvements || 0} improvements</strong>
      <span className="dopt-tip-scores">{GROUPS.map(group => <b key={group.key} className={`is-${scoreBand(scores[group.key])}`}>{group.short} {scores[group.key] ?? '–'}</b>)}</span>
      {issues.map(label => <span key={label}><AlertTriangle size={13}/>{label}</span>)}
    </span>
  </span>;
}

export default function ArticleLibrary({ posts, summary, attention, pagination, categories, tags, authors, filters, onFilters, onEdit, onCreate, onReload, loading, onNotice, onError }) {
  const { user, bootstrap } = useOutletContext();
  const can = permission => permissionsAllow(bootstrap?.permissions, permission, user?.is_superuser);
  const canEdit = can('content.edit');
  const canCreate = can('content.create');
  // Row quick actions (publish, schedule, duplicate...) and bulk actions use the bulk API: content.manage.
  const canWrite = can('content.manage');
  const canTrash = can('content.delete') && canWrite;
  const [selected, setSelected] = useState([]);
  const [advanced, setAdvanced] = useState(false);
  const [query, setQuery] = useState(filters.q);
  const [confirmation, setConfirmation] = useState(null);
  const [schedule, setSchedule] = useState('');
  const [busy, setBusy] = useState(false);
  const [analysing, setAnalysing] = useState(false);
  const dialog = useRef(null);
  const viewKey = `resref.article-views.v1.${user?.id || 'local'}`;
  const [views, setViews] = useState(() => { try { const saved=JSON.parse(localStorage.getItem(viewKey)||'[]'); return Array.isArray(saved)?saved.slice(0,8):[]; } catch { return []; } });
  useEffect(() => { setSelected([]); }, [posts]);
  useEffect(() => { setQuery(filters.q); }, [filters.q]);
  useEffect(() => { if (confirmation) dialog.current?.showModal(); else dialog.current?.close(); }, [confirmation]);
  const noun = filters.type === 'page' ? 'pages' : 'articles';
  const choose = (key,value) => onFilters({ ...filters, [key]:value, page:1 });
  const request = (action,ids=selected,title='') => { setSchedule(''); setConfirmation({action,ids,title}); };
  const runAction = async (action, ids, extra = {}) => {
    const result=await DashboardApi.bulkPosts({ action, ids, ...extra });
    onNotice(`${actionLabels[action]}: ${result.updated} ${result.updated===1?'record':'records'} updated.${action==='duplicate'?' The original is unchanged. Attach PDFs separately to the new draft.':''}`);
    await onReload();
    if(result.post) onEdit(result.post);
  };
  const apply = async event => {
    event.preventDefault(); if(!confirmation || busy) return;
    setBusy(true); onError('');
    try {
      await runAction(confirmation.action, confirmation.ids, confirmation.action==='schedule'?{published_at:localScheduleToISO(schedule)}:{});
      setConfirmation(null); setSelected([]);
    } catch(error) { onError(error.message); setConfirmation(null); } finally { setBusy(false); }
  };
  const quick = async (action, post) => {
    if(!DIRECT_ACTIONS.has(action)) { request(action,[post.id],post.title); return; }
    if(busy) return;
    setBusy(true); onError('');
    try { await runAction(action,[post.id]); } catch(error) { onError(error.message); } finally { setBusy(false); }
  };
  const deleteForever = async post => {
    if(window.prompt(`This permanently deletes “${post.title}”. Restore will no longer be possible. Type DELETE to confirm.`)!=='DELETE') return;
    setBusy(true); onError('');
    try { await DashboardApi.deletePost(post.id); onNotice('Trashed content permanently deleted. Restore is no longer available.'); await onReload(); }
    catch(error){ onError(error.message); } finally { setBusy(false); }
  };
  // Scores are calculated on demand; finish the articles that have not been analysed yet.
  const analyseRemaining = async () => {
    setAnalysing(true); onError('');
    try {
      let previous = Infinity;
      for (let round = 0; round < 50; round += 1) {
        const result = await DashboardApi.refreshSeoReports();
        if (!result.remaining || result.remaining >= previous) break;
        previous = result.remaining;
      }
      await onReload();
    } catch(error) { onError(error.message); } finally { setAnalysing(false); }
  };
  const saveView = () => {
    const name=window.prompt('Name this filtered view (saved in this browser):');
    if(!name?.trim()) return;
    const next=[...views.filter(v=>v.name!==name.trim()),{name:name.trim().slice(0,40),filters:{...filters,page:1}}].slice(-8);
    try {localStorage.setItem(viewKey,JSON.stringify(next));setViews(next);onNotice('View saved in this browser.');}catch{onError('This browser cannot save a view.');}
  };
  const removeView = name => {
    const next=views.filter(v=>v.name!==name);
    try {localStorage.setItem(viewKey,JSON.stringify(next));} catch { /* ignore */ }
    setViews(next);
  };
  const activeFilters=['category','tag','author','featured','needs','date_from','date_to'].filter(key=>filters[key]).length;
  const hasFilters = FILTER_KEYS.some(key=>filters[key]);
  const clearFilters = () => onFilters({ type:filters.type, status:filters.status, sort:filters.sort==='updated'?'':filters.sort });
  const chipLabel = {
    q: value=>`Search: “${value}”`,
    category: value=>`Category: ${categories.find(c=>String(c.id)===String(value))?.name||value}`,
    tag: value=>`Tag: ${tags.find(t=>String(t.id)===String(value))?.name||value}`,
    author: value=>`Contributor: ${authors.find(a=>String(a.id)===String(value))?.display_name||value}`,
    featured: ()=>'Featured on homepage',
    needs: value=>value.startsWith('issue:')?`Check: ${CHECK_BY_ID[value.slice(6)]?.label||value.slice(6)}`:[...NEEDS_FILTERS,...SCORE_FILTERS].find(([key])=>key===value)?.[1]||value,
    date_from: value=>`Updated from ${value}`,
    date_to: value=>`Updated to ${value}`,
  };
  const rowMenu = post => {
    const status = editorialStatus(post);
    const featured = post.design_settings?.is_featured === true;
    if (status === 'trash') return [
      { label:'Open record', icon:Eye, onClick:()=>onEdit(post) },
      canWrite && { label:'Restore as draft', icon:ArchiveRestore, onClick:()=>quick('restore',post), disabled:busy },
      canTrash && { divider:true },
      canTrash && { label:'Delete permanently…', icon:Trash2, danger:true, onClick:()=>deleteForever(post), disabled:busy },
    ];
    return [
      { label:canEdit?'Edit':'Inspect', icon:Pencil, onClick:()=>onEdit(post) },
      status==='publish' && { label:'View live', icon:ExternalLink, href:articlePath(post), external:true },
      canWrite && { divider:true },
      canWrite && status!=='publish' && { label:'Publish now', icon:Send, onClick:()=>quick('publish',post), disabled:busy },
      canWrite && { label:status==='scheduled'?'Reschedule…':'Schedule…', icon:CalendarClock, onClick:()=>quick('schedule',post), disabled:busy },
      canWrite && status!=='pending' && { label:'Submit for review', icon:Eye, onClick:()=>quick('pending',post), disabled:busy },
      canWrite && status!=='draft' && { label:'Move to draft', icon:Undo2, onClick:()=>quick('draft',post), disabled:busy },
      canWrite && status!=='private' && { label:'Make private', icon:Lock, onClick:()=>quick('private',post), disabled:busy },
      canWrite && { divider:true },
      canWrite && (featured
        ? { label:'Remove featured status', icon:StarOff, onClick:()=>quick('unfeature',post), disabled:busy }
        : { label:'Feature on homepage', icon:Star, onClick:()=>quick('feature',post), disabled:busy }),
      canWrite && { label:'Duplicate as draft', icon:Copy, onClick:()=>quick('duplicate',post), disabled:busy },
      canTrash && { divider:true },
      canTrash && { label:'Move to trash', icon:Trash2, danger:true, onClick:()=>quick('trash',post), disabled:busy },
    ];
  };
  const quickBulk = filters.status==='trash' ? ['restore'] : ['publish','draft',...(canTrash?['trash']:[])];
  const bulkOptions = Object.entries(actionLabels).filter(([key])=>key!=='duplicate'&&(key!=='trash'||canTrash));
  const total = pagination?.total_items ?? posts.length;

  return <section className="article-library dart-library" aria-label="Article management workspace" aria-busy={loading}>
    <div className="dart-topline">
      <div className="dart-type-switch" role="group" aria-label="Content type">
        <button type="button" aria-pressed={filters.type==='post'} onClick={()=>onFilters({type:'post'})}><BookOpen size={15}/> Articles</button>
        <button type="button" aria-pressed={filters.type==='page'} onClick={()=>onFilters({type:'page'})}><FileStack size={15}/> Pages</button>
      </div>
      <div className="article-view-tabs dart-status-tabs" aria-label="Publication status views">
        {STATUS_VIEWS.map(([status,label,key])=><button key={key} type="button" aria-pressed={filters.status===status} onClick={()=>choose('status',status)}>{label}<span>{summary?.[key]??'—'}</span></button>)}
      </div>
    </div>

    {filters.status!=='trash'&&<div className="dart-attention" aria-label="Needs attention">
      <span className="dart-attention-label"><AlertTriangle size={15}/> Needs attention</span>
      {NEEDS_FILTERS.filter(([key])=>filters.type!=='page'||!['category','contributors'].includes(key)).map(([key,label])=>{const count=attention?.[key];return <button key={key} type="button" aria-pressed={filters.needs===key} className={count?'has-items':''} onClick={()=>choose('needs',filters.needs===key?'':key)}>{label}<span>{count??'—'}</span></button>;})}
      {attention?.pending>0&&<button type="button" className="dopt-analyse" disabled={analysing} onClick={analyseRemaining}><RefreshCw size={13} className={analysing?'spin':''}/>{analysing?'Calculating scores…':`Scores pending for ${attention.pending} — calculate now`}</button>}
    </div>}

    <div className="article-table-panel dart-panel">
      <form className="article-filter-toolbar dart-toolbar" onSubmit={e=>{e.preventDefault();choose('q',query.trim());}}>
        <label className="article-search dart-search"><Search size={17} aria-hidden="true"/><input aria-label={`Search ${noun}`} placeholder={`Search articles${filters.type==='page'?' and pages':''}…`} value={query} onChange={e=>setQuery(e.target.value)}/>{query&&<button type="button" className="dart-search-clear" aria-label="Clear search" onClick={()=>{setQuery('');if(filters.q)choose('q','');}}><X size={15}/></button>}<button type="submit" aria-label="Run article search"><Search size={16}/></button></label>
        <select aria-label="Filter by category" value={filters.category} onChange={e=>choose('category',e.target.value)}><option value="">All categories</option>{categories.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select>
        <select aria-label="Filter by author" value={filters.author} onChange={e=>choose('author',e.target.value)}><option value="">All contributors</option>{authors.map(a=><option key={a.id} value={a.id}>{a.display_name}</option>)}</select>
        <select aria-label="Sort articles" value={filters.sort} onChange={e=>choose('sort',e.target.value)}><option value="updated">Latest updated</option><option value="published">Latest published</option><option value="oldest">Oldest published</option><option value="title">Title A–Z</option><option value="scheduled">Publication date ↑</option><option value="score">Lowest optimization score</option><option value="score_desc">Highest optimization score</option></select>
        <button type="button" className={`admin-button admin-button-secondary dart-filter-button ${advanced?'is-open':''}`} onClick={()=>setAdvanced(!advanced)} aria-expanded={advanced} aria-controls="article-advanced-filters"><Filter size={16}/> Filters{activeFilters>0?` (${activeFilters})`:''}</button>
      </form>
      {advanced&&<div className="article-advanced-filters dart-advanced" id="article-advanced-filters">
        <label>Tag<select aria-label="Filter by tag" value={filters.tag} onChange={e=>choose('tag',e.target.value)}><option value="">All tags</option>{tags.map(t=><option key={t.id} value={t.id}>{t.name}</option>)}</select></label>
        <label>Editorial checks<select aria-label="Editorial checks" value={filters.needs} onChange={e=>choose('needs',e.target.value)}><option value="">All {noun}</option>{[...NEEDS_FILTERS,...SCORE_FILTERS].map(([key,label])=><option key={key} value={key}>{label}</option>)}{filters.needs.startsWith('issue:')&&<option value={filters.needs}>{chipLabel.needs(filters.needs)}</option>}</select></label>
        <label>Homepage<select aria-label="Homepage" value={filters.featured} onChange={e=>choose('featured',e.target.value)}><option value="">All content</option><option value="true">Featured only</option></select></label>
        <label>Updated from<input aria-label="Updated from" type="date" value={filters.date_from} onChange={e=>choose('date_from',e.target.value)}/></label>
        <label>Updated to<input aria-label="Updated to" type="date" value={filters.date_to} onChange={e=>choose('date_to',e.target.value)}/></label>
        <button type="button" className="admin-button admin-button-secondary" onClick={saveView}><Plus size={15}/> Save view</button>
      </div>}
      {(hasFilters||views.length>0)&&<div className="dart-chip-row">
        {hasFilters&&<div className="dart-active-filters" aria-label="Active filters">
          {FILTER_KEYS.filter(key=>filters[key]).map(key=><span className="dart-filter-chip" key={key}>{chipLabel[key](filters[key])}<button type="button" aria-label={`Remove filter ${chipLabel[key](filters[key])}`} onClick={()=>choose(key,'')}><X size={13}/></button></span>)}
          <button type="button" className="dart-link-button" onClick={clearFilters}>Clear filters</button>
        </div>}
        {views.length>0&&<div className="dart-saved-views" aria-label="Saved article views">
          <span>Saved views</span>
          {views.map(v=><span className="dart-view-chip" key={v.name}><button type="button" onClick={()=>onFilters(v.filters)}>{v.name}</button><button type="button" aria-label={`Delete saved view ${v.name}`} onClick={()=>removeView(v.name)}><X size={12}/></button></span>)}
        </div>}
      </div>}
      <div className="article-list-context dart-context">
        <span role="status">{loading?'Loading content…':`${total} ${total===1?noun.slice(0,-1):noun}`}{filters.q?` matching “${filters.q}”`:''}</span>
        <button type="button" className="dash-icon-button" disabled={loading} onClick={onReload} aria-label="Refresh article list" title="Refresh"><RefreshCw size={15} className={loading?'spin':''}/></button>
      </div>

      <div className="article-table-scroll dart-table-wrap">
        <table className="article-management-table dart-table">
          <thead><tr><th className="dart-col-check"><input type="checkbox" aria-label="Select all articles on this page" disabled={!posts.length||loading||!canWrite} checked={posts.length>0&&selected.length===posts.length} onChange={e=>setSelected(e.target.checked?posts.map(p=>p.id):[])}/></th><th>{filters.type==='page'?'Page':'Article'}</th><th>Status</th><th>Readiness</th><th>SEO · AEO · GEO</th><th>Category</th><th>Contributors</th><th>Updated</th><th className="dart-col-actions"><span className="sr-only">Actions</span></th></tr></thead>
          <tbody>
            {loading&&!posts.length&&Array.from({length:5},(_,i)=><tr className="dart-skeleton-row" key={`s${i}`} aria-hidden="true"><td colSpan={9}><span/><span/></td></tr>)}
            {posts.map(post=>{const status=editorialStatus(post);const featured=post.design_settings?.is_featured===true;return <tr key={post.id} className={selected.includes(post.id)?'is-selected':''}>
              <td className="dart-cell-check"><input type="checkbox" aria-label={`Select ${post.title}`} checked={selected.includes(post.id)} disabled={loading||!canWrite} onChange={e=>setSelected(current=>e.target.checked?[...current,post.id]:current.filter(id=>id!==post.id))}/></td>
              <td className="dart-cell-title"><div className="article-row-title dart-row-title">{post.featured_image?<img src={optimizedImageUrl(post.featured_image,true)} loading="lazy" alt=""/>:<span className="article-thumbnail-empty"><FileText size={20}/></span>}<div><button type="button" onClick={()=>onEdit(post)}>{post.title||'Untitled'}</button><small title={articlePath(post)}>{featured&&<span className="dart-featured"><Star size={11} aria-hidden="true"/> Featured</span>}/{post.slug}</small></div></div></td>
              <td className="dart-cell-status"><StatusBadge value={status}/>{status==='scheduled'&&<small className="article-schedule-date">{new Date(post.published_at).toLocaleString(undefined,{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'})}</small>}</td>
              <td className="dart-cell-ready"><Readiness post={post}/></td>
              <td className="dart-cell-ready dart-cell-score"><Optimization post={post}/></td>
              <td className="dart-cell-meta" data-label="Category">{post.categories.map(c=>c.name).join(', ')||<span className="article-muted">Uncategorized</span>}</td>
              <td className="dart-cell-meta" data-label="Contributors">{post.author||<span className="article-muted">Not assigned</span>}</td>
              <td className="article-date dart-cell-meta" data-label="Updated" title={new Date(post.updated_at).toLocaleString()}>{date(post.updated_at)}{Date.now()-new Date(post.updated_at).getTime()<30*864e5&&<small>{relativeTime(post.updated_at)}</small>}</td>
              <td className="dart-cell-actions"><div className="article-row-actions dart-row-actions"><button type="button" className="dash-icon-button" title={canEdit?'Edit article':'Inspect article'} aria-label={`${canEdit?'Edit':'Inspect'} ${post.title}`} onClick={()=>onEdit(post)}><Pencil size={15}/></button>{status==='publish'&&<a className="dash-icon-button" href={articlePath(post)} target="_blank" rel="noreferrer" title="View published article" aria-label={`View ${post.title}`}><ExternalLink size={15}/></a>}<ActionMenu label={`More actions for ${post.title}`} items={rowMenu(post)}/></div></td>
            </tr>;})}
          </tbody>
        </table>
      </div>
      {!posts.length&&!loading&&<div className="article-library-empty dart-empty">
        {filters.status==='trash'&&!hasFilters
          ? <><span className="dart-empty-icon"><Trash2 size={26}/></span><h2>Trash is empty</h2><p>Items you move to Trash appear here. They can be restored as drafts or deleted permanently.</p></>
          : hasFilters||filters.status
            ? <><span className="dart-empty-icon"><Search size={26}/></span><h2>No {noun} match this view</h2><p>Try a different search or clear your filters. Your existing content has not changed.</p><div className="dart-empty-actions">{hasFilters&&<button className="admin-button admin-button-secondary" onClick={clearFilters}>Clear filters</button>}{filters.status&&<button className="admin-button admin-button-secondary" onClick={()=>onFilters({type:filters.type})}>Show all content</button>}</div></>
            : <><span className="dart-empty-icon"><FilePlus2 size={26}/></span><h2>No {noun} yet</h2><p>Start your first {filters.type==='page'?'page':'article'}. Drafts stay private until you publish them.</p>{canCreate&&<button className="admin-button" onClick={()=>onCreate(filters.type)}><Plus size={16}/> {filters.type==='page'?'New page':'New article'}</button>}</>}
      </div>}
      <div className="article-table-footer dart-footer"><span>{total} records · {selected.length} selected</span><AdminPagination pagination={pagination} onPage={page=>onFilters({...filters,page})}/><label>Rows<select aria-label="Articles per page" value={filters.per_page} onChange={e=>choose('per_page',e.target.value)}>{[20,50,100].map(n=><option key={n}>{n}</option>)}</select></label></div>
    </div>

    {selected.length>0&&<div className="dart-bulk-bar" role="region" aria-label="Bulk actions">
      <strong>{selected.length} selected <small>on this page</small></strong>
      <div className="dart-bulk-quick">{quickBulk.map(key=><button key={key} type="button" className={`admin-button ${key==='trash'?'admin-button-danger':'admin-button-secondary'}`} disabled={busy||loading} onClick={()=>request(key)}>{key==='publish'?<Send size={15}/>:key==='draft'?<EyeOff size={15}/>:key==='trash'?<Trash2 size={15}/>:<ArchiveRestore size={15}/>}{actionLabels[key]}</button>)}</div>
      <select aria-label="Bulk action" value="" disabled={busy||loading} onChange={e=>{if(e.target.value)request(e.target.value);}}><option value="">More actions…</option>{bulkOptions.map(([key,label])=><option key={key} value={key}>{label}</option>)}</select>
      <button type="button" className="dash-icon-button" onClick={()=>setSelected([])} aria-label="Clear selection"><X size={17}/></button>
    </div>}

    <dialog ref={dialog} className="article-action-dialog dart-dialog" aria-labelledby="article-action-title" onCancel={e=>{if(busy)e.preventDefault();else setConfirmation(null);}} onClose={()=>{if(!busy)setConfirmation(null);}}>
      {confirmation&&<form onSubmit={apply}><header><h2 id="article-action-title">{actionLabels[confirmation.action]}</h2><button type="button" className="dash-icon-button" disabled={busy} onClick={()=>setConfirmation(null)} aria-label="Cancel action"><X size={18}/></button></header>
        <p>{confirmation.title?<>This will affect “<strong>{confirmation.title}</strong>”.</>:<>This will affect {confirmation.ids.length} selected {confirmation.ids.length===1?'record':'records'}.</>}</p>
        {confirmation.action==='trash'&&<p>Content and media are preserved. You can restore these records from the Trash view.</p>}
        {confirmation.action==='publish'&&<p>These records will become public immediately. Existing past publication dates and URLs will be kept.</p>}
        {confirmation.action==='draft'&&<p>Published records moved to draft are removed from the public site until they are published again.</p>}
        {confirmation.action==='private'&&<p>Private records are hidden from the public site.</p>}
        {confirmation.action==='duplicate'&&<p>Create an unpublished copy with the same content, categories, and contributor credits. The original and its URL stay unchanged. PDFs must be attached separately.</p>}
        {confirmation.action==='schedule'&&<label>Publication date and time<input type="datetime-local" required value={schedule} onChange={e=>setSchedule(e.target.value)}/><small>Your timezone: {Intl.DateTimeFormat().resolvedOptions().timeZone}. Publication is automatic at this time.</small></label>}
        <footer><button type="button" className="admin-button admin-button-secondary" disabled={busy} onClick={()=>setConfirmation(null)}>Cancel</button><button className={`admin-button ${confirmation.action==='trash'?'admin-button-danger':''}`} disabled={busy}>{busy?'Applying…':actionLabels[confirmation.action]}</button></footer></form>}
    </dialog>
  </section>;
}
