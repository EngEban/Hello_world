import { ArrowDown, ArrowUp, Eye, EyeOff, ExternalLink, GlobeLock, Globe2, GripVertical, Pencil, Plus, Save, Send, Trash2, Undo2, X } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { DashboardApi } from '../../../api/dashboardApi';
import AdminNotice from '../../../components/dashboard/AdminNotice';
import AdminPageHeader from '../../../components/dashboard/AdminPageHeader';
import { Drawer, StateBlock } from '../../../components/dashboard/DashboardPrimitives';
import { initials, useUnsavedWarning } from '../media/libraryKit';
import TeamMemberDrawer from './TeamMemberDrawer';
import '../../../styles/dashboard/dash-library.css';
import '../../../styles/dashboard/dash-team-page.css';

const LEVEL_HELP = {
  founder: 'The largest layout: big photo, introduction and vision statement.',
  leadership: 'Medium portraits with a short introduction. Suits the board.',
  directors: 'Compact rows with a small photo. Suits department leaders.',
  team: 'Small entries grouped under the team name. Suits departments and their members.',
};

/** Sections with one member moved to `sectionId` at `index`. */
function placeMember(sections, id, sectionId, index) {
  const member = sections.flatMap(section => section.members).find(item => item.id === id);
  return sections.map(section => {
    const members = section.members.filter(item => item.id !== id);
    if (section.id === sectionId) members.splice(index ?? members.length, 0, { ...member, section_id: sectionId });
    return { ...section, members };
  });
}

function SectionDrawer({ section, levels, onClose, onSave, onDelete }) {
  const [form, setForm] = useState(null);
  const [original, setOriginal] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!section) { setForm(null); return; }
    const next = { name: '', description: '', level: 'team', is_visible: true, ...section };
    setForm(next); setOriginal(JSON.stringify(next)); setError('');
  }, [section]);

  const dirty = Boolean(form) && JSON.stringify(form) !== original;
  useUnsavedWarning(dirty);
  const close = () => { if (dirty && !window.confirm('Discard unsaved changes to this section?')) return; onClose(); };
  const update = ({ target }) => setForm(current => ({ ...current, [target.name]: target.type === 'checkbox' ? target.checked : target.value }));
  const submit = async event => {
    event.preventDefault(); setSaving(true); setError('');
    try { await onSave(form); }
    catch (err) { setError(err.message); }
    finally { setSaving(false); }
  };
  const occupied = form?.members?.length > 0;

  return <Drawer open={Boolean(form)} onClose={close} width={560} title={form?.id ? 'Edit section' : 'New section'} subtitle="A section or team on the Team page. Sections with no published members are not shown."
    footer={form && <>
      {form.id && <button type="button" className="admin-button admin-button-danger dlib-footer-start" disabled={occupied} title={occupied ? 'Move or remove its members first' : undefined} onClick={() => onDelete(form)}><Trash2 size={15} /> Delete</button>}
      <button className="admin-button admin-button-secondary" type="button" onClick={close}><X size={15} /> Cancel</button>
      <button className="admin-button" form="dtp-section-form" disabled={saving}><Save size={15} /> Save section</button>
    </>}>
    {form && <form id="dtp-section-form" className="dlib-form" onSubmit={submit}>
      {error && <AdminNotice type="error">{error}</AdminNotice>}
      <label>Name<input required name="name" value={form.name} onChange={update} maxLength={120} placeholder="Research Team" /></label>
      <label>Display level<select name="level" value={form.level} onChange={update}>{levels.map(level => <option key={level.id} value={level.id}>{level.label}</option>)}</select><small>{LEVEL_HELP[form.level]}</small></label>
      <label>Description (optional)<textarea name="description" value={form.description} onChange={update} rows="3" maxLength={600} /></label>
      <label className="admin-check"><input type="checkbox" name="is_visible" checked={form.is_visible} onChange={update} /> Show this section on the Team page</label>
      {occupied && <p className="dlib-muted">To delete this section, first move or remove its {form.members.length} {form.members.length === 1 ? 'member' : 'members'}.</p>}
    </form>}
  </Drawer>;
}

function PageIntro({ settings, onSave }) {
  const [form, setForm] = useState({ hero_title: settings.hero_title, hero_text: settings.hero_text });
  const [saving, setSaving] = useState(false);
  const dirty = form.hero_title !== settings.hero_title || form.hero_text !== settings.hero_text;
  useUnsavedWarning(dirty);
  const submit = async event => {
    event.preventDefault(); setSaving(true);
    try { await onSave(form); } finally { setSaving(false); }
  };
  return <form className="dashboard-card dlib-form dtp-intro" onSubmit={submit}>
    <h2>Page introduction</h2>
    <div className="dtp-intro-fields">
      <label>Title<input required value={form.hero_title} onChange={event => setForm(current => ({ ...current, hero_title: event.target.value }))} maxLength={160} /></label>
      <label>Text<textarea rows="2" value={form.hero_text} onChange={event => setForm(current => ({ ...current, hero_text: event.target.value }))} maxLength={600} placeholder="A sentence or two shown under the title." /></label>
    </div>
    <div><button className="admin-button admin-button-secondary" disabled={!dirty || saving}><Save size={15} /> {saving ? 'Saving...' : 'Save introduction'}</button></div>
  </form>;
}

export default function DashboardTeamPage() {
  const { bootstrap } = useOutletContext() || {};
  const refused = bootstrap && !bootstrap.is_super_admin;
  const [data, setData] = useState(null);
  const [status, setStatus] = useState('loading');
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [member, setMember] = useState(null);
  const [section, setSection] = useState(null);
  const [drag, setDrag] = useState(null);
  const [publishing, setPublishing] = useState(false);

  const load = useCallback(async () => {
    try { setData(await DashboardApi.getTeamPage()); setStatus('ready'); }
    catch (err) { setError(err.message); setStatus(err.status === 403 ? 'refused' : 'error'); }
  }, []);
  useEffect(() => { if (!refused) load(); }, [load, refused]);

  if (refused || status === 'refused') return <StateBlock type="error" title="Super Admins only" text="Only a Super Admin can manage the Team page." />;
  if (status === 'loading') return <StateBlock type="loading" title="Loading the Team page" />;
  if (!data) return <StateBlock type="error" title="The Team page could not be loaded" text={error} />;

  const { settings, sections, levels } = data;
  const setSections = next => setData(current => ({ ...current, sections: next }));
  const members = sections.flatMap(item => item.members);
  const shown = sections.filter(item => item.is_visible);
  const publishedCount = shown.flatMap(item => item.members).filter(item => item.status === 'published').length;
  const draftCount = members.filter(item => item.status === 'draft').length;
  const hiddenCount = sections.length - shown.length;

  const run = async (action, message) => {
    setError(''); setNotice('');
    try { await action(); if (message) setNotice(message); }
    catch (err) { setError(err.message); }
    await load();
  };
  const persistMembers = (next, sectionId) => {
    setSections(next);
    const ids = next.find(item => item.id === sectionId).members.map(item => item.id);
    return run(() => DashboardApi.arrangeTeamMembers(sectionId, ids));
  };
  const moveMember = (id, sectionId, index) => persistMembers(placeMember(sections, id, sectionId, index), sectionId);
  const moveSection = (id, target) => {
    const next = sections.filter(item => item.id !== id);
    next.splice(target, 0, sections.find(item => item.id === id));
    return next;
  };
  const saveSections = next => { setSections(next); return run(() => DashboardApi.reorderTeamSections(next.map(item => item.id))); };

  const endDrag = () => {
    if (!drag) return;
    setDrag(null);
    if (drag.type === 'section') saveSections(sections);
    else persistMembers(sections, members.find(item => item.id === drag.id).section_id);
  };

  const togglePublish = async () => {
    const next = !settings.is_published;
    if (!window.confirm(next ? 'Publish the Team page? Everyone will be able to see it at /team.' : 'Unpublish the Team page? Visitors will no longer be able to see it.')) return;
    setPublishing(true);
    await run(() => DashboardApi.publishTeamPage(next), next ? 'The Team page is now live at /team.' : 'The Team page is unpublished and hidden from visitors.');
    setPublishing(false);
  };
  const saveMember = async form => {
    await DashboardApi.saveTeamMember(form, form.id);
    setMember(null); setNotice(`${form.full_name} saved as ${form.status === 'published' ? 'published' : 'a draft'}.`); setError('');
    await load();
  };
  const deleteMember = form => {
    if (!window.confirm(`Remove ${form.full_name} from the Team page? This cannot be undone.`)) return;
    setMember(null);
    run(() => DashboardApi.deleteTeamMember(form.id), `${form.full_name} removed.`);
  };
  const saveSection = async form => {
    await DashboardApi.saveTeamSection({ name: form.name, description: form.description, level: form.level, is_visible: form.is_visible }, form.id);
    setSection(null); setNotice(`Section “${form.name}” saved.`); setError('');
    await load();
  };
  const deleteSection = form => {
    if (!window.confirm(`Delete the section “${form.name}”?`)) return;
    setSection(null);
    run(() => DashboardApi.deleteTeamSection(form.id), `Section “${form.name}” deleted.`);
  };

  return (
    <div className="dlib-page dtp-page">
      <AdminPageHeader
        eyebrow="Content library"
        title="Team Page"
        text="Sections, members and photos for the public Team page. Only Super Admins can see or change this."
        actions={<>
          <a className="admin-button admin-button-secondary" href="/team/preview" target="_blank" rel="noopener noreferrer"><ExternalLink size={15} /> Preview</a>
          <button type="button" className="admin-button" onClick={() => setSection({ level: 'team' })}><Plus size={15} /> Add section</button>
        </>}
      />
      {notice && <AdminNotice type="success">{notice}</AdminNotice>}{error && <AdminNotice type="error">{error}</AdminNotice>}

      <section className={`dashboard-card dtp-status ${settings.is_published ? 'is-live' : 'is-draft'}`} aria-label="Publication status">
        <span className="dtp-status-icon">{settings.is_published ? <Globe2 size={22} aria-hidden="true" /> : <GlobeLock size={22} aria-hidden="true" />}</span>
        <div className="dtp-status-copy">
          <strong>{settings.is_published ? <>Published. Live at <a href="/team" target="_blank" rel="noopener noreferrer">/team</a></> : 'Unpublished draft'}</strong>
          <p>{settings.is_published ? 'Visitors can see this page. Published members appear straight away.' : 'Visitors and search engines cannot see this page. It stays hidden until you publish it here.'}</p>
          <small>{publishedCount} published · {draftCount} {draftCount === 1 ? 'draft' : 'drafts'}{hiddenCount > 0 && ` · ${hiddenCount} hidden ${hiddenCount === 1 ? 'section' : 'sections'}`}</small>
        </div>
        <button type="button" className={`admin-button ${settings.is_published ? 'admin-button-secondary' : ''}`} disabled={publishing} onClick={togglePublish}>
          {settings.is_published ? <><Undo2 size={15} /> Unpublish page</> : <><Send size={15} /> Publish page</>}
        </button>
      </section>

      <PageIntro key={`${settings.hero_title}|${settings.hero_text}`} settings={settings} onSave={payload => run(() => DashboardApi.saveTeamPageSettings(payload), 'Introduction saved.')} />

      <ol className="dtp-sections" aria-label="Sections">
        {sections.map((item, sectionIndex) => (
          <li key={item.id} className={`dashboard-card dtp-section ${drag?.id === item.id && drag.type === 'section' ? 'is-dragging' : ''} ${item.is_visible ? '' : 'is-hidden'}`}
            onDragOver={event => {
              if (!drag) return;
              if (drag.type === 'section') {
                event.preventDefault();
                if (drag.id !== item.id) setSections(moveSection(drag.id, sectionIndex));
              } else {
                event.preventDefault();
                if (!item.members.some(entry => entry.id === drag.id)) setSections(placeMember(sections, drag.id, item.id));
              }
            }}>
            <header className="dtp-section-head">
              <span className="dtp-handle" draggable title="Drag to reorder" aria-hidden="true"
                onDragStart={event => { event.dataTransfer.effectAllowed = 'move'; event.dataTransfer.setData('text/plain', String(item.id)); setDrag({ type: 'section', id: item.id }); }}
                onDragEnd={endDrag}><GripVertical size={16} /></span>
              <div className="dtp-section-title">
                <h2>{item.name}</h2>
                <small>{levels.find(level => level.id === item.level)?.label} · {item.members.length} {item.members.length === 1 ? 'member' : 'members'}{!item.is_visible && ' · Hidden'}</small>
              </div>
              <div className="dtp-actions">
                <span className="dtp-arrows">
                  <button type="button" disabled={sectionIndex === 0} aria-label={`Move ${item.name} up`} onClick={() => saveSections(moveSection(item.id, sectionIndex - 1))}><ArrowUp size={14} /></button>
                  <button type="button" disabled={sectionIndex === sections.length - 1} aria-label={`Move ${item.name} down`} onClick={() => saveSections(moveSection(item.id, sectionIndex + 1))}><ArrowDown size={14} /></button>
                </span>
                <button type="button" className="dtp-icon" aria-label={item.is_visible ? `Hide ${item.name}` : `Show ${item.name}`} title={item.is_visible ? 'Hide section' : 'Show section'} onClick={() => run(() => DashboardApi.saveTeamSection({ is_visible: !item.is_visible }, item.id))}>{item.is_visible ? <Eye size={16} /> : <EyeOff size={16} />}</button>
                <button type="button" className="dtp-icon" aria-label={`Edit ${item.name}`} title="Edit section" onClick={() => setSection(item)}><Pencil size={15} /></button>
                <button type="button" className="admin-button admin-button-secondary" onClick={() => setMember({ section_id: item.id })}><Plus size={15} /> Add member</button>
              </div>
            </header>

            {item.members.length === 0
              ? <p className="dtp-empty">No members yet. Add one, or drag someone here.</p>
              : <ol className="dtp-members">
                {item.members.map((person, index) => (
                  <li key={person.id} className={drag?.id === person.id && drag.type === 'member' ? 'is-dragging' : ''}
                    onDragOver={event => {
                      if (drag?.type !== 'member') return;
                      event.preventDefault(); event.stopPropagation();
                      if (drag.id !== person.id) setSections(placeMember(sections, drag.id, item.id, index));
                    }}>
                    <span className="dtp-handle" draggable title="Drag to reorder or move to another section" aria-hidden="true"
                      onDragStart={event => { event.stopPropagation(); event.dataTransfer.effectAllowed = 'move'; event.dataTransfer.setData('text/plain', String(person.id)); setDrag({ type: 'member', id: person.id }); }}
                      onDragEnd={event => { event.stopPropagation(); endDrag(); }}><GripVertical size={16} /></span>
                    <span className="dlib-avatar dlib-avatar-sm">{person.photo_url ? <img src={person.photo_url} alt="" loading="lazy" /> : <span>{initials(person.full_name)}</span>}</span>
                    <button type="button" className="dtp-member-name" onClick={() => setMember(person)}>
                      <strong>{person.full_name}</strong>
                      <small>{[person.role, person.department].filter(Boolean).join(' · ') || 'No role yet'}</small>
                    </button>
                    <span className={`dlib-pill ${person.status === 'published' ? 'dlib-pill-ok' : ''}`}>{person.status === 'published' ? 'Published' : 'Draft'}</span>
                    <select className="dtp-move" aria-label={`Move ${person.full_name} to another section`} value={item.id} onChange={event => moveMember(person.id, Number(event.target.value))}>
                      <option value={item.id}>Move to...</option>
                      {sections.filter(option => option.id !== item.id).map(option => <option key={option.id} value={option.id}>{option.name}</option>)}
                    </select>
                    <span className="dtp-arrows">
                      <button type="button" disabled={index === 0} aria-label={`Move ${person.full_name} up`} onClick={() => moveMember(person.id, item.id, index - 1)}><ArrowUp size={14} /></button>
                      <button type="button" disabled={index === item.members.length - 1} aria-label={`Move ${person.full_name} down`} onClick={() => moveMember(person.id, item.id, index + 1)}><ArrowDown size={14} /></button>
                    </span>
                  </li>
                ))}
              </ol>}
          </li>
        ))}
      </ol>

      <TeamMemberDrawer member={member} sections={sections} pageLive={settings.is_published} onClose={() => setMember(null)} onSave={saveMember} onDelete={deleteMember} />
      <SectionDrawer section={section} levels={levels} onClose={() => setSection(null)} onSave={saveSection} onDelete={deleteSection} />
    </div>
  );
}
