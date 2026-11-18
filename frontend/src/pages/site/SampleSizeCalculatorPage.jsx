/**
 * Sample size calculator, study-type driven:
 *   1. What type of study are you conducting?   2. Your study information (simple fields only)
 *   3. Calculate   →   4. Required sample size, with how it was reached and a write-up.
 * Statistical settings (power, α, allocation, design effect, effect sizes, exact method) stay under
 * "Advanced options". Calculations run on the server (/api/sample-size/calculate/).
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import ToolGuide from '../../components/public/ToolGuide';
import { AlertTriangle, Calculator, ChevronDown, Copy, Download, FileDown, Library, Save, X } from 'lucide-react';
import { get, post, postForBlob } from '../../api/apiClient';
import { UsageApi, isUsageRefusal, usageSummary } from '../../api/usageApi';
import { useAccount } from '../../contexts/AccountContext';
import useToolWorkspace from '../../hooks/useToolWorkspace';
import { DESIGN_FORMS, FIELDS, TEXT, TOOL_KEY, apiInputs, calculationsCsv, fieldKey, fieldVisible, loadWorkspace, normalizeWorkspace, saveWorkspace, workspaceHasContent } from '../../features/sampleSizeCalculator/designs';
import { STUDY_FIELDS, STUDY_TYPES, fieldKeyOf, startForm, stepLabel, studySpec } from '../../features/sampleSizeCalculator/studyTypes';
import { DesignLibrary, SdHelper } from '../../features/sampleSizeCalculator/SampleSizeDialogs';
import '../../features/sampleSizeCalculator/studio.css';

const SEO_DESCRIPTION = 'Free sample size calculator for medical research. Choose your study type — survey, prevalence, cross-sectional, cohort, case-control, RCT, diagnostic, correlation or regression — and get the required sample size with a ready-to-use write-up in English and Arabic.';

const UI = {
  en: {
    title: 'Sample size calculator', step1: 'What type of study are you conducting?', step2: 'Your study information', measure: 'What will you measure?',
    calculate: 'Calculate sample size', advanced: 'Advanced options', advancedHint: 'Optional. Standard values are already used.',
    alsoCalc: 'Calculate', modes: { n: 'Sample size', power: 'Power for a fixed number', mde: 'Smallest detectable effect', precision: 'Precision for a fixed number' },
    available: 'Number of participants you can include', method: 'Calculation method', exactMethod: 'Choose a specific method',
    placeholder: 'Enter your study information and press Calculate.', required: 'Required sample size', invite: 'people to invite', recruit: 'participants to recruit',
    complete: 'should complete the study', perGroup: 'per group', how: 'How this number was reached', more: 'More details', power: 'Power', withN: 'With this number',
    detect: 'You can detect', live: 'Live', optional: 'optional', changed: 'Inputs changed — results update automatically.', sep: ';',
  },
  ar: {
    title: 'حاسبة حجم العينة', step1: 'ما نوع الدراسة التي تجريها؟', step2: 'معلومات دراستك', measure: 'ماذا ستقيس؟',
    calculate: 'احسب حجم العينة', advanced: 'خيارات متقدمة', advancedHint: 'اختياري. القيم القياسية مستخدمة مسبقاً.',
    alsoCalc: 'احسب', modes: { n: 'حجم العينة', power: 'القوة لعدد محدد', mde: 'أصغر أثر قابل للاكتشاف', precision: 'الدقة لعدد محدد' },
    available: 'عدد المشاركين المتاح', method: 'طريقة الحساب', exactMethod: 'اختر طريقة محددة',
    placeholder: 'أدخل معلومات دراستك واضغط «احسب».', required: 'حجم العينة المطلوب', invite: 'شخصاً يجب دعوتهم', recruit: 'مشاركاً يجب تجنيدهم',
    complete: 'يجب أن يُكملوا الدراسة', perGroup: 'لكل مجموعة', how: 'كيف وصلنا إلى هذا الرقم', more: 'تفاصيل إضافية', power: 'القوة', withN: 'مع هذا العدد',
    detect: 'يمكنك اكتشاف', live: 'مباشر', optional: 'اختياري', changed: 'تغيرت المدخلات — تُحدَّث النتائج تلقائياً.', sep: '؛',
  },
};

function upsertMeta(attribute, key, content) {
  let tag = document.head.querySelector(`meta[${attribute}="${key}"]`);
  if (!tag) {
    tag = document.createElement('meta');
    tag.setAttribute(attribute, key);
    document.head.appendChild(tag);
  }
  tag.setAttribute('content', content);
}

/** API inputs: significance split into α / sides; a case-control "controls per case" becomes the cases : controls ratio. */
function requestInputs(form) {
  const inputs = apiInputs(form);
  if (form.studyType === 'case_control' && form.ratio) inputs.ratio = 1 / Number(form.ratio);
  const names = form.studyType && form.studyType !== 'custom' ? studySpec(form.studyType, form.variant).groups : null;
  if (names) inputs.group_names = names.en.join(',');
  return inputs;
}

function StudyField({ name, form, setValue, lang, onHelper, specs = STUDY_FIELDS, keyOf = fieldKeyOf }) {
  const spec = specs[name];
  if (!spec) return null;
  const key = keyOf(name);
  const value = form[key] ?? '';
  const label = spec[lang] || spec.en;
  const id = `ssz-${name}`;
  const ratioLabel = name === 'ratio' && form.studyType === 'case_control' ? (lang === 'ar' ? 'عدد الضوابط لكل حالة' : 'Controls per case') : null;
  if (spec.kind === 'select') {
    return (
      <label className="ssz-field" htmlFor={id}>
        <span>{label}</span>
        <select id={id} value={String(value)} onChange={(event) => setValue(key, event.target.value)}>
          {spec.options.map(([optionValue, optionLabel]) => <option key={optionValue} value={optionValue}>{typeof optionLabel === 'string' ? optionLabel : optionLabel[lang] || optionLabel.en}</option>)}
        </select>
        {spec.help && <small className="ssz-help">{spec.help[lang] || spec.help.en}</small>}
      </label>
    );
  }
  return (
    <div className="ssz-field">
      <label htmlFor={id}>{ratioLabel || label}{spec.optional && <small className="ssz-optional"> ({UI[lang].optional})</small>}</label>
      <span className="ssz-input">
        <input id={id} inputMode={spec.kind === 'text' ? 'text' : 'decimal'} value={value} placeholder={spec.placeholder || ''} onChange={(event) => setValue(key, event.target.value)} />
        {spec.kind === 'percent' && <em>%</em>}
        {spec.unit && form.unit && <em>{form.unit}</em>}
      </span>
      {spec.help && <small className="ssz-help">{spec.help[lang] || spec.help.en}</small>}
      {spec.helper === 'sd' && <button type="button" className="ssz-link" onClick={() => onHelper(key)}>{TEXT[lang].estimate}</button>}
    </div>
  );
}

function PowerCurve({ result }) {
  const points = result?.curve || [];
  if (points.length < 3) return null;
  const width = 360;
  const minN = points[0].n;
  const maxN = points[points.length - 1].n;
  const x = (n) => 40 + ((n - minN) / Math.max(1, maxN - minN)) * (width - 52);
  const y = (p) => 160 - p * 140;
  const current = result.per_group[0].recruit;
  return (
    <figure className="ssz-curve">
      <svg viewBox={`0 0 ${width} 190`} role="img" aria-label={`Power from ${Math.round(points[0].power * 100)}% with ${minN} to ${Math.round(points[points.length - 1].power * 100)}% with ${maxN} per group`}>
        <line x1="40" y1="20" x2="40" y2="160" stroke="#d5dbe6" />
        <line x1="40" y1="160" x2={width - 12} y2="160" stroke="#d5dbe6" />
        <line x1="40" y1={y(0.8)} x2={width - 12} y2={y(0.8)} stroke="#b7791f" strokeDasharray="4 4" />
        <text x={width - 14} y={y(0.8) - 5} textAnchor="end" fontSize="10" fill="#8a5a00">80%</text>
        <text x="34" y="24" textAnchor="end" fontSize="10" fill="#5b6b86">100%</text>
        <text x="40" y="176" fontSize="10" fill="#5b6b86">{minN}</text>
        <text x={width - 12} y="176" textAnchor="end" fontSize="10" fill="#5b6b86">{maxN}</text>
        <polyline fill="none" stroke="#126ac6" strokeWidth="2.5" points={points.map((p) => `${x(p.n)},${y(p.power)}`).join(' ')} />
        {current >= minN && current <= maxN && <circle cx={x(current)} cy={y(result.power || 0.8)} r="5" fill="#062b80" />}
      </svg>
      <figcaption>Power by number recruited per group</figcaption>
    </figure>
  );
}

export default function SampleSizeCalculatorPage() {
  const { account, loading: accountLoading } = useAccount();
  const [lang, setLang] = useState(() => { try { return localStorage.getItem('resref_analyzer_lang') === 'ar' ? 'ar' : 'en'; } catch { return 'en'; } });
  const u = UI[lang];
  const t = TEXT[lang];
  const [workspace, setWorkspace] = useState(loadWorkspace);
  const [form, setForm] = useState(() => {
    const last = normalizeWorkspace(loadWorkspace()).last;
    return last && last.studyType ? last : startForm('survey');
  });
  const [catalog, setCatalog] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  // On narrow screens the answer sits below the inputs; a pinned bar shows it while it is off screen.
  const answerRef = useRef(null);
  const [answerVisible, setAnswerVisible] = useState(true);
  useEffect(() => {
    const node = answerRef.current;
    if (!node || typeof IntersectionObserver === 'undefined') return undefined;
    const observer = new IntersectionObserver(([entry]) => setAnswerVisible(entry.isIntersecting), { threshold: 0.15 });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  const [textLang, setTextLang] = useState(lang);
  const [notice, setNotice] = useState('');
  const [helperFor, setHelperFor] = useState(null);
  const [libraryOpen, setLibraryOpen] = useState(false);
  const charged = useRef('');

  useToolWorkspace({
    toolKey: TOOL_KEY, account, accountLoading, workspace, setWorkspace, normalize: normalizeWorkspace,
    hasContent: workspaceHasContent, persistLocal: saveWorkspace, onRemoteLoaded: () => {}, adoptEmptyRemote: true, markSyncingImmediately: true,
  });

  useEffect(() => {
    document.title = 'Sample Size Calculator for Medical Research | ResRef';
    upsertMeta('name', 'description', SEO_DESCRIPTION);
    upsertMeta('property', 'og:title', 'Sample Size Calculator | ResRef');
    upsertMeta('property', 'og:description', SEO_DESCRIPTION);
    get('/sample-size/designs/').then(setCatalog).catch(() => setCatalog(null));
  }, []);

  useEffect(() => { if (form) setWorkspace((current) => ({ ...current, last: form })); }, [form]);

  // The answer follows every change to the inputs (no Calculate button).
  const formKey = JSON.stringify(form);
  useEffect(() => {
    if (!form) return undefined;
    const controller = new AbortController();
    setBusy(true);
    const timer = window.setTimeout(() => {
      post('/sample-size/calculate/', { design: form.design, mode: form.mode, inputs: requestInputs(form) }, { signal: controller.signal, timeoutMs: 30000 })
        .then((data) => { setResult(data); setError(''); })
        .catch((requestError) => { if (requestError.name !== 'AbortError') { setError(requestError.message); setResult(null); } })
        .finally(() => setBusy(false));
    }, 250);
    return () => { window.clearTimeout(timer); controller.abort(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [formKey]);

  const custom = form?.studyType === 'custom';
  const spec = form && !custom ? studySpec(form.studyType, form.variant) : null;
  const design = catalog?.designs?.find((item) => item.id === form?.design);
  const modes = design?.modes || ['n'];
  const writeup = result ? `${textLang === 'ar' ? result.writeup_ar : result.writeup_en}${form?.sd_source ? (textLang === 'ar' ? ` (المصدر: ${form.sd_source})` : ` The standard deviation was taken from ${form.sd_source}.`) : ''}` : '';

  const setValue = (key, value) => setForm((previous) => ({ ...previous, [key]: value }));
  const chooseStudy = (typeId, variantId) => setForm(startForm(typeId, variantId));
  const chooseVariant = (variantId) => setForm(startForm(form.studyType, variantId));
  const changeLang = (next) => {
    setLang(next);
    setTextLang(next);
    try { localStorage.setItem('resref_analyzer_lang', next); } catch { /* blocked */ }
  };

  async function charge() {
    if (charged.current === formKey) return true;
    try {
      const data = await UsageApi.consume('sample_size_calculator');
      charged.current = formKey;
      const summary = usageSummary(data.usage);
      if (summary) setNotice(summary);
      return true;
    } catch (usageError) {
      if (isUsageRefusal(usageError)) { setNotice(usageError.message); return false; }
      return true;
    }
  }

  const studyLabel = custom ? (lang === 'ar' ? result?.label_ar : result?.label) : spec ? `${spec.type[lang]}${spec.variant ? ` — ${spec.variant[lang]}` : ''}` : '';

  async function copyWriteup() {
    if (!result || !(await charge())) return;
    try { await navigator.clipboard.writeText(writeup); setNotice(t.copied); } catch { setNotice(writeup); }
  }

  async function downloadWord() {
    if (!result || !(await charge())) return;
    const ar = textLang === 'ar';
    const rows = (result.steps || []).map((step) => [stepLabel(step, textLang, form), String(step.n)]);
    const report = {
      lang: textLang, title: ar ? `حساب حجم العينة — ${studyLabel}` : `Sample size calculation — ${studyLabel}`,
      sections: [
        { heading: ar ? 'حجم العينة' : 'Sample size', paragraphs: [writeup],
          tables: rows.length ? [{ caption: ar ? 'خطوات الحساب' : 'How the number was reached', columns: [ar ? 'الخطوة' : 'Step', ar ? 'العدد' : 'Number'], rows }] : [] },
      ],
    };
    try {
      const blob = await postForBlob('/sample-size/docx/', { report });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `sample-size-${form.studyType}.docx`;
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 2000);
    } catch (exportError) {
      setNotice(exportError.message);
    }
  }

  async function saveCalculation() {
    if (!result || !(await charge())) return;
    const entry = { id: `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`, createdAt: new Date().toISOString(), design: form.design,
                    label: studyLabel, mode: form.mode, summary: `${result.total.recruit}`, writeup, form };
    setWorkspace((current) => ({ ...current, calculations: [entry, ...current.calculations].slice(0, 40) }));
    setNotice(t.saved);
  }

  function exportCsv() {
    const blob = new Blob([calculationsCsv(workspace.calculations)], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'resref-sample-size-calculations.csv';
    link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 2000);
  }

  const groupNames = spec?.groups?.[lang] || null;
  const answer = useMemo(() => {
    if (!result) return null;
    const twoPlus = result.per_group.length > 1;
    const names = twoPlus && groupNames && groupNames.length === result.per_group.length ? groupNames : null;
    if (result.answer.kind === 'power') return { big: `${Math.round(result.power * 100)}%`, unit: u.power.toLowerCase(), line: `${u.withN}: ${result.total.recruit}.` };
    if (result.answer.kind === 'mde') {
      const v = result.answer.value;
      const p1 = Number(form.p1) / 100;
      let big = v >= 10 ? v.toFixed(1) : v.toFixed(2);
      if (form.design === 'two_proportions') big = form.relative_risk ? `RR ${(v / p1).toFixed(2)}` : form.odds_ratio_exposure ? `OR ${((v / (1 - v)) / (p1 / (1 - p1))).toFixed(2)}` : `${(v * 100).toFixed(1)}%`;
      return { big, unit: form.unit || '', line: u.detect };
    }
    if (result.answer.kind === 'precision') return { big: result.design === 'single_mean' ? `±${result.answer.value.toFixed(2)}` : `±${(result.answer.value * 100).toFixed(1)}%`, unit: '', line: '' };
    const inviting = Number(form.response_rate || 100) < 100;
    const line = twoPlus
      ? `${names ? result.per_group.map((g, i) => `${g.recruit} ${names[i]}`).join(' + ') : `${result.per_group.map((g) => g.recruit).join(' + ')} ${u.perGroup}`}${u.sep} ${result.total.completers} ${u.complete}.`
      : result.total.recruit !== result.total.completers ? `${result.total.completers} ${u.complete}.` : '';
    return { big: result.total.recruit.toLocaleString(), unit: inviting ? u.invite : u.recruit, line };
  }, [result, form, u, groupNames]);

  const simpleFields = custom ? (DESIGN_FORMS[form.design]?.main || []) : spec?.simple || [];
  const advancedFields = custom ? (DESIGN_FORMS[form.design]?.advanced || []) : spec?.advanced || [];
  const renderField = (name) => (custom
    ? (fieldVisible(name, form) && <StudyField key={name} name={name} form={form} setValue={setValue} lang={lang} onHelper={setHelperFor} specs={FIELDS} keyOf={fieldKey} />)
    : <StudyField key={name} name={name} form={form} setValue={setValue} lang={lang} onHelper={setHelperFor} />);

  return (
    <section className="ssz-page">
      <div className="ssz" dir={lang === 'ar' ? 'rtl' : 'ltr'} lang={lang}>
        <header className="ssz-bar">
          <div className="ssz-brand"><span className="ssz-logo" aria-hidden="true"><Calculator size={17} /></span><h1>{u.title}</h1></div>
          <div className="ssz-segment" role="group" aria-label="Language">
            <button type="button" aria-pressed={lang === 'en'} onClick={() => changeLang('en')}>EN</button>
            <button type="button" aria-pressed={lang === 'ar'} onClick={() => changeLang('ar')} lang="ar">عربي</button>
          </div>
        </header>

        {notice && <p className="ssz-notice" role="status">{notice}<button type="button" className="ssz-icon" onClick={() => setNotice('')} aria-label={t.close}><X size={14} /></button></p>}

        {form && (
          <div className="ssz-layout">
            <div className="ssz-left">
            <section className="ssz-card ssz-step-card" aria-labelledby="ssz-step1">
              <h2 id="ssz-step1"><span className="ssz-step-num">1</span>{u.step1}</h2>
              <div className="ssz-types" role="group" aria-label={u.step1}>
                {STUDY_TYPES.map((type) => (
                  <button type="button" key={type.id} className="ssz-type" aria-pressed={form.studyType === type.id} onClick={() => chooseStudy(type.id)} title={type.desc[lang]}>
                    {type[lang]}
                  </button>
                ))}
              </div>
              {spec && <p className="ssz-type-desc">{spec.type.desc[lang]}</p>}
            </section>
            <section className="ssz-card ssz-main-card" aria-labelledby="ssz-step2">
              <h2 id="ssz-step2"><span className="ssz-step-num">2</span>{u.step2}{studyLabel && <small> · {studyLabel}</small>}</h2>
              {spec?.type.variants && (
                <div className="ssz-outcome">
                  <span>{u.measure}</span>
                  <div className="ssz-segment ssz-segment-lg" role="group" aria-label={u.measure}>
                    {spec.type.variants.map((variant) => <button type="button" key={variant.id} aria-pressed={form.variant === variant.id} onClick={() => chooseVariant(variant.id)}>{variant[lang]}</button>)}
                  </div>
                </div>
              )}
              <div className="ssz-grid">
                {form.mode !== 'n' && (
                  <div className="ssz-field"><label htmlFor="ssz-available">{groupNames ? `${u.available} (${groupNames[0]})` : u.available}</label>
                    <span className="ssz-input"><input id="ssz-available" inputMode="numeric" value={form.n_available ?? ''} onChange={(event) => setValue('n_available', event.target.value)} /></span></div>
                )}
                {simpleFields.filter((name) => !(form.mode === 'mde' && [design?.effect, 'relative_risk', 'odds_ratio_exposure'].includes(custom ? fieldKey(name) : fieldKeyOf(name)))).map(renderField)}
              </div>

              <details className="ssz-advanced">
                <summary><ChevronDown size={16} aria-hidden="true" /> {u.advanced} <small>{u.advancedHint}</small></summary>
                <div className="ssz-grid">
                  {modes.length > 1 && (
                    <label className="ssz-field" htmlFor="ssz-mode"><span>{u.alsoCalc}</span>
                      <select id="ssz-mode" value={form.mode} onChange={(event) => setForm((previous) => ({ ...previous, mode: event.target.value, n_available: previous.n_available || result?.per_group?.[0]?.recruit || 100 }))}>
                        {modes.map((mode) => <option key={mode} value={mode}>{u.modes[mode]}</option>)}
                      </select></label>
                  )}
                  {advancedFields.map(renderField)}
                  {custom && design?.kind === 'power' && <StudyField name="power" form={form} setValue={setValue} lang={lang} onHelper={setHelperFor} />}
                  {custom && design?.kind === 'power' && <StudyField name="significance" form={form} setValue={setValue} lang={lang} onHelper={setHelperFor} />}
                </div>
                <div className="ssz-method-row">
                  {result && <p className="ssz-muted"><strong>{u.method}:</strong> {result.method}</p>}
                  <button type="button" className="ssz-button" onClick={() => setLibraryOpen(true)}><Library size={14} aria-hidden="true" /> {u.exactMethod}</button>
                </div>
              </details>
            </section>
            </div>

            <aside ref={answerRef} className={`ssz-card ssz-answer ${busy ? 'is-busy' : ''}`} aria-live="polite" aria-labelledby="ssz-step3">
              <h2 id="ssz-step3" className="ssz-answer-label"><span className="ssz-step-num">3</span>{u.required}<span className="ssz-live"><span aria-hidden="true" />{u.live}</span></h2>
              {error && <p className="ssz-error" role="alert"><AlertTriangle size={16} aria-hidden="true" /> {error}</p>}
              {!error && !result && <p className="ssz-muted">{t.checking}</p>}
              {!error && result && answer && (
                <>
                  <div className="ssz-answer-number"><strong dir="ltr">{answer.big}</strong><span>{answer.unit}</span></div>
                  {answer.line && <p className="ssz-answer-detail">{answer.line}</p>}
                  {result.steps?.length > 1 && result.answer.kind === 'n' && (
                    <div className="ssz-steps">
                      <h3>{u.how}</h3>
                      <ol>{result.steps.map((step) => <li key={step.key}><span>{stepLabel(step, lang, form)}</span><strong>{step.n.toLocaleString()}</strong></li>)}</ol>
                    </div>
                  )}
                  {result.warnings.map((warning) => <p key={warning} className="ssz-warning" dir="auto"><AlertTriangle size={15} aria-hidden="true" /> {warning}</p>)}
                  <div className="ssz-writeup">
                    <div className="ssz-card-head">
                      <h3>{t.writeUp}</h3>
                      <div className="ssz-segment" role="group" aria-label={t.writeUp}>
                        <button type="button" aria-pressed={textLang === 'en'} onClick={() => setTextLang('en')}>English</button>
                        <button type="button" aria-pressed={textLang === 'ar'} onClick={() => setTextLang('ar')} lang="ar">العربية</button>
                      </div>
                    </div>
                    <p dir={textLang === 'ar' ? 'rtl' : 'ltr'} lang={textLang}>{writeup}</p>
                  </div>
                  <div className="ssz-actions">
                    <button type="button" className="ssz-button ssz-primary" onClick={copyWriteup}><Copy size={15} aria-hidden="true" /> {t.copy}</button>
                    <button type="button" className="ssz-button" onClick={downloadWord}><FileDown size={15} aria-hidden="true" /> {t.word}</button>
                    <button type="button" className="ssz-button" onClick={saveCalculation}><Save size={15} aria-hidden="true" /> {t.save}</button>
                  </div>
                  {(result.curve?.length > 2 || result.scenarios || result.criteria) && (
                    <details className="ssz-advanced">
                      <summary><ChevronDown size={16} aria-hidden="true" /> {u.more}</summary>
                      {result.criteria && <ul className="ssz-criteria">{result.criteria.map((c) => <li key={c.name}><span>{c.name}</span><strong>{c.n}</strong></li>)}</ul>}
                      <PowerCurve result={result} />
                      {result.scenarios && (
                        <div className="ssz-table-wrap">
                          <table className="ssz-table">
                            <caption>{t.scenarios}</caption>
                            <thead><tr><th scope="col">{t.effect}</th><th scope="col">80%</th><th scope="col">90%</th></tr></thead>
                            <tbody>{result.scenarios.map((row) => (
                              <tr key={row.effect} className={row.current ? 'is-current' : ''}>
                                <th scope="row">{form.design === 'two_proportions' && form.relative_risk ? `RR ${(row.effect / (Number(form.p1) / 100)).toFixed(2)}` : ['two_proportions', 'mcnemar'].includes(form.design) ? `${(row.effect * 100).toFixed(1)}%` : row.effect >= 10 ? row.effect.toFixed(1) : row.effect.toFixed(2)}</th>
                                <td>{row.p80 ?? '—'}</td><td>{row.p90 ?? '—'}</td>
                              </tr>))}</tbody>
                          </table>
                        </div>
                      )}
                      <p className="ssz-muted">{result.reference}</p>
                    </details>
                  )}
                </>
              )}
            </aside>
            {answer && !answerVisible && (
              <button type="button" className={`ssz-peek ${busy ? 'is-busy' : ''}`} onClick={() => answerRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })}>
                <span>{u.required}</span>
                <strong dir="ltr">{answer.big}</strong>
                <small>{answer.unit}</small>
                <ChevronDown size={18} aria-hidden="true" />
              </button>
            )}
          </div>
        )}

        {workspace.calculations.length > 0 && (
          <section className="ssz-card ssz-history-card" aria-label={t.history}>
            <div className="ssz-card-head">
              <h2>{t.history}</h2>
              <button type="button" className="ssz-button" onClick={exportCsv}><Download size={14} aria-hidden="true" /> {t.exportCsv}</button>
            </div>
            <ul className="ssz-history">
              {workspace.calculations.slice(0, 8).map((item) => (
                <li key={item.id}>
                  <span><strong>{item.label}</strong><small>{new Date(item.createdAt).toLocaleString()} · {item.summary}</small></span>
                  <span>
                    <button type="button" className="ssz-link" onClick={() => setForm(item.form)}>{t.restore}</button>
                    <button type="button" className="ssz-icon" onClick={() => setWorkspace((current) => ({ ...current, calculations: current.calculations.filter((c) => c.id !== item.id) }))} aria-label={t.remove}><X size={14} /></button>
                  </span>
                </li>
              ))}
            </ul>
          </section>
        )}

        <SdHelper open={Boolean(helperFor)} lang={lang} onClose={() => setHelperFor(null)}
                  onUse={(value, source) => { setForm((previous) => ({ ...previous, [helperFor]: value, sd_source: source || previous.sd_source })); setHelperFor(null); }} />
        <DesignLibrary open={libraryOpen} lang={lang} catalog={catalog} onClose={() => setLibraryOpen(false)}
                       onPick={(designId) => {
                         setForm({ studyType: 'custom', variant: null, design: designId, mode: 'n', significance: '0.05|2', power: '80', dropout: 10, ...DESIGN_FORMS[designId].defaults });
                         setLibraryOpen(false);
                       }} />
      </div>

      <ToolGuide path="/tools/sample-size-calculator" />
    </section>
  );
}
