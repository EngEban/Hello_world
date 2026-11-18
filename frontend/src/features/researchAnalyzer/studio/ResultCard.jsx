/** One analysis result: headline, key numbers, tables, chart, checks and write-up, with Simple / Full views. */
import React, { useState } from 'react';
import { AlertTriangle, Check, CircleAlert, Copy, Info, X } from 'lucide-react';
import { useStudioLang } from './i18n.jsx';
import StudioChart from './StudioChart.jsx';
import { describeResult } from './resultModel';

export function DataTable({ table }) {
  return (
    <div className="ras-table-wrap">
      <table className="ras-table">
        {table.caption && <caption>{table.caption}</caption>}
        {/* dir="auto" keeps numbers such as ".068" or "25 (41.7)" in reading order inside Arabic (RTL) tables. */}
        <thead><tr>{table.columns.map((column, index) => <th key={index} scope="col" dir="auto">{column}</th>)}</tr></thead>
        <tbody>
          {table.rows.map((row, rowIndex) => (
            <tr key={rowIndex}>{row.map((cell, cellIndex) => (cellIndex === 0
              ? <th key={cellIndex} scope="row" dir="auto">{cell}</th>
              : <td key={cellIndex} dir="auto">{cell}</td>))}</tr>
          ))}
        </tbody>
      </table>
      {table.note && <p className="ras-table-note">{table.note}</p>}
    </div>
  );
}

export default function ResultCard({ entry, onToggleReport, onRemove, onRerun }) {
  const { t, lang } = useStudioLang();
  const [view, setView] = useState('simple');
  const [textLang, setTextLang] = useState(lang);
  const [copied, setCopied] = useState(false);
  const model = describeResult(entry.result);
  if (!model) return null;
  const full = view === 'full';
  const tables = model.tables.filter((table) => full || !table.full);
  const checks = full ? model.checks : model.checks.filter((check) => check.ok === false);
  const text = model.text[textLang] || model.text.en;

  async function copyText() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch { /* clipboard may be blocked */ }
  }

  return (
    <article className="ras-card ras-result" aria-label={model.title}>
      <div className="ras-result-top">
        <span className="ras-meta">{model.meta && model.meta.includes(model.title) ? model.meta : [model.title, model.meta].filter(Boolean).join(' · ')}</span>
        <div className="ras-result-actions">
          <div className="ras-segment" role="group" aria-label="Detail level">
            <button type="button" aria-pressed={!full} onClick={() => setView('simple')}>{t.simple}</button>
            <button type="button" aria-pressed={full} onClick={() => setView('full')}>{t.full}</button>
          </div>
          <button type="button" className="ras-icon-button" onClick={onRemove} aria-label={t.dismiss}><X size={16} /></button>
        </div>
      </div>

      {model.decision && <p className="ras-decision"><Info size={16} aria-hidden="true" />{model.decision}</p>}
      <h3 className="ras-headline" dir="auto">{model.headline[lang] || model.headline.en}</h3>

      {model.alert?.kind === 'reverse' && (
        <div className="ras-alert" role="alert">
          <AlertTriangle size={18} aria-hidden="true" />
          <p><strong>{model.alert.items.join(', ')}</strong> {lang === 'ar' ? 'يبدو أنها معكوسة الصياغة (ارتباط سالب مع بقية الفقرات).' : 'seems to be reverse-worded (it correlates negatively with the other items).'}</p>
          <button type="button" className="ras-button ras-button-primary"
                  onClick={() => onRerun({ ...entry.params, reverse_items: [...(entry.params.reverse_items || []), ...model.alert.items] })}>
            {lang === 'ar' ? 'اعكسها وأعد التشغيل' : 'Reverse and re-run'}
          </button>
        </div>
      )}

      {model.kpis.length > 0 && (
        <div className="ras-kpis">
          {model.kpis.map((kpi) => (
            <div className="ras-kpi" key={kpi.label}>
              <span className="ras-kpi-label">{kpi.label}</span>
              <strong className="ras-kpi-value" dir="ltr">{kpi.value}</strong>
              {kpi.sub && <span className="ras-kpi-sub" dir="auto">{kpi.sub}</span>}
            </div>
          ))}
        </div>
      )}

      {model.notes.map((note) => <p key={note} className="ras-note" dir="auto">{note}</p>)}
      {model.chart && <StudioChart chart={model.chart} name={entry.method} />}
      {tables.map((table, index) => <DataTable key={`${table.caption}-${index}`} table={table} />)}

      {checks.length > 0 && (
        <div className="ras-checks">
          {full && <h4>{t.checks}</h4>}
          <ul>
            {checks.map((check) => (
              <li key={check.name} className={check.ok === false ? 'is-warn' : 'is-ok'}>
                {check.ok === false ? <CircleAlert size={16} aria-hidden="true" /> : <Check size={16} aria-hidden="true" />}
                <span><strong>{check.name}</strong>{check.detail ? <> — {check.detail}</> : null}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {text && (
        <div className="ras-writeup">
          <div className="ras-writeup-bar">
            <h4>{t.writeUp}</h4>
            <div className="ras-segment" role="group" aria-label="Write-up language">
              <button type="button" aria-pressed={textLang === 'en'} onClick={() => setTextLang('en')}>English</button>
              <button type="button" aria-pressed={textLang === 'ar'} onClick={() => setTextLang('ar')} lang="ar">العربية</button>
            </div>
          </div>
          <p className="ras-writeup-text" dir={textLang === 'ar' ? 'rtl' : 'ltr'} lang={textLang}>{text}</p>
        </div>
      )}

      <div className="ras-result-footer">
        <button type="button" className={`ras-button ${entry.inReport ? 'ras-button-done' : 'ras-button-primary'}`} onClick={onToggleReport} aria-pressed={entry.inReport}>
          {entry.inReport ? <><Check size={15} aria-hidden="true" /> {t.inReport}</> : t.addToReport}
        </button>
        <button type="button" className="ras-button" onClick={copyText}><Copy size={14} aria-hidden="true" /> {copied ? t.copied : t.copy}</button>
      </div>
    </article>
  );
}
