import { AlertTriangle, CheckSquare, ChevronLeft, ChevronRight, Copy, ExternalLink, Globe2, ImageOff, ImagePlus, Images, LayoutGrid, Link2, List, Loader2, Pencil, Search, Square, Trash2, Upload, UploadCloud, X } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { DashboardApi } from '../../../api/dashboardApi';
import ActionMenu from '../../../components/dashboard/ActionMenu';
import AdminNotice from '../../../components/dashboard/AdminNotice';
import AdminPageHeader from '../../../components/dashboard/AdminPageHeader';
import AdminPagination from '../../../components/dashboard/AdminPagination';
import { Drawer, StatCard, StateBlock } from '../../../components/dashboard/DashboardPrimitives';
import { optimizedImageUrl } from '../../../utils/optimizedImages';
import { Segmented, copyText, formatBytes, readStored, uploadMediaWithProgress, useLibraryPermissions, useUnsavedWarning, validateImageFile, writeStored } from './libraryKit';
import '../../../styles/dashboard/dash-library.css';

const SOURCE_LABELS = { upload: 'Uploaded file', external: 'External URL', wordpress: 'WordPress import' };
const fileTitle = name => name.replace(/\.[^.]+$/, '').replace(/[-_]+/g, ' ').trim();
const extension = url => (String(url || '').split('?')[0].match(/\.([a-z0-9]{2,5})$/i)?.[1] || '').toUpperCase();
const fileName = url => decodeURIComponent(String(url || '').split('?')[0].split('/').pop() || '');
const shortDate = value => value ? new Date(value).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }) : '—';
let queueId = 0;

export default function DashboardMediaPage() {
  const { canCreate, canWrite, canDelete } = useLibraryPermissions('media');
  const [media, setMedia] = useState([]);
  const [pagination, setPagination] = useState(null);
  const [summary, setSummary] = useState(null);
  const [filters, setFilters] = useState({ q: '', missing_alt: '', source: '', sort: 'newest', page: 1 });
  const [search, setSearch] = useState('');
  const [view, setView] = useState(() => readStored('resref.media.view', 'grid'));
  const [status, setStatus] = useState('loading');
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [selection, setSelection] = useState(() => new Set());
  const [detail, setDetail] = useState(null);
  const [addMode, setAddMode] = useState('upload');
  const [queue, setQueue] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [external, setExternal] = useState({ url: '', title: '', alt_text: '' });
  const [pageDrag, setPageDrag] = useState(false);
  const fileRef = useRef(null);
  const dragDepth = useRef(0);
  const requestRef = useRef(0);

  const load = useCallback(async (next = filters) => {
    const request = ++requestRef.current;
    setStatus(current => current === 'ready' ? 'refreshing' : 'loading');
    try {
      const data = await DashboardApi.getMedia(next);
      if (request !== requestRef.current) return;
      setMedia(data.results || []);
      setPagination(data.pagination);
      setSummary(data.summary || null);
      setStatus('ready');
    } catch (err) {
      if (request !== requestRef.current) return;
      setError(err.message);
      setStatus('ready');
    }
  }, [filters]);

  useEffect(() => { load(filters); }, [filters]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const timer = setTimeout(() => setFilters(current => current.q === search.trim() ? current : { ...current, q: search.trim(), page: 1 }), 300);
    return () => clearTimeout(timer);
  }, [search]);

  const pendingQueue = queue.filter(item => item.status === 'queued' || item.status === 'error');
  useUnsavedWarning(uploading || pendingQueue.length > 0);

  const updateFilters = patch => { setSelection(new Set()); setFilters(current => ({ ...current, ...patch, page: patch.page || 1 })); };
  const changeView = next => { setView(next); writeStored('resref.media.view', next); };
  const flash = message => { setError(''); setNotice(message); };

  const addFiles = fileList => {
    if (!canCreate) return;
    const files = [...(fileList || [])];
    if (!files.length) return;
    setAddMode('upload');
    const items = files.map(file => {
      const problem = validateImageFile(file);
      return { id: ++queueId, file, preview: '', title: fileTitle(file.name), alt_text: '', status: problem ? 'invalid' : 'queued', progress: 0, error: problem };
    });
    setQueue(current => [...current, ...items]);
    // Previews are data: URLs because the site's Content-Security-Policy does not allow blob: images.
    items.filter(item => item.status === 'queued').forEach(item => {
      const reader = new FileReader();
      reader.onload = () => setQueue(current => current.map(entry => entry.id === item.id ? { ...entry, preview: String(reader.result || '') } : entry));
      reader.readAsDataURL(item.file);
    });
  };
  const updateQueue = (id, patch) => setQueue(current => current.map(item => item.id === id ? { ...item, ...patch } : item));
  const removeQueued = id => setQueue(current => current.filter(item => item.id !== id));
  const clearQueue = () => setQueue([]);

  const uploadQueue = async event => {
    event?.preventDefault();
    const ready = queue.filter(item => item.status === 'queued' || item.status === 'error');
    if (!ready.length) { setError('Choose one or more image files first.'); return; }
    setUploading(true); setError(''); setNotice('');
    let done = 0;
    for (const item of ready) {
      updateQueue(item.id, { status: 'uploading', progress: 0, error: '' });
      const body = new FormData();
      body.append('file', item.file);
      if (item.title.trim()) body.append('title', item.title.trim());
      if (item.alt_text.trim()) body.append('alt_text', item.alt_text.trim());
      try {
        await uploadMediaWithProgress(body, progress => updateQueue(item.id, { progress }));
        updateQueue(item.id, { status: 'done', progress: 100 });
        done += 1;
      } catch (err) {
        updateQueue(item.id, { status: 'error', error: err.message });
      }
    }
    setUploading(false);
    if (done) {
      setNotice(`${done} ${done === 1 ? 'image' : 'images'} added to Media Library.`);
      setQueue(current => current.filter(item => item.status !== 'done'));
      setFilters(current => ({ ...current, page: 1, sort: 'newest', missing_alt: '', source: '' }));
    } else {
      setError('No images were uploaded. Check the messages next to each file.');
    }
  };

  const addExternal = async event => {
    event.preventDefault(); setError('');
    if (!external.url.trim().startsWith('https://')) { setError('External image URLs must start with https://.'); return; }
    const body = new FormData();
    Object.entries(external).forEach(([key, value]) => { if (value.trim()) body.append(key, value.trim()); });
    try {
      await DashboardApi.saveMedia(body);
      setExternal({ url: '', title: '', alt_text: '' });
      flash('Image added to Media Library.');
      updateFilters({ sort: 'newest' });
    } catch (err) { setError(err.message); }
  };

  const copy = async url => {
    const ok = await copyText(url);
    if (ok) flash('Image URL copied. Paste it into the visual editor or featured-image field.');
    else setError('Could not copy automatically. Select the URL in the details panel and copy it manually.');
  };

  const remove = async (asset, usage) => {
    const usedText = usage?.total ? ` It is still used in ${usage.total} ${usage.total === 1 ? 'place' : 'places'}; those pages will show a broken image.` : '';
    if (!window.confirm(`Delete "${asset.title || 'this image'}" from Media Library?${usedText}`)) return false;
    try {
      await DashboardApi.deleteMedia(asset.id);
      flash('Image removed.');
      setSelection(current => { const next = new Set(current); next.delete(asset.id); return next; });
      await load(filters);
      return true;
    } catch (err) { setError(err.message); return false; }
  };

  const toggleSelect = id => setSelection(current => { const next = new Set(current); if (next.has(id)) next.delete(id); else next.add(id); return next; });
  const allSelected = media.length > 0 && media.every(asset => selection.has(asset.id));
  const selectAll = () => setSelection(allSelected ? new Set() : new Set(media.map(asset => asset.id)));
  const bulkDelete = async () => {
    const ids = [...selection];
    if (!ids.length || !window.confirm(`Delete ${ids.length} selected ${ids.length === 1 ? 'image' : 'images'} from Media Library? Pages that still use them will show broken images. This cannot be undone.`)) return;
    let failed = 0;
    for (const id of ids) { try { await DashboardApi.deleteMedia(id); } catch { failed += 1; } }
    setSelection(new Set());
    if (failed) setError(`${failed} ${failed === 1 ? 'image' : 'images'} could not be deleted.`);
    else flash(`${ids.length} ${ids.length === 1 ? 'image' : 'images'} removed.`);
    load(filters);
  };
  const bulkCopy = async () => {
    const urls = media.filter(asset => selection.has(asset.id)).map(asset => asset.url).join('\n');
    if (await copyText(urls)) flash(`${selection.size} image URLs copied, one per line.`);
  };

  const onDragEnter = event => { if (!canCreate || ![...(event.dataTransfer?.types || [])].includes('Files')) return; dragDepth.current += 1; setPageDrag(true); };
  const onDragLeave = () => { dragDepth.current = Math.max(0, dragDepth.current - 1); if (!dragDepth.current) setPageDrag(false); };
  const onDrop = event => { if (!pageDrag) return; event.preventDefault(); dragDepth.current = 0; setPageDrag(false); addFiles(event.dataTransfer.files); };

  const openIndex = media.findIndex(asset => asset.id === detail?.id);
  const missing = summary?.missing_alt ?? 0;
  const filtered = Boolean(filters.q || filters.missing_alt || filters.source);
  const onPageItems = media.length;

  return (
    <div className={`dlib-page dlib-media ${pageDrag ? 'is-dragging' : ''}`} onDragEnter={onDragEnter} onDragLeave={onDragLeave} onDragOver={event => { if (pageDrag) event.preventDefault(); }} onDrop={onDrop}>
      <AdminPageHeader
        eyebrow="Content library"
        title="Media Library"
        text="Browse imported WordPress images, upload new image files, or register an external image URL. Click any image to edit its title, alternative text and caption."
        actions={canCreate && <button type="button" className="admin-button" onClick={() => fileRef.current?.click()}><Upload size={15} /> Upload images</button>}
      />
      {notice && <AdminNotice type="success">{notice}</AdminNotice>}{error && <AdminNotice type="error">{error}</AdminNotice>}

      <section className="dash-stat-grid dlib-stats" aria-label="Media overview">
        <StatCard icon={Images} label="Images" value={summary?.total ?? '—'} hint="In the library" loading={!summary && status === 'loading'} />
        <button type="button" className={`dash-stat dlib-stat-button ${missing ? 'dash-stat-amber' : 'dash-stat-blue'} ${filters.missing_alt ? 'is-active' : ''}`} onClick={() => updateFilters({ missing_alt: filters.missing_alt ? '' : '1' })} aria-pressed={Boolean(filters.missing_alt)}>
          <span className="dash-stat-icon" aria-hidden="true"><AlertTriangle size={19} /></span>
          <span className="dash-stat-copy"><small>Missing alt text</small><strong>{summary ? missing : '—'}</strong><em>{filters.missing_alt ? 'Showing these · click to show all' : 'Click to review'}</em></span>
        </button>
        <StatCard icon={LayoutGrid} label="Showing" value={pagination?.total_items ?? '—'} hint={filtered ? 'Matching your filters' : 'All images'} loading={!pagination && status === 'loading'} />
        <StatCard icon={Globe2} label="Described" value={summary ? Math.max(0, summary.total - missing) : '—'} hint={summary?.total ? `${Math.round(((summary.total - missing) / summary.total) * 100)}% have alt text` : 'Accessible images'} loading={!summary && status === 'loading'} />
      </section>

      {canCreate && (
        <section className="dashboard-card dlib-add-card media-upload" aria-labelledby="dlib-add-title">
          <div className="dlib-card-head">
            <h2 id="dlib-add-title"><ImagePlus size={18} aria-hidden="true" /> Add Image</h2>
            <Segmented label="How to add" value={addMode} onChange={setAddMode} options={[{ id: 'upload', label: 'Upload files', icon: UploadCloud }, { id: 'url', label: 'External URL', icon: Link2 }]} />
          </div>
          {addMode === 'upload' ? (
            <form onSubmit={uploadQueue}>
              <label className="dlib-dropzone" onDragOver={event => event.preventDefault()} onDrop={event => { event.preventDefault(); event.stopPropagation(); dragDepth.current = 0; setPageDrag(false); addFiles(event.dataTransfer.files); }}>
                <UploadCloud size={28} aria-hidden="true" />
                <strong>Drop images here, or <span>browse your computer</span></strong>
                <small>JPG, PNG, WEBP or GIF · up to 8 MB each · several files at once · a WebP copy is created automatically</small>
                <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp,image/gif" multiple onChange={event => { addFiles(event.target.files); event.target.value = ''; }} aria-label="Upload Image" />
              </label>
              {queue.length > 0 && (
                <ul className="dlib-queue" aria-label="Images waiting to upload">
                  {queue.map(item => (
                    <li key={item.id} className={`is-${item.status}`}>
                      {item.preview ? <img src={item.preview} alt="" /> : <span className="dash-media-skeleton" aria-hidden="true" />}
                      <div className="dlib-queue-fields">
                        <label>Image Title<input value={item.title} onChange={event => updateQueue(item.id, { title: event.target.value })} disabled={item.status === 'uploading' || item.status === 'invalid'} /></label>
                        <label>Alternative Text<input value={item.alt_text} onChange={event => updateQueue(item.id, { alt_text: event.target.value })} placeholder="Describe the image for accessibility" disabled={item.status === 'uploading' || item.status === 'invalid'} /></label>
                      </div>
                      <div className="dlib-queue-status">
                        <small>{item.file.name} · {formatBytes(item.file.size)}</small>
                        {item.status === 'uploading' && <span className="dlib-progress" role="progressbar" aria-valuenow={item.progress} aria-valuemin="0" aria-valuemax="100" aria-label={`Uploading ${item.file.name}`}><b style={{ width: `${item.progress}%` }} /></span>}
                        {item.status === 'uploading' && <small>{item.progress < 100 ? `Uploading ${item.progress}%` : 'Optimising…'}</small>}
                        {item.error && <small className="dlib-error-text" role="alert">{item.error}</small>}
                        {!item.alt_text && item.status === 'queued' && <small className="dlib-hint-text">Add alt text now to save a step later.</small>}
                      </div>
                      <button type="button" className="dash-icon-button" onClick={() => removeQueued(item.id)} disabled={item.status === 'uploading'} aria-label={`Remove ${item.file.name} from the upload list`}><X size={16} /></button>
                    </li>
                  ))}
                </ul>
              )}
              <div className="dlib-add-actions">
                <span>{queue.length ? `${pendingQueue.length} ready to upload${queue.some(item => item.status === 'invalid') ? ' · invalid files are skipped' : ''}` : 'Tip: you can also drop files anywhere on this page.'}</span>
                {queue.length > 0 && <button type="button" className="admin-button admin-button-secondary" onClick={clearQueue} disabled={uploading}>Clear list</button>}
                <button className="admin-button" disabled={uploading}>{uploading ? <Loader2 size={15} className="spin" /> : <Upload size={15} />} Add to Library</button>
              </div>
            </form>
          ) : (
            <form onSubmit={addExternal}>
              <div className="admin-form-grid dlib-url-grid">
                <label>External Image URL<input name="url" type="url" required value={external.url} onChange={event => setExternal({ ...external, url: event.target.value })} placeholder="https://..." /></label>
                <label>Image Title<input name="title" value={external.title} onChange={event => setExternal({ ...external, title: event.target.value })} /></label>
                <label>Alternative Text<input name="alt_text" value={external.alt_text} onChange={event => setExternal({ ...external, alt_text: event.target.value })} placeholder="Describe the image for accessibility" /></label>
              </div>
              <div className="dlib-add-actions"><span>The image stays hosted at its original address. Only trusted https:// links are accepted.</span><button className="admin-button"><Upload size={15} /> Add to Library</button></div>
            </form>
          )}
        </section>
      )}

      <section className="dashboard-card dlib-library">
        <div className="dlib-toolbar">
          <form className="dash-search-field" role="search" onSubmit={event => { event.preventDefault(); updateFilters({ q: search.trim() }); }}>
            <Search size={16} aria-hidden="true" />
            <input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search image titles, alt text, captions or URLs" aria-label="Search media" />
            {search && <button type="button" className="dlib-clear" onClick={() => setSearch('')} aria-label="Clear search"><X size={14} /></button>}
          </form>
          <Segmented label="Alt text filter" value={filters.missing_alt ? 'missing' : 'all'} onChange={value => updateFilters({ missing_alt: value === 'missing' ? '1' : '' })} options={[{ id: 'all', label: 'All', count: summary?.total }, { id: 'missing', label: 'Missing alt text', count: summary?.missing_alt }]} />
          <select value={filters.source} onChange={event => updateFilters({ source: event.target.value })} aria-label="Image source">
            <option value="">All sources</option><option value="upload">Uploaded files</option><option value="external">External URLs</option><option value="wordpress">WordPress imports</option>
          </select>
          <select value={filters.sort} onChange={event => updateFilters({ sort: event.target.value })} aria-label="Sort images">
            <option value="newest">Newest first</option><option value="oldest">Oldest first</option><option value="title">Title A–Z</option>
          </select>
          <Segmented label="Layout" value={view} onChange={changeView} options={[{ id: 'grid', label: 'Grid', icon: LayoutGrid, iconOnly: true }, { id: 'list', label: 'List', icon: List, iconOnly: true }]} />
        </div>

        {(canDelete || media.length > 0) && (
          <div className={`dlib-selectbar ${selection.size ? 'has-selection' : ''}`}>
            <button type="button" className="dlib-link-button" onClick={selectAll} disabled={!media.length}>{allSelected ? <CheckSquare size={15} /> : <Square size={15} />} {allSelected ? 'Clear selection' : 'Select page'}</button>
            <span role="status">{selection.size ? `${selection.size} selected` : `${onPageItems} on this page${status === 'refreshing' ? ' · updating…' : ''}`}</span>
            {selection.size > 0 && <>
              <button type="button" className="admin-button admin-button-secondary" onClick={bulkCopy}><Copy size={14} /> Copy URLs</button>
              {canDelete && <button type="button" className="admin-button admin-button-danger" onClick={bulkDelete}><Trash2 size={14} /> Delete selected</button>}
            </>}
          </div>
        )}

        {status === 'loading' ? (
          <div className="dlib-media-grid" aria-busy="true">{Array.from({ length: 12 }, (_, index) => <span className="dlib-skeleton" key={index} />)}</div>
        ) : !media.length ? (
          <StateBlock type="empty" title={filters.missing_alt && !filters.q ? 'Every image has alt text' : 'No images found'} text={filtered ? 'Change the search text or filters.' : 'Upload an image to start your library.'} action={filtered && <button type="button" className="admin-button admin-button-secondary" onClick={() => { setSearch(''); updateFilters({ q: '', missing_alt: '', source: '' }); }}>Clear filters</button>} />
        ) : view === 'grid' ? (
          <div className="dlib-media-grid media-grid">
            {media.map(asset => (
              <article className={`media-card dlib-media-card ${selection.has(asset.id) ? 'is-selected' : ''}`} key={asset.id}>
                <button type="button" className="dlib-media-open" onClick={() => setDetail(asset)} aria-label={`Open details for ${asset.title || 'untitled image'}`}>
                  <span className="media-thumb dlib-thumb">{asset.url ? <img src={optimizedImageUrl(asset.url, true)} alt={asset.alt_text || asset.title} loading="lazy" /> : <ImageOff size={22} />}</span>
                </button>
                <label className="dlib-check" title="Select image"><input type="checkbox" checked={selection.has(asset.id)} onChange={() => toggleSelect(asset.id)} aria-label={`Select ${asset.title || 'image'}`} /></label>
                <div className="dlib-media-meta">
                  <strong title={asset.title}>{asset.title || 'Untitled image'}</strong>
                  <small className={asset.alt_text ? '' : 'is-missing'}>{asset.alt_text || <><AlertTriangle size={11} aria-hidden="true" /> No alternative text</>}</small>
                  <div className="dlib-media-actions">
                    <button type="button" className="dlib-icon-text" onClick={() => copy(asset.url)}><Copy size={14} /> Copy URL</button>
                    <ActionMenu label={`More actions for ${asset.title || 'image'}`} items={[
                      { label: canWrite ? 'Edit details' : 'View details', icon: Pencil, onClick: () => setDetail(asset) },
                      { label: 'Open original', icon: ExternalLink, href: asset.url, external: true },
                      canDelete && { divider: true },
                      canDelete && { label: 'Delete', icon: Trash2, danger: true, onClick: () => remove(asset) },
                    ]} />
                  </div>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="dashboard-table-wrap">
            <table className="dashboard-table dlib-table">
              <thead><tr><th className="dlib-col-check"><input type="checkbox" checked={allSelected} onChange={selectAll} aria-label="Select all images on this page" /></th><th>Image</th><th>Alternative text</th><th>Source</th><th>Added</th><th><span className="dlib-sr">Actions</span></th></tr></thead>
              <tbody>
                {media.map(asset => (
                  <tr key={asset.id} className={selection.has(asset.id) ? 'is-selected' : ''}>
                    <td className="dlib-col-check"><input type="checkbox" checked={selection.has(asset.id)} onChange={() => toggleSelect(asset.id)} aria-label={`Select ${asset.title || 'image'}`} /></td>
                    <td data-label="Image" className="dlib-cell-main"><button type="button" className="dlib-row-title" onClick={() => setDetail(asset)}><span className="dlib-row-thumb">{asset.url ? <img src={optimizedImageUrl(asset.url, true)} alt="" loading="lazy" /> : <ImageOff size={16} />}</span><span><strong>{asset.title || 'Untitled image'}</strong><small>{fileName(asset.url)}</small></span></button></td>
                    <td data-label="Alternative text">{asset.alt_text ? <span className="dlib-clamp">{asset.alt_text}</span> : <span className="dlib-missing-pill"><AlertTriangle size={12} /> Missing</span>}</td>
                    <td data-label="Source">{SOURCE_LABELS[asset.source] || '—'}</td>
                    <td data-label="Added">{shortDate(asset.created_at)}</td>
                    <td className="dlib-row-actions">
                      <button type="button" className="dash-icon-button" onClick={() => copy(asset.url)} aria-label={`Copy URL of ${asset.title || 'image'}`} title="Copy URL"><Copy size={15} /></button>
                      <ActionMenu label={`More actions for ${asset.title || 'image'}`} items={[
                        { label: canWrite ? 'Edit details' : 'View details', icon: Pencil, onClick: () => setDetail(asset) },
                        { label: 'Open original', icon: ExternalLink, href: asset.url, external: true },
                        canDelete && { divider: true },
                        canDelete && { label: 'Delete', icon: Trash2, danger: true, onClick: () => remove(asset) },
                      ]} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <AdminPagination pagination={pagination} onPage={page => { setSelection(new Set()); setFilters(current => ({ ...current, page })); }} />
      </section>

      {pageDrag && <div className="dlib-drop-overlay" aria-hidden="true"><UploadCloud size={40} /><strong>Drop to add images to the upload list</strong></div>}

      <MediaDetailDrawer
        asset={detail}
        canWrite={canWrite}
        canDelete={canDelete}
        onClose={() => setDetail(null)}
        onPrev={openIndex > 0 ? () => setDetail(media[openIndex - 1]) : null}
        onNext={openIndex >= 0 && openIndex < media.length - 1 ? () => setDetail(media[openIndex + 1]) : null}
        position={openIndex >= 0 ? `${openIndex + 1} of ${media.length} on this page` : ''}
        onCopy={copy}
        onDelete={async (asset, usage) => { if (await remove(asset, usage)) setDetail(null); }}
        onSaved={saved => { setMedia(current => current.map(item => item.id === saved.id ? { ...item, ...saved } : item)); setDetail(current => current ? { ...current, ...saved } : current); flash('Image details saved.'); load(filters); }}
        onError={setError}
      />
    </div>
  );
}

function MediaDetailDrawer({ asset, canWrite, canDelete, onClose, onPrev, onNext, position, onCopy, onDelete, onSaved, onError }) {
  const [form, setForm] = useState({ title: '', alt_text: '', caption: '' });
  const [dimensions, setDimensions] = useState(null);
  const [usage, setUsage] = useState(null);
  const [saving, setSaving] = useState(false);
  const assetId = asset?.id;

  useEffect(() => {
    if (!asset) return undefined;
    setForm({ title: asset.title || '', alt_text: asset.alt_text || '', caption: asset.caption || '' });
    setDimensions(null);
    setUsage(null);
    let active = true;
    DashboardApi.getMedia({ id: asset.id, usage: 1 }).then(data => { if (active) setUsage(data.results?.[0]?.usage || { total: 0, posts: [] }); }).catch(() => { if (active) setUsage(undefined); });
    return () => { active = false; };
  }, [assetId]); // eslint-disable-line react-hooks/exhaustive-deps

  const dirty = Boolean(asset) && (form.title !== (asset.title || '') || form.alt_text !== (asset.alt_text || '') || form.caption !== (asset.caption || ''));
  useUnsavedWarning(dirty);

  const close = () => { if (dirty && !window.confirm('Discard unsaved changes to this image?')) return; onClose(); };
  const go = handler => { if (dirty && !window.confirm('Discard unsaved changes to this image?')) return; handler(); };
  const save = async event => {
    event.preventDefault();
    if (!canWrite) return;
    setSaving(true);
    const body = new FormData();
    body.append('title', form.title.trim());
    body.append('alt_text', form.alt_text.trim());
    body.append('caption', form.caption.trim());
    try {
      const data = await DashboardApi.saveMedia(body, asset.id);
      onSaved(data.media || { ...asset, ...form });
    } catch (err) { onError(err.message); }
    finally { setSaving(false); }
  };

  const meta = asset ? [
    ['Dimensions', dimensions ? `${dimensions.w} × ${dimensions.h} px` : 'Measuring…'],
    ['Format', extension(asset.url) || '—'],
    ['Source', SOURCE_LABELS[asset.source] || (asset.wordpress_id ? 'WordPress import' : '—')],
    ['Added', shortDate(asset.created_at)],
    asset.wordpress_id ? ['WordPress ID', asset.wordpress_id] : null,
  ].filter(Boolean) : [];

  return (
    <Drawer open={Boolean(asset)} onClose={close} width={600} title={asset?.title || 'Untitled image'} subtitle={position || 'Image details'}
      footer={asset && <>
        {canDelete && <button type="button" className="admin-button admin-button-danger dlib-footer-start" onClick={() => onDelete(asset, usage)}><Trash2 size={15} /> Delete</button>}
        <button type="button" className="admin-button admin-button-secondary" onClick={close}>{dirty ? 'Cancel' : 'Close'}</button>
        {canWrite && <button className="admin-button" form="dlib-media-form" disabled={saving || !dirty}>{saving ? <Loader2 size={15} className="spin" /> : null} Save details</button>}
      </>}>
      {asset && <>
        <div className="dlib-preview">
          {asset.url ? <img key={asset.id} src={asset.url} alt={asset.alt_text || ''} onLoad={event => setDimensions({ w: event.currentTarget.naturalWidth, h: event.currentTarget.naturalHeight })} /> : <ImageOff size={32} />}
          {(onPrev || onNext) && <div className="dlib-preview-nav">
            <button type="button" className="dash-icon-button" onClick={() => go(onPrev)} disabled={!onPrev} aria-label="Previous image"><ChevronLeft size={18} /></button>
            <button type="button" className="dash-icon-button" onClick={() => go(onNext)} disabled={!onNext} aria-label="Next image"><ChevronRight size={18} /></button>
          </div>}
        </div>
        <dl className="dlib-meta-grid">{meta.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>

        <div className="dlib-url-row">
          <label className="dlib-field-label" htmlFor="dlib-media-url">Image URL</label>
          <div><input id="dlib-media-url" readOnly value={asset.url || ''} onFocus={event => event.target.select()} /><button type="button" className="admin-button admin-button-secondary" onClick={() => onCopy(asset.url)}><Copy size={14} /> Copy URL</button><a className="admin-button admin-button-secondary" href={asset.url} target="_blank" rel="noreferrer"><ExternalLink size={14} /> Open original</a></div>
        </div>

        <form id="dlib-media-form" className="dlib-form" onSubmit={save}>
          <label>Image Title<input name="title" value={form.title} onChange={event => setForm({ ...form, title: event.target.value })} disabled={!canWrite} /></label>
          <label>Alternative Text
            <textarea name="alt_text" rows="2" value={form.alt_text} onChange={event => setForm({ ...form, alt_text: event.target.value })} placeholder="Describe what the image shows" disabled={!canWrite} maxLength={500} />
            {form.alt_text.trim()
              ? <small>{form.alt_text.trim().length}/500 characters · used by screen readers and search engines.</small>
              : <small className="dlib-alt-hint"><AlertTriangle size={13} aria-hidden="true" /> Missing alt text. Describe what the image shows and why it matters (for example “Bar chart comparing response rates by age group”). Leave it empty only for purely decorative images.</small>}
          </label>
          <label>Caption<textarea name="caption" rows="3" value={form.caption} onChange={event => setForm({ ...form, caption: event.target.value })} placeholder="Optional caption shown with the image" disabled={!canWrite} /></label>
          {dirty && <p className="dlib-dirty-note" role="status">Unsaved changes</p>}
        </form>

        <section className="dlib-usage" aria-label="Where this image is used">
          <h3>Where it’s used</h3>
          {usage === null ? <p className="dlib-muted"><Loader2 size={14} className="spin" /> Checking articles, authors and categories…</p>
            : usage === undefined ? <p className="dlib-muted">Usage could not be checked.</p>
            : !usage.total ? <p className="dlib-muted">Not found in any article, author profile or category. Safe to delete.</p>
            : <>
              <p className="dlib-muted">Used in {usage.post_count || 0} {usage.post_count === 1 ? 'article/page' : 'articles/pages'}{usage.authors ? `, ${usage.authors} author ${usage.authors === 1 ? 'profile' : 'profiles'}` : ''}{usage.categories ? `, ${usage.categories} ${usage.categories === 1 ? 'category' : 'categories'}` : ''}.</p>
              <ul>{usage.posts.map(post => <li key={post.id}><Link to={`/dashboard/posts?type=${post.post_type === 'page' ? 'page' : 'post'}&edit=${post.id}`}>{post.title}</Link></li>)}</ul>
              {usage.post_count > usage.posts.length && <p className="dlib-muted">…and {usage.post_count - usage.posts.length} more.</p>}
            </>}
        </section>
      </>}
    </Drawer>
  );
}
