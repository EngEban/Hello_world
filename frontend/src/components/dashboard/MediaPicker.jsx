import { useEffect, useRef, useState } from 'react';
import { Check, ImageOff, Loader2, Search, Upload, X } from 'lucide-react';
import { DashboardApi } from '../../api/dashboardApi';
import { optimizedImageUrl } from '../../utils/optimizedImages';

/**
 * Choose an image from the Media Library (or upload a new one) instead of
 * copying URLs by hand. Calls onSelect(asset) with the media record
 * ({ id, url, title, alt_text, ... }).
 */
export default function MediaPicker({ open, onClose, onSelect, title = 'Choose an image', canUpload = true }) {
  const [query, setQuery] = useState('');
  const [state, setState] = useState({ status: 'idle', items: [], pagination: null, error: '' });
  const [page, setPage] = useState(1);
  const [uploading, setUploading] = useState(false);
  const dialogRef = useRef(null);
  const searchRef = useRef(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) { dialog.showModal(); searchRef.current?.focus(); }
    if (!open && dialog.open) dialog.close();
  }, [open]);

  useEffect(() => {
    if (!open) return undefined;
    let active = true;
    const timer = setTimeout(() => {
      setState(current => ({ ...current, status: 'loading', error: '' }));
      DashboardApi.getMedia({ q: query.trim(), page })
        .then(data => { if (active) setState(current => ({ status: 'ready', items: page > 1 ? [...current.items, ...(data.results || [])] : (data.results || []), pagination: data.pagination, error: '' })); })
        .catch(error => { if (active) setState(current => ({ ...current, status: 'error', error: error.message })); });
    }, 250);
    return () => { active = false; clearTimeout(timer); };
  }, [open, query, page]);

  const upload = async event => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    const form = new FormData();
    form.append('file', file);
    form.append('title', file.name.replace(/\.[^.]+$/, ''));
    setUploading(true);
    try {
      const data = await DashboardApi.saveMedia(form);
      const asset = data.asset || data.media || data;
      if (asset?.url) { onSelect(asset); onClose(); }
      else { setPage(1); setQuery(''); }
    } catch (error) {
      setState(current => ({ ...current, error: error.message }));
    } finally {
      setUploading(false);
    }
  };

  return (
    <dialog ref={dialogRef} className="dash-media-picker" aria-label={title} onClose={onClose} onCancel={onClose}
      onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}>
      <div className="dash-media-picker-panel">
        <header>
          <h2>{title}</h2>
          <button type="button" className="dash-icon-button" onClick={onClose} aria-label="Close"><X size={18} /></button>
        </header>
        <div className="dash-media-picker-tools">
          <label className="dash-search-field">
            <Search size={16} aria-hidden="true" />
            <input ref={searchRef} value={query} onChange={event => { setQuery(event.target.value); setPage(1); }} placeholder="Search by title, alt text or file name" aria-label="Search media" />
          </label>
          {canUpload && (
            <label className="admin-button dash-upload-button">
              {uploading ? <Loader2 size={16} className="spin" /> : <Upload size={16} />}
              <span>{uploading ? 'Uploading…' : 'Upload new'}</span>
              <input type="file" accept="image/jpeg,image/png,image/webp,image/gif" onChange={upload} disabled={uploading} hidden />
            </label>
          )}
        </div>
        {state.error && <p className="dash-inline-error" role="alert">{state.error}</p>}
        <div className="dash-media-picker-grid" aria-busy={state.status === 'loading'}>
          {state.items.map(item => (
            <button type="button" key={item.id} className="dash-media-tile" onClick={() => { onSelect(item); onClose(); }} title={item.title || item.url}>
              {item.url ? <img src={optimizedImageUrl(item.url, true)} alt={item.alt_text || ''} loading="lazy" /> : <span className="dash-media-missing"><ImageOff size={20} /></span>}
              <span className="dash-media-tile-label">{item.title || 'Untitled image'}</span>
              <span className="dash-media-tile-check" aria-hidden="true"><Check size={14} /></span>
            </button>
          ))}
          {state.status === 'ready' && !state.items.length && <p className="dash-media-empty">No images match this search.</p>}
          {state.status === 'loading' && !state.items.length && Array.from({ length: 8 }, (_, index) => <span className="dash-media-skeleton" key={index} />)}
        </div>
        {state.pagination?.has_next && (
          <footer><button type="button" className="admin-button admin-button-secondary" disabled={state.status === 'loading'} onClick={() => setPage(current => current + 1)}>Load more</button></footer>
        )}
      </div>
    </dialog>
  );
}
