import { ExternalLink, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { trackEvent } from '../../utils/analytics';
import '../../styles/pages/google-form-dialog.css';

/** The embeddable address of a public Google Form link, or '' for any other link (short and edit links included). */
export function googleFormEmbedUrl(href) {
  try {
    const url = new URL(href);
    if (url.protocol !== 'https:' || url.hostname !== 'docs.google.com' || !/^\/forms\/.+\/viewform$/.test(url.pathname)) return '';
    url.searchParams.delete('usp');
    url.searchParams.set('embedded', 'true');
    // An Arabic form otherwise renders right to left, unlike the rest of the site.
    url.searchParams.set('hl', 'en');
    return url.toString();
  } catch {
    return '';
  }
}

/** A Google Form in a window over the page, so applicants stay on the site. */
export default function GoogleFormDialog({ form, onClose }) {
  const ref = useRef(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    setLoaded(false);
    if (form && !dialog.open) {
      dialog.showModal();
      trackEvent('google_form_open', { form_name: form.title });
    }
    if (!form && dialog.open) dialog.close();
  }, [form]);

  return (
    <dialog ref={ref} className="rp-form-dialog" aria-label={form?.title} onClose={onClose} onCancel={onClose}
      onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}>
      {form && <div className="rp-form-dialog-panel">
        <header>
          <h2>{form.title}</h2>
          <a href={form.href} target="_blank" rel="noopener noreferrer"><ExternalLink size={15} aria-hidden="true" /><span>Open in a new tab</span></a>
          <button type="button" onClick={onClose} aria-label="Close the form"><X size={20} aria-hidden="true" /></button>
        </header>
        <div className="rp-form-dialog-body">
          {!loaded && <p role="status">Loading the form...</p>}
          <iframe src={form.embedUrl} title={form.title} onLoad={() => setLoaded(true)} />
        </div>
      </div>}
    </dialog>
  );
}
