import { BookOpenCheck, Check, Globe2, LockKeyhole, Mail, MailCheck, RefreshCcw, ShieldCheck, Sparkles, UserRound } from 'lucide-react';
import { useMemo, useState } from 'react';
import { isValidPhoneNumber } from 'react-phone-number-input';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { AccountApi } from '../../api/accountApi';
import CountrySelect from '../../components/account/CountrySelect';
import GoogleSignInButton from '../../components/account/GoogleSignInButton';
import PhoneField from '../../components/account/PhoneField';
import { guessCountry } from '../../components/account/countries';
import { useAccount } from '../../contexts/AccountContext';
import '../../styles/pages/account.css';
import { trackEvent } from '../../utils/analytics';
import { usePageMeta } from '../../utils/seo';

function stateFallback(state) {
  const from = state?.from;
  const path = `${from?.pathname || ''}${from?.search || ''}`;
  return isAllowedNextPath(path) ? path : '/';
}

function isAllowedNextPath(value) {
  const pathname = String(value || '').split('?')[0];
  const blocked = ['/sign-in', '/register', '/auth', '/account/reset-password'];
  return Boolean(value) && value.startsWith('/') && !value.startsWith('//') && !blocked.includes(pathname);
}

function safeNextPath(search, state) {
  const fallback = stateFallback(state);
  const next = new URLSearchParams(search).get('next') || fallback;
  if (!isAllowedNextPath(next)) return fallback;
  return next;
}

function validateForm(form, { isRegister, resetMode }) {
  const errors = {};
  if (isRegister && !resetMode && form.full_name.trim().length < 2) errors.full_name = 'Enter your name as it should appear on your account.';
  // Sign-in accepts an email or a username; registration and reset need an email.
  if (!isRegister && !resetMode) { if (!form.email.trim()) errors.email = 'Enter your email address or username.'; }
  else if (!/^\S+@\S+\.\S+$/.test(form.email.trim())) errors.email = 'Enter a valid email address.';
  if (!resetMode && !form.password) errors.password = 'Enter your password.';
  if (isRegister && !resetMode && form.password.length < 12) errors.password = 'Use at least 12 characters for a secure password.';
  if (isRegister && !resetMode && !form.country) errors.country = 'Select the country you live or work in.';
  if (isRegister && !resetMode && form.phone_number && !isValidPhoneNumber(form.phone_number)) errors.phone_number = 'Enter a valid phone number, or leave it empty.';
  return errors;
}

const SIGN_IN_META = { title: 'Sign in | ResRef', description: 'Sign in to your ResRef account to use research tools and save your work.' };
const REGISTER_META = { title: 'Create an account | ResRef', description: 'Create a free ResRef account for research tools, saved workspaces and updates.' };

export default function AccountAuthPage({ mode = 'login' }) {
  const isRegister = mode === 'register';
  usePageMeta(isRegister ? REGISTER_META : SIGN_IN_META);
  const location = useLocation();
  const navigate = useNavigate();
  const { account, setAccount } = useAccount();
  const nextPath = useMemo(() => safeNextPath(location.search, location.state), [location.search, location.state]);
  const nextQuery = nextPath === '/' ? '' : `?next=${encodeURIComponent(nextPath)}`;
  const [form, setForm] = useState(() => ({ full_name: '', email: '', password: '', country: guessCountry(), phone_number: '', marketing_opt_in: false, remember: true }));
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [resetMode, setResetMode] = useState(false);
  const signInMode = !isRegister && !resetMode;
  const [showPassword, setShowPassword] = useState(false);
  const [fieldErrors, setFieldErrors] = useState({});
  // After sign-up (or a login of an unconfirmed account) we wait for the
  // emailed link; the address is kept so the link can be re-sent.
  const [pendingEmail, setPendingEmail] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [resending, setResending] = useState(false);

  if (account) return <Navigate to={nextPath} replace />;

  const setField = (name, value) => {
    const next = { ...form, [name]: value };
    setForm(next);
    setFieldErrors(validateForm(next, { isRegister, resetMode }));
  };
  const update = event => setField(event.target.name, event.target.type === 'checkbox' ? event.target.checked : event.target.value);

  const finishSignIn = nextAccount => {
    setAccount(nextAccount);
    navigate(nextPath, { replace: true });
  };

  const submit = async event => {
    event.preventDefault();
    setError('');
    setNotice('');
    const validationErrors = validateForm(form, { isRegister, resetMode });
    setFieldErrors(validationErrors);
    if (Object.keys(validationErrors).length || submitting) return;
    setSubmitting(true);
    try {
      if (resetMode) {
        setNotice((await AccountApi.requestPasswordReset(form.email)).message);
        return;
      }
      if (isRegister) {
        const { remember: _remember, ...registration } = form;
        const data = await AccountApi.register(registration);
        trackEvent('sign_up', { method: 'email' });
        // Confirmation switched off on the server: the account is signed in.
        if (data.account) {
          finishSignIn(data.account);
          return;
        }
        setPendingEmail(form.email);
        setNotice(data.message);
        return;
      }
      const data = await AccountApi.login({ email: form.email, password: form.password, remember: form.remember });
      finishSignIn(data.account);
    } catch (err) {
      if (err.code === 'email_unconfirmed') setPendingEmail(form.email);
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const resend = async () => {
    if (resending) return;
    setError('');
    setResending(true);
    try {
      await AccountApi.resendConfirmation(pendingEmail);
      const time = new Date().toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
      setNotice(`A new confirmation link was sent to ${pendingEmail} at ${time}. It can take a minute to arrive; please check your spam folder too.`);
    } catch (err) {
      setError(err.message);
    } finally {
      setResending(false);
    }
  };

  if (pendingEmail && isRegister && notice) {
    return <section className="rp-auth">
      <div className="rh-container rp-auth-shell">
        <AuthBrandPanel
          title="One last step to activate your account."
          text="Confirm your email address to finish creating your ResRef membership. As soon as the link is opened you are signed in and ready to go."
        />
        <div className="rp-auth-card account-confirm-card" role="status">
          <span className="rp-auth-card-icon" aria-hidden="true"><MailCheck size={24} /></span>
          <h2>Check your inbox</h2>
          <p>{notice}</p>
          <p>Email: <strong>{pendingEmail}</strong>. Confirmation links are valid for 48 hours; check your spam folder if nothing arrives within a few minutes.</p>
          {error && <p className="account-error">{error}</p>}
          <button className="button account-submit" type="button" onClick={resend} disabled={resending}><RefreshCcw size={16} aria-hidden="true" />{resending ? 'Sending…' : 'Send the link again'}</button>
          <p className="rp-auth-switch">Already confirmed? <Link to={`/sign-in${nextQuery}`}>Sign in</Link></p>
        </div>
      </div>
    </section>;
  }

  const fieldClass = name => `rp-auth-input${fieldErrors[name] ? ' has-error' : ''}`;

  return <section className="rp-auth">
    <div className="rh-container rp-auth-shell">
      <AuthBrandPanel
        title="Your research workspace, ready for the future."
        text="Create a secure ResRef account today. Free membership starts with the core platform, while the account structure is ready for premium tools and services as they are introduced."
        benefits
      />
      <form className="rp-auth-card rh-form" onSubmit={submit} noValidate>
        {!resetMode && <nav className="rp-auth-tabs" aria-label="Account access">
          <Link to={`/sign-in${nextQuery}`} className={!isRegister ? 'is-active' : ''} aria-current={!isRegister ? 'page' : undefined}>Sign in</Link>
          <Link to={`/register${nextQuery}`} className={isRegister ? 'is-active' : ''} aria-current={isRegister ? 'page' : undefined}>Create account</Link>
        </nav>}
        <div className="rp-auth-card-head">
          <h2>{resetMode ? 'Reset your password' : isRegister ? 'Create your account' : 'Welcome back'}</h2>
          <p>{resetMode ? 'Enter your email and we will send a secure reset link.' : isRegister ? 'Start with a free ResRef account.' : 'Sign in to access your ResRef profile and synced tools.'}</p>
        </div>
        {error && <p className="account-error">{error}</p>}
        {pendingEmail && !isRegister && <button className="rp-auth-link" type="button" onClick={resend}>Send a new confirmation link</button>}
        {notice && <p className="account-success">{notice}</p>}
        {isRegister && !resetMode && <label className="rp-auth-field">Full Name<span className={fieldClass('full_name')}><UserRound size={18} aria-hidden="true" /><input required name="full_name" value={form.full_name} onChange={update} autoComplete="name" aria-invalid={Boolean(fieldErrors.full_name)} /></span>{fieldErrors.full_name && <small className="form-field-error">{fieldErrors.full_name}</small>}</label>}
        <label className="rp-auth-field">{signInMode ? 'Email or username' : 'Email Address'}<span className={fieldClass('email')}><Mail size={18} aria-hidden="true" /><input required type={signInMode ? 'text' : 'email'} name="email" value={form.email} onChange={update} autoComplete={signInMode ? 'username' : 'email'} autoCapitalize="none" autoCorrect="off" spellCheck={false} aria-invalid={Boolean(fieldErrors.email)} /></span>{fieldErrors.email && <small className="form-field-error">{fieldErrors.email}</small>}</label>
        {!resetMode && <label className="rp-auth-field">
          Password
          <span className={`${fieldClass('password')} rp-auth-password`}><LockKeyhole size={18} aria-hidden="true" /><input required type={showPassword ? 'text' : 'password'} name="password" value={form.password} onChange={update} autoComplete={isRegister ? 'new-password' : 'current-password'} autoCapitalize="none" autoCorrect="off" spellCheck={false} aria-invalid={Boolean(fieldErrors.password)} /><button type="button" onClick={() => setShowPassword(current => !current)} aria-label={showPassword ? 'Hide password' : 'Show password'}>{showPassword ? 'Hide' : 'Show'}</button></span>
          {fieldErrors.password && <small className="form-field-error">{fieldErrors.password}</small>}
          {isRegister && <small className="rp-auth-hint">Use at least 12 characters. Avoid common or personal passwords.</small>}
        </label>}
        {isRegister && !resetMode && <label className="rp-auth-field">Country<span className={`${fieldClass('country')} rp-auth-select`}><Globe2 size={18} aria-hidden="true" /><CountrySelect required value={form.country} onChange={update} invalid={Boolean(fieldErrors.country)} /></span>{fieldErrors.country && <small className="form-field-error">{fieldErrors.country}</small>}</label>}
        {isRegister && !resetMode && <div className="rp-auth-field">
          <label htmlFor="register-phone">Phone number (optional)</label>
          <PhoneField id="register-phone" value={form.phone_number} onChange={value => setField('phone_number', value)} defaultCountry={form.country} invalid={Boolean(fieldErrors.phone_number)} />
          {fieldErrors.phone_number ? <small className="form-field-error">{fieldErrors.phone_number}</small> : <small className="rp-auth-hint">Include the country code. Used only for account and service contact.</small>}
        </div>}
        {!isRegister && !resetMode && <div className="rp-auth-row-split">
          <label className="rp-auth-check"><input type="checkbox" name="remember" checked={form.remember} onChange={update} /> Keep me signed in</label>
          <button className="rp-auth-link" type="button" onClick={() => setResetMode(true)}>Forgot your password?</button>
        </div>}
        {isRegister && !resetMode && <label className="rp-auth-check"><input type="checkbox" name="marketing_opt_in" checked={form.marketing_opt_in} onChange={update} /> Send me occasional ResRef updates.</label>}
        <button className="button account-submit" disabled={submitting} aria-busy={submitting}>{submitting ? (resetMode ? 'Sending…' : isRegister ? 'Creating your account…' : 'Signing in…') : resetMode ? 'Send Reset Link' : isRegister ? 'Create Free Account' : 'Sign In'}</button>
        {resetMode && <button className="rp-auth-link rp-auth-back" type="button" onClick={() => { setResetMode(false); setNotice(''); setFieldErrors({}); }}>Back to sign in</button>}
        {!resetMode && <GoogleSignInButton onSuccess={finishSignIn} onError={setError} />}
        <p className="rp-auth-switch">
          {isRegister ? <>Already a member? <Link to={`/sign-in${nextQuery}`}>Sign in</Link></> : <>New to ResRef? <Link to={`/register${nextQuery}`}>Create an account</Link></>}
        </p>
      </form>
    </div>
  </section>;
}

const MEMBER_BENEFITS = [
  { Icon: Sparkles, text: 'Free membership with the core ResRef research platform.' },
  { Icon: BookOpenCheck, text: 'Research tools that save your work to your profile.' },
  { Icon: Check, text: 'Ready for premium tools and services as they are introduced.' },
];

function AuthBrandPanel({ title, text, benefits = false }) {
  return <aside className="rp-auth-brand">
    <span className="rp-auth-brand-glow" aria-hidden="true" />
    <div className="rp-auth-brand-copy">
      <span className="rh-label rh-label-light">ResRef Membership</span>
      <h1>{title}</h1>
      <p>{text}</p>
    </div>
    {benefits && <ul className="rp-auth-benefits">
      {MEMBER_BENEFITS.map(({ Icon, text: benefit }) => <li key={benefit}><span aria-hidden="true"><Icon size={16} /></span>{benefit}</li>)}
    </ul>}
    <div className="rp-auth-trust"><ShieldCheck size={19} aria-hidden="true" /><span>Protected by Django sessions, CSRF checks, strong password validation, and throttled sign-in attempts.</span></div>
  </aside>;
}
