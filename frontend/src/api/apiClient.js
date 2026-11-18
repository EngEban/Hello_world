function getDefaultApiBaseUrl() {
  // Keep local Vite requests same-origin so they use vite.config.js's /api
  // proxy. Production deployments still provide VITE_API_BASE_URL explicitly.
  return '/api';
}

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || getDefaultApiBaseUrl()).replace(/\/+$/, '');
// A free Render service can take 30–50 seconds to wake after inactivity.  The
// old 15-second client timeout made a healthy request look like a failed one.
// Mutating requests are deliberately never retried here, so a slow save cannot
// create duplicate records.
const DEFAULT_TIMEOUT_MS = 60000;

export class ApiError extends Error {
  constructor(message, details = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = details.status || 0;
    this.code = details.code || '';
    this.data = details.data || null;
  }
}

// Endpoints where a 401 means "wrong credentials", not "session expired".
const CREDENTIAL_ENDPOINTS = ['/accounts/login/', '/accounts/google/', '/accounts/register/', '/dashboard/auth/login/', '/accounts/password/'];
export const UNAUTHORIZED_EVENT = 'resref:unauthorized';

function notifyUnauthorized(path) {
  if (CREDENTIAL_ENDPOINTS.some(endpoint => path.startsWith(endpoint))) return;
  window.dispatchEvent(new CustomEvent(UNAUTHORIZED_EVENT, { detail: { path, area: path.startsWith('/dashboard/') ? 'dashboard' : 'account' } }));
}

function getCookie(name) {
  return document.cookie.split('; ').find(row => row.startsWith(`${name}=`))?.split('=').slice(1).join('=') || '';
}

async function ensureCsrfToken() {
  // Cookies are shared across localhost ports and may belong to another dev
  // server/session. Obtain a token from the actual API before a write; Django
  // also rotates it after login, so a cached token is not reliable here.
  const response = await fetch(`${API_BASE_URL}/accounts/csrf/`, { credentials: 'include' });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || !payload.csrfToken) {
    throw new Error('Could not retrieve the security token. Please refresh the page and try again.');
  }
  return payload.csrfToken;
}

export async function apiRequest(path, options = {}) {
  const isFormData = options.body instanceof FormData;
  const method = (options.method || 'GET').toUpperCase();
  const canRetry = method === 'GET' && options.retry !== false;
  const attempts = canRetry ? 2 : 1;

  const { headers: callerHeaders, signal: callerSignal, timeoutMs, retry: _retry, ...fetchOptions } = options;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    if (callerSignal?.aborted) throw callerSignal.reason ?? new DOMException('Aborted', 'AbortError');
    const controller = new AbortController();
    let timedOut = false;
    const timeout = window.setTimeout(() => { timedOut = true; controller.abort(); }, timeoutMs || DEFAULT_TIMEOUT_MS);
    // A caller's AbortController (e.g. an effect cleanup) cancels the request too.
    const forwardAbort = () => controller.abort();
    callerSignal?.addEventListener('abort', forwardAbort, { once: true });
    try {
    const csrfToken = ['POST', 'PUT', 'PATCH', 'DELETE'].includes(method) ? await ensureCsrfToken() : '';
    const response = await fetch(`${API_BASE_URL}${path}`, {
      credentials: 'include',
      ...fetchOptions,
      // Merge headers last so a caller's headers add to, not replace, CSRF/JSON.
      headers: { ...(isFormData ? {} : { 'Content-Type': 'application/json' }), ...(csrfToken ? { 'X-CSRFToken': csrfToken } : {}), ...(callerHeaders || {}) },
      signal: controller.signal,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      if (response.status === 401) notifyUnauthorized(path);
      throw new ApiError(data.error || (response.status === 403 && !Object.keys(data).length ? 'Security verification failed. Refresh this page and try signing in again.' : `API request failed (${response.status})`), {
        status: response.status,
        code: data.code || '',
        data,
      });
    }
    return data;
    } catch (error) {
      if (error.name === 'AbortError' && !timedOut) throw error; // cancelled by the caller: not a failure
      const transient = error.name === 'AbortError' || error instanceof TypeError;
      if (transient && attempt + 1 < attempts) {
        await new Promise(resolve => window.setTimeout(resolve, 900));
        continue;
      }
      if (error.name === 'AbortError') throw new Error('The request took longer than one minute. The service may be waking up; please try once more.');
      if (error instanceof TypeError) throw new Error('Could not connect to the API. Check your connection and try again.');
      throw error;
    } finally {
      window.clearTimeout(timeout);
      callerSignal?.removeEventListener('abort', forwardAbort);
    }
  }

  throw new Error('Could not complete the request. Please try again.');
}

/** POST JSON and receive a file (e.g. a Word export) as a Blob. */
export async function postForBlob(path, body, { timeoutMs = 60000 } = {}) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const csrfToken = await ensureCsrfToken();
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new ApiError(data.error || `API request failed (${response.status})`, { status: response.status, code: data.code || '', data });
    }
    return await response.blob();
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('The export took too long. Please try again.');
    if (error instanceof TypeError) throw new Error('Could not connect to the API. Check your connection and try again.');
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}

export const get = (path, options) => apiRequest(path, options);
export const post = (path, body, options) => apiRequest(path, { method: 'POST', body: JSON.stringify(body), ...options });
export const upload = (path, body, options) => apiRequest(path, { method: 'POST', body, ...options });
