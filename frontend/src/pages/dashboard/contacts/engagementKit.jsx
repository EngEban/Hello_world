import { Check, Copy } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { permissionsAllow } from '../users/adminShared';

/** Permission check against the dashboard bootstrap (superusers and '*' can do everything). */
export function usePermissions() {
  const context = useOutletContext() || {};
  const permissions = context.bootstrap?.permissions || [];
  const isSuperuser = Boolean(context.user?.is_superuser);
  return {
    user: context.user,
    can: permission => permissionsAllow(permissions, permission, isSuperuser),
  };
}

/** True while the viewport matches the query (used to switch reading pane <-> drawer). */
export function useMediaQuery(query) {
  const get = () => (typeof window !== 'undefined' && window.matchMedia ? window.matchMedia(query).matches : false);
  const [matches, setMatches] = useState(get);
  useEffect(() => {
    if (!window.matchMedia) return undefined;
    const media = window.matchMedia(query);
    const onChange = () => setMatches(media.matches);
    onChange();
    media.addEventListener('change', onChange);
    return () => media.removeEventListener('change', onChange);
  }, [query]);
  return matches;
}

export const label = value => String(value || '').replaceAll('_', ' ').replace(/^./, char => char.toUpperCase());

export function formatDateTime(value) {
  if (!value) return 'Not recorded';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Not recorded';
  return date.toLocaleString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

export function formatDate(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

export function relativeTime(value) {
  if (!value) return '';
  const minutes = Math.round((Date.now() - new Date(value).getTime()) / 60000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.round(hours / 24);
  if (days < 7) return `${days} d ago`;
  return new Date(value).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: days > 300 ? 'numeric' : undefined });
}

export function initials(name = '') {
  const parts = String(name).trim().split(/[\s@._-]+/).filter(Boolean);
  return ((parts[0]?.[0] || '?') + (parts[1]?.[0] || '')).toUpperCase();
}

export function Avatar({ name, size = 'md' }) {
  return <span className={`eng-avatar eng-avatar-${size}`} aria-hidden="true">{initials(name)}</span>;
}

/** Digits-only WhatsApp link, or '' when the number is unusable. */
export function whatsappHref(value) {
  const digits = String(value || '').replace(/\D/g, '');
  return digits.length >= 7 ? `https://wa.me/${digits}` : '';
}

export function mailtoHref(email, subject) {
  if (!email) return '';
  return `mailto:${email}${subject ? `?subject=${encodeURIComponent(subject)}` : ''}`;
}

/** Small button that copies text and briefly shows a check mark. */
export function CopyButton({ text, label: buttonLabel = 'Copy email', className = 'admin-button admin-button-secondary' }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try { await navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1600); } catch { setCopied(false); }
  };
  return <button type="button" className={className} onClick={copy} disabled={!text} aria-live="polite">{copied ? <Check size={15} /> : <Copy size={15} />} {copied ? 'Copied' : buttonLabel}</button>;
}

/** Segmented status control: one button per workflow status. */
export function StatusSteps({ statuses, value, onChange, disabled, name = 'Status' }) {
  return (
    <div className="eng-steps" role="group" aria-label={name}>
      {statuses.map(status => (
        <button key={status} type="button" className={value === status ? 'is-active' : ''} aria-pressed={value === status} disabled={disabled} onClick={() => value !== status && onChange(status)}>
          <span className={`eng-dot eng-dot-${status.replaceAll('_', '-')}`} aria-hidden="true" />{label(status)}
        </button>
      ))}
    </div>
  );
}

/** Definition list of label/value pairs; empty values are skipped. */
export function DetailList({ items }) {
  const rows = items.filter(([, value]) => value !== undefined && value !== null && value !== '');
  if (!rows.length) return null;
  return <dl className="eng-details">{rows.map(([term, value]) => <div key={term}><dt>{term}</dt><dd>{value}</dd></div>)}</dl>;
}
