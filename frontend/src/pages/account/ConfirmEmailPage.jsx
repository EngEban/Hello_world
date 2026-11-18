import { CircleAlert, MailCheck, ShieldCheck } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { AccountApi } from '../../api/accountApi';
import LoadingState from '../../components/common/LoadingState';
import { useAccount } from '../../contexts/AccountContext';
import '../../styles/pages/account.css';
import { usePageMeta } from '../../utils/seo';

// Target of the link in the sign-up email: confirms the address and signs in.
const META = { title: 'Confirm email | ResRef', description: 'Confirm the email address for your ResRef account.' };

export default function ConfirmEmailPage() {
  usePageMeta(META);
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';
  const navigate = useNavigate();
  const { setAccount } = useAccount();
  const [state, setState] = useState({ status: token ? 'working' : 'error', message: token ? '' : 'This confirmation link is incomplete.' });
  const sent = useRef(false);

  useEffect(() => {
    if (!token || sent.current) return;
    sent.current = true; // tokens are single-use: never post twice (StrictMode)
    AccountApi.confirmRegistration(token)
      .then(data => {
        setAccount(data.account);
        setState({ status: 'done', message: 'Your email is confirmed and you are signed in.' });
        window.setTimeout(() => navigate('/account', { replace: true }), 1200);
      })
      .catch(error => setState({ status: 'error', message: error.message }));
  }, [token, navigate, setAccount]);

  const isError = state.status === 'error';
  return <section className="rp-auth rp-auth-single">
    <div className="rh-container rp-auth-narrow">
      <div className={`rp-auth-card account-confirm-card${isError ? ' is-error' : ''}`} role="status">
        <span className="rp-auth-card-icon" aria-hidden="true">{isError ? <CircleAlert size={24} /> : <MailCheck size={24} />}</span>
        <span className="rh-label">Email confirmation</span>
        <h1 className="rh-visually-hidden">Confirm your ResRef email</h1>
        <h2>{isError ? 'Link not valid' : 'Confirming your email'}</h2>
        {state.status === 'working' ? <div className="rp-auth-loading"><LoadingState /></div> : <p className={isError ? 'account-error' : 'account-success'}>{state.message}</p>}
        {isError && <p className="rp-auth-switch"><Link to="/sign-in">Go to sign in</Link> to request a new link.</p>}
        <p className="rp-auth-footnote"><ShieldCheck size={16} aria-hidden="true" />Confirmation links are single-use and valid for 48 hours.</p>
      </div>
    </div>
  </section>;
}
