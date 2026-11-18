/** Step 2: variables on the side, the question card, results, and suggested analyses — one workspace. */
import React, { useEffect, useRef, useState } from 'react';
import { Check, Play } from 'lucide-react';
import { useStudioLang } from './i18n.jsx';
import AskCard from './AskCard.jsx';
import ResultCard from './ResultCard.jsx';
import { fetchAnalysisPlan } from '../services/researchAnalyzerApi';

const TYPE_OPTIONS = ['numeric', 'categorical', 'ordinal', 'likert', 'id', 'text', 'date'];

function VariablesPanel({ variables, onTypeChange }) {
  const { t } = useStudioLang();
  return (
    <aside className="ras-card ras-vars" aria-label={t.variables}>
      <div className="ras-vars-head"><h2>{t.variables}</h2><span>{variables.length} {t.detected}</span></div>
      <ul>
        {variables.map((variable) => {
          const muted = ['id', 'text', 'date'].includes(variable.type);
          const meta = variable.missing ? `${variable.missing} ${t.missing}` : variable.type === 'numeric' && variable.min !== undefined ? `${variable.min}–${variable.max}` : `${variable.unique ?? ''} ${t.values}`;
          return (
            <li key={variable.name} className={muted ? 'is-muted' : ''}>
              <span className="ras-var-name" title={variable.name}>{variable.name}<small>{meta}</small></span>
              <label className="ras-visually-hidden" htmlFor={`type-${variable.name}`}>{variable.name} type</label>
              <select id={`type-${variable.name}`} className="ras-type" value={variable.type} onChange={(event) => onTypeChange(variable.name, event.target.value)}>
                {TYPE_OPTIONS.map((type) => <option key={type} value={type}>{t.types[type]}</option>)}
              </select>
            </li>
          );
        })}
      </ul>
      <p className="ras-muted">{t.variablesHint}</p>
    </aside>
  );
}

function Suggestions({ variables, catalog, planVersion, ranKeys, onRun, busy }) {
  const { t, lang } = useStudioLang();
  const [entries, setEntries] = useState([]);
  useEffect(() => {
    let live = true;
    fetchAnalysisPlan().then((plan) => {
      if (!live) return;
      const group = variables.find((v) => v.role === 'grouping' && v.type !== 'id');
      const analysable = variables.filter((v) => !['id', 'text', 'date'].includes(v.type)).map((v) => ({ name: v.name, type: v.type }));
      const items = [];
      if (group) items.push({ key: `table_one:${group.name}`, method: 'table_one', params: { group: group.name, variables: analysable }, title: `Table 1 by ${group.name}` });
      (plan.entries || []).filter((entry) => !['descriptive', 'demographic'].includes(entry.test)).forEach((entry) => {
        const [first, ...rest] = entry.variables;
        const title = entry.test === 'paired_ttest' || entry.test === 'wilcoxon' ? `${first} → ${rest.join(', ')}` : rest.length ? `${first} by ${rest.join(', ')}` : first;
        items.push({ key: `${entry.test}:${entry.variables.join(',')}`, method: entry.test, params: entry.params, title, detail: entry.decision });
      });
      setEntries(items.slice(0, 6));
    }).catch(() => live && setEntries([]));
    return () => { live = false; };
  }, [planVersion, variables]);
  if (!entries.length) return null;
  const label = (id) => catalog?.methods?.find((m) => m.id === id)?.[lang === 'ar' ? 'label_ar' : 'label'] || id;
  return (
    <section className="ras-card ras-suggest" aria-label={t.suggestions}>
      <h2>{t.suggestions}</h2>
      <p className="ras-muted">{t.suggestionsHint}</p>
      <ul>
        {entries.map((entry) => (
          <li key={entry.key}>
            <span><strong>{entry.title}</strong><small>{label(entry.method)}</small></span>
            {ranKeys.includes(entry.key)
              ? <span className="ras-done"><Check size={14} aria-hidden="true" /> {t.inReport}</span>
              : <button type="button" className="ras-button" disabled={busy} onClick={() => onRun(entry.method, entry.params, label(entry.method), entry.key)}><Play size={13} aria-hidden="true" /> {t.runAndAdd}</button>}
          </li>
        ))}
      </ul>
    </section>
  );
}

export default function Workspace({ variables, catalog, results, busy, error, onTypeChange, onRun, onToggleReport, onRemove, onRerun, onOpenLibrary, manualMethod, onCloseManual, planVersion }) {
  const { t } = useStudioLang();
  const newestRef = useRef(null);
  const newestId = results[0]?.id;
  const seen = useRef(newestId);
  useEffect(() => {
    // Bring a new result into view; restoring saved results on load does not scroll.
    if (newestId && newestId !== seen.current) newestRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    seen.current = newestId;
  }, [newestId]);
  return (
    <div className="ras-workspace">
      <VariablesPanel variables={variables} onTypeChange={onTypeChange} />
      <div className="ras-main">
        <AskCard variables={variables} catalog={catalog} manualMethod={manualMethod} onCloseManual={onCloseManual} onOpenLibrary={onOpenLibrary} onRun={onRun} busy={busy} />
        {error && <p className="ras-error" role="alert">{error}</p>}
        {results.map((entry, index) => (
          <div key={entry.id} ref={index === 0 ? newestRef : undefined} className="ras-result-anchor"><ResultCard entry={entry} onToggleReport={() => onToggleReport(entry.id)} onRemove={() => onRemove(entry.id)}
                      onRerun={(params) => onRerun(entry, params)} /></div>
        ))}
        {!results.length && <p className="ras-empty">{t.noResults}</p>}
        <Suggestions variables={variables} catalog={catalog} planVersion={planVersion} ranKeys={results.map((r) => r.key).filter(Boolean)} onRun={onRun} busy={busy} />
      </div>
    </div>
  );
}
