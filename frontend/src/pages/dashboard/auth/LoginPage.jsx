import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { ShieldCheck, ArrowLeft, BookOpen, BarChart3, Users, Loader2, AlertTriangle, CornerDownLeft } from 'lucide-react';
import { DashboardApi } from '../../../api/dashboardApi';
import { ASSETS } from '../../../siteData';
import '../../../styles/dashboard/dashboard-brand.css';
import '../../../styles/dashboard/dash-admin.css';

function validate(form) {
  const errors = {};
  if (!form.email.trim()) errors.email = 'Enter your email address or username.';
  if (!form.password) errors.password = 'Enter your password.';
  return errors;
}

export default function DashboardLoginPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  // Return to the page that asked for sign-in, but only inside the dashboard.
  const requestedNext = searchParams.get('next') || '';
  const nextPath = requestedNext.startsWith('/dashboard') && !requestedNext.startsWith('//') ? requestedNext : '/dashboard';
  const [form, setForm] = useState({ email: '', password: '' });
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [capsLock, setCapsLock] = useState(false);
  const returnLabel = nextPath !== '/dashboard' ? nextPath.replace(/^\/dashboard\/?/, '').split(/[?#]/)[0].replace(/[-/]/g, ' ').trim() : '';

  const login = async (event) => {
    event.preventDefault();
    if (loading) return;
    const errors = validate(form);
    setFieldErrors(errors);
    if (Object.keys(errors).length) return;
    setError('');
    setLoading(true);
    try {
      await DashboardApi.login({ username: form.email.trim(), password: form.password });
      navigate(nextPath, { replace: true });
    } catch (err) {
      setError(err.message || 'Invalid email address or password.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="login-page rh-tokens rh-dash-login">
      <section className="rp-dash-login-panel" aria-label="About the ResRef workspace">
        <div className="rp-dash-login-logo">
          <img src={ASSETS.logo} alt="" />
          <img src={ASSETS.logoWordmark} alt="ResRef" />
        </div>
        <div className="rp-dash-login-copy">
          <span className="rh-label rh-label-light">Editorial workspace</span>
          <p className="rp-dash-login-title">Publishing and operations for the ResRef research platform.</p>
          <ul>
            <li><span><BookOpen size={17} /></span>Articles, pages, media and taxonomy</li>
            <li><span><Users size={17} /></span>Users, team and forms</li>
            <li><span><BarChart3 size={17} /></span>Reports, premium controls and settings</li>
          </ul>
        </div>
        <small className="rp-dash-login-note"><ShieldCheck size={14} /> Authorized team members only</small>
      </section>
      <div className="login-card">
        <Link to="/" className="login-back-link"><ArrowLeft size={16} /> Back to ResRef</Link>
        <div className="login-brand">
          <div className="login-brand-mark"><img src={ASSETS.logo} alt="" /></div>
          <h1>ResRef Dashboard</h1>
          <p>Medical Research Platform — Admin Panel</p>
        </div>
        {returnLabel && <p className="login-return-note"><CornerDownLeft size={14} aria-hidden="true" /><span>Sign in to continue to <strong>{returnLabel}</strong>.</span></p>}
        {error && <div className="login-error" role="alert">{error}</div>}
        <form onSubmit={login}>
          <label>
            Email or Username
            <input
              required type="text" name="email" autoComplete="username"
              autoCapitalize="none" autoCorrect="off" spellCheck={false}
              placeholder="admin or you@example.com"
              value={form.email}
              onChange={e => { const next = { ...form, email: e.target.value }; setForm(next); setFieldErrors(validate(next)); }}
              aria-invalid={Boolean(fieldErrors.email)}
            />
            {fieldErrors.email && <small className="form-field-error">{fieldErrors.email}</small>}
          </label>
          <label>
            Password
            <div className="login-password-control">
              <input
                required type={showPassword ? 'text' : 'password'} name="password" autoComplete="current-password"
                aria-label="Password"
                autoCapitalize="none" autoCorrect="off" spellCheck={false}
                placeholder="Enter your password"
                value={form.password}
                onChange={e => { const next = { ...form, password: e.target.value }; setForm(next); setFieldErrors(validate(next)); }}
                aria-invalid={Boolean(fieldErrors.password)}
                aria-describedby={capsLock ? 'login-caps-warning' : undefined}
                onKeyUp={e => setCapsLock(Boolean(e.getModifierState?.('CapsLock')))}
                onKeyDown={e => setCapsLock(Boolean(e.getModifierState?.('CapsLock')))}
                onBlur={() => setCapsLock(false)}
              />
              <button type="button" onClick={() => setShowPassword(current => !current)} aria-label={showPassword ? 'Hide password' : 'Show password'}>{showPassword ? 'Hide' : 'Show'}</button>
            </div>
            {capsLock && <small className="login-caps-warning" id="login-caps-warning" role="status"><AlertTriangle size={13} /> Caps Lock is on</small>}
            {fieldErrors.password && <small className="form-field-error">{fieldErrors.password}</small>}
          </label>
          <button className="login-submit" disabled={loading}>
            {loading ? <><Loader2 size={16} className="login-spin" aria-hidden="true" /> Signing in...</> : 'Sign in to Dashboard'}
          </button>
        </form>
        <div className="login-footer">
          <Link to="/sign-in">Sign in to your ResRef account</Link>
          <div className="login-trust"><ShieldCheck size={15} /><span>Protected by Django sessions and CSRF</span></div>
          <small className="login-help">Lost access? Ask a ResRef administrator to reset your account from User Management.</small>
        </div>
      </div>
    </main>
  );
}
