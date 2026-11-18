import { ArrowLeft, KeyRound, LockKeyhole, ShieldCheck } from 'lucide-react';
import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { AccountApi } from '../../api/accountApi';
import '../../styles/pages/account.css';
import { usePageMeta } from '../../utils/seo';

const META = { title: 'Reset password | ResRef', description: 'Choose a new password for your ResRef account.' };

export default function AccountResetPasswordPage() {
  usePageMeta(META);
  const [params] = useSearchParams();
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [fieldError, setFieldError] = useState('');
  const submit = async event => {
    event.preventDefault(); setError('');
    if (password.length < 12) {
      setFieldError('Use at least 12 characters for a secure password.');
      return;
    }
    try { await AccountApi.confirmPasswordReset({ uid: params.get('uid'), token: params.get('token'), new_password: password }); setNotice('Password reset complete. You can sign in now.'); }
    catch (err) { setError(err.message); }
  };
  return <section className="rp-auth rp-auth-single">
    <div className="rh-container rp-auth-narrow">
      <form className="rp-auth-card rh-form" onSubmit={submit} noValidate>
        <span className="rp-auth-card-icon" aria-hidden="true"><KeyRound size={24} /></span>
        <div className="rp-auth-card-head">
          <span className="rh-label">Account security</span>
          <h1>Choose a new password</h1>
          <p>Use at least 12 characters and choose one you have not used for this account before.</p>
        </div>
        {error && <p className="account-error">{error}</p>}
        {notice && <p className="account-success">{notice}</p>}
        <label className="rp-auth-field">New Password<span className={`rp-auth-input rp-auth-password${fieldError ? ' has-error' : ''}`}><LockKeyhole size={18} aria-hidden="true" /><input required type={showPassword ? 'text' : 'password'} value={password} onChange={event => { const value = event.target.value; setPassword(value); setFieldError(value && value.length < 12 ? 'Use at least 12 characters for a secure password.' : ''); }} autoComplete="new-password" autoCapitalize="none" autoCorrect="off" spellCheck={false} aria-invalid={Boolean(fieldError)} /><button type="button" onClick={() => setShowPassword(current => !current)} aria-label={showPassword ? 'Hide password' : 'Show password'}>{showPassword ? 'Hide' : 'Show'}</button></span>{fieldError && <small className="form-field-error">{fieldError}</small>}</label>
        <button className="button account-submit" disabled={Boolean(notice)}>Reset Password</button>
        <p className="rp-auth-switch"><Link to="/sign-in"><ArrowLeft size={15} aria-hidden="true" />Back to sign in</Link></p>
        <p className="rp-auth-footnote"><ShieldCheck size={16} aria-hidden="true" />Reset links are single-use and expire automatically.</p>
      </form>
    </div>
  </section>;
}
