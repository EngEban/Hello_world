/**
 * Research Analyzer studio: three steps — Upload → Analyse → Report.
 * Work (dataset summary, variable types, results, report choices) is kept in sessionStorage per analyzer
 * session, so a reload or going back never loses results.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { FileText } from 'lucide-react';
import { StudioLangProvider, useStudioLang } from './i18n.jsx';
import UploadScreen from './UploadScreen.jsx';
import Workspace from './Workspace.jsx';
import ReportScreen from './ReportScreen.jsx';
import MethodsLibrary from './MethodsLibrary.jsx';
import { clearSession, fetchMethods, hasSession, runAnalysis, updateVariables } from '../services/researchAnalyzerApi';
import './studio.css';

const STORE_KEY = 'resref_analyzer_studio';
function loadStore() {
  try {
    const stored = JSON.parse(sessionStorage.getItem(STORE_KEY) || 'null');
    return stored && hasSession() ? stored : null;
  } catch {
    return null;
  }
}

function saveStore(state) {
  try { sessionStorage.setItem(STORE_KEY, JSON.stringify(state)); } catch { /* storage full or blocked */ }
}

function withRoles(variables) {
  // Suggested roles feed the "Suggested for your data" list; the question card never depends on them.
  return variables.map((v) => ({ ...v, role: v.role || v.suggested_role || 'unspecified' }));
}

function Studio() {
  const { t, lang, setLang, isRTL } = useStudioLang();
  const stored = loadStore();
  const [step, setStep] = useState(stored ? stored.step || 1 : 0);
  const [dataset, setDataset] = useState(stored?.dataset || null);
  const [variables, setVariables] = useState(stored?.variables || []);
  const [results, setResults] = useState(stored?.results || []);
  const [catalog, setCatalog] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [manualMethod, setManualMethod] = useState(null);
  const [planVersion, setPlanVersion] = useState(0);

  useEffect(() => { fetchMethods().then(setCatalog).catch(() => setCatalog(null)); }, []);
  useEffect(() => {
    if (dataset) saveStore({ step, dataset, variables, results });
  }, [step, dataset, variables, results]);
  useEffect(() => { window.scrollTo({ top: 0, behavior: 'smooth' }); }, [step]);

  async function handleUploaded(data) {
    const nextVariables = withRoles(data.variables || []);
    setDataset({ filename: data.filename, rows: data.summary?.rows, cols: data.summary?.cols, missing: data.summary?.missing_cells });
    setVariables(nextVariables);
    setResults([]);
    setStep(1);
    try { await updateVariables(nextVariables); } catch { /* suggestions fall back to detected types */ }
    setPlanVersion((v) => v + 1);
  }

  async function changeType(name, type) {
    const next = variables.map((v) => (v.name === name ? { ...v, type, role: type === 'id' ? 'identifier' : (v.role === 'identifier' ? 'unspecified' : v.role) } : v));
    setVariables(next);
    try { await updateVariables(next); setPlanVersion((v) => v + 1); } catch (saveError) { setError(saveError.message); }
  }

  const run = useCallback(async (method, params, label, key) => {
    setBusy(true);
    setError('');
    try {
      const result = await runAnalysis(method, params);
      setResults((previous) => [{ id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`, key, method, params, label, result, inReport: true }, ...previous]);
      setManualMethod(null);
    } catch (runError) {
      if (runError.status === 404) {
        setError(lang === 'ar' ? 'انتهت الجلسة. ارفع الملف مرة أخرى.' : 'This session has expired. Please upload the file again.');
      } else {
        setError(runError.message || 'The analysis could not be run.');
      }
    } finally {
      setBusy(false);
    }
  }, [lang]);

  async function rerun(entry, params) {
    setBusy(true);
    try {
      const result = await runAnalysis(entry.method, params);
      setResults((previous) => previous.map((item) => (item.id === entry.id ? { ...item, params, result } : item)));
    } catch (runError) {
      setError(runError.message);
    } finally {
      setBusy(false);
    }
  }

  const toggleReport = (id) => setResults((previous) => previous.map((item) => (item.id === id ? { ...item, inReport: !item.inReport } : item)));
  const removeResult = (id) => setResults((previous) => previous.filter((item) => item.id !== id));
  const reportEntries = [...results].reverse().filter((item) => item.inReport);
  function moveInReport(id, direction) {
    // Report order is oldest-first; results are stored newest-first, so reverse the direction.
    setResults((previous) => {
      const index = previous.findIndex((item) => item.id === id);
      const included = previous.map((item, i) => (item.inReport ? i : -1)).filter((i) => i >= 0);
      const position = included.indexOf(index);
      const swapWith = included[position - direction];
      if (swapWith === undefined) return previous;
      const next = [...previous];
      [next[index], next[swapWith]] = [next[swapWith], next[index]];
      return next;
    });
  }

  async function startOver() {
    try { await clearSession(); } catch { /* already gone */ }
    try { sessionStorage.removeItem(STORE_KEY); } catch { /* blocked */ }
    setDataset(null);
    setVariables([]);
    setResults([]);
    setStep(0);
  }

  const steps = t.steps;
  return (
    <div className="ras" dir={isRTL ? 'rtl' : 'ltr'} lang={lang}>
      <header className="ras-bar">
        <div className="ras-brand">
          <span className="ras-logo" aria-hidden="true">R</span>
          <span>ResRef <b>{t.brand}</b></span>
          {dataset && <span className="ras-file" title={dataset.filename}>{dataset.filename} · {dataset.rows} {t.rows}</span>}
        </div>
        <nav className="ras-steps" aria-label="Steps">
          {steps.map((label, index) => {
            const enabled = index === 0 || Boolean(dataset);
            return (
              <button type="button" key={label} aria-current={step === index ? 'step' : undefined} disabled={!enabled}
                      onClick={() => (index === 0 && dataset ? startOver() : setStep(index))} className={step === index ? 'is-active' : ''}>
                <span>{index + 1}</span>{index === 0 && dataset ? t.newFile : label}
              </button>
            );
          })}
        </nav>
        <div className="ras-bar-end">
          {dataset && step !== 2 && (
            <button type="button" className="ras-button ras-button-primary" onClick={() => setStep(2)}>
              <FileText size={15} aria-hidden="true" /> {t.viewReport} <span className="ras-count">{reportEntries.length}</span>
            </button>
          )}
          <div className="ras-segment" role="group" aria-label="Language">
            <button type="button" aria-pressed={lang === 'en'} onClick={() => setLang('en')}>EN</button>
            <button type="button" aria-pressed={lang === 'ar'} onClick={() => setLang('ar')} lang="ar">عربي</button>
          </div>
        </div>
      </header>

      {step === 0 && <UploadScreen onUploaded={handleUploaded} />}
      {step === 1 && dataset && (
        <Workspace variables={variables} catalog={catalog} results={results} busy={busy} error={error} onTypeChange={changeType} onRun={run}
                   onToggleReport={toggleReport} onRemove={removeResult} onRerun={rerun} onOpenLibrary={() => setLibraryOpen(true)}
                   manualMethod={manualMethod} onCloseManual={() => setManualMethod(null)} planVersion={planVersion} />
      )}
      {step === 2 && dataset && (
        <ReportScreen entries={reportEntries} filename={dataset.filename} catalog={catalog} onMove={moveInReport} onRemove={toggleReport} onBack={() => setStep(1)} />
      )}
      <MethodsLibrary catalog={catalog} open={libraryOpen} onClose={() => setLibraryOpen(false)}
                      onPick={(method) => { setManualMethod(method); setLibraryOpen(false); setStep(1); }} />
    </div>
  );
}

export default function AnalyzerStudio() {
  return (
    <StudioLangProvider>
      <Studio />
    </StudioLangProvider>
  );
}
