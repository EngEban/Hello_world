/** Step 3: the assembled manuscript section — reorder, switch language, download Word, print or copy. */
import React, { useMemo, useState } from 'react';
import { ArrowDown, ArrowUp, Copy, FileDown, Printer } from 'lucide-react';
import { useStudioLang } from './i18n.jsx';
import { DataTable } from './ResultCard.jsx';
import { describeResult } from './resultModel';
import { exportReportDocx } from '../services/researchAnalyzerApi';

const GENERAL = {
  en: 'All tests were two-sided with α = 0.05. Each analysis used the records with complete data for its variables. Analyses were performed with ResRef Analyzer.',
  ar: 'كانت جميع الاختبارات ثنائية الطرف بمستوى دلالة 0.05، واستخدم كل تحليل السجلات المكتملة لمتغيراته. أُجريت التحليلات باستخدام محلّل ResRef.',
};

export function buildReport(entries, lang, filename, catalog) {
  const arabicLabel = (id) => catalog?.methods?.find((method) => method.id === id)?.label_ar;
  const models = entries.map((entry) => ({ entry, model: describeResult(entry.result) })).filter((item) => item.model);
  const methods = [...new Set(models.map(({ model }) => model.methods?.[lang] || model.methods?.en).filter(Boolean))];
  const stem = (filename || 'analysis').replace(/\.[^.]+$/, '');
  return {
    lang,
    title: lang === 'ar' ? `التحليل الإحصائي — ${stem}` : `Statistical analysis — ${stem}`,
    sections: [
      { heading: lang === 'ar' ? 'التحليل الإحصائي' : 'Statistical analysis', paragraphs: [...methods, GENERAL[lang]] },
      ...models.map(({ entry, model }) => ({
        heading: (lang === 'ar' && arabicLabel(entry.method)) || model.title,
        paragraphs: [model.text[lang] || model.text.en].filter(Boolean),
        tables: model.tables.filter((table) => !table.full).map(({ caption, columns, rows, note }) => ({ caption, columns, rows: rows.map((row) => row.map((cell) => String(cell ?? ''))), note })),
      })),
    ],
  };
}

export default function ReportScreen({ entries, filename, catalog, onMove, onRemove, onBack }) {
  const { t, lang: uiLang } = useStudioLang();
  const [lang, setLang] = useState(uiLang);
  const [status, setStatus] = useState('');
  const report = useMemo(() => buildReport(entries, lang, filename, catalog), [entries, lang, filename, catalog]);
  const plainText = report.sections.map((section) => [section.heading, ...section.paragraphs].join('\n\n')).join('\n\n');

  async function download() {
    setStatus('…');
    try {
      const blob = await exportReportDocx(report);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${(filename || 'analysis').replace(/\.[^.]+$/, '')}-report.docx`;
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 2000);
      setStatus('');
    } catch (error) {
      setStatus(error.message);
    }
  }

  async function copyAll() {
    try { await navigator.clipboard.writeText(plainText); setStatus(t.copied); window.setTimeout(() => setStatus(''), 1600); } catch { /* blocked */ }
  }

  return (
    <div className="ras-report">
      <aside className="ras-card ras-report-side" aria-label={t.inThisReport}>
        <div className="ras-field">
          <span>{t.language}</span>
          <div className="ras-segment" role="group" aria-label={t.language}>
            <button type="button" aria-pressed={lang === 'en'} onClick={() => setLang('en')}>English</button>
            <button type="button" aria-pressed={lang === 'ar'} onClick={() => setLang('ar')} lang="ar">العربية</button>
          </div>
        </div>
        <h2>{t.inThisReport}</h2>
        {entries.length === 0 ? <p className="ras-muted">{t.reportEmpty}</p> : (
          <ol className="ras-outline">
            {entries.map((entry, index) => (
              <li key={entry.id}>
                <span>{describeResult(entry.result)?.title}</span>
                <span className="ras-outline-actions">
                  <button type="button" className="ras-icon-button" disabled={index === 0} onClick={() => onMove(entry.id, -1)} aria-label={t.moveUp}><ArrowUp size={14} /></button>
                  <button type="button" className="ras-icon-button" disabled={index === entries.length - 1} onClick={() => onMove(entry.id, 1)} aria-label={t.moveDown}><ArrowDown size={14} /></button>
                  <button type="button" className="ras-link" onClick={() => onRemove(entry.id)}>{t.dismiss}</button>
                </span>
              </li>
            ))}
          </ol>
        )}
        <div className="ras-report-buttons">
          <button type="button" className="ras-button ras-button-primary" disabled={!entries.length} onClick={download}><FileDown size={15} aria-hidden="true" /> {t.download}</button>
          <button type="button" className="ras-button" disabled={!entries.length} onClick={() => window.print()}><Printer size={15} aria-hidden="true" /> {t.print}</button>
          <button type="button" className="ras-button" disabled={!entries.length} onClick={copyAll}><Copy size={15} aria-hidden="true" /> {t.copyAll}</button>
        </div>
        {status && <p className="ras-muted" role="status">{status}</p>}
        <button type="button" className="ras-link" onClick={onBack}>← {t.backToAnalyse}</button>
      </aside>

      <article className="ras-paper" dir={lang === 'ar' ? 'rtl' : 'ltr'} lang={lang}>
        <h1>{report.title}</h1>
        {entries.length === 0 ? <p className="ras-muted">{t.reportEmpty}</p> : report.sections.map((section, index) => (
          <section key={`${section.heading}-${index}`}>
            <h2>{section.heading}</h2>
            {section.paragraphs.map((paragraph) => <p key={paragraph}>{paragraph}</p>)}
            {(section.tables || []).map((table, tableIndex) => <DataTable key={tableIndex} table={table} />)}
          </section>
        ))}
      </article>
    </div>
  );
}
