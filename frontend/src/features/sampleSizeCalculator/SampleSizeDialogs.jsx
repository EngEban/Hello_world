/** Dialogs for the sample size studio: the SD helper and the library of all designs. */
import { useEffect, useMemo, useRef, useState } from 'react';
import { X } from 'lucide-react';
import { TEXT, pooledSd, sdFromCi, sdFromIqr } from './designs';

function useDialog(open) {
  const ref = useRef(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);
  return ref;
}

function NumberField({ label, value, onChange }) {
  return (
    <label className="ssz-field">
      <span>{label}</span>
      <input inputMode="decimal" value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

export function SdHelper({ open, lang, onClose, onUse }) {
  const t = TEXT[lang];
  const ref = useDialog(open);
  const [tab, setTab] = useState('groups');
  const [v, setV] = useState({ sd1: '', n1: '', sd2: '', n2: '', lower: '', upper: '', n: '', q1: '', q3: '' });
  const [source, setSource] = useState('');
  const set = (key) => (value) => setV((previous) => ({ ...previous, [key]: value }));
  const num = (key) => Number(String(v[key]).replace(',', '.'));
  const value = tab === 'groups' ? pooledSd(num('sd1'), num('n1'), num('sd2'), num('n2'))
    : tab === 'ci' ? sdFromCi(num('lower'), num('upper'), num('n')) : sdFromIqr(num('q1'), num('q3'));
  const how = {
    groups: lang === 'ar' ? 'انحراف معياري مُجمَّع موزون بحجم المجموعتين.' : 'Pooled SD, weighted by group size.',
    ci: lang === 'ar' ? 'SD = √n × (الحد الأعلى − الأدنى) ÷ (2 × t).' : 'SD = √n × (upper − lower) ÷ (2 × t), using the t value for n − 1 degrees of freedom.',
    iqr: lang === 'ar' ? 'تقريب صالح عندما يكون التوزيع متماثلاً تقريباً.' : 'IQR ÷ 1.35 — valid when the outcome is roughly symmetric (Wan et al., 2014).',
  }[tab];
  const tabs = [['groups', lang === 'ar' ? 'المتوسط ± الانحراف لكل مجموعة' : 'Mean ± SD for each group'], ['ci', lang === 'ar' ? 'فترة ثقة 95%' : '95% confidence interval'], ['iqr', lang === 'ar' ? 'الوسيط والمدى الربيعي' : 'Median and IQR']];
  return (
    <dialog ref={ref} className="ssz-dialog" onClose={onClose} aria-labelledby="ssz-helper-title" dir={lang === 'ar' ? 'rtl' : 'ltr'}>
      <div className="ssz-dialog-head">
        <div><h2 id="ssz-helper-title">{t.helperTitle}</h2><p>{t.helperCopy}</p></div>
        <button type="button" className="ssz-icon" onClick={onClose} aria-label={t.close}><X size={18} /></button>
      </div>
      <div className="ssz-chips" role="tablist">
        {tabs.map(([id, label]) => <button type="button" role="tab" key={id} aria-selected={tab === id} className="ssz-chip" aria-pressed={tab === id} onClick={() => setTab(id)}>{label}</button>)}
      </div>
      <div className="ssz-grid">
        {tab === 'groups' && <>
          <NumberField label={lang === 'ar' ? 'انحراف المجموعة أ' : 'Group A SD'} value={v.sd1} onChange={set('sd1')} />
          <NumberField label={lang === 'ar' ? 'حجم المجموعة أ' : 'Group A n'} value={v.n1} onChange={set('n1')} />
          <NumberField label={lang === 'ar' ? 'انحراف المجموعة ب' : 'Group B SD'} value={v.sd2} onChange={set('sd2')} />
          <NumberField label={lang === 'ar' ? 'حجم المجموعة ب' : 'Group B n'} value={v.n2} onChange={set('n2')} />
        </>}
        {tab === 'ci' && <>
          <NumberField label={lang === 'ar' ? 'الحد الأدنى' : '95% CI lower'} value={v.lower} onChange={set('lower')} />
          <NumberField label={lang === 'ar' ? 'الحد الأعلى' : '95% CI upper'} value={v.upper} onChange={set('upper')} />
          <NumberField label={lang === 'ar' ? 'حجم المجموعة' : 'Group size (n)'} value={v.n} onChange={set('n')} />
        </>}
        {tab === 'iqr' && <>
          <NumberField label={lang === 'ar' ? 'الربيع الأول' : 'Lower quartile (Q1)'} value={v.q1} onChange={set('q1')} />
          <NumberField label={lang === 'ar' ? 'الربيع الثالث' : 'Upper quartile (Q3)'} value={v.q3} onChange={set('q3')} />
        </>}
      </div>
      <div className="ssz-helper-result">
        <div>
          <span>{lang === 'ar' ? 'الانحراف المعياري' : 'Standard deviation'}</span>
          <strong>{value ? value.toFixed(2) : '—'}</strong>
          <small>{how}</small>
        </div>
        <button type="button" className="ssz-button ssz-primary" disabled={!value} onClick={() => onUse(Number(value.toFixed(2)), source)}>{t.useValue}</button>
      </div>
      <label className="ssz-field"><span>{t.source}</span><input value={source} onChange={(event) => setSource(event.target.value)} placeholder="e.g. Smith et al., Hypertension 2024" /></label>
    </dialog>
  );
}

export function DesignLibrary({ open, lang, catalog, onClose, onPick }) {
  const t = TEXT[lang];
  const ref = useDialog(open);
  const [advanced, setAdvanced] = useState(true);
  const families = useMemo(() => (catalog?.families || []).map((family) => ({
    ...family,
    designs: (catalog?.designs || []).filter((design) => design.family === family.id && (advanced || design.level === 'basic')),
  })).filter((family) => family.designs.length), [catalog, advanced]);
  return (
    <dialog ref={ref} className="ssz-dialog ssz-library" onClose={onClose} aria-labelledby="ssz-library-title" dir={lang === 'ar' ? 'rtl' : 'ltr'}>
      <div className="ssz-dialog-head">
        <div><h2 id="ssz-library-title">{t.library}</h2><p>{t.libraryCopy}</p></div>
        <button type="button" className="ssz-icon" onClick={onClose} aria-label={t.close}><X size={18} /></button>
      </div>
      <label className="ssz-switch">
        <input type="checkbox" role="switch" checked={advanced} onChange={(event) => setAdvanced(event.target.checked)} />
        <span aria-hidden="true" className="ssz-switch-track"><span /></span>{t.showAdvanced}
      </label>
      <div className="ssz-library-grid">
        {families.map((family) => (
          <section key={family.id} className="ssz-family">
            <h3>{lang === 'ar' ? family.label_ar : family.label}</h3>
            <ul>
              {family.designs.map((design) => (
                <li key={design.id}>
                  <button type="button" className={`ssz-design is-${design.level}`} onClick={() => onPick(design.id)}>
                    {lang === 'ar' ? design.label_ar : design.label}
                    {design.level === 'advanced' && <span>{t.adv}</span>}
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </dialog>
  );
}
