import { useEffect, useId, useState } from 'react';
import { CheckCircle2 } from 'lucide-react';
import { PublicWebsiteApi } from '../../api/publicWebsiteApi';
import { trackEvent } from '../../utils/analytics';
import '../../styles/pages/public-forms.css';

const initialForm = { name: '', email: '', whatsapp: '', specialization: '', message: '' };
const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function cleanForm(values) {
  return Object.fromEntries(Object.entries(values).map(([key, value]) => [key, value.trim()]));
}

// kind="application" saves a team application (with optional CV);
// anything else is saved as a service request in the dashboard.
export default function RequestForm({
  id,
  requestType,
  kind = 'service',
  options = [],
  optionLabel = 'Area of Interest',
  selectedOption = '',
  submitLabel = 'Send Request',
  successMessage = 'Your request has been received.',
}) {
  const fieldId = useId();
  const [form, setForm] = useState({ ...initialForm, specialization: selectedOption });
  const [status, setStatus] = useState('');
  const [errorText, setErrorText] = useState('');
  const [cvFile, setCvFile] = useState(null);
  const [fileKey, setFileKey] = useState(0);

  useEffect(() => {
    if (selectedOption) setForm(current => ({ ...current, specialization: selectedOption }));
  }, [selectedOption]);

  const update = event => {
    const { name, value } = event.target;
    setForm(current => ({ ...current, [name]: value }));
    if (status && status !== 'sending') setStatus('');
  };

  const submit = async event => {
    event.preventDefault();
    const payload = cleanForm(form);
    if (!payload.name || !payload.email || !payload.message || (options.length > 0 && !payload.specialization)) {
      setStatus('invalid-required');
      return;
    }
    if (!emailPattern.test(payload.email)) {
      setStatus('invalid-email');
      return;
    }
    if (cvFile && (!/\.(pdf|docx)$/i.test(cvFile.name) || cvFile.size > 5 * 1024 * 1024)) {
      setStatus('invalid-cv');
      return;
    }
    setStatus('sending');
    setErrorText('');
    try {
      if (kind === 'application') {
        await PublicWebsiteApi.submitApplication({ full_name: payload.name, email: payload.email, whatsapp: payload.whatsapp, team: payload.specialization, motivation: payload.message }, cvFile);
      } else {
        await PublicWebsiteApi.submitServiceRequest(requestType, payload);
      }
      trackEvent('form_submit_success', { form_name: requestType });
      setForm({ ...initialForm, specialization: selectedOption });
      setCvFile(null);
      setFileKey(current => current + 1);
      setStatus('done');
    } catch (error) {
      setErrorText(error.status && error.status < 500 ? error.message : '');
      setStatus('error');
    }
  };

  return (
    <form id={id} className="contact-form request-form rh-form rp-form" onSubmit={submit} noValidate>
      <div className="form-row rh-form-row">
        <div className="rp-field">
          <label htmlFor={`${fieldId}-name`}>Full name <span className="rp-required" aria-hidden="true">*</span></label>
          <input id={`${fieldId}-name`} required name="name" value={form.name} onChange={update} placeholder="Full Name" aria-invalid={status === 'invalid-required'} autoComplete="name" />
        </div>
        <div className="rp-field">
          <label htmlFor={`${fieldId}-email`}>Email <span className="rp-required" aria-hidden="true">*</span></label>
          <input id={`${fieldId}-email`} required type="email" name="email" value={form.email} onChange={update} placeholder="Email" aria-invalid={status === 'invalid-email' || status === 'invalid-required'} autoComplete="email" />
        </div>
      </div>
      <div className="rp-field">
        <label htmlFor={`${fieldId}-whatsapp`}>WhatsApp number</label>
        <input id={`${fieldId}-whatsapp`} name="whatsapp" value={form.whatsapp} onChange={update} placeholder="WhatsApp Number" autoComplete="tel" />
      </div>
      {options.length > 0 ? (
        <label className="rp-field rp-select" htmlFor={`${fieldId}-specialization`}>
          <span>{optionLabel} <span className="rp-required" aria-hidden="true">*</span></span>
          <select id={`${fieldId}-specialization`} required name="specialization" value={form.specialization} onChange={update} aria-invalid={status === 'invalid-required' && !form.specialization}>
            <option value="">Select an option</option>
            {options.map(option => <option key={option}>{option}</option>)}
          </select>
        </label>
      ) : (
        <div className="rp-field"><label htmlFor={`${fieldId}-specialization`}>{optionLabel}</label><input id={`${fieldId}-specialization`} name="specialization" value={form.specialization} onChange={update} placeholder={optionLabel} /></div>
      )}
      <div className="rp-field">
        <label htmlFor={`${fieldId}-message`}>Message <span className="rp-required" aria-hidden="true">*</span></label>
        <textarea id={`${fieldId}-message`} required name="message" value={form.message} onChange={update} placeholder="Tell us about your background, goals, and how we can help." aria-invalid={status === 'invalid-required'} />
      </div>
      {kind === 'application' && (
        <label className="request-form-file rp-field rp-file">
          CV (optional, PDF or Word, up to 5 MB)
          <input key={fileKey} type="file" name="cv" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={event => setCvFile(event.target.files?.[0] || null)} />
        </label>
      )}
      <div className="rp-form-footer">
        <button className="button" disabled={status === 'sending'} aria-busy={status === 'sending'}>{status === 'sending' ? 'Sending...' : submitLabel}</button>
        <small className="rp-form-note"><span aria-hidden="true">*</span> Required fields</small>
      </div>
      {status === 'invalid-required' && <p className="error" role="alert">Please add your name, email, message, and select an option where required.</p>}
      {status === 'invalid-email' && <p className="error" role="alert">Please enter a valid email address.</p>}
      {status === 'invalid-cv' && <p className="error" role="alert">The CV must be a PDF or .docx file of 5 MB or less.</p>}
      {status === 'done' && <p className="success" role="status" aria-live="polite"><CheckCircle2 size={20} aria-hidden="true" /><span>{successMessage}</span></p>}
      {status === 'error' && <p className="error" role="alert">{errorText || 'Could not send your request. Please try again in a moment.'}</p>}
    </form>
  );
}
