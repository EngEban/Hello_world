import { CreditCard, DollarSign, ExternalLink, Gauge, Pencil, Plus, RefreshCw, Save, Search, ShieldCheck, Sparkles, X } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useOutletContext, useSearchParams } from 'react-router-dom';
import { DashboardApi } from '../../../api/dashboardApi';
import { UsageApi } from '../../../api/usageApi';
import ActionMenu from '../../../components/dashboard/ActionMenu';
import AdminNotice from '../../../components/dashboard/AdminNotice';
import AdminPageHeader from '../../../components/dashboard/AdminPageHeader';
import { DashboardTable, Drawer, StatCard, StateBlock, Tabs } from '../../../components/dashboard/DashboardPrimitives';
import { hasPermission } from '../users/adminShared';
import '../../../styles/dashboard/dash-admin.css';

const emptyPlan = { code: '', label: '', description: '', tier: 'premium', provider: 'manual', provider_price_id: '', billing_interval: 'month', price_cents: 0, currency: 'USD', is_public: true, is_active: true };
const emptyFeature = { code: '', label: '', description: '', free_enabled: true, premium_enabled: true, is_active: true };
const emptyLimit = { feature_code: 'journal_finder', tier: 'free', period: 'day', limit: 50, is_active: true };
const PERIOD_LABELS = { day: 'per day', month: 'per month', lifetime: 'in total' };
const INTERVAL_LABELS = { none: 'one-off / no billing', month: 'per month', year: 'per year' };
const DISPLAY_LABELS = { always: 'Always show', near_limit: 'Near the limit', never: 'Never' };

// Plain-language warnings when Premium would get less than Free.
function tierWarnings(limits, labelFor) {
  const active = limits.filter(item => item.is_active);
  const warnings = [];
  active.filter(item => item.tier === 'premium').forEach(premium => {
    const free = active.find(item => item.tier === 'free' && item.feature_code === premium.feature_code && item.period === premium.period);
    const name = labelFor(premium.feature_code);
    if (!free && !active.some(item => item.tier === 'free' && item.feature_code === premium.feature_code)) {
      warnings.push(`${name}: Premium is limited to ${premium.limit} ${PERIOD_LABELS[premium.period] || premium.period}, but Free has no limit at all.`);
    } else if (free && free.limit > premium.limit) {
      warnings.push(`${name}: Free allows ${free.limit} ${PERIOD_LABELS[free.period]}, more than Premium (${premium.limit}).`);
    }
  });
  return warnings;
}

function money(cents, currency = 'USD') {
  const value = Number(cents || 0) / 100;
  try {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: currency || 'USD' }).format(value);
  } catch {
    return `${currency || 'USD'} ${value.toFixed(2)}`;
  }
}

function accessLabel(feature) {
  if (!feature.is_active) return 'Disabled';
  if (feature.free_enabled && feature.premium_enabled) return 'Free + Premium';
  if (!feature.free_enabled && feature.premium_enabled) return 'Premium only';
  if (feature.free_enabled && !feature.premium_enabled) return 'Free only';
  return 'No tier access';
}
const accessTone = feature => (!feature.is_active ? 'is-off' : !feature.free_enabled && feature.premium_enabled ? 'is-premium' : feature.free_enabled && feature.premium_enabled ? 'is-ok' : 'is-warn');

function Switch({ checked, onChange, label, disabled }) {
  return (
    <label className="dash-adm-switch" title={label} onClick={event => event.stopPropagation()}>
      <input type="checkbox" checked={Boolean(checked)} onChange={event => onChange(event.target.checked)} disabled={disabled} aria-label={label} />
      <span aria-hidden="true" />
    </label>
  );
}

export default function DashboardPremiumControlsPage() {
  const { user, bootstrap } = useOutletContext() || {};
  const canWrite = hasPermission(user, bootstrap, 'premium.edit');
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = ['features', 'plans', 'limits', 'enforcement'].includes(searchParams.get('tab')) ? searchParams.get('tab') : 'features';
  const [features, setFeatures] = useState([]);
  const [plans, setPlans] = useState([]);
  const [limits, setLimits] = useState([]);
  const [policies, setPolicies] = useState([]);
  const [usageTimezone, setUsageTimezone] = useState('UTC');
  const [editor, setEditor] = useState(null); // { kind: 'feature'|'plan'|'limit', item }
  const [query, setQuery] = useState('');
  const [featureFilter, setFeatureFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  const loadPremiumControls = async () => {
    setLoading(true);
    setError('');
    try {
      const [featureData, planData, limitData] = await Promise.all([
        DashboardApi.getFeatureEntitlements(),
        DashboardApi.getSubscriptionPlans(),
        DashboardApi.getUsageLimits(),
      ]);
      setFeatures(featureData.results || []);
      setPlans(planData.results || []);
      setLimits(limitData.results || []);
    } catch (err) {
      setError(err.message || 'Premium controls could not be loaded.');
    } finally {
      setLoading(false);
    }
    // Usage policies load separately so an older backend without the usage
    // app still shows the other tabs.
    try {
      const policyData = await UsageApi.getPolicies();
      setPolicies(policyData.results || []);
      setUsageTimezone(policyData.timezone || 'UTC');
    } catch {
      setPolicies([]);
    }
  };
  useEffect(() => { loadPremiumControls(); }, []);
  const setTab = value => { const params = new URLSearchParams(searchParams); if (value === 'features') params.delete('tab'); else params.set('tab', value); setSearchParams(params, { replace: true }); setQuery(''); };

  const premiumSummary = useMemo(() => ({
    activeFeatures: features.filter(item => item.is_active).length,
    premiumOnly: features.filter(item => item.is_active && item.premium_enabled && !item.free_enabled).length,
    publicPlans: plans.filter(item => item.is_active && item.is_public).length,
    activeLimits: limits.filter(item => item.is_active).length,
  }), [features, plans, limits]);
  const featureByCode = useMemo(() => Object.fromEntries(features.map(item => [item.code, item])), [features]);
  const limitsByFeature = useMemo(() => limits.reduce((map, item) => ({ ...map, [item.feature_code]: [...(map[item.feature_code] || []), item] }), {}), [limits]);

  const matches = (...values) => !query.trim() || values.join(' ').toLowerCase().includes(query.trim().toLowerCase());
  const visibleFeatures = features.filter(item => matches(item.label, item.code, item.description) && (
    !featureFilter || (featureFilter === 'premium' && item.is_active && item.premium_enabled && !item.free_enabled)
    || (featureFilter === 'free' && item.is_active && item.free_enabled) || (featureFilter === 'disabled' && !item.is_active)));
  const visiblePlans = plans.filter(item => matches(item.label, item.code, item.description, item.tier, item.provider));
  const visibleLimits = limits.filter(item => matches(item.feature_code, featureByCode[item.feature_code]?.label, item.tier, item.period));
  const visiblePolicies = policies.filter(item => matches(item.label, item.feature_code));
  const warnings = useMemo(() => tierWarnings(limits, code => featureByCode[code]?.label || code), [limits, featureByCode]);

  const saveFeature = async item => {
    setError(''); setSaving(true);
    try {
      const isNew = !item.id || item.id === 'new';
      const data = await DashboardApi.saveFeatureEntitlement(item, isNew ? null : item.id);
      setFeatures(current => (isNew ? [...current, data.feature] : current.map(entry => (entry.id === data.feature.id ? data.feature : entry))).sort((a, b) => a.label.localeCompare(b.label)));
      setNotice(`Feature access saved: ${data.feature.label}`);
      return true;
    } catch (err) {
      setError(err.message);
      return false;
    } finally { setSaving(false); }
  };
  const savePlan = async item => {
    setError(''); setSaving(true);
    try {
      const isNew = !item.id || item.id === 'new';
      const data = await DashboardApi.saveSubscriptionPlan(item, isNew ? null : item.id);
      setPlans(current => (isNew ? [...current, data.plan] : current.map(entry => (entry.id === data.plan.id ? data.plan : entry))));
      setNotice(`Plan saved: ${data.plan.label}`);
      return true;
    } catch (err) {
      setError(err.message);
      return false;
    } finally { setSaving(false); }
  };
  const saveLimit = async item => {
    setError(''); setSaving(true);
    try {
      const isNew = !item.id || item.id === 'new';
      const data = await DashboardApi.saveUsageLimit(item, isNew ? null : item.id);
      setLimits(current => (isNew ? [...current, data.limit] : current.map(entry => (entry.id === data.limit.id ? data.limit : entry))));
      setNotice(`Usage limit saved: ${data.limit.feature_code}`);
      return true;
    } catch (err) {
      setError(err.message);
      return false;
    } finally { setSaving(false); }
  };
  const savePolicy = async item => {
    setError(''); setSaving(true);
    try {
      const data = await UsageApi.savePolicy(item.feature_code, item);
      setPolicies(current => current.map(entry => (entry.feature_code === data.policy.feature_code ? data.policy : entry)));
      setNotice(`Usage enforcement saved: ${data.policy.label} (limits ${data.policy.limits_enabled ? 'on' : 'off'})`);
      return true;
    } catch (err) {
      setError(err.message);
      return false;
    } finally { setSaving(false); }
  };
  const saveEditor = async event => {
    event.preventDefault();
    const save = { feature: saveFeature, plan: savePlan, limit: saveLimit, policy: savePolicy }[editor.kind];
    if (await save(editor.item)) setEditor(null);
  };
  const patchEditor = patch => setEditor(current => ({ ...current, item: { ...current.item, ...patch } }));
  const isNewItem = editor && (!editor.item.id || editor.item.id === 'new');

  const featureColumns = [
    { key: 'label', label: 'Feature', render: row => <span className="dash-adm-stack dash-adm-feature"><strong>{row.label}</strong><code>{row.code}</code>{row.description && <small>{row.description}</small>}</span> },
    { key: 'access', label: 'Access', render: row => <span className={`dash-adm-pill ${accessTone(row)}`}>{accessLabel(row)}</span> },
    { key: 'free_enabled', label: 'Free users', render: row => <Switch checked={row.free_enabled} disabled={!canWrite || saving} label={`Free users can use ${row.label}`} onChange={value => saveFeature({ ...row, free_enabled: value })} /> },
    { key: 'premium_enabled', label: 'Premium users', render: row => <Switch checked={row.premium_enabled} disabled={!canWrite || saving} label={`Premium users can use ${row.label}`} onChange={value => saveFeature({ ...row, premium_enabled: value })} /> },
    { key: 'is_active', label: 'Active', render: row => <Switch checked={row.is_active} disabled={!canWrite || saving} label={`${row.label} is active`} onChange={value => saveFeature({ ...row, is_active: value })} /> },
    { key: 'limits', label: 'Limits', render: row => { const count = (limitsByFeature[row.code] || []).filter(item => item.is_active).length; return count ? <button type="button" className="dash-adm-link" onClick={() => { setTab('limits'); setQuery(row.code); }}><Gauge size={13} /> {count}</button> : <span className="dash-adm-muted">None</span>; } },
    { key: 'actions', label: 'Actions', render: row => <span className="dash-adm-row-actions" onClick={event => event.stopPropagation()} onKeyDown={event => event.stopPropagation()}><ActionMenu label={`Actions for ${row.label}`} items={[
      { label: canWrite ? 'Edit feature' : 'View feature', icon: Pencil, onClick: () => setEditor({ kind: 'feature', item: row }) },
      canWrite && { label: 'Add usage limit', icon: Gauge, onClick: () => setEditor({ kind: 'limit', item: { ...emptyLimit, feature_code: row.code } }) },
    ]} /></span> },
  ];
  const planColumns = [
    { key: 'label', label: 'Plan', render: row => <span className="dash-adm-stack dash-adm-feature"><strong>{row.label}</strong><code>{row.code}</code>{row.description && <small>{row.description}</small>}</span> },
    { key: 'tier', label: 'Tier', render: row => <span className={`dash-adm-pill ${row.tier === 'premium' ? 'is-premium' : 'is-free'}`}>{row.tier === 'premium' ? 'Premium' : 'Free'}</span> },
    { key: 'price', label: 'Price', render: row => <span className="dash-adm-stack"><strong className="dash-adm-price">{money(row.price_cents, row.currency)}</strong><small>{INTERVAL_LABELS[row.billing_interval] || row.billing_interval}</small></span> },
    { key: 'provider', label: 'Provider', render: row => <span className="dash-adm-stack"><span>{row.provider === 'stripe' ? 'Stripe' : 'Manual'}</span>{row.provider_price_id && <code>{row.provider_price_id}</code>}</span> },
    { key: 'visibility', label: 'Status', render: row => <span className="dash-adm-stack"><span className={`dash-adm-pill ${row.is_active ? 'is-ok' : 'is-off'}`}>{row.is_active ? 'Active' : 'Inactive'}</span><small>{row.is_public ? 'Public' : 'Hidden'}</small></span> },
    { key: 'actions', label: 'Actions', render: row => <span className="dash-adm-row-actions" onClick={event => event.stopPropagation()} onKeyDown={event => event.stopPropagation()}><ActionMenu label={`Actions for ${row.label}`} items={[
      { label: canWrite ? 'Edit plan' : 'View plan', icon: Pencil, onClick: () => setEditor({ kind: 'plan', item: row }) },
      canWrite && { label: row.is_active ? 'Deactivate plan' : 'Activate plan', icon: CreditCard, onClick: () => savePlan({ ...row, is_active: !row.is_active }) },
      canWrite && { label: row.is_public ? 'Hide from public' : 'Make public', icon: ShieldCheck, onClick: () => savePlan({ ...row, is_public: !row.is_public }) },
    ]} /></span> },
  ];
  const limitColumns = [
    { key: 'feature_code', label: 'Feature', render: row => <span className="dash-adm-stack dash-adm-feature"><strong>{featureByCode[row.feature_code]?.label || row.feature_code}</strong><code>{row.feature_code}</code></span> },
    { key: 'tier', label: 'Tier', render: row => <span className={`dash-adm-pill ${row.tier === 'premium' ? 'is-premium' : 'is-free'}`}>{row.tier === 'premium' ? 'Premium' : 'Free'}</span> },
    { key: 'limit', label: 'Allowance', render: row => <span className="dash-adm-stack"><strong className="dash-adm-price">{row.limit}</strong><small>{PERIOD_LABELS[row.period] || row.period}</small></span> },
    { key: 'is_active', label: 'Active', render: row => <Switch checked={row.is_active} disabled={!canWrite || saving} label={`Limit for ${row.feature_code} is active`} onChange={value => saveLimit({ ...row, is_active: value })} /> },
    { key: 'actions', label: 'Actions', render: row => <span className="dash-adm-row-actions" onClick={event => event.stopPropagation()} onKeyDown={event => event.stopPropagation()}><ActionMenu label={`Actions for ${row.feature_code} limit`} items={[
      { label: canWrite ? 'Edit limit' : 'View limit', icon: Pencil, onClick: () => setEditor({ kind: 'limit', item: row }) },
    ]} /></span> },
  ];

  const policyColumns = [
    { key: 'label', label: 'Feature', render: row => <span className="dash-adm-stack dash-adm-feature"><strong>{row.label}</strong><code>{row.feature_code}</code><small>{row.runs_in_browser ? 'Runs in the browser: counted when results are shown' : 'Counted on the server'}</small></span> },
    { key: 'limits_enabled', label: 'Limits on', render: row => <Switch checked={row.limits_enabled} disabled={!canWrite || saving} label={`Usage limits are enforced for ${row.label}`} onChange={value => savePolicy({ ...row, limits_enabled: value })} /> },
    { key: 'used_today', label: 'Used today', render: row => <span className="dash-adm-stack"><strong className="dash-adm-price">{row.used_today}</strong><small>{row.subjects_today} {row.subjects_today === 1 ? 'person' : 'people'}</small></span> },
    { key: 'anonymous', label: 'Visitors (no account)', render: row => <span className="dash-adm-stack"><Switch checked={row.meter_anonymous} disabled={!canWrite || saving} label={`Count visitors without an account for ${row.label}`} onChange={value => savePolicy({ ...row, meter_anonymous: value })} /><small>{row.meter_anonymous ? (row.anonymous_daily_limit != null ? `${row.anonymous_daily_limit} per day` : 'Counted, no limit') : 'Not counted'}</small></span> },
    { key: 'admin_bypass', label: 'Admins unlimited', render: row => <Switch checked={row.admin_bypass} disabled={!canWrite || saving} label={`Administrators are never limited on ${row.label}`} onChange={value => savePolicy({ ...row, admin_bypass: value })} /> },
    { key: 'display_mode', label: 'Show remaining', render: row => <span className="dash-adm-muted">{DISPLAY_LABELS[row.display_mode] || row.display_mode}</span> },
    { key: 'actions', label: 'Actions', render: row => <span className="dash-adm-row-actions" onClick={event => event.stopPropagation()} onKeyDown={event => event.stopPropagation()}><ActionMenu label={`Actions for ${row.label} enforcement`} items={[
      { label: canWrite ? 'Edit enforcement' : 'View enforcement', icon: Pencil, onClick: () => setEditor({ kind: 'policy', item: row }) },
      { label: 'Show Free/Premium limits', icon: Gauge, onClick: () => { setTab('limits'); setQuery(row.feature_code); } },
    ]} /></span> },
  ];

  const newButton = {
    features: canWrite && <button type="button" className="admin-button" onClick={() => setEditor({ kind: 'feature', item: { ...emptyFeature, id: 'new' } })}><Plus size={15} /> Add feature rule</button>,
    plans: canWrite && <button type="button" className="admin-button" onClick={() => setEditor({ kind: 'plan', item: { ...emptyPlan, id: 'new' } })}><Plus size={15} /> Create Plan</button>,
    limits: canWrite && <button type="button" className="admin-button" onClick={() => setEditor({ kind: 'limit', item: { ...emptyLimit, id: 'new' } })}><Plus size={15} /> Create Limit</button>,
    enforcement: null,
  }[tab];
  const intro = {
    features: 'Turn off Free access to make a tool premium-only. The backend entitlement system uses these rules. Switches save immediately.',
    plans: 'Prepare Free and Premium plans safely. Stripe price IDs are references only; card details are never stored.',
    limits: 'Limit expensive tools by feature, user tier, and period. Example: free users get 50 Journal Finder searches per day.',
    enforcement: `Master switches for the limits. "Limits on" off means nobody is blocked for that tool (use is still counted). Days reset at midnight ${usageTimezone}. Administrators are never limited unless you turn that off.`,
  }[tab];
  const editorTitles = { feature: ['Add feature rule', 'Edit feature access'], plan: ['New plan', 'Edit plan'], limit: ['New limit', 'Edit usage limit'], policy: ['Usage enforcement', 'Usage enforcement'] };

  return (
    <div className="dash-adm-page">
      <AdminPageHeader
        eyebrow="Monetisation"
        title="Premium Controls"
        text="Control which tools are free, premium-only, limited, public, active, or connected to future billing plans."
        actions={<>
          <a className="admin-button admin-button-secondary" href="/account" target="_blank" rel="noreferrer"><ExternalLink size={15} /> Preview Account Page</a>
          <button className="admin-button admin-button-secondary" type="button" onClick={loadPremiumControls}><RefreshCw size={15} /> Refresh Controls</button>
        </>}
      />
      {notice && <AdminNotice type="success">{notice}</AdminNotice>}
      {error && <AdminNotice type="error">{error}</AdminNotice>}
      {warnings.length > 0 && <AdminNotice type="info">Check these limits: {warnings.join(' ')}</AdminNotice>}

      <section className="dash-stat-grid" aria-label="Premium summary">
        <StatCard icon={ShieldCheck} label="Active features" value={premiumSummary.activeFeatures} hint={`${features.length} feature rules`} loading={loading} />
        <StatCard icon={Sparkles} label="Premium only" value={premiumSummary.premiumOnly} hint="Hidden from Free users" loading={loading} />
        <StatCard icon={DollarSign} label="Public plans" value={premiumSummary.publicPlans} hint={`${plans.length} plans in total`} loading={loading} />
        <StatCard icon={Gauge} label="Usage limits" value={premiumSummary.activeLimits} hint="Active quotas" loading={loading} />
      </section>

      <div className="dash-adm-tabbar">
        <Tabs label="Premium controls" value={tab} onChange={setTab} tabs={[
          { id: 'features', label: 'Features', count: features.length },
          { id: 'plans', label: 'Plans', count: plans.length },
          { id: 'limits', label: 'Usage limits', count: limits.length },
          { id: 'enforcement', label: 'Enforcement', count: policies.length },
        ]} />
        {newButton}
      </div>

      <section className={`dashboard-card dash-adm-card dash-adm-cards ${tab === 'features' ? 'dash-adm-premium-features' : ''}`}>
        <div className="dash-adm-section-head">
          <div><h2>{{ features: 'Tool Access Control', plans: 'Subscription Plans', limits: 'Usage Limits', enforcement: 'Usage Enforcement' }[tab]}</h2><p>{intro}</p></div>
          <div className="dash-adm-head-tools">
            {tab === 'features' && <select aria-label="Filter features" value={featureFilter} onChange={event => setFeatureFilter(event.target.value)}><option value="">All features</option><option value="premium">Premium only</option><option value="free">Available to Free</option><option value="disabled">Disabled</option></select>}
            <label className="dash-search-field dash-adm-export-search"><Search size={16} aria-hidden="true" /><input type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Search" aria-label="Search this list" />{query && <button type="button" className="dash-adm-clear" onClick={() => setQuery('')} aria-label="Clear search"><X size={14} /></button>}</label>
          </div>
        </div>
        {loading ? <StateBlock type="loading" title="Loading premium controls" /> : (
          <>
            {tab === 'features' && (features.length === 0
              ? <StateBlock type="empty" title="No features loaded yet" text="Click Refresh Controls. If this stays empty, the backend server needs a restart from the correct project folder." />
              : <DashboardTable rows={visibleFeatures} columns={featureColumns} onRowClick={row => setEditor({ kind: 'feature', item: row })} emptyTitle="No features match" />)}
            {tab === 'plans' && <DashboardTable rows={visiblePlans} columns={planColumns} onRowClick={row => setEditor({ kind: 'plan', item: row })} emptyTitle={plans.length ? 'No plans match' : 'No plans yet'} />}
            {tab === 'enforcement' && <DashboardTable rows={visiblePolicies} columns={policyColumns} onRowClick={row => setEditor({ kind: 'policy', item: row })} emptyTitle={policies.length ? 'No tools match' : 'Usage enforcement is not available on this server yet'} />}
            {tab === 'limits' && <DashboardTable rows={visibleLimits} columns={limitColumns} onRowClick={row => setEditor({ kind: 'limit', item: row })} emptyTitle={limits.length ? 'No limits match' : 'No usage limits yet'} />}
          </>
        )}
      </section>

      <datalist id="premium-feature-codes">{features.map(item => <option key={item.code} value={item.code}>{item.label}</option>)}</datalist>
      <Drawer
        open={Boolean(editor)}
        title={editor ? editorTitles[editor.kind][isNewItem ? 0 : 1] : ''}
        subtitle={editor && !isNewItem ? (editor.item.label || editor.item.feature_code) : 'Nothing is saved until you click the button below.'}
        onClose={() => setEditor(null)}
        footer={<>
          <button type="button" className="admin-button admin-button-secondary" onClick={() => setEditor(null)}>Cancel</button>
          {canWrite && editor && <button type="submit" form="premium-editor" className="admin-button" disabled={saving}><Save size={15} /> {saving ? 'Saving…' : { feature: isNewItem ? 'Create Rule' : 'Save Access', plan: isNewItem ? 'Create Plan' : 'Save Plan', limit: isNewItem ? 'Create Limit' : 'Save Limit', policy: 'Save Enforcement' }[editor.kind]}</button>}
        </>}
      >
        {editor && (
          <form id="premium-editor" className="dashboard-form dash-adm-form" onSubmit={saveEditor}>
            <fieldset disabled={!canWrite} className="dash-adm-fieldset">
              {editor.kind === 'feature' && <>
                <div className="dash-adm-form-section">
                  <div className="admin-form-grid">
                    <label>Feature code<input value={editor.item.code || ''} disabled={!isNewItem} onChange={event => patchEditor({ code: event.target.value })} placeholder="journal_finder" required /></label>
                    <label>Display label<input value={editor.item.label || ''} onChange={event => patchEditor({ label: event.target.value })} placeholder="Journal Finder" required /></label>
                  </div>
                  <label>Description<textarea value={editor.item.description || ''} onChange={event => patchEditor({ description: event.target.value })} rows="3" /></label>
                </div>
                <div className="dash-adm-form-section">
                  <h3>Who can use it</h3>
                  <p className="dash-adm-hint">Result: <span className={`dash-adm-pill ${accessTone(editor.item)}`}>{accessLabel(editor.item)}</span></p>
                  <div className="dash-adm-switches">
                    <label className="admin-check"><input type="checkbox" checked={Boolean(editor.item.is_active)} onChange={event => patchEditor({ is_active: event.target.checked })} /><span>Active<small>Disabled features are unavailable to everyone.</small></span></label>
                    <label className="admin-check"><input type="checkbox" checked={Boolean(editor.item.free_enabled)} onChange={event => patchEditor({ free_enabled: event.target.checked })} /><span>Free users</span></label>
                    <label className="admin-check"><input type="checkbox" checked={Boolean(editor.item.premium_enabled)} onChange={event => patchEditor({ premium_enabled: event.target.checked })} /><span>Premium users</span></label>
                  </div>
                </div>
              </>}
              {editor.kind === 'plan' && <>
                <div className="dash-adm-form-section">
                  <div className="admin-form-grid">
                    <label>Code<input value={editor.item.code || ''} disabled={!isNewItem} onChange={event => patchEditor({ code: event.target.value })} placeholder="premium_monthly" required /></label>
                    <label>Label<input value={editor.item.label || ''} onChange={event => patchEditor({ label: event.target.value })} placeholder="Premium Monthly" required /></label>
                    <label>Tier<select value={editor.item.tier || 'free'} onChange={event => patchEditor({ tier: event.target.value })}><option value="free">Free</option><option value="premium">Premium</option></select></label>
                    <label>Billing<select value={editor.item.billing_interval || 'none'} onChange={event => patchEditor({ billing_interval: event.target.value })}><option value="none">None</option><option value="month">Monthly</option><option value="year">Yearly</option></select></label>
                  </div>
                  <label>Description<textarea value={editor.item.description || ''} onChange={event => patchEditor({ description: event.target.value })} rows="3" /></label>
                </div>
                <div className="dash-adm-form-section">
                  <h3>Price and provider</h3>
                  <div className="admin-form-grid">
                    <label>Price cents<input type="number" min="0" value={editor.item.price_cents || 0} onChange={event => patchEditor({ price_cents: Number(event.target.value) })} /><small className="dash-adm-muted">Shown as {money(editor.item.price_cents, editor.item.currency)}</small></label>
                    <label>Currency<input value={editor.item.currency || 'USD'} onChange={event => patchEditor({ currency: event.target.value })} /></label>
                    <label>Provider<select value={editor.item.provider || 'manual'} onChange={event => patchEditor({ provider: event.target.value })}><option value="manual">Manual</option><option value="stripe">Stripe</option></select></label>
                    <label>Stripe price ID<input value={editor.item.provider_price_id || ''} onChange={event => patchEditor({ provider_price_id: event.target.value })} placeholder="price_..." /></label>
                  </div>
                  <div className="dash-adm-switches">
                    <label className="admin-check"><input type="checkbox" checked={Boolean(editor.item.is_public)} onChange={event => patchEditor({ is_public: event.target.checked })} /><span>Public<small>Listed on the account and upgrade pages.</small></span></label>
                    <label className="admin-check"><input type="checkbox" checked={Boolean(editor.item.is_active)} onChange={event => patchEditor({ is_active: event.target.checked })} /><span>Active</span></label>
                  </div>
                </div>
              </>}
              {editor.kind === 'policy' && <>
                <div className="dash-adm-form-section">
                  <h3>{editor.item.label}</h3>
                  <p className="dash-adm-hint">Free and Premium allowances are set on the Usage limits tab. These switches decide whether those limits apply at all.</p>
                  <div className="dash-adm-switches">
                    <label className="admin-check"><input type="checkbox" checked={Boolean(editor.item.limits_enabled)} onChange={event => patchEditor({ limits_enabled: event.target.checked })} /><span>Limits on<small>Off = unlimited for everyone. Use is still counted.</small></span></label>
                    <label className="admin-check"><input type="checkbox" checked={Boolean(editor.item.admin_bypass)} onChange={event => patchEditor({ admin_bypass: event.target.checked })} /><span>Administrators unlimited</span></label>
                  </div>
                </div>
                <div className="dash-adm-form-section">
                  <h3>Visitors without an account</h3>
                  <div className="dash-adm-switches">
                    <label className="admin-check"><input type="checkbox" checked={Boolean(editor.item.meter_anonymous)} onChange={event => patchEditor({ meter_anonymous: event.target.checked })} /><span>Count visitors by network address<small>Addresses are stored only as a one-way code. Shared networks (offices, universities) share one allowance.</small></span></label>
                  </div>
                  <div className="admin-form-grid">
                    <label>Visitor daily limit<input type="number" min="0" value={editor.item.anonymous_daily_limit ?? ''} onChange={event => patchEditor({ anonymous_daily_limit: event.target.value === '' ? null : Number(event.target.value) })} placeholder="No limit" /></label>
                    <label>Visitor monthly limit<input type="number" min="0" value={editor.item.anonymous_monthly_limit ?? ''} onChange={event => patchEditor({ anonymous_monthly_limit: event.target.value === '' ? null : Number(event.target.value) })} placeholder="No limit" /></label>
                  </div>
                </div>
                <div className="dash-adm-form-section">
                  <h3>What users see</h3>
                  <div className="admin-form-grid">
                    <label>Show remaining allowance<select value={editor.item.display_mode || 'near_limit'} onChange={event => patchEditor({ display_mode: event.target.value })}>{Object.entries(DISPLAY_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
                  </div>
                  <label>Extra message when the limit is reached<input value={editor.item.limit_message || ''} maxLength={300} onChange={event => patchEditor({ limit_message: event.target.value })} placeholder="Upgrade to Premium for more searches." /></label>
                  <p className="dash-adm-hint">Today: {editor.item.used_today} uses by {editor.item.subjects_today} {editor.item.subjects_today === 1 ? 'person' : 'people'}.</p>
                </div>
              </>}
              {editor.kind === 'limit' && (
                <div className="dash-adm-form-section">
                  <div className="admin-form-grid">
                    <label>Feature code<input list="premium-feature-codes" value={editor.item.feature_code || ''} disabled={!isNewItem} onChange={event => patchEditor({ feature_code: event.target.value })} required /></label>
                    <label>Tier<select value={editor.item.tier || 'free'} onChange={event => patchEditor({ tier: event.target.value })}><option value="free">Free</option><option value="premium">Premium</option></select></label>
                    <label>Period<select value={editor.item.period || 'day'} onChange={event => patchEditor({ period: event.target.value })}><option value="day">Daily</option><option value="month">Monthly</option><option value="lifetime">Lifetime</option></select></label>
                    <label>Limit<input type="number" min="1" value={editor.item.limit || 1} onChange={event => patchEditor({ limit: Number(event.target.value) })} /></label>
                  </div>
                  <p className="dash-adm-hint">{editor.item.tier === 'premium' ? 'Premium' : 'Free'} users can use {featureByCode[editor.item.feature_code]?.label || editor.item.feature_code || 'this feature'} {editor.item.limit || 1} {editor.item.limit === 1 ? 'time' : 'times'} {PERIOD_LABELS[editor.item.period] || ''}.</p>
                  <div className="dash-adm-switches"><label className="admin-check"><input type="checkbox" checked={Boolean(editor.item.is_active)} onChange={event => patchEditor({ is_active: event.target.checked })} /><span>Limit active</span></label></div>
                </div>
              )}
            </fieldset>
          </form>
        )}
      </Drawer>
    </div>
  );
}
