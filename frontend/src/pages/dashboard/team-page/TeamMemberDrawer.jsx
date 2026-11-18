import { ImageOff, ImagePlus, Plus, Save, Send, Trash2, Undo2, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import AdminNotice from '../../../components/dashboard/AdminNotice';
import { Drawer } from '../../../components/dashboard/DashboardPrimitives';
import MediaPicker from '../../../components/dashboard/MediaPicker';
import { initials, useUnsavedWarning } from '../media/libraryKit';

const MAX_LINKS = 6;

export default function TeamMemberDrawer({ member, sections, pageLive, onClose, onSave, onDelete }) {
  const [form, setForm] = useState(null);
  const [original, setOriginal] = useState('');
  const [picker, setPicker] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!member) { setForm(null); return; }
    const next = { full_name: '', role: '', department: '', bio: '', vision: '', photo_id: null, photo_url: '', links: [], status: 'draft', ...member };
    setForm(next); setOriginal(JSON.stringify(next)); setError('');
  }, [member]);

  const dirty = Boolean(form) && JSON.stringify(form) !== original;
  useUnsavedWarning(dirty);
  const close = () => { if (dirty && !window.confirm('Discard unsaved changes to this member?')) return; onClose(); };
  const update = ({ target }) => setForm(current => ({ ...current, [target.name]: target.name === 'section_id' ? Number(target.value) : target.value }));
  const setLink = (index, key, value) => setForm(current => ({ ...current, links: current.links.map((link, at) => at === index ? { ...link, [key]: value } : link) }));

  const save = async status => {
    setSaving(true); setError('');
    try { await onSave({ ...form, status }); }
    catch (err) { setError(err.message); }
    finally { setSaving(false); }
  };
  const submit = event => {
    event.preventDefault();
    const status = event.nativeEvent.submitter?.dataset.status || form.status;
    save(status);
  };

  const section = form && sections.find(item => item.id === form.section_id);
  const published = form?.status === 'published';
  return <>
    <Drawer open={Boolean(form)} onClose={close} width={680}
      title={form?.id ? 'Edit member' : 'New member'}
      subtitle={pageLive ? 'The Team page is live, so publishing a member shows them to visitors straight away.' : 'Nothing here is public until you publish the whole Team page.'}
      footer={form && <>
        {form.id && <button type="button" className="admin-button admin-button-danger dlib-footer-start" onClick={() => onDelete(form)}><Trash2 size={15} /> Remove</button>}
        <button className="admin-button admin-button-secondary" type="button" onClick={close}><X size={15} /> Cancel</button>
        <button className="admin-button admin-button-secondary" form="dtp-member-form" data-status="draft" disabled={saving}>{published ? <Undo2 size={15} /> : <Save size={15} />} {published ? 'Back to draft' : 'Save draft'}</button>
        <button className="admin-button" form="dtp-member-form" data-status="published" disabled={saving}>{published ? <Save size={15} /> : <Send size={15} />} {published ? 'Save changes' : 'Publish member'}</button>
      </>}>
      {form && <form id="dtp-member-form" className="dlib-form" onSubmit={submit}>
        {error && <AdminNotice type="error">{error}</AdminNotice>}
        <div className="dlib-author-photo">
          <span className="dlib-avatar dlib-avatar-xl">{form.photo_url ? <img src={form.photo_url} alt="" /> : <span>{form.full_name ? initials(form.full_name) : <ImageOff size={24} aria-hidden="true" />}</span>}</span>
          <div className="dtp-photo-actions">
            <strong>Photo</strong>
            <small>{form.photo_url ? 'From the Media Library' : 'No photo yet. Initials are shown instead.'}</small>
            <div>
              <button type="button" className="admin-button admin-button-secondary" onClick={() => setPicker(true)}><ImagePlus size={15} /> {form.photo_url ? 'Change photo' : 'Upload or choose'}</button>
              {form.photo_url && <button type="button" className="admin-button admin-button-secondary" onClick={() => setForm(current => ({ ...current, photo_id: null, photo_url: '' }))}>Remove photo</button>}
            </div>
          </div>
        </div>

        <fieldset className="dlib-fieldset">
          <legend>Identity</legend>
          <div className="dlib-form-grid">
            <label>Full name<input required name="full_name" value={form.full_name} onChange={update} maxLength={150} /></label>
            <label>Section<select name="section_id" value={form.section_id} onChange={update}>{sections.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
            <label>Role<input name="role" value={form.role} onChange={update} maxLength={150} placeholder="Director of Research" /><small>Needed before publishing.</small></label>
            <label>Department<input name="department" value={form.department} onChange={update} maxLength={120} /></label>
          </div>
        </fieldset>

        <fieldset className="dlib-fieldset">
          <legend>About</legend>
          <label>Short introduction<textarea name="bio" value={form.bio} onChange={update} rows="4" maxLength={2000} /></label>
          {section?.level === 'founder' && <label>A few words about ResRef and its vision<textarea name="vision" value={form.vision} onChange={update} rows="4" maxLength={2000} /><small>Shown as a highlighted statement beside the introduction.</small></label>}
        </fieldset>

        <fieldset className="dlib-fieldset">
          <legend>Links</legend>
          {form.links.map((link, index) => <div className="dtp-link-row" key={index}>
            <label>Label<input value={link.label} onChange={event => setLink(index, 'label', event.target.value)} maxLength={60} placeholder="LinkedIn" /></label>
            <label>Address<input value={link.url} onChange={event => setLink(index, 'url', event.target.value)} maxLength={500} placeholder="https://..." /></label>
            <button type="button" className="dash-icon-button" aria-label={`Remove link ${link.label || index + 1}`} onClick={() => setForm(current => ({ ...current, links: current.links.filter((_, at) => at !== index) }))}><X size={16} /></button>
          </div>)}
          {form.links.length < MAX_LINKS && <div><button type="button" className="admin-button admin-button-secondary" onClick={() => setForm(current => ({ ...current, links: [...current.links, { label: '', url: '' }] }))}><Plus size={15} /> Add link</button></div>}
        </fieldset>
        {dirty && <p className="dlib-dirty-note" role="status">Unsaved changes</p>}
      </form>}
    </Drawer>
    <MediaPicker open={picker} onClose={() => setPicker(false)} title="Choose a photo" onSelect={asset => setForm(current => current ? { ...current, photo_id: asset.id, photo_url: asset.url } : current)} />
  </>;
}
