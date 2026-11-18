import { MailCheck, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { AccountApi } from '../../api/accountApi';

// Native modal <dialog>: focus is trapped and Escape closes it.
export default function EmailChangeDialog({ onClose, onSent }) {
  const dialog = useRef(null);
  const [form, setForm] = useState({ new_email: '', current_password: '' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const node = dialog.current;
    if (node && !node.open) node.showModal?.();
    return () => node?.open && node.close();
  }, []);

  const submit = async event => {
    event.preventDefault();
    setError('');
    setBusy(true);
    try {
      const data = await AccountApi.requestEmailChange(form);
      onSent(data.message);
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  };

  const update = event => setForm(current => ({ ...current, [event.target.name]: event.target.value }));

  return <dialog ref={dialog} className="rp-acct-dialog" aria-labelledby="email-change-title" onClose={onClose} onCancel={onClose}>
    <form className="rh-form" onSubmit={submit}>
      <div className="rp-acct-dialog-head">
        <h2 id="email-change-title">Change email address</h2>
        <button className="rp-acct-dialog-close" type="button" onClick={onClose} aria-label="Close"><X size={18} aria-hidden="true" /></button>
      </div>
      <p className="rp-acct-hint">We send a confirmation link to the new address. Your email changes only after you open that link while signed in.</p>
      {error && <p className="account-error">{error}</p>}
      <label>
        New Email Address
        <input type="email" name="new_email" required value={form.new_email} onChange={update} autoComplete="email" autoCapitalize="none" spellCheck={false} />
      </label>
      <label>
        Current Password
        <input type="password" name="current_password" required value={form.current_password} onChange={update} autoComplete="current-password" />
      </label>
      <div className="rp-acct-actions">
        <button className="button" disabled={busy}><MailCheck size={15} aria-hidden="true" />{busy ? 'Sending...' : 'Send confirmation link'}</button>
        <button className="rp-acct-link" type="button" onClick={onClose}>Cancel</button>
      </div>
    </form>
  </dialog>;
}
