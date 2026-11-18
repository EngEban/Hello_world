import { get, post } from './apiClient';
import { trackEvent } from '../utils/analytics';

// Server-side usage allowances (backend/usage). The server is the only
// authority: these calls just read or report usage so the UI can explain it.
export const UsageApi = {
  getAll: () => get('/usage/'),
  getFeature: feature => get(`/usage/${encodeURIComponent(feature)}/`),
  // Browser-side tools (Journal Finder, Sample Size Calculator) report one
  // action here before showing results; a 429 means the allowance is used up.
  consume: async feature => {
    const data = await post(`/usage/${encodeURIComponent(feature)}/consume/`, {});
    trackEvent('tool_use', { tool_name: feature });
    return data;
  },
  // Dashboard (settings permission).
  getPolicies: () => get('/usage/admin/policies/'),
  savePolicy: (feature, payload) => post(`/usage/admin/policies/${encodeURIComponent(feature)}/save/`, payload),
};

export const isUsageLimitError = error => error?.status === 429 && error?.code === 'usage_limit';

// Errors that must stop a browser-side tool. Anything else (network blips,
// timeouts) lets the tool continue: it already runs in the browser.
export const isUsageRefusal = error => isUsageLimitError(error)
  || ['premium_required', 'auth_required', 'feature_disabled'].includes(error?.code);

export const usageFromError = error => error?.data?.usage || null;

export function formatResetTime(iso) {
  if (!iso) return '';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
}

const PERIOD_WORDS = { day: 'today', month: 'this month', lifetime: 'in total' };
const PLAN_WORDS = { free: 'Free plan', premium: 'Premium plan', anonymous: 'without an account' };

// "3 of 10 searches used today (Free plan)." or '' when nothing should show.
export function usageSummary(usage) {
  if (!usage || usage.unlimited || usage.limit == null || usage.display_mode === 'never') return '';
  const remaining = Number(usage.remaining ?? 0);
  const limit = Number(usage.limit);
  const nearLimit = remaining <= Math.max(3, Math.ceil(limit * 0.2));
  if (usage.display_mode !== 'always' && !nearLimit) return '';
  const unit = limit === 1 ? usage.unit?.singular || 'use' : usage.unit?.plural || 'uses';
  const used = Math.max(limit - remaining, 0);
  const plan = PLAN_WORDS[usage.plan] ? ` (${PLAN_WORDS[usage.plan]})` : '';
  const reset = remaining === 0 && usage.reset_at ? ` Resets ${formatResetTime(usage.reset_at)}.` : '';
  return `${used} of ${limit} ${unit} used ${PERIOD_WORDS[usage.period] || ''}${plan}.${reset}`;
}
