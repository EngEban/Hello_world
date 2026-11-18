import { BellRing, BriefcaseBusiness, CreditCard, Eye, Info, Link2, Megaphone, RefreshCw, Search, Send, ShieldAlert, Sparkles, Users, X } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useOutletContext, useSearchParams } from 'react-router-dom';
import { DashboardApi } from '../../../api/dashboardApi';
import ActionMenu from '../../../components/dashboard/ActionMenu';
import AdminNotice from '../../../components/dashboard/AdminNotice';
import AdminPageHeader from '../../../components/dashboard/AdminPageHeader';
import { DashboardCard, DashboardModal, Drawer, StatCard, StateBlock } from '../../../components/dashboard/DashboardPrimitives';
import { hasPermission, relativeTime } from '../users/adminShared';
import '../../../styles/dashboard/dash-admin.css';

const initialForm = { audience: 'all', user_ids: [], title: '', message: '', notification_type: 'info', action_url: '' };
const AUDIENCES = [
  ['all', 'All active users', 'Everyone with an active account'],
  ['admins', 'Dashboard administrators', 'Admins and super admins'],
  ['staff', 'Dashboard staff', 'Everyone with dashboard access'],
  ['premium', 'Premium members', 'Accounts on a Premium plan'],
  ['free', 'Free members', 'Accounts on the Free plan'],
  ['selected', 'Selected users', 'Pick people one by one'],
];
const TYPES = [['info', 'Information', Info], ['announcement', 'Announcement', Megaphone], ['opportunity', 'Opportunity', BriefcaseBusiness], ['security', 'Security', ShieldAlert], ['billing', 'Billing', CreditCard]];
const typeMeta = value => TYPES.find(([id]) => id === value) || TYPES[0];
const audienceLabel = value => AUDIENCES.find(([id]) => id === value)?.[1] || (value === 'system' ? 'System message' : value);

function validate(form) {
  const errors = {};
  if (!form.title.trim()) errors.title = 'Enter a clear notification title.';
  if (!form.message.trim()) errors.message = 'Enter the message recipients should receive.';
  if (form.audience === 'selected' && form.user_ids.length === 0) errors.user_ids = 'Select at least one recipient.';
  if (form.action_url && !(/^\//.test(form.action_url) || /^https:\/\//.test(form.action_url))) errors.action_url = 'Use an internal path starting with / or an HTTPS link.';
  return errors;
}

export default function DashboardNotificationsPage() {
  const { user, bootstrap } = useOutletContext() || {};
  const canSend = hasPermission(user, bootstrap, 'notifications.create');
  const [searchParams] = useSearchParams();
  const presetUser = Number(searchParams.get('user')) || null;
  const [form, setForm] = useState(presetUser ? { ...initialForm, audience: 'selected', user_ids: [presetUser] } : initialForm);
  const [errors, setErrors] = useState({});
  const [touched, setTouched] = useState(false);
  const [users, setUsers] = useState([]);
  const [recipientQuery, setRecipientQuery] = useState('');
  const [history, setHistory] = useState([]);
  const [audienceCounts, setAudienceCounts] = useState({});
  const [historyQuery, setHistoryQuery] = useState('');
  const [historyType, setHistoryType] = useState('');
  const [selected, setSelected] = useState(null);
  const [confirming, setConfirming] = useState(false);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const selectedUsers = useMemo(() => new Set(form.user_ids.map(Number)), [form.user_ids]);

  const update = patch => {
    const next = { ...form, ...patch };
    setForm(next);
    if (touched) setErrors(validate(next));
  };
  const load = async () => {
    setLoading(true);
    try {
      const [usersData, historyData] = await Promise.all([
        DashboardApi.getUsers({ per_page: 100, status: 'active' }), DashboardApi.getNotifications(),
      ]);
      setUsers(usersData.results || []);
      setHistory(historyData.results || []);
      setAudienceCounts(historyData.audience_counts || {});
    } catch (err) { setError(err.message); } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const toggleRecipient = id => update({ user_ids: selectedUsers.has(id) ? form.user_ids.filter(value => Number(value) !== id) : [...form.user_ids, id] });
  const visibleUsers = users.filter(item => !recipientQuery.trim() || `${item.display_name} ${item.username} ${item.email}`.toLowerCase().includes(recipientQuery.trim().toLowerCase()));
  const reach = form.audience === 'selected' ? form.user_ids.length : audienceCounts[form.audience];

  const requestSend = event => {
    event.preventDefault();
    setTouched(true);
    const nextErrors = validate(form);
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length) return;
    setConfirming(true);
  };
  const send = async () => {
    setConfirming(false);
    setSending(true); setError(''); setNotice('');
    try {
      const result = await DashboardApi.sendNotification(form);
      setNotice(`Notification sent to ${result.recipient_count} active account${result.recipient_count === 1 ? '' : 's'}.`);
      setForm(initialForm); setErrors({}); setTouched(false); await load();
    } catch (err) { setError(err.message); } finally { setSending(false); }
  };
  const reuse = item => {
    setForm({ ...initialForm, title: item.title, message: item.message, notification_type: item.type || 'info', action_url: item.action_url || '', audience: AUDIENCES.some(([id]) => id === item.audience) && item.audience !== 'selected' ? item.audience : 'all' });
    setSelected(null);
    document.querySelector('.dash-adm-composer')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const stats = useMemo(() => {
    const campaigns = history.filter(item => item.audience !== 'system');
    const delivered = campaigns.reduce((sum, item) => sum + (item.recipient_count || 0), 0);
    const read = campaigns.reduce((sum, item) => sum + (item.read_count || 0), 0);
    return { campaigns: campaigns.length, delivered, rate: delivered ? Math.round((read / delivered) * 100) : 0, last: campaigns[0]?.created_at };
  }, [history]);
  const visibleHistory = history.filter(item => (!historyType || item.type === historyType)
    && (!historyQuery.trim() || `${item.title} ${item.message} ${item.audience} ${item.created_by}`.toLowerCase().includes(historyQuery.trim().toLowerCase())));
  const [, typeLabel, TypeIcon] = typeMeta(form.notification_type);

  return <div className="dash-adm-page">
    <AdminPageHeader eyebrow="System" title="Notifications" text="Send precise account notifications, review delivery history, and keep every recipient’s read status separate." actions={<button type="button" className="admin-button admin-button-secondary" onClick={load}><RefreshCw size={15} /> Refresh</button>} />
    {notice && <AdminNotice type="success">{notice}</AdminNotice>}
    {error && <AdminNotice type="error">{error}</AdminNotice>}

    <section className="dash-stat-grid" aria-label="Notification summary">
      <StatCard icon={BellRing} label="Campaigns sent" value={stats.campaigns} hint="Last 100 shown below" loading={loading} />
      <StatCard icon={Users} label="Deliveries" value={stats.delivered} hint="Account inboxes reached" loading={loading} />
      <StatCard icon={Eye} label="Read rate" value={`${stats.rate}%`} hint="Across sent campaigns" loading={loading} />
      <StatCard icon={Send} label="Last sent" value={stats.last ? relativeTime(stats.last) : '—'} hint={stats.last ? new Date(stats.last).toLocaleDateString() : 'Nothing sent yet'} loading={loading} />
    </section>

    <div className="dash-adm-grid">
      <section className="dashboard-card dash-adm-composer dash-adm-span-7">
        <div className="dashboard-card-head"><div><span>New notification</span><h2>Message your audience</h2></div><BellRing size={21} /></div>
        <form className="dashboard-form" onSubmit={requestSend} noValidate>
          <fieldset className="dash-adm-choice-group" disabled={!canSend}>
            <legend>Audience</legend>
            <div className="dash-adm-choices">
              {AUDIENCES.map(([id, label, hint]) => (
                <label key={id} className={form.audience === id ? 'is-selected' : ''}>
                  <input type="radio" name="audience" value={id} checked={form.audience === id} onChange={() => update({ audience: id })} />
                  <span><strong>{label}</strong><small>{hint}</small></span>
                  {id !== 'selected' && audienceCounts[id] !== undefined && <em>{audienceCounts[id]}</em>}
                  {id === 'selected' && form.user_ids.length > 0 && <em>{form.user_ids.length}</em>}
                </label>
              ))}
            </div>
          </fieldset>
          {form.audience === 'selected' && <fieldset className="notification-recipient-list dash-adm-recipients" disabled={!canSend}>
            <legend><Users size={16} /> Select recipients <small>{form.user_ids.length} selected</small></legend>
            <div className="dash-adm-recipient-tools">
              <label className="dash-search-field"><Search size={15} aria-hidden="true" /><input type="search" value={recipientQuery} onChange={event => setRecipientQuery(event.target.value)} placeholder="Find people" aria-label="Find recipients" /></label>
              <button type="button" className="dash-adm-link" onClick={() => update({ user_ids: [...new Set([...form.user_ids.map(Number), ...visibleUsers.map(item => item.id)])] })}>Select all shown</button>
              {form.user_ids.length > 0 && <button type="button" className="dash-adm-link" onClick={() => update({ user_ids: [] })}>Clear</button>}
            </div>
            <div className="dash-adm-recipient-scroll">
              {visibleUsers.map(item => <label key={item.id}><input type="checkbox" checked={selectedUsers.has(item.id)} onChange={() => toggleRecipient(item.id)} /><span>{item.display_name || item.username}</span><small>{item.email}</small></label>)}
              {!visibleUsers.length && <p className="dash-adm-hint">{loading ? 'Loading people…' : 'No active users match.'}</p>}
            </div>
            {errors.user_ids && <small className="form-field-error">{errors.user_ids}</small>}
          </fieldset>}
          <fieldset className="dash-adm-choice-group" disabled={!canSend}>
            <legend>Type</legend>
            <div className="dash-adm-typechips">
              {TYPES.map(([id, label, Icon]) => <label key={id} className={form.notification_type === id ? 'is-selected' : ''}><input type="radio" name="notification_type" value={id} checked={form.notification_type === id} onChange={() => update({ notification_type: id })} /><Icon size={14} /> {label}</label>)}
            </div>
          </fieldset>
          <label>Title<input name="title" value={form.title} maxLength="200" onChange={event => update({ title: event.target.value })} aria-invalid={Boolean(errors.title)} disabled={!canSend} /><span className="dash-adm-counter">{form.title.length}/200</span>{errors.title && <small className="form-field-error">{errors.title}</small>}</label>
          <label>Message<textarea name="message" value={form.message} maxLength="4000" rows="5" onChange={event => update({ message: event.target.value })} aria-invalid={Boolean(errors.message)} disabled={!canSend} /><span className="dash-adm-counter">{form.message.length}/4000</span>{errors.message && <small className="form-field-error">{errors.message}</small>}</label>
          <label>Optional action link<input name="action_url" value={form.action_url} placeholder="/opportunities or https://…" onChange={event => update({ action_url: event.target.value })} aria-invalid={Boolean(errors.action_url)} disabled={!canSend} />{errors.action_url && <small className="form-field-error">{errors.action_url}</small>}</label>
          <div className="dash-adm-send-row">
            <span className="dash-adm-muted">{reach !== undefined ? <>Will reach <strong>{reach}</strong> active account{reach === 1 ? '' : 's'}.</> : 'Recipients are counted when you send.'}</span>
            <button className="admin-button" disabled={sending || !canSend}><Send size={15} /> {sending ? 'Sending…' : 'Send notification'}</button>
          </div>
          {!canSend && <p className="dash-adm-hint">Sending needs the settings.write permission.</p>}
        </form>
      </section>

      <DashboardCard eyebrow="Preview" title="What recipients see" className="dash-adm-span-5 dash-adm-preview-card">
        <div className={`dash-adm-preview is-${form.notification_type}`}>
          <span className="dash-adm-preview-icon" aria-hidden="true"><TypeIcon size={18} /></span>
          <div>
            <small>{typeLabel} · just now</small>
            <strong>{form.title.trim() || 'Your notification title'}</strong>
            <p>{form.message.trim() || 'The message appears here, exactly as recipients will read it in their account notifications.'}</p>
            {form.action_url && <span className="dash-adm-preview-link"><Link2 size={13} /> {form.action_url}</span>}
          </div>
        </div>
        <ul className="dash-adm-preview-facts">
          <li><span>Audience</span><strong>{audienceLabel(form.audience)}</strong></li>
          <li><span>Recipients</span><strong>{reach ?? '—'}</strong></li>
          <li><span>Delivery</span><strong>Account inbox, read status per person</strong></li>
        </ul>
      </DashboardCard>
    </div>

    <section className="dashboard-card dash-adm-card notification-history-card">
      <div className="dash-adm-section-head">
        <div><h2>Recent delivery campaigns</h2><p>Management history of notifications sent from the dashboard and by the system.</p></div>
        <div className="dash-adm-head-tools">
          <select aria-label="Filter by type" value={historyType} onChange={event => setHistoryType(event.target.value)}><option value="">All types</option>{TYPES.map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select>
          <label className="dash-search-field dash-adm-export-search"><Search size={16} aria-hidden="true" /><input type="search" value={historyQuery} onChange={event => setHistoryQuery(event.target.value)} placeholder="Search history" aria-label="Search history" />{historyQuery && <button type="button" className="dash-adm-clear" onClick={() => setHistoryQuery('')} aria-label="Clear search"><X size={14} /></button>}</label>
        </div>
      </div>
      {loading ? <StateBlock type="loading" title="Loading notification history" /> : visibleHistory.length === 0 ? <StateBlock type="empty" title={history.length ? 'No notifications match' : 'No dashboard notifications sent yet'} /> : (
        <ol className="dash-adm-history">
          {visibleHistory.map(item => {
            const [, label, Icon] = typeMeta(item.type);
            const rate = item.recipient_count ? Math.round((item.read_count / item.recipient_count) * 100) : 0;
            return (
              <li key={item.id}>
                <button type="button" className="dash-adm-history-main" onClick={() => setSelected(item)}>
                  <span className={`dash-adm-preview-icon is-${item.type}`} aria-hidden="true"><Icon size={16} /></span>
                  <span className="dash-adm-history-copy"><strong>{item.title}</strong><small>{item.message}</small></span>
                </button>
                <span className="dash-adm-history-meta">
                  <span className="dash-adm-pill is-info">{audienceLabel(item.audience)}</span>
                  <span className="dash-adm-readbar" title={`${item.read_count}/${item.recipient_count} read`}><i><b style={{ width: `${rate}%` }} /></i>{item.read_count}/{item.recipient_count} read</span>
                  <time dateTime={item.created_at} title={new Date(item.created_at).toLocaleString()}>{relativeTime(item.created_at)}</time>
                </span>
                <ActionMenu label={`Actions for ${item.title}`} items={[
                  { label: 'View details', icon: Eye, onClick: () => setSelected(item) },
                  canSend && { label: 'Reuse as new notification', icon: Sparkles, onClick: () => reuse(item) },
                ]} />
                <span className="dash-adm-sr">{label}</span>
              </li>
            );
          })}
        </ol>
      )}
    </section>

    <Drawer open={Boolean(selected)} title={selected?.title || ''} subtitle={selected ? `${typeMeta(selected.type)[1]} · ${new Date(selected.created_at).toLocaleString()}` : ''} onClose={() => setSelected(null)}
      footer={selected && canSend && <button type="button" className="admin-button admin-button-secondary" onClick={() => reuse(selected)}><Sparkles size={15} /> Reuse as new notification</button>}>
      {selected && (
        <dl className="dash-adm-details">
          <div><dt>Message</dt><dd>{selected.message}</dd></div>
          {selected.action_url && <div><dt>Action link</dt><dd><code>{selected.action_url}</code></dd></div>}
          <div><dt>Audience</dt><dd>{audienceLabel(selected.audience)}</dd></div>
          <div><dt>Read</dt><dd>{selected.read_count} of {selected.recipient_count} recipients</dd></div>
          <div><dt>Sent by</dt><dd>{selected.created_by || 'System'}</dd></div>
        </dl>
      )}
    </Drawer>

    {confirming && (
      <DashboardModal title="Send this notification?" onClose={() => setConfirming(false)} footer={<>
        <button type="button" className="admin-button admin-button-secondary" onClick={() => setConfirming(false)}>Cancel</button>
        <button type="button" className="admin-button" onClick={send}><Send size={15} /> Send now</button>
      </>}>
        <div className="dash-adm-confirm">
          <p><strong>{form.title}</strong> will go to <strong>{audienceLabel(form.audience)}</strong>{reach !== undefined ? <> ({reach} active account{reach === 1 ? '' : 's'})</> : ''}. Notifications cannot be recalled once sent.</p>
        </div>
      </DashboardModal>
    )}
  </div>;
}
