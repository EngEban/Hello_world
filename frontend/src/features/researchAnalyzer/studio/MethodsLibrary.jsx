/** Every method, grouped by family; basic first, advanced behind a switch. Picking one opens its input form. */
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Search, X } from 'lucide-react';
import { useStudioLang } from './i18n.jsx';

export default function MethodsLibrary({ catalog, open, onClose, onPick }) {
  const { t, lang } = useStudioLang();
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [query, setQuery] = useState('');
  const dialogRef = useRef(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  const families = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return (catalog?.families || []).map((family) => ({
      ...family,
      methods: (catalog?.methods || []).filter((method) => method.family === family.id)
        .filter((method) => showAdvanced || needle || method.level === 'basic')
        .filter((method) => !needle || `${method.label} ${method.label_ar}`.toLowerCase().includes(needle)),
    })).filter((family) => family.methods.length);
  }, [catalog, showAdvanced, query]);

  return (
    <dialog ref={dialogRef} className="ras-library" onClose={onClose} aria-labelledby="ras-library-title" dir={lang === 'ar' ? 'rtl' : 'ltr'}>
      <div className="ras-library-head">
        <div>
          <h2 id="ras-library-title">{t.libraryTitle}</h2>
          <p>{t.libraryCopy}</p>
        </div>
        <button type="button" className="ras-icon-button" onClick={onClose} aria-label={t.close}><X size={18} /></button>
      </div>
      <div className="ras-library-tools">
        <label className="ras-search">
          <Search size={16} aria-hidden="true" />
          <span className="ras-visually-hidden">{t.search}</span>
          <input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder={t.search} />
        </label>
        <label className="ras-switch">
          <input type="checkbox" role="switch" checked={showAdvanced} onChange={(event) => setShowAdvanced(event.target.checked)} />
          <span aria-hidden="true" className="ras-switch-track"><span /></span>
          {t.showAdvanced}
        </label>
      </div>
      <div className="ras-library-grid">
        {families.map((family) => (
          <section key={family.id} className="ras-family">
            <h3>{lang === 'ar' ? family.label_ar : family.label}</h3>
            <p>{family.question}</p>
            <ul>
              {family.methods.map((method) => (
                <li key={method.id}>
                  <button type="button" className={`ras-method is-${method.level}`} onClick={() => onPick(method)}>
                    {lang === 'ar' ? method.label_ar : method.label}
                    {method.level === 'advanced' && <span className="ras-level">{t.advancedLevel}</span>}
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
      {catalog?.always_included && (
        <div className="ras-included">
          <h3>{t.included}</h3>
          <ul>{catalog.always_included.map((item) => <li key={item}>{item}</li>)}</ul>
        </div>
      )}
    </dialog>
  );
}
