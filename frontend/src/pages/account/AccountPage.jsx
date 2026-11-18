import { ArrowUpRight, Bell, BellOff, Check, CreditCard, Crown, Download, ExternalLink, KeyRound, LockKeyhole, LogOut, MailCheck, Save, ShieldCheck, Sparkles, UserRound, XCircle } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { isValidPhoneNumber } from 'react-phone-number-input';
import { Navigate, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { AccountApi } from '../../api/accountApi';
import AccountPrivacyPanel from '../../components/account/AccountPrivacyPanel';
import CountrySelect from '../../components/account/CountrySelect';
import EmailChangeDialog from '../../components/account/EmailChangeDialog';
import PhoneField from '../../components/account/PhoneField';
import { useAccount } from '../../contexts/AccountContext';
import '../../styles/pages/account.css';
import { usePageMeta } from '../../utils/seo';

const META = { title: 'My account | ResRef', description: 'Manage your ResRef profile, security and membership.' };

export default function AccountPage() {
  usePageMeta(META);
  const { account, loading, setAccount, logout } = useAccount();
  const [searchParams, setSearchParams] = useSearchParams();
  const [profile, setProfile] = useState({});
  const [password, setPassword] = useState({ current_password: '', new_password: '' });
  const [verificationSending, setVerificationSending] = useState(false);
  const [billingConfig, setBillingConfig] = useState(null);
  const [billingBusy, setBillingBusy] = useState('');
  const [notifications, setNotifications] = useState([]);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [failedAvatar, setFailedAvatar] = useState('');
  const [emailChangeOpen, setEmailChangeOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const emailChangeSent = useRef('');

  // Link from the "confirm your new email" message (single-use: post once).
  useEffect(() => {
    const token = searchParams.get('email_change');
    if (!account || !token || emailChangeSent.current === token) return;
    emailChangeSent.current = token;
    setError('');
    AccountApi.confirmEmailChange(token)
      .then(data => { setAccount(data.account); setNotice(`Your account email is now ${data.account.email}.`); })
      .catch(err => setError(err.message))
      .finally(() => setSearchParams({}, { replace: true }));
  }, [account, searchParams, setAccount, setSearchParams]);

  useEffect(() => {
    if (account) setProfile(account);
  }, [account]);

  useEffect(() => {
    if (!account) return;
    let active = true;
    AccountApi.getConfig()
      .then(data => {
        if (active) setBillingConfig(data.billing || null);
      })
      .catch(() => {
        if (active) setBillingConfig(null);
      });
    AccountApi.getNotifications()
      .then(data => {
        if (active) setNotifications(data.results || []);
      })
      .catch(() => {
        if (active) setNotifications([]);
      });
    return () => { active = false; };
  }, [account]);

  useEffect(() => {
    const token = searchParams.get('verify');
    const billingResult = searchParams.get('billing');
    if (account && billingResult) {
      setNotice(billingResult === 'success'
        ? 'Checkout completed. Your subscription will update after Stripe confirms the payment.'
        : 'Checkout was cancelled. No billing change was made.');
      setSearchParams({}, { replace: true });
      return;
    }
    if (!account || !token) return;
    let active = true;
    async function confirmEmail() {
      setError('');
      try {
        const data = await AccountApi.confirmEmailVerification(token);
        if (!active) return;
        setAccount(data.account);
        setNotice('Email verified successfully.');
        setSearchParams({}, { replace: true });
      } catch (err) {
        if (!active) return;
        setError(err.message);
        setSearchParams({}, { replace: true });
      }
    }
    confirmEmail();
    return () => { active = false; };
  }, [account, searchParams, setAccount, setSearchParams]);

  if (!loading && !account) {
    // Keep emailed links (?verify= / ?email_change=) working after signing in.
    const next = `${location.pathname}${location.search}`;
    return <Navigate to={location.search ? `/sign-in?next=${encodeURIComponent(next)}` : '/sign-in'} replace />;
  }
  if (!account) return null;

  const update = event => {
    setProfile({
      ...profile,
      [event.target.name]: event.target.type === 'checkbox' ? event.target.checked : event.target.value,
    });
  };

  const save = async event => {
    event.preventDefault();
    setError('');
    if (profile.phone_number && !isValidPhoneNumber(profile.phone_number)) {
      setError('Enter a valid phone number with its country code, or leave it empty.');
      return;
    }
    try {
      const data = await AccountApi.updateProfile(profile);
      setAccount(data.account);
      setNotice('Profile saved.');
    } catch (err) {
      setError(err.message);
    }
  };

  const changePassword = async event => {
    event.preventDefault();
    setError('');
    try {
      await AccountApi.changePassword(password);
      setPassword({ current_password: '', new_password: '' });
      setNotice('Password updated securely.');
    } catch (err) {
      setError(err.message);
    }
  };

  const requestEmailVerification = async () => {
    setError('');
    setVerificationSending(true);
    try {
      const data = await AccountApi.requestEmailVerification();
      setNotice(data.message || 'A verification link has been sent to your email address.');
    } catch (err) {
      setError(err.message);
    } finally {
      setVerificationSending(false);
    }
  };

  const refreshAccount = async () => {
    const data = await AccountApi.getMe();
    if (data.account) setAccount(data.account);
  };

  const startCheckout = async plan => {
    setError('');
    setBillingBusy(plan);
    try {
      const data = await AccountApi.createBillingCheckout(plan);
      window.location.assign(data.checkout_url);
    } catch (err) {
      setError(err.message);
      setBillingBusy('');
    }
  };

  const openBillingPortal = async () => {
    setError('');
    setBillingBusy('portal');
    try {
      const data = await AccountApi.openBillingPortal();
      window.location.assign(data.portal_url);
    } catch (err) {
      setError(err.message);
      setBillingBusy('');
    }
  };

  const cancelSubscription = async () => {
    setError('');
    setBillingBusy('cancel');
    try {
      await AccountApi.cancelSubscription();
      await refreshAccount();
      setNotice('Subscription cancellation was scheduled for the end of the current period.');
    } catch (err) {
      setError(err.message);
    } finally {
      setBillingBusy('');
    }
  };

  const markNotificationRead = async id => {
    try {
      const data = await AccountApi.markNotificationRead(id);
      setNotifications(items => items.map(item => (item.id === id ? data.notification : item)));
    } catch (err) {
      setError(err.message);
    }
  };

  const availableBillingPlans = (billingConfig?.plans || []).filter(plan => plan.available);
  const activeSubscription = account.subscription;
  const featureEntries = Object.entries(account.features || {});
  const allowedCount = featureEntries.filter(([, feature]) => feature.allowed).length;
  const unreadCount = notifications.filter(item => !item.is_read).length;
  const initial = (account.display_name || account.email || '?').trim().charAt(0).toUpperCase();
  const showAvatar = Boolean(account.avatar_url) && account.avatar_url !== failedAvatar;
  const sections = [
    ['#account-profile', 'Profile', UserRound],
    ['#account-security', 'Security', ShieldCheck],
    ['#account-membership', 'Membership', Crown],
    ['#account-notifications', 'Notifications', Bell],
    ['#account-privacy', 'Your data', Download],
  ];

  return (
    <section className="rp-acct">
      <div className="rh-container">
        <header className="rp-acct-hero">
          <span className="rp-acct-hero-glow" aria-hidden="true" />
          <div className="rp-acct-identity">
            <div className="rp-acct-avatar" aria-hidden="true">
              {showAvatar ? <img src={account.avatar_url} alt="" onError={() => setFailedAvatar(account.avatar_url)} /> : <span>{initial}</span>}
            </div>
            <div className="rp-acct-identity-copy">
              <span className="rh-label rh-label-light">Member Account</span>
              <h1>{account.display_name}</h1>
              <p>Manage your profile, security, and feature access from one place.</p>
              <div className="rp-acct-badges">
                <span className={`rp-acct-tier is-${account.tier}`}><Crown size={15} aria-hidden="true" />{account.tier} membership</span>
                <span className={`rp-acct-pill${account.email_verified ? ' is-ok' : ''}`}><MailCheck size={14} aria-hidden="true" />{account.email_verified ? 'Email verified' : 'Email verification pending'}</span>
              </div>
            </div>
          </div>
          <dl className="rp-acct-stats">
            <div><dt>Tier</dt><dd>{account.tier}</dd></div>
            <div><dt>Features</dt><dd>{allowedCount}/{featureEntries.length}</dd></div>
            <div><dt>Unread</dt><dd>{unreadCount}</dd></div>
          </dl>
          <nav className="rp-acct-nav" aria-label="Account sections">
            {sections.map(([href, label, Icon]) => <a key={href} href={href}><Icon size={15} aria-hidden="true" />{label}</a>)}
          </nav>
        </header>

        <div className="rp-acct-alerts" aria-live="polite">
          {error && <p className="account-error">{error}</p>}
          {notice && <p className="account-success">{notice}</p>}
        </div>

        <div className="rp-acct-grid">
          <form className="rp-acct-panel rp-acct-profile rh-form" id="account-profile" onSubmit={save}>
            <div className="rp-acct-panel-head">
              <span className="rp-acct-icon" aria-hidden="true"><UserRound size={20} /></span>
              <div><h2>Profile</h2><p>How your name and details appear across ResRef.</p></div>
            </div>
            <div className="rh-form-row">
              <label>
                Display Name
                <input name="display_name" value={profile.display_name || ''} onChange={update} />
              </label>
              <label>
                Email Address
                <input value={account.email} disabled />
                {account.has_password
                  ? <button className="rp-acct-link rp-acct-inline-link" type="button" onClick={() => setEmailChangeOpen(true)}>Change email</button>
                  : <small className="rp-acct-hint">Add a password to be able to change your email.</small>}
              </label>
              <label>
                Organization
                <input name="organization" value={profile.organization || ''} onChange={update} />
              </label>
              <label>
                Specialization
                <input name="specialization" value={profile.specialization || ''} onChange={update} />
              </label>
            </div>
            <div className="rh-form-row">
              <label>
                Country
                <CountrySelect value={profile.country} onChange={update} />
              </label>
              <div className="rp-acct-field">
                <label htmlFor="account-phone">Phone Number</label>
                <PhoneField id="account-phone" value={profile.phone_number} onChange={value => setProfile(current => ({ ...current, phone_number: value }))} defaultCountry={profile.country} />
                <small className="rp-acct-hint">Optional. Include the country code.</small>
              </div>
            </div>
            <label>
              Avatar Image URL
              <input name="avatar_url" value={profile.avatar_url || ''} onChange={update} placeholder="https://..." />
            </label>
            <label className="rp-acct-check">
              <input type="checkbox" name="marketing_opt_in" checked={profile.marketing_opt_in || false} onChange={update} />
              Send me occasional ResRef updates.
            </label>
            <div className="rp-acct-actions">
              <button className="button">
                <Save size={15} />
                Save Profile
              </button>
            </div>
          </form>

          <form className="rp-acct-panel rp-acct-security rh-form" id="account-security" onSubmit={changePassword}>
            <div className="rp-acct-panel-head">
              <span className="rp-acct-icon" aria-hidden="true"><ShieldCheck size={20} /></span>
              <div><h2>Security</h2><p>{account.auth_provider === 'google' ? 'Your account is connected to Google. You can add a password through the reset-password flow.' : 'Change your password regularly and do not reuse it on other websites.'}</p></div>
            </div>
            <div className={`rp-acct-verify ${account.email_verified ? 'is-verified' : 'is-pending'}`}>
              <MailCheck size={18} aria-hidden="true" />
              <span>
                <strong>{account.email_verified ? 'Email verified' : 'Email verification pending'}</strong>
                <small>{account.email_verified ? 'Your email address is confirmed.' : 'Verify your email to protect account recovery and future billing workflows.'}</small>
              </span>
              {!account.email_verified && (
                <button className="rp-acct-link" type="button" onClick={requestEmailVerification} disabled={verificationSending}>
                  {verificationSending ? 'Sending...' : 'Send link'}
                </button>
              )}
            </div>
            {!account.has_password && <p className="rp-acct-hint">This account signs in with Google and has no password. To add one, sign out and use &quot;Forgot your password?&quot; on the sign-in page.</p>}
            {account.has_password && (
              <>
                <label>
                  Current Password
                  <input required type="password" value={password.current_password} onChange={event => setPassword({ ...password, current_password: event.target.value })} autoComplete="current-password" autoCapitalize="none" autoCorrect="off" spellCheck={false} />
                </label>
                <label>
                  New Password
                  <input required type="password" value={password.new_password} onChange={event => setPassword({ ...password, new_password: event.target.value })} autoComplete="new-password" autoCapitalize="none" autoCorrect="off" spellCheck={false} />
                  <small className="rp-acct-hint">Use a new password with at least 12 characters. Previous passwords cannot be reused.</small>
                </label>
                <button className="button"><KeyRound size={15} aria-hidden="true" />Update Password</button>
              </>
            )}
            <div className="rp-acct-signout">
              <button className="rp-acct-link" type="button" onClick={logout}><LogOut size={15} aria-hidden="true" />Sign Out</button>
            </div>
          </form>

          <section className="rp-acct-panel rp-acct-membership" id="account-membership" aria-labelledby="account-membership-title">
            <div className="rp-acct-panel-head rp-acct-panel-head-split">
              <span className="rp-acct-icon is-strong" aria-hidden="true"><Crown size={20} /></span>
              <div>
                <h2 id="account-membership-title">Membership Access</h2>
                <p>Your account is currently on the <strong>{account.tier}</strong> tier.</p>
              </div>
              <span className="rp-acct-count">{allowedCount} of {featureEntries.length} features unlocked</span>
            </div>
            {activeSubscription && (
              <div className="rp-acct-billing">
                <CreditCard size={18} aria-hidden="true" />
                <span>
                  <strong>{activeSubscription.plan_label}</strong>
                  <small>
                    {activeSubscription.status}
                    {activeSubscription.cancel_at_period_end ? ' - cancels at period end' : ''}
                    {activeSubscription.current_period_end ? ` - renews through ${new Date(activeSubscription.current_period_end).toLocaleDateString()}` : ''}
                  </small>
                </span>
              </div>
            )}
            <ul className="rp-acct-features">
              {featureEntries.map(([code, feature]) => (
                <li className={feature.allowed ? 'is-allowed' : 'is-locked'} key={code}>
                  <span className="rp-acct-feature-mark">{feature.allowed ? <Check size={15} aria-hidden="true" /> : <LockKeyhole size={14} aria-hidden="true" />}<span className="rh-visually-hidden">{feature.allowed ? "Included" : "Locked"}</span></span>
                  <span>
                    <strong>{feature.label}</strong>
                    <small>{feature.description}</small>
                  </span>
                </li>
              ))}
            </ul>
            {billingConfig?.configured ? (
              <div className="rp-acct-billing-actions">
                {account.tier !== 'premium' && availableBillingPlans.map(plan => (
                  <button className="button" type="button" key={plan.code} onClick={() => startCheckout(plan.code)} disabled={Boolean(billingBusy)}>
                    <Crown size={15} />
                    {billingBusy === plan.code ? 'Opening...' : `Upgrade ${plan.interval === 'year' ? 'Yearly' : 'Monthly'}`}
                  </button>
                ))}
                {activeSubscription?.provider === 'stripe' && (
                  <>
                    <button className="button button-outline" type="button" onClick={openBillingPortal} disabled={Boolean(billingBusy)}>
                      <ExternalLink size={15} />
                      {billingBusy === 'portal' ? 'Opening...' : 'Billing Portal'}
                    </button>
                    {activeSubscription.status !== 'canceled' && !activeSubscription.cancel_at_period_end && (
                      <button className="rp-acct-danger" type="button" onClick={cancelSubscription} disabled={Boolean(billingBusy)}>
                        <XCircle size={15} />
                        {billingBusy === 'cancel' ? 'Scheduling...' : 'Cancel at period end'}
                      </button>
                    )}
                  </>
                )}
              </div>
            ) : (
              <p className="rp-acct-note"><Sparkles size={16} aria-hidden="true" />Billing is prepared but Stripe test keys and Premium price IDs are not configured in this environment.</p>
            )}
          </section>

          <section className="rp-acct-panel rp-acct-notifications" id="account-notifications" aria-labelledby="account-notifications-title">
            <div className="rp-acct-panel-head rp-acct-panel-head-split">
              <span className="rp-acct-icon" aria-hidden="true"><Bell size={20} /></span>
              <div>
                <h2 id="account-notifications-title">Notifications</h2>
                <p>Updates about your account and new research opportunities.</p>
              </div>
              {unreadCount > 0 && <span className="rp-acct-count is-unread">{unreadCount} unread</span>}
            </div>
            {notifications.length === 0 ? (
              <p className="rp-acct-empty"><BellOff size={20} aria-hidden="true" />No account notifications yet.</p>
            ) : (
              <div className="rp-acct-notes">
                {notifications.map(item => (
                  <article className={`rp-acct-note-card ${item.is_read ? 'is-read' : 'is-unread'}`} key={item.id}>
                    <span className="rh-chip">{item.type}</span>
                    <strong>{item.title}</strong>
                    <p>{item.message}</p>
                    <div className="rp-acct-note-actions">
                      {item.action_url && <a href={item.action_url}>Open<ArrowUpRight size={14} aria-hidden="true" /></a>}
                      {!item.is_read && item.id && (
                        <button type="button" onClick={() => markNotificationRead(item.id)}><Check size={14} aria-hidden="true" />Mark read</button>
                      )}
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>

          <AccountPrivacyPanel
            account={account}
            onError={setError}
            onNotice={setNotice}
            onDeleted={() => { setAccount(null); navigate('/', { replace: true }); }}
          />
        </div>
      </div>
      {emailChangeOpen && (
        <EmailChangeDialog
          onClose={() => setEmailChangeOpen(false)}
          onSent={message => { setEmailChangeOpen(false); setNotice(message); }}
        />
      )}
    </section>
  );
}
