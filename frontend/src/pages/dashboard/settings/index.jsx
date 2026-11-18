import { AlertTriangle, BookOpen, ExternalLink, Image as ImageIcon, KeyRound, RotateCcw, Save, Search, ShieldCheck, X } from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useOutletContext } from 'react-router-dom';
import { DashboardApi } from '../../../api/dashboardApi';
import AdminNotice from '../../../components/dashboard/AdminNotice';
import AdminPageHeader from '../../../components/dashboard/AdminPageHeader';
import MediaPicker from '../../../components/dashboard/MediaPicker';
import { EDITABLE_SETTINGS, mergeEditableSettings } from '../../../config/editableSettings';
import { hasPermission } from '../users/adminShared';
import '../../../styles/dashboard/dash-admin.css';

const slug = value => `settings-${String(value).toLowerCase().replace(/[^a-z0-9]+/g, '-')}`;
const isLinkKey = key => /(_url|_link|_href)$/.test(key) || key.includes('action_url');
const isImageKey = key => /(image_url|logo_url)$/.test(key);
const isToggle = item => /_enabled$/.test(item.key) && ['true', 'false', ''].includes(String(item.value ?? '').toLowerCase());
const linkProblem = value => (value && !/^(https?:\/\/|mailto:|tel:|\/|#)/i.test(value.trim()) ? 'Use an http(s), mailto or tel link, or a path starting with "/".' : '');

// The 38 setting groups, arranged into a few areas for the section index.
function areaOf(group) {
  if (group === 'General' || group === 'Shared Page Visuals' || group === '404 Page') return 'Site-wide';
  if (/^Home/.test(group)) return 'Homepage';
  if (/ Page$/.test(group)) return 'Page headers';
  return 'Page content';
}
const AREA_ORDER = ['Site-wide', 'Homepage', 'Page headers', 'Page content'];

export default function DashboardSettingsPage() {
  const { user, bootstrap } = useOutletContext() || {};
  const canWrite = hasPermission(user, bootstrap, 'settings.edit');
  const [settings, setSettings] = useState(EDITABLE_SETTINGS);
  const [baseline, setBaseline] = useState(() => Object.fromEntries(EDITABLE_SETTINGS.map(item => [item.key, item.value || ''])));
  const [roles, setRoles] = useState(null);
  const [docs, setDocs] = useState(null);
  const [status, setStatus] = useState('');
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [onlyChanged, setOnlyChanged] = useState(false);
  const [activeGroup, setActiveGroup] = useState('');
  const [picker, setPicker] = useState(null);
  const formRef = useRef(null);

  useEffect(() => {
    let active = true;
    DashboardApi.getSettings()
      .then(data => {
        if (!active) return;
        const merged = mergeEditableSettings(data.results || []);
        setSettings(merged);
        setBaseline(Object.fromEntries(merged.map(item => [item.key, item.value || ''])));
      })
      .catch(err => { if (active) setError(err.message); });
    Promise.allSettled([DashboardApi.getRolesPermissions(), DashboardApi.getDocs()]).then(results => {
      if (!active) return;
      const [roleResult, docResult] = results;
      if (roleResult.status === 'fulfilled') setRoles(roleResult.value);
      if (docResult.status === 'fulfilled') setDocs(docResult.value);
    });
    return () => { active = false; };
  }, []);

  const changedKeys = useMemo(() => new Set(settings.filter(item => (item.value || '') !== (baseline[item.key] ?? '')).map(item => item.key)), [settings, baseline]);
  const dirty = changedKeys.size > 0;
  const groups = useMemo(() => [...new Set(settings.map(item => item.group))], [settings]);
  const q = query.trim().toLowerCase();
  const visibleByGroup = useMemo(() => Object.fromEntries(groups.map(group => [group, settings.filter(item => item.group === group
    && (!onlyChanged || changedKeys.has(item.key))
    && (!q || `${item.label} ${item.key} ${item.value || ''} ${group}`.toLowerCase().includes(q)))])), [groups, settings, onlyChanged, changedKeys, q]);
  const visibleGroups = groups.filter(group => visibleByGroup[group].length);
  const matchCount = visibleGroups.reduce((sum, group) => sum + visibleByGroup[group].length, 0);
  const invalid = settings.filter(item => isLinkKey(item.key) && linkProblem(item.value || ''));

  const update = (key, value) => setSettings(current => current.map(item => item.key === key ? { ...item, value } : item));
  const resetField = key => update(key, baseline[key] ?? '');
  const discard = () => { if (window.confirm(`Discard ${changedKeys.size} unsaved ${changedKeys.size === 1 ? 'change' : 'changes'}?`)) setSettings(current => current.map(item => ({ ...item, value: baseline[item.key] ?? '' }))); };

  const saveSettings = useCallback(async event => {
    event?.preventDefault();
    setStatus('saving');
    setNotice('');
    setError('');
    try {
      await DashboardApi.saveSettings(settings);
      setBaseline(Object.fromEntries(settings.map(item => [item.key, item.value || ''])));
      setNotice('Public settings saved. Refresh the public website to see the changes.');
    } catch (err) {
      setError(err.message);
    } finally {
      setStatus('');
    }
  }, [settings]);

  // Ctrl/Cmd+S saves; leaving with unsaved changes asks first.
  useEffect(() => {
    const onKey = event => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
        event.preventDefault();
        if (canWrite && status !== 'saving') formRef.current?.requestSubmit();
      }
    };
    const onUnload = event => { if (dirty) { event.preventDefault(); event.returnValue = ''; } };
    window.addEventListener('keydown', onKey);
    window.addEventListener('beforeunload', onUnload);
    return () => { window.removeEventListener('keydown', onKey); window.removeEventListener('beforeunload', onUnload); };
  }, [canWrite, status, dirty]);

  // Highlight the group currently in view in the index.
  useEffect(() => {
    const sections = [...document.querySelectorAll('.dash-adm-settings-group')];
    if (!sections.length || typeof IntersectionObserver === 'undefined') return undefined;
    const observer = new IntersectionObserver(entries => {
      const visible = entries.filter(entry => entry.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
      if (visible) setActiveGroup(visible.target.dataset.group);
    }, { rootMargin: '-90px 0px -60% 0px' });
    sections.forEach(section => observer.observe(section));
    return () => observer.disconnect();
  }, [visibleGroups.join('|'), roles, docs]); // eslint-disable-line react-hooks/exhaustive-deps

  const jump = id => { document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' }); };
  const indexAreas = AREA_ORDER.map(area => [area, visibleGroups.filter(group => areaOf(group) === area)]).filter(([, list]) => list.length);

  const renderField = item => {
    const value = item.value || '';
    const changed = changedKeys.has(item.key);
    const problem = isLinkKey(item.key) ? linkProblem(value) : '';
    const id = `setting-${item.key}`;
    return (
      <div className={`dash-adm-setting ${changed ? 'is-changed' : ''} ${value.length > 100 || /_text$/.test(item.key) ? 'is-wide' : ''}`} key={item.key}>
        <div className="dash-adm-setting-label">
          <label htmlFor={id}>{item.label}</label>
          {changed && <button type="button" className="dash-adm-link" onClick={() => resetField(item.key)} title="Undo this change"><RotateCcw size={12} /> Undo</button>}
        </div>
        {isToggle(item) ? (
          <label className="dash-adm-toggle-row">
            <span className="dash-adm-switch"><input id={id} name={item.key} type="checkbox" checked={String(value).toLowerCase() !== 'false'} onChange={event => update(item.key, event.target.checked ? 'true' : 'false')} disabled={!canWrite} /><span aria-hidden="true" /></span>
            <span>{String(value).toLowerCase() !== 'false' ? 'Shown on the website' : 'Hidden'}</span>
          </label>
        ) : value.length > 100 ? (
          <textarea id={id} name={item.key} value={value} onChange={event => update(item.key, event.target.value)} rows="4" readOnly={!canWrite} />
        ) : (
          <div className={isImageKey(item.key) ? 'dash-adm-image-field' : ''}>
            {isImageKey(item.key) && <span className="dash-adm-image-thumb">{value ? <img src={value} alt="" loading="lazy" /> : <ImageIcon size={16} />}</span>}
            <input id={id} name={item.key} value={value} onChange={event => update(item.key, event.target.value)} aria-invalid={Boolean(problem)} readOnly={!canWrite} />
            {isImageKey(item.key) && canWrite && <button type="button" className="admin-button admin-button-secondary" onClick={() => setPicker(item.key)}>Choose</button>}
          </div>
        )}
        <small className="dash-adm-setting-meta"><code>{item.key}</code>{problem && <span className="form-field-error"><AlertTriangle size={12} /> {problem}</span>}</small>
      </div>
    );
  };

  return (
    <div className="dash-adm-page dash-adm-settings-page">
      <AdminPageHeader
        eyebrow="System"
        title="Settings"
        text="Edit public website settings, dashboard role notes, and API documentation. Premium controls now have their own page."
        actions={<a className="admin-button admin-button-secondary" href="/" target="_blank" rel="noreferrer"><ExternalLink size={15} /> View Website</a>}
      />
      {notice && <AdminNotice type="success">{notice}</AdminNotice>}
      {error && <AdminNotice type="error">{error}</AdminNotice>}
      {!canWrite && <AdminNotice type="info">You can view settings, but saving needs the settings.write permission.</AdminNotice>}

      <div className="dash-adm-settings">
        <aside className="dash-adm-settings-index" aria-label="Settings sections">
          <label className="dash-search-field"><Search size={16} aria-hidden="true" /><input type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder={`Search ${settings.length} settings`} aria-label="Search settings" />{query && <button type="button" className="dash-adm-clear" onClick={() => setQuery('')} aria-label="Clear search"><X size={14} /></button>}</label>
          <label className="dash-adm-onlychanged"><input type="checkbox" checked={onlyChanged} onChange={event => setOnlyChanged(event.target.checked)} /> Only unsaved changes{dirty ? ` (${changedKeys.size})` : ''}</label>
          <nav>
            {indexAreas.map(([area, list]) => (
              <div key={area}>
                <span className="dash-adm-index-area">{area}</span>
                {list.map(group => {
                  const changes = visibleByGroup[group].filter(item => changedKeys.has(item.key)).length;
                  return <button type="button" key={group} className={activeGroup === group ? 'is-active' : ''} onClick={() => jump(slug(group))}><span>{group}</span>{changes ? <i className="dash-adm-index-dot" title={`${changes} unsaved`} /> : <small>{visibleByGroup[group].length}</small>}</button>;
                })}
              </div>
            ))}
            {!q && !onlyChanged && <div>
              <span className="dash-adm-index-area">Dashboard</span>
              {roles && <button type="button" className={activeGroup === 'roles' ? 'is-active' : ''} onClick={() => jump('settings-roles')}><span>Roles and permissions</span></button>}
              {docs && <button type="button" className={activeGroup === 'docs' ? 'is-active' : ''} onClick={() => jump('settings-docs')}><span>API documentation</span></button>}
            </div>}
          </nav>
        </aside>

        <div className="dash-adm-settings-main">
          {(q || onlyChanged) && <p className="dash-adm-hint">{matchCount ? `${matchCount} matching ${matchCount === 1 ? 'setting' : 'settings'} in ${visibleGroups.length} ${visibleGroups.length === 1 ? 'section' : 'sections'}.` : 'No settings match.'}</p>}
          <form ref={formRef} onSubmit={saveSettings} className="dash-adm-settings-form">
            {visibleGroups.map(group => (
              <section className="dashboard-card dash-adm-settings-group" key={group} id={slug(group)} data-group={group}>
                <header><span className="dash-adm-index-area">{areaOf(group)}</span><h2>{group}</h2></header>
                <div className="dash-adm-settings-grid">{visibleByGroup[group].map(renderField)}</div>
              </section>
            ))}
            <div className={`dash-adm-savebar ${dirty ? 'is-dirty' : ''}`} role="region" aria-label="Save settings">
              <span className="dash-adm-savebar-status">
                {status === 'saving' ? 'Saving…' : dirty ? <><i aria-hidden="true" />{changedKeys.size} unsaved {changedKeys.size === 1 ? 'change' : 'changes'}</> : 'All changes saved'}
                {invalid.length > 0 && <em><AlertTriangle size={13} /> {invalid.length} link{invalid.length === 1 ? '' : 's'} to check</em>}
              </span>
              <span className="dash-adm-savebar-actions">
                <kbd className="dash-adm-kbd">Ctrl/⌘ S</kbd>
                {dirty && <button type="button" className="admin-button admin-button-secondary" onClick={discard}>Discard</button>}
                <button className="admin-button" disabled={status === 'saving' || !canWrite}><Save size={15} />{status === 'saving' ? 'Saving...' : 'Save Public Settings'}</button>
              </span>
            </div>
          </form>

          {roles && !q && !onlyChanged && (
            <section className="dashboard-card dash-adm-settings-group" id="settings-roles" data-group="roles">
              <header><span className="dash-adm-index-area">Dashboard</span><h2>Roles and Permissions</h2><p className="dash-adm-hint">Your role: <strong>{roles.current_role}</strong>. {roles.roles.length} dashboard roles are set up.</p></header>
              <p>Which sections, pages and actions each role has is managed on its own page.</p>
              <Link className="admin-button admin-button-secondary" to="/dashboard/roles"><ShieldCheck size={15} /> Open Roles &amp; Permissions</Link>
            </section>
          )}

          {docs && !q && !onlyChanged && (
            <section className="dashboard-card dash-adm-settings-group" id="settings-docs" data-group="docs">
              <header><span className="dash-adm-index-area">Dashboard</span><h2>Dashboard API Documentation</h2><p className="dash-adm-hint"><KeyRound size={13} /> {docs.auth}</p></header>
              {docs.patterns && <dl className="dash-adm-details dash-adm-patterns">{Object.entries(docs.patterns).map(([key, text]) => <div key={key}><dt>{key}</dt><dd>{text}</dd></div>)}</dl>}
              <div className="dash-adm-endpoints">{docs.endpoints.map(endpoint => <code key={`${endpoint.method}-${endpoint.path}`}><b className={`is-${endpoint.method.toLowerCase()}`}>{endpoint.method}</b> {endpoint.path}<small>{endpoint.module}</small></code>)}</div>
              <p className="editor-hint"><BookOpen size={13} /> New modules should follow the same pattern: model, serializer, permission, API route, frontend page, and export/report wiring.</p>
            </section>
          )}
        </div>
      </div>
      <MediaPicker open={Boolean(picker)} onClose={() => setPicker(null)} onSelect={asset => { update(picker, asset.url); setPicker(null); }} title="Choose an image for this setting" />
    </div>
  );
}
