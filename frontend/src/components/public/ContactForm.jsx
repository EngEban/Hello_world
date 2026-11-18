import { CheckCircle2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { PublicWebsiteApi } from '../../api/publicWebsiteApi';
import { useAccount } from '../../contexts/AccountContext';
import { trackEvent } from '../../utils/analytics';
import '../../styles/pages/public-forms.css';

const emptyForm = { name: '', company: '', whatsapp: '', email: '', specialization: '', message: '' };
const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
const phoneAllowedPattern = /^\+?[0-9\s().-]{7,20}$/;

function cleanForm(values) {
  return Object.fromEntries(Object.entries(values).map(([key, value]) => [key, value.trim()]));
}

function isValidPhoneNumber(value) {
  if (!value) return true;
  const digits = value.replace(/\D/g, '');
  return digits.length >= 7 && digits.length <= 15 && phoneAllowedPattern.test(value);
}

function accountPrefill(account) {
  if (!account) return emptyForm;
  const name = account.display_name || [account.first_name, account.last_name].filter(Boolean).join(' ') || '';
  return {
    ...emptyForm,
    name,
    company: account.organization || '',
    email: account.email || '',
    specialization: account.specialization || '',
  };
}

export default function ContactForm({
  title,
  text,
  submitLabel = 'Submit',
  messagePlaceholder = 'Your Message',
  className = '',
  initialValues = {},
  requestType = '',
}) {
  const { account } = useAccount() || {};
  const [form, setForm] = useState(emptyForm);
  const [status, setStatus] = useState('');
  const [hasPrefilled, setHasPrefilled] = useState(false);

  useEffect(() => {
    if (!account || hasPrefilled) return;
    const prefill = accountPrefill(account);
    setForm(current => ({
      ...current,
      name: current.name || prefill.name,
      company: current.company || prefill.company,
      email: current.email || prefill.email,
      specialization: current.specialization || prefill.specialization,
    }));
    setHasPrefilled(true);
  }, [account, hasPrefilled]);

  useEffect(() => {
    if (!Object.keys(initialValues).length) return;
    setForm(current => ({
      ...current,
      ...Object.fromEntries(Object.entries(initialValues).filter(([, value]) => value)),
    }));
    setStatus('');
  }, [initialValues.message, initialValues.specialization]);

  const update = event => {
    const { name, value } = event.target;
    setForm(current => ({ ...current, [name]: value }));
    if (status && status !== 'sending') setStatus('');
  };
  const submit = async event => {
    event.preventDefault();
    const payload = cleanForm(form);
    const missingFields = [
      !payload.name && 'name',
      !payload.email && 'email',
      !payload.message && 'message',
    ].filter(Boolean);
    if (missingFields.length) {
      setStatus('invalid-required');
      return;
    }
    if (!emailPattern.test(payload.email)) {
      setStatus('invalid-email');
      return;
    }
    if (!isValidPhoneNumber(payload.whatsapp)) {
      setStatus('invalid-whatsapp');
      return;
    }
    setStatus('sending');
    try {
      if (requestType) await PublicWebsiteApi.submitServiceRequest(requestType, payload);
      else await PublicWebsiteApi.submitContactForm(payload);
      trackEvent('form_submit_success', { form_name: requestType || 'Contact' });
      setStatus('done');
      setForm({ ...accountPrefill(account), message: '' });
    } catch {
      setStatus('error');
    }
  };

  return (
    <form className={`contact-form rh-form rp-form ${className}`.trim()} onSubmit={submit} noValidate>
      {(title || text) && (
        <div className="contact-form-head rp-form-head">
          {title && <h3>{title}</h3>}
          {text && <p>{text}</p>}
        </div>
      )}
      {status === 'done' && (
        <div className="contact-form-success rp-form-success" role="status" aria-live="polite">
          <CheckCircle2 size={24} aria-hidden="true" />
          <span>
            <strong>Your message was sent successfully.</strong>
            <small>Thank you. The ResRef team will review your request and contact you soon.</small>
          </span>
        </div>
      )}
      <div className="form-row rh-form-row">
        <div className="rp-field"><label htmlFor="contact-name">Name <span className="rp-required" aria-hidden="true">*</span></label><input id="contact-name" required name="name" value={form.name} onChange={update} placeholder="Name" aria-label="Name" autoComplete="name" aria-invalid={status === 'invalid-required' && !form.name.trim()} /></div>
        <div className="rp-field"><label htmlFor="contact-company">Company</label><input id="contact-company" name="company" value={form.company} onChange={update} placeholder="Company" aria-label="Company" /></div>
      </div>
      <div className="form-row rh-form-row">
        <div className="rp-field"><label htmlFor="contact-whatsapp">WhatsApp number</label><input id="contact-whatsapp" type="tel" inputMode="tel" autoComplete="tel" name="whatsapp" value={form.whatsapp} onChange={update} placeholder="WhatsApp Number" aria-label="WhatsApp Number" aria-invalid={status === 'invalid-whatsapp'} /></div>
        <div className="rp-field"><label htmlFor="contact-email">Email <span className="rp-required" aria-hidden="true">*</span></label><input id="contact-email" required type="email" inputMode="email" autoComplete="email" name="email" value={form.email} onChange={update} placeholder="Email" aria-label="Email" aria-invalid={status === 'invalid-email' || status === 'invalid-required'} /></div>
      </div>
      <div className="rp-field"><label htmlFor="contact-specialization">Specialization</label><input id="contact-specialization" name="specialization" value={form.specialization} onChange={update} placeholder="Specialization" aria-label="Specialization" /></div>
      <div className="rp-field"><label htmlFor="contact-message">Message <span className="rp-required" aria-hidden="true">*</span></label><textarea id="contact-message" required name="message" value={form.message} onChange={update} placeholder={messagePlaceholder} aria-label="Message" aria-invalid={status === 'invalid-required' && !form.message.trim()} /></div>
      <div className="rp-form-footer">
        <button className="button" disabled={status === 'sending'} aria-busy={status === 'sending'}>{status === 'sending' ? 'Sending...' : submitLabel}</button>
        <small className="rp-form-note"><span aria-hidden="true">*</span> Required fields</small>
      </div>
      {status === 'invalid-required' && <p className="error" role="alert">Missing required details: please add your name, a valid email address, and your message.</p>}
      {status === 'invalid-email' && <p className="error" role="alert">Email looks incomplete. Use a full address like name@example.com.</p>}
      {status === 'invalid-whatsapp' && <p className="error" role="alert">WhatsApp number looks invalid. Use digits with country code, for example +971 55 997 7405.</p>}
      {status === 'error' && <p className="error" role="alert">Could not submit your message. Please try again.</p>}
    </form>
  );
}
