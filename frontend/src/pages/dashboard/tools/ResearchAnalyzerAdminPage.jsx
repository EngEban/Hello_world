import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowRight,
  BarChart3,
  ExternalLink,
  Gauge,
  Plus,
  RefreshCw,
  Save,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';
import { DashboardApi } from '../../../api/dashboardApi';
import { UsageApi } from '../../../api/usageApi';
import AdminNotice from '../../../components/dashboard/AdminNotice.jsx';
import AdminPageHeader from '../../../components/dashboard/AdminPageHeader.jsx';
import { DashboardCard, StatCard } from '../../../components/dashboard/DashboardPrimitives.jsx';
import '../../../styles/dashboard/dash-admin.css';

const PERIOD_LABELS = { day: 'per day', month: 'per month', lifetime: 'in total' };

function money(cents, currency = 'USD') {
  try {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: currency || 'USD' }).format(Number(cents || 0) / 100);
  } catch {
    return `${currency} ${(Number(cents || 0) / 100).toFixed(2)}`;
  }
}

const FEATURE_CODE = 'research_analyzer';

const defaultFeature = {
  code: FEATURE_CODE,
  label: 'Research Analyzer',
  description: 'Guided upload, data preparation, statistical analysis, and master report generation.',
  free_enabled: false,
  premium_enabled: true,
  is_active: true,
};

const defaultLimit = {
  feature_code: FEATURE_CODE,
  tier: 'premium',
  period: 'month',
  limit: 25,
  is_active: true,
};

function normalizeFeature(feature) {
  return {
    ...defaultFeature,
    ...(feature || {}),
  };
}

function getAccessLevel(feature) {
  if (feature.free_enabled && feature.premium_enabled) return 'free';
  if (!feature.free_enabled && feature.premium_enabled) return 'premium';
  return 'admin';
}

function accessPatch(value) {
  if (value === 'free') return { free_enabled: true, premium_enabled: true };
  if (value === 'premium') return { free_enabled: false, premium_enabled: true };
  return { free_enabled: false, premium_enabled: false };
}

function accessLabel(feature) {
  if (!feature.is_active) return 'Disabled';
  if (feature.free_enabled && feature.premium_enabled) return 'Free + premium';
  if (!feature.free_enabled && feature.premium_enabled) return 'Premium only';
  if (feature.free_enabled && !feature.premium_enabled) return 'Free only';
  return 'Admin only';
}

export default function ResearchAnalyzerAdminPage() {
  const [feature, setFeature] = useState(defaultFeature);
  const [plans, setPlans] = useState([]);
  const [limits, setLimits] = useState([]);
  const [newLimit, setNewLimit] = useState(defaultLimit);
  const [policy, setPolicy] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  const analyzerLimits = useMemo(
    () => limits.filter(item => item.feature_code === FEATURE_CODE),
    [limits],
  );
  const activePlans = useMemo(
    () => plans.filter(item => item.is_active !== false),
    [plans],
  );

  const loadControls = async () => {
    setLoading(true);
    setError('');
    try {
      const [featureData, planData, limitData] = await Promise.all([
        DashboardApi.getFeatureEntitlements(),
        DashboardApi.getSubscriptionPlans(),
        DashboardApi.getUsageLimits(),
      ]);
      const featureList = featureData.results || [];
      const configuredFeature = featureList.find(item => item.code === FEATURE_CODE);
      setFeature(normalizeFeature(configuredFeature));
      setPlans(planData.results || []);
      setLimits(limitData.results || []);
    } catch (err) {
      setError(err?.message || 'Could not load analyzer controls.');
    } finally {
      setLoading(false);
    }
    try {
      const policyData = await UsageApi.getPolicies();
      setPolicy((policyData.results || []).find(item => item.feature_code === FEATURE_CODE) || null);
    } catch {
      setPolicy(null);
    }
  };

  const togglePolicyLimits = async enabled => {
    setSaving(true);
    setError('');
    setNotice('');
    try {
      const data = await UsageApi.savePolicy(FEATURE_CODE, { limits_enabled: enabled });
      setPolicy(data.policy);
      setNotice(enabled ? 'Analyzer usage limits switched on.' : 'Analyzer usage limits switched off: nobody is blocked (use is still counted).');
    } catch (err) {
      setError(err?.message || 'Could not save the usage switch.');
    } finally {
      setSaving(false);
    }
  };

  useEffect(() => {
    loadControls();
  }, []);

  const updateFeature = patch => {
    setFeature(current => ({ ...current, ...patch }));
  };

  const updateLimit = (id, patch) => {
    setLimits(current => current.map(item => (item.id === id ? { ...item, ...patch } : item)));
  };

  const saveFeature = async () => {
    setSaving(true);
    setError('');
    setNotice('');
    try {
      const data = await DashboardApi.saveFeatureEntitlement(feature, feature.id || null);
      setFeature(normalizeFeature(data.feature));
      setNotice('Research Analyzer access settings saved.');
    } catch (err) {
      setError(err?.message || 'Could not save analyzer access.');
    } finally {
      setSaving(false);
    }
  };

  const saveLimit = async limit => {
    setSaving(true);
    setError('');
    setNotice('');
    try {
      const data = await DashboardApi.saveUsageLimit(limit, limit.id || null);
      const saved = data.limit;
      setLimits(current => {
        const exists = current.some(item => item.id === saved.id);
        return exists ? current.map(item => (item.id === saved.id ? saved : item)) : [...current, saved];
      });
      setNewLimit(defaultLimit);
      setNotice('Usage limit saved.');
    } catch (err) {
      setError(err?.message || 'Could not save usage limit.');
    } finally {
      setSaving(false);
    }
  };

  const limitFields = (value, onChange) => (
    <>
      <label><span>Tier</span><select value={value.tier} onChange={event => onChange({ tier: event.target.value })}><option value="free">Free</option><option value="premium">Premium</option></select></label>
      <label><span>Period</span><select value={value.period} onChange={event => onChange({ period: event.target.value })}><option value="day">Daily</option><option value="month">Monthly</option><option value="lifetime">Lifetime</option></select></label>
      <label><span>Limit</span><input type="number" min="1" value={value.limit} onChange={event => onChange({ limit: Number(event.target.value) || 1 })} /></label>
    </>
  );

  return (
    <div className="admin-page research-analyzer-admin dash-adm-page">
      <AdminPageHeader
        eyebrow="Research tools"
        title="Research Analyzer Controls"
        text="Manage visibility, premium access, usage limits, and the public analyzer workspace from one secure dashboard page."
        actions={(
          <>
            <button className="admin-button admin-button-secondary" type="button" onClick={loadControls}>
              <RefreshCw size={15} /> Refresh
            </button>
            <Link className="admin-button" to="/tools/research-analyzer" target="_blank" rel="noreferrer">
              <ExternalLink size={15} /> Open Tool
            </Link>
          </>
        )}
      />

      {error && <AdminNotice type="error">{error}</AdminNotice>}
      {notice && <AdminNotice type="success">{notice}</AdminNotice>}

      <section className="dash-stat-grid" aria-label="Analyzer summary">
        <StatCard icon={BarChart3} label="Feature status" value={feature.is_active ? 'Active' : 'Disabled'} hint={feature.is_active ? 'Visible on the tools page' : 'Hidden from everyone'} tone={feature.is_active ? 'blue' : 'amber'} loading={loading} />
        <StatCard icon={ShieldCheck} label="Access rule" value={accessLabel(feature)} hint="Who can open the analyzer" loading={loading} />
        <StatCard icon={Gauge} label="Usage limits" value={analyzerLimits.length} hint={`${analyzerLimits.filter(item => item.is_active).length} active quotas`} loading={loading} />
        <StatCard icon={Sparkles} label="Active plans" value={activePlans.length} hint="Billing plans available" to="/dashboard/premium-controls?tab=plans" loading={loading} />
      </section>

      <div className="dash-adm-grid">
        <DashboardCard eyebrow="Feature entitlement" title="Free / premium access" className="dash-adm-span-7" actions={<button className="admin-button" type="button" onClick={saveFeature} disabled={saving || loading}><Save size={15} /> Save Access</button>}>
          <p className="dash-adm-hint">The public tool follows these dashboard rules. Backend endpoints also enforce access, so premium controls are not only hidden in the interface.</p>
          <div className="admin-form-grid dashboard-form dash-adm-ra-form">
            <label>Feature name<input value={feature.label || ''} onChange={event => updateFeature({ label: event.target.value })} /></label>
            <label>Feature code<input value={FEATURE_CODE} disabled /></label>
            <label>Access level
              <select value={getAccessLevel(feature)} onChange={event => updateFeature(accessPatch(event.target.value))}>
                <option value="free">Free registered users</option>
                <option value="premium">Premium users only</option>
                <option value="admin">Admin only</option>
              </select>
            </label>
            <label>Status
              <select value={feature.is_active ? 'active' : 'inactive'} onChange={event => updateFeature({ is_active: event.target.value === 'active' })}>
                <option value="active">Active and visible</option>
                <option value="inactive">Disabled</option>
              </select>
            </label>
            <label className="admin-field-full">Description<textarea rows={4} value={feature.description || ''} onChange={event => updateFeature({ description: event.target.value })} /></label>
          </div>
          <div className="dash-adm-access-map" aria-label="Access summary">
            <span className={feature.is_active && feature.free_enabled ? 'is-on' : ''}><strong>Free users</strong>{feature.is_active && feature.free_enabled ? 'Can use it' : 'No access'}</span>
            <span className={feature.is_active && feature.premium_enabled ? 'is-on' : ''}><strong>Premium users</strong>{feature.is_active && feature.premium_enabled ? 'Can use it' : 'No access'}</span>
            <span className={feature.is_active ? 'is-on' : ''}><strong>Administrators</strong>{feature.is_active ? 'Always' : 'Disabled'}</span>
          </div>
        </DashboardCard>

        <DashboardCard eyebrow="Billing" title="Plans" className="dash-adm-span-5" actions={<Link className="dash-adm-link" to="/dashboard/premium-controls?tab=plans">Manage plans <ArrowRight size={13} /></Link>}>
          {activePlans.length === 0 ? <p className="dash-adm-hint">No active plans yet. Create them in Premium controls.</p> : (
            <ul className="dash-adm-planlist">
              {activePlans.map(plan => (
                <li key={plan.id}>
                  <span><strong>{plan.label}</strong><small>{plan.is_public ? 'Public' : 'Hidden'} · {plan.provider === 'stripe' ? 'Stripe' : 'Manual'}</small></span>
                  <span className={`dash-adm-pill ${plan.tier === 'premium' ? 'is-premium' : 'is-free'}`}>{plan.tier === 'premium' ? 'Premium' : 'Free'}</span>
                  <em>{money(plan.price_cents, plan.currency)}{plan.billing_interval && plan.billing_interval !== 'none' ? ` / ${plan.billing_interval}` : ''}</em>
                </li>
              ))}
            </ul>
          )}
        </DashboardCard>

        <DashboardCard eyebrow="Usage limits" title="Analyzer quotas" className="dash-adm-span-12">
          {policy && (
            <div className="dash-adm-switches">
              <label className="admin-check">
                <input type="checkbox" checked={Boolean(policy.limits_enabled)} disabled={saving} onChange={event => togglePolicyLimits(event.target.checked)} />
                <span>Enforce the quotas below<small>Off = unlimited for everyone; runs are still counted. Today: {policy.used_today} analyses by {policy.subjects_today} {policy.subjects_today === 1 ? 'person' : 'people'}. Uploads and saving never count.</small></span>
              </label>
            </div>
          )}
          {analyzerLimits.length === 0 && (
            <AdminNotice type="info">
              No analyzer limits yet. Add a limit if you want to cap daily or monthly analyzer usage for free or premium users.
            </AdminNotice>
          )}
          {analyzerLimits.length > 0 && (
            <div className="dash-adm-quota-list">
              {analyzerLimits.map(limit => (
                <article className="dash-adm-quota" key={limit.id}>
                  <div className="dash-adm-quota-summary"><Gauge size={16} /><span><strong>{limit.limit} {PERIOD_LABELS[limit.period] || limit.period}</strong><small>{limit.tier === 'premium' ? 'Premium' : 'Free'} users · {limit.is_active ? 'active' : 'inactive'}</small></span></div>
                  <div className="dash-adm-filters">
                    {limitFields(limit, patch => updateLimit(limit.id, patch))}
                    <label><span>Status</span><select value={limit.is_active ? 'active' : 'inactive'} onChange={event => updateLimit(limit.id, { is_active: event.target.value === 'active' })}><option value="active">Active</option><option value="inactive">Inactive</option></select></label>
                  </div>
                  <button className="admin-button admin-button-secondary" type="button" onClick={() => saveLimit(limit)} disabled={saving}><Save size={14} /> Save</button>
                </article>
              ))}
            </div>
          )}
          <div className="dash-adm-quota is-new">
            <div className="dash-adm-quota-summary"><Plus size={16} /><span><strong>Add usage rule</strong><small>{newLimit.tier === 'premium' ? 'Premium' : 'Free'} users get {newLimit.limit} analyses {PERIOD_LABELS[newLimit.period]}</small></span></div>
            <div className="dash-adm-filters">{limitFields(newLimit, patch => setNewLimit(current => ({ ...current, ...patch })))}</div>
            <button className="admin-button" type="button" onClick={() => saveLimit(newLimit)} disabled={saving}><Plus size={14} /> Add Limit</button>
          </div>
        </DashboardCard>
      </div>
    </div>
  );
}
