/** Step 1: drop a file (or pick an example dataset). */
import React, { useRef, useState } from 'react';
import { Lock, UploadCloud } from 'lucide-react';
import { useStudioLang } from './i18n.jsx';
import { uploadFile } from '../services/researchAnalyzerApi';

const ALLOWED = ['csv', 'tsv', 'txt', 'xlsx', 'xls', 'sav', 'zsav', 'por', 'dta', 'json'];
const MAX_MB = 20;
// Public files are served from Vite's base path ("/static/" in production builds).
const EXAMPLES = ['trial', 'survey', 'diagnostic'].map((key) => ({ key, file: `${import.meta.env.BASE_URL}analyzer-example-${key}.csv` }));

export default function UploadScreen({ onUploaded }) {
  const { t } = useStudioLang();
  const inputRef = useRef(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [dragging, setDragging] = useState(false);

  async function send(file) {
    const extension = file.name.split('.').pop().toLowerCase();
    if (!ALLOWED.includes(extension)) { setError(`.${extension} files are not supported. Use Excel, CSV, SPSS, Stata or JSON.`); return; }
    if (file.size > MAX_MB * 1024 * 1024) { setError(`This file is ${(file.size / 1048576).toFixed(1)} MB; the limit is ${MAX_MB} MB.`); return; }
    if (!file.size) { setError('This file is empty.'); return; }
    setError('');
    setBusy(true);
    try {
      onUploaded(await uploadFile(file));
    } catch (uploadError) {
      setError(uploadError.message || 'The file could not be read.');
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = '';
    }
  }

  async function loadExample(example) {
    setBusy(true);
    setError('');
    try {
      const response = await fetch(example.file);
      if (!response.ok) throw new Error('missing example');
      const blob = await response.blob();
      await send(new File([blob], `example-${example.key}.csv`, { type: 'text/csv' }));
    } catch {
      setError('The example could not be loaded.');
      setBusy(false);
    }
  }

  return (
    <div className="ras-upload">
      <div className="ras-hero">
        <h1>{t.heroTitle}<br />{t.heroTitle2}</h1>
        <p>{t.heroCopy}</p>
      </div>
      <button
        type="button"
        className={`ras-drop ${dragging ? 'is-dragging' : ''}`}
        onClick={() => inputRef.current?.click()}
        onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => { event.preventDefault(); setDragging(false); if (event.dataTransfer.files[0]) send(event.dataTransfer.files[0]); }}
        disabled={busy}
        aria-describedby="ras-drop-help"
      >
        <span className="ras-drop-icon" aria-hidden="true"><UploadCloud size={30} /></span>
        <span className="ras-drop-title">{busy ? t.uploading : <>{t.dropTitle} <u>{t.browse}</u></>}</span>
        <span id="ras-drop-help" className="ras-drop-help">{t.dropFormats}</span>
        <span className="ras-drop-privacy"><Lock size={14} aria-hidden="true" /> {t.privacy}</span>
      </button>
      <input ref={inputRef} type="file" hidden accept=".csv,.tsv,.txt,.xlsx,.xls,.sav,.zsav,.por,.dta,.json"
             onChange={(event) => event.target.files[0] && send(event.target.files[0])} />
      {error && <p className="ras-error" role="alert">{error}</p>}
      <div className="ras-examples">
        <span>{t.tryExample}</span>
        {EXAMPLES.map((example) => (
          <button type="button" key={example.key} className="ras-chip" disabled={busy} onClick={() => loadExample(example)}>{t.examples[example.key]}</button>
        ))}
      </div>
      <ol className="ras-how">
        {t.how.map(([step, title, copy]) => (
          <li key={step}><span>{step}</span><strong>{title}</strong><p>{copy}</p></li>
        ))}
      </ol>
    </div>
  );
}
