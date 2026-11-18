import { ExternalLink, Image as ImageIcon, ImagePlus, Loader2, RotateCcw, Save, Search, Undo2, Upload, X } from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { DashboardApi } from '../../../api/dashboardApi';
import AdminNotice from '../../../components/dashboard/AdminNotice';
import AdminPageHeader from '../../../components/dashboard/AdminPageHeader';
import MediaPicker from '../../../components/dashboard/MediaPicker';
import { BOOLEAN_SETTING_KEYS, CONTENT_STUDIO_PAGES, FONT_SETTING_KEYS, IMAGE_SETTING_KEYS, ORDER_SETTING_KEYS } from '../../../config/contentStudio';
import { EDITABLE_SETTINGS, mergeEditableSettings } from '../../../config/editableSettings';
import defaultHomepageHero from '../../../assets/homepage/global-research-atlas-hero-4k.webp';
import { slugify, useLibraryPermissions, useUnsavedWarning, validateImageFile } from '../media/libraryKit';
import '../../../styles/dashboard/dash-library.css';

const URL_KEY_PATTERN = /(_url|_link)$/;
const CONTENT_STUDIO_MANAGER_ACTIONS = {
  homepage: [
    ['Manage research resources', '/dashboard/posts'],
    ['Manage research categories', '/dashboard/categories'],
    ['Manage opportunities', '/dashboard/opportunities'],
    ['Edit visual assets', '/dashboard/media'],
  ],
  database: [
    ['Manage author profiles', '/dashboard/authors'],
    ['Manage database content', '/dashboard/posts'],
    ['Manage categories', '/dashboard/categories'],
    ['Manage media', '/dashboard/media'],
  ],
  tools: [
    ['Control premium tools', '/dashboard/premium-controls'],
    ['Manage tool images', '/dashboard/media'],
  ],
  consultation: [
    ['Manage services', '/dashboard/services'],
    ['Review service requests', '/dashboard/forms'],
  ],
  opportunities: [
    ['Manage opportunities', '/dashboard/opportunities'],
    ['Review applications', '/dashboard/forms'],
  ],
  team: [
    ['Manage team cards and Google Form links', '/dashboard/applications'],
    ['Review team applications', '/dashboard/forms'],
  ],
  'about-contact': [
    ['Manage FAQ items', '/dashboard/faq'],
    ['Review contact inbox', '/dashboard/contacts'],
    ['Manage media', '/dashboard/media'],
  ],
  'library-pages': [
    ['Manage articles and pages', '/dashboard/posts'],
    ['Manage categories', '/dashboard/categories'],
  ],
  learning: [
    ['Manage author profiles', '/dashboard/authors'],
    ['Manage learning articles', '/dashboard/posts'],
    ['Manage Mastering Research category', '/dashboard/categories'],
  ],
  'shared-visuals': [
    ['Open Media Library', '/dashboard/media'],
  ],
  global: [
    ['Open public settings', '/dashboard/settings'],
  ],
};
const PAGE_PATHS = { homepage: '/', database: '/database', tools: '/tools', learning: '/articles', consultation: '/consultation', opportunities: '/opportunities', team: '/join', 'about-contact': '/about', 'library-pages': '/questionnaires', 'shared-visuals': '/', global: '/' };
const GROUP_PATHS = [
  [/^About/, '/about'], [/^Contact/, '/contact'], [/^FAQ/, '/faq'], [/^Questionnaires/, '/questionnaires'], [/^404/, '/resref-page-not-found'],
  [/^Sample Size/, '/tools/sample-size-calculator'], [/^Reference Generator/, '/tools/reference-generator'], [/^Journal Finder/, '/tools/journal-finder'], [/^Research Analyzer/, '/tools/research-analyzer'],
];
const groupPath = (group, pageId) => GROUP_PATHS.find(([pattern]) => pattern.test(group))?.[1] || PAGE_PATHS[pageId] || '/';
const groupAnchor = group => `cs-${slugify(group)}`;
const groupTitle = (group, pageLabel) => group.replace(/^Homepage · /, '').replace(new RegExp(`^${pageLabel} `), '') || group;

function isSafeUrlValue(key, value) {
  const text = String(value || '').trim();
  if (!text || !URL_KEY_PATTERN.test(key)) return true;
  if (IMAGE_SETTING_KEYS.has(key)) return text.startsWith('/') || text.startsWith('http://') || text.startsWith('https://');
  return text.startsWith('/') || text.startsWith('#') || text.startsWith('mailto:') || text.startsWith('tel:') || text.startsWith('http://') || text.startsWith('https://');
}

function shouldUseTextarea(setting) {
  const key = setting.key.toLowerCase();
  const value = setting.value || '';
  return key.includes('_text') || key.includes('description') || value.length > 110;
}

function settingHelp(setting) {
  if (BOOLEAN_SETTING_KEYS.has(setting.key)) return 'Controls whether this section appears on the public website.';
  if (ORDER_SETTING_KEYS.has(setting.key)) return 'Sections display in ascending order. Use 10, 20, 30 and so on to leave room for future sections.';
  if (IMAGE_SETTING_KEYS.has(setting.key) && setting.key === 'homepage_hero_image_url') return 'This is the homepage map artwork. Leave the field empty to use the built-in 4K map, or upload/select a replacement.';
  if (IMAGE_SETTING_KEYS.has(setting.key)) return 'Upload or select a Media Library image. The page layout controls its crop and size.';
  if (FONT_SETTING_KEYS.has(setting.key)) return 'Use a CSS size such as clamp(40px, 5vw, 72px), 48px, or a numeric font weight like 800.';
  if (URL_KEY_PATTERN.test(setting.key)) return 'Use an internal path like /database or a trusted full URL.';
  return '';
}

function inputKind(setting) {
  if (IMAGE_SETTING_KEYS.has(setting.key)) return 'image';
  if (BOOLEAN_SETTING_KEYS.has(setting.key)) return 'boolean';
  if (ORDER_SETTING_KEYS.has(setting.key)) return 'order';
  if (setting.key.endsWith('_weight')) return 'weight';
  if (setting.key.endsWith('_style')) return 'style';
  if (setting.key.endsWith('_size')) return 'size';
  if (shouldUseTextarea(setting)) return 'textarea';
  return 'input';
}

const PAGE_BY_GROUP = new Map(CONTENT_STUDIO_PAGES.flatMap(page => page.groups.map(group => [group, page])));

export default function ContentStudioPage() {
  const { canWriteSettings } = useLibraryPermissions();
  const [activePage, setActivePage] = useState(CONTENT_STUDIO_PAGES[0].id);
  const [settings, setSettings] = useState(EDITABLE_SETTINGS);
  const [saved, setSaved] = useState(() => Object.fromEntries(EDITABLE_SETTINGS.map(item => [item.key, item.value || ''])));
  const [uploadingKey, setUploadingKey] = useState('');
  const [pickerKey, setPickerKey] = useState('');
  const [status, setStatus] = useState('loading');
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [activeGroup, setActiveGroup] = useState('');
  const mainRef = useRef(null);

  useEffect(() => {
    let active = true;
    DashboardApi.getSettings().then(data => {
      if (!active) return;
      const merged = mergeEditableSettings(data.results || []);
      setSettings(merged);
      setSaved(Object.fromEntries(merged.map(item => [item.key, item.value || ''])));
    }).catch(err => { if (active) setError(err.message); }).finally(() => { if (active) setStatus('ready'); });
    return () => { active = false; };
  }, []);

  const dirtyKeys = useMemo(() => settings.filter(item => (item.value || '') !== (saved[item.key] ?? '')).map(item => item.key), [settings, saved]);
  const dirtySet = useMemo(() => new Set(dirtyKeys), [dirtyKeys]);
  const dirtyByPage = useMemo(() => {
    const map = new Map();
    settings.forEach(item => { if (dirtySet.has(item.key)) { const page = PAGE_BY_GROUP.get(item.group)?.id; if (page) map.set(page, (map.get(page) || 0) + 1); } });
    return map;
  }, [settings, dirtySet]);
  useUnsavedWarning(dirtyKeys.length > 0);

  const activeConfig = CONTENT_STUDIO_PAGES.find(page => page.id === activePage) || CONTENT_STUDIO_PAGES[0];
  const managerActions = CONTENT_STUDIO_MANAGER_ACTIONS[activeConfig.id] || [];
  const groupedSettings = useMemo(() => activeConfig.groups.map(group => ({ group, page: activeConfig, fields: settings.filter(item => item.group === group) })).filter(item => item.fields.length), [activeConfig, settings]);
  const fieldCountByPage = useMemo(() => new Map(CONTENT_STUDIO_PAGES.map(page => [page.id, settings.filter(item => page.groups.includes(item.group)).length])), [settings]);

  const searchResults = useMemo(() => {
    const text = query.trim().toLowerCase();
    if (!text) return null;
    const groups = [];
    CONTENT_STUDIO_PAGES.forEach(page => page.groups.forEach(group => {
      const fields = settings.filter(item => item.group === group && `${item.label} ${item.key} ${item.value || ''} ${group}`.toLowerCase().includes(text));
      if (fields.length) groups.push({ group, page, fields });
    }));
    return groups;
  }, [query, settings]);

  const stats = useMemo(() => {
    const fields = groupedSettings.flatMap(group => group.fields);
    return {
      fields: fields.length,
      sections: fields.filter(item => BOOLEAN_SETTING_KEYS.has(item.key)).length,
      hidden: fields.filter(item => BOOLEAN_SETTING_KEYS.has(item.key) && item.value === 'false').length,
      links: fields.filter(item => URL_KEY_PATTERN.test(item.key)).length,
      images: fields.filter(item => IMAGE_SETTING_KEYS.has(item.key)).length,
    };
  }, [groupedSettings]);

  // Highlight the section currently in view in the index.
  useEffect(() => {
    if (searchResults || !groupedSettings.length) return undefined;
    setActiveGroup(groupedSettings[0].group);
    const observer = new IntersectionObserver(entries => {
      const visible = entries.filter(entry => entry.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
      if (visible) setActiveGroup(visible.target.dataset.group);
    }, { rootMargin: '-90px 0px -60% 0px' });
    mainRef.current?.querySelectorAll('[data-group]').forEach(node => observer.observe(node));
    return () => observer.disconnect();
  }, [groupedSettings, searchResults, status]);

  const update = (key, value) => setSettings(current => current.map(item => item.key === key ? { ...item, value } : item));
  const revert = key => update(key, saved[key] ?? '');
  const discardAll = () => { if (window.confirm(`Discard ${dirtyKeys.length} unsaved ${dirtyKeys.length === 1 ? 'change' : 'changes'}?`)) setSettings(current => current.map(item => ({ ...item, value: saved[item.key] ?? item.value }))); };

  const switchPage = id => { setActivePage(id); setQuery(''); window.scrollTo({ top: 0, behavior: 'smooth' }); };
  const jumpTo = (group, pageId = activePage) => {
    const go = () => document.getElementById(groupAnchor(group))?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    if (pageId !== activePage || query) { setActivePage(pageId); setQuery(''); setTimeout(go, 60); } else go();
  };

  const uploadImage = async (setting, file) => {
    if (!file) return;
    setError(''); setNotice('');
    const problem = validateImageFile(file);
    if (problem) { setError(problem.replace('Upload a', 'Please upload a').replace('Image uploads must be smaller than 8 MB.', 'Please upload an image smaller than 8 MB.')); return; }
    setUploadingKey(setting.key);
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('title', `${setting.label} - ${file.name}`);
      formData.append('alt_text', setting.label);
      const data = await DashboardApi.saveMedia(formData);
      const url = data.media?.url || data.media?.source_url || '';
      if (!url) throw new Error('Upload succeeded, but no media URL was returned.');
      update(setting.key, url);
      setNotice('Image uploaded and assigned to this field. Save Content to publish the change.');
    } catch (err) { setError(err.message); }
    finally { setUploadingKey(''); }
  };

  const save = useCallback(async event => {
    event?.preventDefault();
    if (!canWriteSettings) return;
    setError(''); setNotice('');
    const unsafe = settings.find(item => !isSafeUrlValue(item.key, item.value));
    if (unsafe) {
      setError(`${unsafe.label} must be a safe internal path or trusted URL.`);
      const page = PAGE_BY_GROUP.get(unsafe.group);
      if (page) jumpTo(unsafe.group, page.id);
      return;
    }
    setStatus('saving');
    try {
      await DashboardApi.saveSettings(settings);
      setSaved(Object.fromEntries(settings.map(item => [item.key, item.value || ''])));
      setNotice('Content Studio changes saved. Refresh the public website to see updates.');
    } catch (err) { setError(err.message); }
    finally { setStatus('ready'); }
  }, [settings, canWriteSettings]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const onKey = event => { if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') { event.preventDefault(); if (dirtyKeys.length && status === 'ready') save(); } };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [save, dirtyKeys.length, status]);

  const renderField = setting => {
    const value = setting.value || '';
    const type = inputKind(setting);
    const isImage = type === 'image';
    const inputId = `content-studio-file-${setting.key}`;
    const fieldId = `cs-field-${setting.key}`;
    const previewValue = value || (setting.key === 'homepage_hero_image_url' ? defaultHomepageHero : '');
    const changed = dirtySet.has(setting.key);
    const help = settingHelp(setting);
    const wide = isImage || type === 'textarea';
    let control;
    if (type === 'boolean') {
      control = <select id={fieldId} value={value || 'true'} onChange={event => update(setting.key, event.target.value)} disabled={!canWriteSettings}><option value="true">Visible</option><option value="false">Hidden</option></select>;
    } else if (type === 'weight') {
      control = <select id={fieldId} value={value || '900'} onChange={event => update(setting.key, event.target.value)} disabled={!canWriteSettings}><option value="400">400 Regular</option><option value="600">600 Semibold</option><option value="700">700 Bold</option><option value="800">800 Extra bold</option><option value="900">900 Black</option></select>;
    } else if (type === 'order') {
      control = <input id={fieldId} type="number" min="1" step="1" value={value} onChange={event => update(setting.key, event.target.value)} disabled={!canWriteSettings} />;
    } else if (type === 'textarea') {
      control = <textarea id={fieldId} value={value} onChange={event => update(setting.key, event.target.value)} rows="3" disabled={!canWriteSettings} />;
    } else if (!isImage) {
      control = <input id={fieldId} value={value} onChange={event => update(setting.key, event.target.value)} disabled={!canWriteSettings} />;
    }
    return (
      <div className={`dlib-cs-field ${wide ? 'is-wide' : ''} ${type === 'boolean' ? 'is-toggle' : ''} ${changed ? 'is-changed' : ''}`} key={setting.key}>
        <div className="dlib-cs-label">
          <label htmlFor={fieldId}>{setting.label}</label>
          {changed && <span className="dlib-cs-changed">Edited<button type="button" onClick={() => revert(setting.key)} aria-label={`Undo changes to ${setting.label}`} title="Undo"><Undo2 size={12} /></button></span>}
        </div>
        {isImage ? (
          <div className="dlib-cs-image">
            <div className={`dlib-cs-image-preview ${previewValue ? '' : 'is-empty'}`} onDragOver={event => event.preventDefault()} onDrop={event => { event.preventDefault(); if (canWriteSettings) uploadImage(setting, event.dataTransfer.files?.[0]); }}>
              {previewValue ? <img src={previewValue} alt={`Preview of ${setting.label}`} /> : <span><ImageIcon size={20} aria-hidden="true" /><small>Drop an image here</small></span>}
              {!value && previewValue && <em>Built-in default</em>}
            </div>
            <div className="dlib-cs-image-controls">
              <input id={fieldId} value={value} onChange={event => update(setting.key, event.target.value)} placeholder="Media URL or trusted https image URL" disabled={!canWriteSettings} />
              {canWriteSettings && <div className="dlib-inline-actions">
                <button type="button" className="admin-button admin-button-secondary" onClick={() => setPickerKey(setting.key)}><ImagePlus size={14} /> Media Library</button>
                <input id={inputId} type="file" accept="image/png,image/jpeg,image/webp,image/gif" onChange={event => { uploadImage(setting, event.target.files?.[0]); event.target.value = ''; }} hidden />
                <button type="button" className="admin-button admin-button-secondary" onClick={() => document.getElementById(inputId)?.click()} disabled={uploadingKey === setting.key}>{uploadingKey === setting.key ? <Loader2 size={14} className="spin" /> : <Upload size={14} />} {uploadingKey === setting.key ? 'Uploading...' : 'Upload'}</button>
                {value && <button type="button" className="admin-button admin-button-secondary" onClick={() => update(setting.key, '')} aria-label={`Remove ${setting.label} image`}>Clear</button>}
              </div>}
            </div>
          </div>
        ) : control}
        <small className="dlib-cs-help">{help}{help ? ' · ' : ''}<code>{setting.key}</code></small>
      </div>
    );
  };

  const renderGroup = ({ group, page, fields }, showPage = false) => {
    const changed = fields.filter(item => dirtySet.has(item.key)).length;
    const toggle = fields.find(item => BOOLEAN_SETTING_KEYS.has(item.key));
    return (
      <section className="dashboard-card dlib-cs-group" key={`${page.id}-${group}`} id={groupAnchor(group)} data-group={group} aria-labelledby={`${groupAnchor(group)}-title`}>
        <header className="dlib-cs-group-head">
          <div>
            <span className="dash-eyebrow">{showPage ? page.label : `${fields.length} fields`}{changed ? <em className="dlib-cs-dot-label"> · {changed} edited</em> : null}</span>
            <h2 id={`${groupAnchor(group)}-title`}>{groupTitle(group, page.label)}</h2>
          </div>
          <div className="dlib-inline-actions">
            {toggle && <span className={`dlib-pill ${toggle.value === 'false' ? '' : 'dlib-pill-ok'}`}>{toggle.value === 'false' ? 'Section hidden' : 'Section visible'}</span>}
            <a className="dlib-icon-text" href={groupPath(group, page.id)} target="_blank" rel="noreferrer"><ExternalLink size={14} /> View on site</a>
          </div>
        </header>
        <div className="dlib-cs-fields">{fields.map(renderField)}</div>
      </section>
    );
  };

  const pickerSetting = settings.find(item => item.key === pickerKey);

  return (
    <div className="dlib-page dlib-cs">
      <AdminPageHeader
        eyebrow="Content Studio"
        title="Page Content Editor"
        text="Control important page copy, section visibility, buttons, links, and key images without changing the frontend layout."
        actions={<a className="admin-button admin-button-secondary" href="/" target="_blank" rel="noreferrer"><ExternalLink size={15} /> View Website</a>}
      />
      {notice && <AdminNotice type="success">{notice}</AdminNotice>}
      {error && <AdminNotice type="error">{error}</AdminNotice>}
      {!canWriteSettings && <AdminNotice type="info">You can view website content, but your role cannot save changes. Ask an administrator for settings access.</AdminNotice>}

      <div className="dlib-cs-shell">
        <aside className="dlib-cs-nav" aria-label="Content Studio pages">
          <label className="dlib-cs-mobile-select">
            <span>Editable area</span>
            <select value={activePage} onChange={event => switchPage(event.target.value)}>{CONTENT_STUDIO_PAGES.map(page => <option key={page.id} value={page.id}>{page.label}{dirtyByPage.get(page.id) ? ` (${dirtyByPage.get(page.id)} edited)` : ''}</option>)}</select>
          </label>
          <nav className="dlib-cs-nav-list">
            <strong>Editable Areas</strong>
            {CONTENT_STUDIO_PAGES.map(page => {
              const active = page.id === activePage && !searchResults;
              return (
                <div key={page.id} className={active ? 'is-active' : ''}>
                  <button type="button" onClick={() => switchPage(page.id)} aria-current={active ? 'page' : undefined}>
                    <span>{page.label}</span>
                    {dirtyByPage.get(page.id) ? <i className="dlib-cs-dirty-dot" title={`${dirtyByPage.get(page.id)} unsaved`}>{dirtyByPage.get(page.id)}</i> : <em>{fieldCountByPage.get(page.id)}</em>}
                  </button>
                  {active && groupedSettings.length > 1 && (
                    <ul aria-label={`${page.label} sections`}>
                      {groupedSettings.map(({ group, fields }) => (
                        <li key={group}><a href={`#${groupAnchor(group)}`} className={activeGroup === group ? 'is-current' : ''} onClick={event => { event.preventDefault(); jumpTo(group); }}>
                          {groupTitle(group, page.label)}{fields.some(item => dirtySet.has(item.key)) && <i className="dlib-cs-dirty-dot is-small" aria-label="has unsaved changes" />}
                        </a></li>
                      ))}
                    </ul>
                  )}
                </div>
              );
            })}
          </nav>
        </aside>

        <form className="dlib-cs-main" onSubmit={save} ref={mainRef}>
          <label className="dash-search-field dlib-cs-search">
            <Search size={16} aria-hidden="true" />
            <input type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Search all website content — labels, text, links, keys" aria-label="Search all settings" />
            {query && <button type="button" className="dlib-clear" onClick={() => setQuery('')} aria-label="Clear search"><X size={14} /></button>}
          </label>

          {searchResults ? (
            <>
              <p className="dlib-hint-line" role="status">{searchResults.reduce((sum, item) => sum + item.fields.length, 0)} matching fields in {searchResults.length} sections across all pages.</p>
              {searchResults.length ? searchResults.map(item => renderGroup(item, true)) : <section className="dashboard-card"><p className="dlib-muted">Nothing matches “{query}”. Try a word from the public page, a link, or a setting key.</p></section>}
            </>
          ) : (
            <>
              <section className="dashboard-card dlib-cs-overview">
                <div className="dlib-cs-overview-copy">
                  <span className="dash-eyebrow">Editable area</span>
                  <h2>{activeConfig.label}</h2>
                  <p>{activeConfig.description}</p>
                  <div className="dlib-inline-actions">
                    <a className="admin-button admin-button-secondary" href={PAGE_PATHS[activeConfig.id] || '/'} target="_blank" rel="noreferrer"><ExternalLink size={15} /> View on site</a>
                  </div>
                </div>
                <dl className="dlib-cs-stats">
                  <div><dt>Fields</dt><dd>{stats.fields}</dd></div>
                  <div><dt>Sections</dt><dd>{stats.sections}{stats.hidden ? <small> · {stats.hidden} hidden</small> : null}</dd></div>
                  <div><dt>Links</dt><dd>{stats.links}</dd></div>
                  <div><dt>Images</dt><dd>{stats.images}</dd></div>
                </dl>
                {managerActions.length > 0 && (
                  <div className="dlib-cs-managers">
                    <strong>{activeConfig.id === 'team' ? 'Manage team entries and Google Form links' : `Manage ${activeConfig.label} content safely`}</strong>
                    <p>Content Studio edits stable page copy. Use these managers for records, cards, submissions, media, and advanced controls without breaking the public layout.</p>
                    <div className="dlib-cs-manager-links">{managerActions.map(([label, href]) => <Link key={href} to={href}>{label}</Link>)}</div>
                  </div>
                )}
              </section>
              {groupedSettings.length > 1 && (
                <nav className="dlib-cs-chips" aria-label="Jump to section">
                  {groupedSettings.map(({ group, fields }) => <button type="button" key={group} className={activeGroup === group ? 'is-current' : ''} onClick={() => jumpTo(group)}>{groupTitle(group, activeConfig.label)}{fields.some(item => dirtySet.has(item.key)) && <i className="dlib-cs-dirty-dot is-small" />}</button>)}
                </nav>
              )}
              {status === 'loading' ? <section className="dashboard-card"><p className="dlib-muted"><Loader2 size={14} className="spin" /> Loading editable content...</p></section> : groupedSettings.map(item => renderGroup(item))}
            </>
          )}

          <div className={`dlib-savebar content-studio-savebar ${dirtyKeys.length ? 'is-dirty' : ''}`} role="region" aria-label="Save changes">
            <span role="status">{status === 'saving' ? 'Saving changes…' : dirtyKeys.length ? <><strong>{dirtyKeys.length} unsaved {dirtyKeys.length === 1 ? 'change' : 'changes'}</strong> in {[...dirtyByPage.keys()].map(id => CONTENT_STUDIO_PAGES.find(page => page.id === id)?.label).join(', ')} · Ctrl / ⌘ S</> : 'All changes saved. Changes are saved to dashboard settings and rendered by the public React pages.'}</span>
            {dirtyKeys.length > 0 && <button type="button" className="admin-button admin-button-secondary" onClick={discardAll} disabled={status === 'saving'}><RotateCcw size={15} /> Discard</button>}
            {canWriteSettings && <button className="admin-button" disabled={status !== 'ready' || !dirtyKeys.length}><Save size={15} /> {status === 'saving' ? 'Saving...' : 'Save Content'}</button>}
          </div>
        </form>
      </div>
      <MediaPicker open={Boolean(pickerKey)} onClose={() => setPickerKey('')} title={pickerSetting ? `Choose an image for “${pickerSetting.label}”` : 'Choose an image'} onSelect={asset => { if (pickerKey) update(pickerKey, asset.url); }} />
    </div>
  );
}
