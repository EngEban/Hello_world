/**
 * Ask a question in plain words → ResRef recommends a method and explains why → Run.
 * Advanced options (adjustment, event / reference values, pairwise method, alternatives) stay hidden until asked for.
 * When a method is picked from the library, the card shows that method's own input form instead.
 */
import React, { useEffect, useMemo, useState } from 'react';
import { ChevronDown, Library, Sparkles, X } from 'lucide-react';
import { useStudioLang } from './i18n.jsx';
import { fetchLevels, recommendMethod } from '../services/researchAnalyzerApi';

const ANALYSABLE = (v) => !['id', 'text', 'date'].includes(v.type);
const IS_NUMBER = (v) => ['numeric', 'ordinal', 'likert'].includes(v.type);
const IS_CATEGORY = (v) => ['categorical', 'ordinal', 'likert'].includes(v.type) || (v.unique != null && v.unique <= 12);

const QUESTIONS = {
  compare: { parts: [{ en: 'Compare', ar: 'قارن' }, { field: 'outcome', filter: ANALYSABLE }, { en: 'between', ar: 'بين' }, { field: 'group', filter: IS_CATEGORY }],
             required: ['outcome', 'group'], advanced: [{ field: 'covariates', multi: true, label: 'adjustFor', filter: ANALYSABLE }] },
  relate: { parts: [{ en: 'Relationship between', ar: 'العلاقة بين' }, { field: 'var1', filter: ANALYSABLE }, { en: 'and', ar: 'و' }, { field: 'var2', filter: ANALYSABLE }],
            required: ['var1', 'var2'], advanced: [{ field: 'covariates', multi: true, label: 'adjustFor', filter: IS_NUMBER }] },
  predict: { parts: [{ en: 'Predict', ar: 'تنبأ بـ' }, { field: 'outcome', filter: ANALYSABLE }, { en: 'from', ar: 'من' }, { field: 'predictors', multi: true, filter: ANALYSABLE }],
             required: ['outcome', 'predictors'] },
  change: { parts: [{ en: 'Change in', ar: 'التغير في' }, { field: 'measures', multi: true, filter: IS_NUMBER, ordered: true }, { en: 'over time', ar: 'عبر الزمن' }],
            required: ['measures'], advanced: [{ field: 'between', label: 'groupsBetween', filter: IS_CATEGORY }] },
  accuracy: { parts: [{ en: 'Accuracy of', ar: 'دقة' }, { field: 'test', filter: ANALYSABLE }, { en: 'against', ar: 'مقارنةً بـ' }, { field: 'reference', filter: IS_CATEGORY }],
              required: ['test', 'reference'] },
  reliability: { parts: [{ en: 'Reliability of', ar: 'ثبات' }, { field: 'items', multi: true, filter: ANALYSABLE }], required: ['items'] },
  describe: { parts: [{ en: 'Describe the sample, split by', ar: 'صِف العينة مقسّمة حسب' }, { field: 'group', filter: IS_CATEGORY, optional: true }], required: [] },
  one_sample: { parts: [{ en: 'Is the average', ar: 'هل متوسط' }, { field: 'variable', filter: IS_NUMBER }, { en: 'different from', ar: 'يختلف عن' }, { field: 'test_value', number: true }],
                required: ['variable'] },
};

const OUTCOME_GROUP = ['ttest', 'welch', 'mann_whitney', 'anova', 'welch_anova', 'kruskal', 'two_by_two'];
const PAIR = ['chi_square', 'pearson', 'spearman', 'kendall', 'cohens_kappa'];
const REGRESSION = ['linear_regression', 'logistic_regression', 'multinomial_logistic', 'ordinal_logistic', 'count_regression'];

/** Parameters for any method from the question's fields (used when switching to an alternative). */
export function paramsFor(method, fields, variables) {
  const typeOf = Object.fromEntries(variables.map((v) => [v.name, v.type]));
  const first = fields.outcome || fields.var1 || fields.test || fields.variable;
  const second = fields.group || fields.var2 || fields.reference;
  const predictors = fields.predictors?.length ? fields.predictors : [second, ...(fields.covariates || [])].filter(Boolean);
  if (OUTCOME_GROUP.includes(method)) return { outcome: first, group: second };
  if (PAIR.includes(method)) return { var1: first, var2: second };
  if (REGRESSION.includes(method)) return { outcome: first, predictors, categorical_predictors: predictors.filter((p) => typeOf[p] === 'categorical') };
  if (method === 'ancova') return { outcome: first, group: second, covariates: fields.covariates || [] };
  if (method === 'factorial_anova') return { outcome: first, factors: [second, ...(fields.covariates || [])].filter(Boolean) };
  if (['paired_ttest', 'wilcoxon', 'mcnemar'].includes(method)) return { pre: fields.measures?.[0], post: fields.measures?.[1] };
  if (method === 'repeated_measures_anova') return { measures: fields.measures || [] };
  if (method === 'mixed_anova') return { measures: fields.measures || [], between: fields.between };
  if (method === 'partial_correlation') return { var1: first, var2: second, covariates: fields.covariates || [] };
  if (method === 'correlation_matrix') return { variables: [fields.var1, fields.var2, ...(fields.covariates || [])].filter(Boolean) };
  if (method === 'one_sample_ttest') return { variable: fields.variable, test_value: Number(fields.test_value || 0) };
  if (method === 'cronbach') return { items: fields.items || [], reverse_items: [] };
  if (['icc', 'fleiss_kappa'].includes(method)) return { raters: fields.items || [] };
  if (method === 'table_one') return { group: fields.group || null, variables: variables.filter(ANALYSABLE).map((v) => ({ name: v.name, type: v.type })) };
  if (method === 'diagnostic_accuracy') return { test: fields.test, reference: fields.reference };
  return {};
}

function VariableSelect({ value, onChange, options, label, optional, t }) {
  return (
    <select className="ras-pick" aria-label={label} value={value || ''} onChange={(event) => onChange(event.target.value || null)}>
      <option value="">{optional ? '—' : t.select}</option>
      {options.map((v) => <option key={v.name} value={v.name}>{v.name}</option>)}
    </select>
  );
}

function MultiPicker({ values = [], onChange, options, label, t, ordered }) {
  const remaining = options.filter((v) => !values.includes(v.name));
  return (
    <span className="ras-multi" aria-label={label}>
      {values.map((name, index) => (
        <span className="ras-token" key={name}>
          {ordered && <span className="ras-token-index">{index + 1}</span>}{name}
          <button type="button" onClick={() => onChange(values.filter((v) => v !== name))} aria-label={`Remove ${name}`}><X size={12} /></button>
        </span>
      ))}
      {remaining.length > 0 && (
        <select className="ras-pick ras-pick-add" aria-label={`${label}: ${t.add}`} value="" onChange={(event) => event.target.value && onChange([...values, event.target.value])}>
          <option value="">{t.add}</option>
          {remaining.map((v) => <option key={v.name} value={v.name}>{v.name}</option>)}
        </select>
      )}
    </span>
  );
}

function LevelSelect({ variable, value, onChange, label, t }) {
  const [levels, setLevels] = useState([]);
  useEffect(() => {
    let live = true;
    if (!variable) { setLevels([]); return undefined; }
    fetchLevels(variable).then((data) => live && setLevels(data.levels || [])).catch(() => live && setLevels([]));
    return () => { live = false; };
  }, [variable]);
  if (!variable || !levels.length) return null;
  return (
    <label className="ras-field">
      <span>{label}</span>
      <select value={value || ''} onChange={(event) => onChange(event.target.value || null)}>
        <option value="">{t.automatic}</option>
        {levels.map((level) => <option key={level.value} value={level.value}>{level.value} ({level.count})</option>)}
      </select>
    </label>
  );
}

function MethodOptions({ method, params, options, setOptions, t }) {
  const set = (key) => (value) => setOptions((previous) => ({ ...previous, [key]: value }));
  if (method === 'two_by_two') {
    return <>
      <LevelSelect variable={params.outcome} value={options.event_level} onChange={set('event_level')} label={t.eventValue} t={t} />
      <LevelSelect variable={params.group} value={options.reference_group} onChange={set('reference_group')} label={t.referenceGroup} t={t} />
    </>;
  }
  if (method === 'logistic_regression') return <LevelSelect variable={params.outcome} value={options.event_level} onChange={set('event_level')} label={t.eventValue} t={t} />;
  if (method === 'diagnostic_accuracy') return <LevelSelect variable={params.reference} value={options.reference_positive} onChange={set('reference_positive')} label={t.positiveValue} t={t} />;
  if (method === 'anova') {
    return (
      <label className="ras-field"><span>{t.pairwise}</span>
        <select value={options.posthoc || 'auto'} onChange={(event) => set('posthoc')(event.target.value)}>
          <option value="auto">{t.automatic}</option><option value="tukey">Tukey HSD</option><option value="games_howell">Games-Howell</option>
          <option value="bonferroni">Bonferroni</option><option value="holm">Holm</option>
        </select>
      </label>
    );
  }
  if (method === 'linear_regression') {
    return <label className="ras-check"><input type="checkbox" checked={Boolean(options.robust)} onChange={(event) => set('robust')(event.target.checked)} /> {t.robust}</label>;
  }
  if (method === 'cronbach') {
    return (
      <fieldset className="ras-field"><legend>{t.reverseItems}</legend>
        <div className="ras-check-row">
          {(params.items || []).map((item) => (
            <label key={item} className="ras-check"><input type="checkbox" checked={(options.reverse_items || []).includes(item)}
              onChange={(event) => set('reverse_items')(event.target.checked ? [...(options.reverse_items || []), item] : (options.reverse_items || []).filter((i) => i !== item))} /> {item}</label>
          ))}
        </div>
      </fieldset>
    );
  }
  return null;
}

/** Input form generated from a library method's declared inputs. */
function ManualForm({ method, variables, onRun, onClose, busy, t, lang }) {
  const [values, setValues] = useState({});
  const set = (key, value) => setValues((previous) => ({ ...previous, [key]: value }));
  const allowed = (input) => variables.filter(ANALYSABLE).filter((v) => !input.types || input.types.includes(v.type) || (input.types.includes('categorical') && IS_CATEGORY(v)));
  const ready = method.inputs.every((input) => !input.required || (Array.isArray(values[input.key]) ? values[input.key].length : values[input.key] !== undefined && values[input.key] !== null && values[input.key] !== ''));
  function run() {
    const params = { ...values };
    if (method.id === 'descriptive' || method.id === 'table_one') {
      params.variables = (values.variables || []).map((name) => ({ name, type: variables.find((v) => v.name === name)?.type || 'numeric' }));
    }
    if (method.id === 'one_sample_ttest') params.test_value = Number(values.test_value || 0);
    onRun(method.id, params, method.label);
  }
  return (
    <div className="ras-manual">
      <div className="ras-manual-head">
        <span className="ras-tag"><Library size={14} aria-hidden="true" /> {lang === 'ar' ? method.label_ar : method.label}</span>
        <button type="button" className="ras-icon-button" onClick={onClose} aria-label={t.close}><X size={16} /></button>
      </div>
      <div className="ras-manual-grid">
        {method.inputs.map((input) => {
          if (input.kind === 'variable') {
            return <label className="ras-field" key={input.key}><span>{input.label}{input.required ? '' : ' (optional)'}</span>
              <VariableSelect value={values[input.key]} onChange={(value) => set(input.key, value)} options={allowed(input)} label={input.label} optional={!input.required} t={t} /></label>;
          }
          if (input.kind === 'variables') {
            return <div className="ras-field" key={input.key}><span>{input.label}</span>
              <MultiPicker values={values[input.key] || []} onChange={(value) => set(input.key, value)} options={allowed(input)} label={input.label} t={t} /></div>;
          }
          if (input.kind === 'number') {
            return <label className="ras-field" key={input.key}><span>{input.label}</span>
              <input type="number" step="any" value={values[input.key] ?? ''} onChange={(event) => set(input.key, event.target.value)} /></label>;
          }
          if (input.kind === 'choice') {
            return <label className="ras-field" key={input.key}><span>{input.label}</span>
              <select value={values[input.key] || ''} onChange={(event) => set(input.key, event.target.value || undefined)}>
                <option value="">{t.automatic}</option>{input.options.map((option) => <option key={option} value={option}>{option}</option>)}
              </select></label>;
          }
          if (input.kind === 'level') return <LevelSelect key={input.key} variable={values[input.of]} value={values[input.key]} onChange={(value) => set(input.key, value)} label={input.label} t={t} />;
          if (input.kind === 'subset') {
            const pool = Array.isArray(values[input.of]) ? values[input.of] : [];
            if (!pool.length) return null;
            return <fieldset className="ras-field" key={input.key}><legend>{input.label}</legend><div className="ras-check-row">
              {pool.map((name) => <label key={name} className="ras-check"><input type="checkbox" checked={(values[input.key] || []).includes(name)}
                onChange={(event) => set(input.key, event.target.checked ? [...(values[input.key] || []), name] : (values[input.key] || []).filter((n) => n !== name))} /> {name}</label>)}
            </div></fieldset>;
          }
          return null;
        })}
      </div>
      <div className="ras-ask-footer"><span />
        <button type="button" className="ras-button ras-button-primary ras-button-lg" disabled={!ready || busy} onClick={run}>{busy ? t.running : t.run}</button>
      </div>
    </div>
  );
}

export default function AskCard({ variables, catalog, manualMethod, onCloseManual, onOpenLibrary, onRun, busy }) {
  const { t, lang } = useStudioLang();
  const [question, setQuestion] = useState('compare');
  const [fields, setFields] = useState({});
  const [recommendation, setRecommendation] = useState(null);
  const [selectionError, setSelectionError] = useState('');
  const [chosen, setChosen] = useState(null);
  const [options, setOptions] = useState({});
  const [advanced, setAdvanced] = useState(false);
  const config = QUESTIONS[question];
  const ready = config.required.every((key) => (Array.isArray(fields[key]) ? fields[key].length >= (key === 'measures' || key === 'items' ? 2 : 1) : fields[key]));
  const fieldKey = JSON.stringify(fields);

  useEffect(() => {
    setRecommendation(null);
    setSelectionError('');
    setChosen(null);
    setOptions({});
    if (!ready) return undefined;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      recommendMethod(question, fields, { signal: controller.signal })
        .then((data) => setRecommendation(data))
        .catch((error) => { if (error.name !== 'AbortError') setSelectionError(error.message); });
    }, 250);
    return () => { window.clearTimeout(timer); controller.abort(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [question, fieldKey, ready]);

  const setField = (key, value) => setFields((previous) => ({ ...previous, [key]: value }));
  const method = chosen || recommendation?.method;
  const baseParams = useMemo(() => {
    if (!recommendation) return {};
    return chosen ? paramsFor(chosen, fields, variables) : recommendation.params;
  }, [recommendation, chosen, fields, variables]);
  const methodLabel = (id) => catalog?.methods?.find((m) => m.id === id)?.[lang === 'ar' ? 'label_ar' : 'label'] || recommendation?.alternatives?.find((a) => a.method === id)?.label || id;

  function changeQuestion(next) {
    setQuestion(next);
    setFields({});
  }

  if (manualMethod) {
    return (
      <section className="ras-card ras-ask" aria-label={t.chooseMethod}>
        <ManualForm method={manualMethod} variables={variables} onRun={onRun} onClose={onCloseManual} busy={busy} t={t} lang={lang} />
      </section>
    );
  }

  return (
    <section className="ras-card ras-ask" aria-label={t.askTitle}>
      <div className="ras-ask-head">
        <h2>{t.askTitle}</h2>
        <button type="button" className="ras-link" onClick={onOpenLibrary}><Library size={15} aria-hidden="true" /> {t.chooseMethod}</button>
      </div>
      <div className="ras-chips" role="group" aria-label="Question type">
        {Object.keys(QUESTIONS).map((key) => (
          <button type="button" key={key} className="ras-chip" aria-pressed={question === key} onClick={() => changeQuestion(key)}>{t.questions[key]}</button>
        ))}
      </div>

      <div className="ras-sentence" dir={lang === 'ar' ? 'rtl' : 'ltr'}>
        {config.parts.map((part, index) => {
          if (!part.field) return <span key={index} className="ras-sentence-word">{part[lang] || part.en}</span>;
          const pool = variables.filter(part.filter);
          if (part.number) {
            return <input key={index} className="ras-pick ras-pick-number" type="number" step="any" aria-label={t.testValue}
                          value={fields[part.field] ?? ''} onChange={(event) => setField(part.field, event.target.value)} placeholder="0" />;
          }
          return part.multi
            ? <MultiPicker key={index} values={fields[part.field]} onChange={(value) => setField(part.field, value)} options={pool} label={part.field} t={t} ordered={part.ordered} />
            : <VariableSelect key={index} value={fields[part.field]} onChange={(value) => setField(part.field, value)} options={pool} label={part.field} optional={part.optional} t={t} />;
        })}
      </div>

      {selectionError && <p className="ras-error" role="alert" dir="auto">{selectionError}</p>}

      {recommendation && (
        <div className="ras-reco">
          <div className="ras-reco-main">
            <Sparkles size={18} aria-hidden="true" />
            <div>
              <span className="ras-reco-tag">{chosen ? t.yourChoice : t.recommended}</span>
              <strong>{methodLabel(method)}</strong>
              {!chosen && (
                <ul className="ras-reasons">{recommendation.reasons.map((reason) => <li key={reason} dir="auto">{reason}</li>)}</ul>
              )}
              {recommendation.warnings?.map((warning) => <p className="ras-warning" key={warning} dir="auto">{warning}</p>)}
            </div>
          </div>
          <div className="ras-reco-actions">
            <button type="button" className="ras-button" aria-expanded={advanced} onClick={() => setAdvanced(!advanced)}>
              {advanced ? t.hideAdvanced : t.advanced} <ChevronDown size={14} aria-hidden="true" className={advanced ? 'is-open' : ''} />
            </button>
            <button type="button" className="ras-button ras-button-primary ras-button-lg" disabled={busy}
                    onClick={() => onRun(method, { ...baseParams, ...options }, methodLabel(method))}>{busy ? t.running : t.run}</button>
          </div>
        </div>
      )}

      {recommendation && advanced && (
        <div className="ras-advanced">
          {config.advanced?.map((item) => {
            const used = Object.entries(fields).filter(([key]) => key !== item.field).flatMap(([, value]) => value || []);
            const pool = variables.filter(item.filter).filter((v) => !used.includes(v.name));
            return item.multi
              ? <div className="ras-field" key={item.field}><span>{t[item.label]}</span>
                  <MultiPicker values={fields[item.field]} onChange={(value) => setField(item.field, value)} options={pool} label={t[item.label]} t={t} /></div>
              : <label className="ras-field" key={item.field}><span>{t[item.label]}</span>
                  <VariableSelect value={fields[item.field]} onChange={(value) => setField(item.field, value)} options={pool} label={t[item.label]} optional t={t} /></label>;
          })}
          <MethodOptions method={method} params={baseParams} options={options} setOptions={setOptions} t={t} />
          {recommendation.alternatives?.length > 0 && (
            <label className="ras-field"><span>{t.otherMethods}</span>
              <select value={chosen || ''} onChange={(event) => { setChosen(event.target.value || null); setOptions({}); }}>
                <option value="">{t.automatic}: {methodLabel(recommendation.method)}</option>
                {recommendation.alternatives.map((alt) => <option key={alt.method} value={alt.method}>{alt.label} — {alt.when}</option>)}
              </select>
            </label>
          )}
        </div>
      )}
    </section>
  );
}
