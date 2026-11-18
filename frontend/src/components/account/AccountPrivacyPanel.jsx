import { Download, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { AccountApi } from '../../api/accountApi';

// "Your data": download a JSON copy, or delete (deactivate + anonymise) the account.
export default function AccountPrivacyPanel({ account, onError, onNotice, onDeleted }) {
  const [busy, setBusy] = useState('');
  const [deletion, setDeletion] = useState(null); // { confirm, current_password } while open

  const downloadData = async () => {
    onError('');
    setBusy('export');
    try {
      const data = await AccountApi.exportAccount();
      const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }));
      const link = document.createElement('a');
      link.href = url;
      link.download = `resref-account-${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      onNotice('Your data was downloaded as a JSON file.');
    } catch (err) {
      onError(err.message);
    } finally {
      setBusy('');
    }
  };

  const deleteAccount = async event => {
    event.preventDefault();
    onError('');
    setBusy('delete');
    try {
      await AccountApi.deleteAccount(deletion);
      onDeleted();
    } catch (err) {
      onError(err.message);
      setBusy('');
    }
  };

  const confirmed = deletion?.confirm.trim().toUpperCase() === 'DELETE';

  return <section className="rp-acct-panel rp-acct-privacy" id="account-privacy" aria-labelledby="account-privacy-title">
    <div className="rp-acct-panel-head">
      <span className="rp-acct-icon" aria-hidden="true"><Download size={20} /></span>
      <div>
        <h2 id="account-privacy-title">Your Data</h2>
        <p>Download a copy of what is stored with your account, or delete the account.</p>
      </div>
    </div>
    <div className="rp-acct-actions">
      <button className="button button-outline" type="button" onClick={downloadData} disabled={Boolean(busy)}>
        <Download size={15} aria-hidden="true" />
        {busy === 'export' ? 'Preparing...' : 'Download my data'}
      </button>
      {!deletion && <button className="rp-acct-danger" type="button" onClick={() => setDeletion({ confirm: '', current_password: '' })}><Trash2 size={15} aria-hidden="true" />Delete my account</button>}
    </div>
    {deletion && (
      <form className="rp-acct-delete rh-form" onSubmit={deleteAccount}>
        <p><strong>This cannot be undone.</strong> Your name, email, phone and profile details are removed and you are signed out. Records we must keep, such as billing history, no longer identify you. Cancel any paid subscription first.</p>
        <label>
          Type DELETE to confirm
          <input name="confirm" value={deletion.confirm} onChange={event => setDeletion({ ...deletion, confirm: event.target.value })} autoComplete="off" autoCapitalize="characters" spellCheck={false} />
        </label>
        {account.has_password && (
          <label>
            Current Password
            <input type="password" name="current_password" value={deletion.current_password} onChange={event => setDeletion({ ...deletion, current_password: event.target.value })} autoComplete="current-password" />
          </label>
        )}
        <div className="rp-acct-actions">
          <button className="rp-acct-danger is-solid" disabled={!confirmed || Boolean(busy)}>
            <Trash2 size={15} aria-hidden="true" />{busy === 'delete' ? 'Deleting...' : 'Permanently delete account'}
          </button>
          <button className="rp-acct-link" type="button" onClick={() => setDeletion(null)}>Cancel</button>
        </div>
      </form>
    )}
  </section>;
}
