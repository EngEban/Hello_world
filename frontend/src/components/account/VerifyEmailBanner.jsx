import { useState } from 'react';
import { MailWarning, X } from 'lucide-react';
import { AccountApi } from '../../api/accountApi';
import { useAccount } from '../../contexts/AccountContext';
import '../../styles/pages/verify-email-banner.css';

const formatDate = value => new Date(value).toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short' });

/** Reminder for signed-in members who have not confirmed their email yet. */
export default function VerifyEmailBanner() {
  const { account } = useAccount();
  const [state, setState] = useState({ status: 'idle', message: '' });
  const [hidden, setHidden] = useState(false);
  if (!account || account.email_verified || hidden) return null;

  const resend = async () => {
    setState({ status: 'sending', message: '' });
    try {
      await AccountApi.requestEmailVerification();
      setState({ status: 'sent', message: `New link sent to ${account.email}. It can take a minute to arrive; check spam too.` });
    } catch (error) {
      setState({ status: 'error', message: error.message || 'Could not send the link. Please try again in a moment.' });
    }
  };

  return (
    <div className="rr-verify-banner" role="status">
      <div className="rh-container rr-verify-banner-inner">
        <MailWarning size={18} aria-hidden="true" />
        <p>
          <strong>Please confirm your email.</strong>{' '}
          {state.message || (account.email_verify_by
            ? `We sent a link to ${account.email}. Confirm it by ${formatDate(account.email_verify_by)} to keep access.`
            : `We sent a link to ${account.email}.`)}
        </p>
        {state.status !== 'sent' && (
          <button type="button" onClick={resend} disabled={state.status === 'sending'}>
            {state.status === 'sending' ? 'Sending…' : 'Resend link'}
          </button>
        )}
        <button type="button" className="rr-verify-banner-close" onClick={() => setHidden(true)} aria-label="Hide reminder"><X size={16} /></button>
      </div>
    </div>
  );
}
