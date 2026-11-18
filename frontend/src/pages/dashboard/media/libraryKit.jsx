// Small helpers shared by the content-library pages (media, categories, tags, authors, FAQ, website content).
import { useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import { API_BASE_URL } from '../../../api/apiClient';
import { permissionsAllow } from '../users/adminShared';

export const IMAGE_TYPES = new Set(['image/jpeg', 'image/png', 'image/webp', 'image/gif']);
export const IMAGE_MAX_SIZE = 8 * 1024 * 1024;

export const slugify = value => String(value || '').toLowerCase().trim().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

/** Create/edit/delete rights for one permission module (media, taxonomy, faq...). */
export function useLibraryPermissions(module = 'content') {
  const { user, bootstrap } = useOutletContext() || {};
  const has = permission => permissionsAllow(bootstrap?.permissions, permission, user?.is_superuser);
  // Before the session is known, keep controls available; the API still enforces every permission.
  const known = Boolean(user);
  return {
    canCreate: !known || has(`${module}.create`),
    canWrite: !known || has(`${module}.edit`),
    canDelete: !known || has(`${module}.delete`),
    canWriteSettings: !known || has('settings.edit'),
  };
}

/** Warn before leaving the page while a form has unsaved edits. */
export function useUnsavedWarning(dirty) {
  useEffect(() => {
    if (!dirty) return undefined;
    const onBeforeUnload = event => { event.preventDefault(); event.returnValue = ''; };
    window.addEventListener('beforeunload', onBeforeUnload);
    return () => window.removeEventListener('beforeunload', onBeforeUnload);
  }, [dirty]);
}

export async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const area = document.createElement('textarea');
    area.value = text;
    area.setAttribute('readonly', '');
    area.style.position = 'fixed';
    area.style.opacity = '0';
    document.body.appendChild(area);
    area.select();
    const ok = document.execCommand('copy');
    area.remove();
    return ok;
  }
}

export function validateImageFile(file) {
  if (!IMAGE_TYPES.has(file.type)) return 'Upload a JPG, PNG, WEBP, or GIF image.';
  if (file.size > IMAGE_MAX_SIZE) return 'Image uploads must be smaller than 8 MB.';
  return '';
}

export function formatBytes(bytes) {
  if (!bytes && bytes !== 0) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Upload a media FormData with progress events (fetch has no upload progress). */
export async function uploadMediaWithProgress(formData, onProgress) {
  const tokenResponse = await fetch(`${API_BASE_URL}/accounts/csrf/`, { credentials: 'include' });
  const tokenPayload = await tokenResponse.json().catch(() => ({}));
  if (!tokenResponse.ok || !tokenPayload.csrfToken) throw new Error('Could not retrieve the security token. Please refresh the page and try again.');
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open('POST', `${API_BASE_URL}/dashboard/media/save/`);
    request.withCredentials = true;
    request.setRequestHeader('X-CSRFToken', tokenPayload.csrfToken);
    request.upload.onprogress = event => { if (event.lengthComputable) onProgress?.(Math.round((event.loaded / event.total) * 100)); };
    request.onload = () => {
      let data = {};
      try { data = JSON.parse(request.responseText || '{}'); } catch { data = {}; }
      if (request.status >= 200 && request.status < 300) resolve(data);
      else reject(new Error(data.error || `Upload failed (${request.status})`));
    };
    request.onerror = () => reject(new Error('Could not connect to the API. Check your connection and try again.'));
    request.ontimeout = () => reject(new Error('The upload took too long. Please try again.'));
    request.timeout = 120000;
    request.send(formData);
  });
}

const ENTITIES = { amp: '&', lt: '<', gt: '>', quot: '"', '#39': "'", apos: "'", nbsp: ' ' };
/** Imported WordPress names can contain HTML entities such as &amp;; show them as text. */
export const decodeEntities = value => String(value || '').replace(/&(amp|lt|gt|quot|#39|apos|nbsp);/g, (_, name) => ENTITIES[name]);

export function initials(name) {
  return String(name || '?').replace(/^(dr|prof|mr|mrs|ms)\.?\s+/i, '').split(/\s+/).filter(Boolean).slice(0, 2).map(part => part[0]).join('').toUpperCase() || '?';
}

/** Compact segmented control (radio-group semantics) for view and filter switches. */
export function Segmented({ options, value, onChange, label }) {
  return (
    <div className="dlib-segmented" role="radiogroup" aria-label={label}>
      {options.map(option => {
        const Icon = option.icon;
        const active = value === option.id;
        return (
          <button key={option.id} type="button" role="radio" aria-checked={active} className={active ? 'is-active' : ''} onClick={() => onChange(option.id)} title={option.title || option.label}>
            {Icon && <Icon size={15} aria-hidden="true" />}
            {option.label && <span className={option.iconOnly ? 'dlib-sr' : ''}>{option.label}</span>}
            {option.count !== undefined && option.count !== null && <em>{option.count}</em>}
          </button>
        );
      })}
    </div>
  );
}

export function readStored(key, fallback) {
  try { return window.localStorage.getItem(key) || fallback; } catch { return fallback; }
}

export function writeStored(key, value) {
  try { window.localStorage.setItem(key, value); } catch { /* storage unavailable */ }
}
