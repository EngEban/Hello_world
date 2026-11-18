import { get, post, postForBlob, upload } from '../../../api/apiClient.js';

const SESSION_KEY = 'resref_research_analyzer_session_id';
const API_PREFIX = '/research-analyzer';

function rememberSession(data) {
  if (data?.session_id) {
    sessionStorage.setItem(SESSION_KEY, data.session_id);
  }
  return data;
}

function currentSessionId() {
  return sessionStorage.getItem(SESSION_KEY) || '';
}

export async function uploadFile(file, onProgress) {
  const form = new FormData();
  form.append('file', file);
  const data = await upload(`${API_PREFIX}/upload/`, form, { timeoutMs: 60000 });
  if (onProgress) onProgress(100);
  return rememberSession(data);
}

export async function updateVariables(variables) {
  return post(`${API_PREFIX}/variables/`, { session_id: currentSessionId(), variables }, { timeoutMs: 60000 });
}

export async function prepareData(options) {
  return post(`${API_PREFIX}/prepare/`, { session_id: currentSessionId(), options }, { timeoutMs: 60000 });
}

export async function runAnalysis(test, params) {
  return post(`${API_PREFIX}/analyze/`, { session_id: currentSessionId(), test, params }, { timeoutMs: 60000 });
}

export async function fetchAnalysisPlan() {
  const sessionId = encodeURIComponent(currentSessionId());
  return get(`${API_PREFIX}/analysis-plan/?session_id=${sessionId}`, { timeoutMs: 60000 });
}

export async function generateMasterAnalysis() {
  return post(`${API_PREFIX}/report/generate/`, { session_id: currentSessionId() }, { timeoutMs: 120000 });
}

export async function fetchMasterReport() {
  const sessionId = encodeURIComponent(currentSessionId());
  return get(`${API_PREFIX}/report/?session_id=${sessionId}`, { timeoutMs: 60000 });
}

export function hasSession() {
  return Boolean(currentSessionId());
}

export async function fetchMethods() {
  return get(`${API_PREFIX}/methods/`, { timeoutMs: 30000 });
}

export async function recommendMethod(question, fields, { signal } = {}) {
  return post(`${API_PREFIX}/recommend/`, { session_id: currentSessionId(), question, fields }, { timeoutMs: 30000, signal });
}

export async function fetchLevels(variable) {
  const sessionId = encodeURIComponent(currentSessionId());
  return get(`${API_PREFIX}/levels/?session_id=${sessionId}&variable=${encodeURIComponent(variable)}`, { timeoutMs: 30000 });
}

export async function exportReportDocx(report) {
  return postForBlob(`${API_PREFIX}/report/docx/`, { session_id: currentSessionId(), report }, { timeoutMs: 60000 });
}

export async function clearSession() {
  const sessionId = currentSessionId();
  if (!sessionId) return;
  await post(`${API_PREFIX}/session/${encodeURIComponent(sessionId)}/clear/`, {}, { timeoutMs: 30000 });
  sessionStorage.removeItem(SESSION_KEY);
}
