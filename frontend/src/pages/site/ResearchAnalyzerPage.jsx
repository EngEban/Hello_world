import React from 'react';
import ToolGuide from '../../components/public/ToolGuide';
import { Link } from 'react-router-dom';
import { LayoutDashboard, Lock, ShieldCheck, Sparkles } from 'lucide-react';
import AnalyzerStudio from '../../features/researchAnalyzer/studio/AnalyzerStudio.jsx';
import { SEO } from '../../config/contentStructure';
import { useAccount } from '../../contexts/AccountContext';
import useToolUsage from '../../hooks/useToolUsage';
import { usePageMeta } from '../../utils/seo';
import '../../styles/tools/tool-studio.css';
import '../../styles/tools/research-analyzer-studio.css';

// Compact tool header shown while access is checked or when the analyzer is gated,
// so the page keeps one h1 and the same workspace framing as the open analyzer.
function AnalyzerGateHeader({ state }) {
  const label = state === 'loading' ? 'Checking access' : state === 'signed-out' ? 'Account required' : 'Premium workspace';
  return (
    <header className="rp-studio-header rp-ra-header">
      <div className="rp-studio-header-main">
        <span className="rp-studio-badge" aria-hidden="true"><LayoutDashboard size={28} /></span>
        <div className="rp-studio-heading">
                    <h1>ResRef Analyzer</h1>
          <p>Statistical Analysis Platform for Researchers</p>
        </div>
      </div>
      <div className="rp-studio-header-side">
        <div className="rp-studio-sync" data-state={state === 'loading' ? 'loading' : 'guest'}>
          <span className="rp-studio-sync-icon">{state === 'signed-out' ? <Lock size={19} /> : <ShieldCheck size={19} />}</span>
          <span className="rp-studio-sync-state">{label}</span>
          <strong>Secure research workspace</strong>
        </div>
      </div>
    </header>
  );
}

function AnalyzerAccessGate({ type }) {
  const signedOut = type === 'signed-out';
  return (
    <div className="rp-ra-gate" role="status">
      <div className="rp-ra-gate-icon">
        {signedOut ? <Lock size={28} /> : <Sparkles size={28} />}
      </div>
      <div className="rp-ra-gate-copy">
        <p className="rh-label">{signedOut ? 'Account required' : 'Premium workspace'}</p>
        <h2>{signedOut ? 'Sign in to open the ResRef Analyzer' : 'Upgrade to use the full analyzer workflow'}</h2>
        <p>
          {signedOut
            ? 'Guest access to the analyzer is switched off right now. Sign in with a free ResRef account to continue.'
            : 'This tool can be controlled from the dashboard as a premium feature, including usage limits and subscriptions.'}
        </p>
        <div className="rp-ra-gate-actions">
          <Link className="rh-button rh-button-primary" to="/sign-in">{signedOut ? 'Sign in' : 'Manage account'}</Link>
          <Link className="rh-button rh-button-outline" to="/contact">Contact ResRef</Link>
        </div>
      </div>
      <div className="rp-ra-gate-note">
        <ShieldCheck size={18} />
        Backend entitlement checks protect upload, analysis, and report endpoints.
      </div>
    </div>
  );
}

export default function ResearchAnalyzerPage() {
  usePageMeta(SEO.researchAnalyzer);
  const { account, loading } = useAccount();
  // The server decides access (visitors count as Free); the account's feature
  // list is only a fallback while the usage answer is loading.
  const { usage, loaded: usageLoaded, summary: usageLine } = useToolUsage('research_analyzer', account?.email || '');
  const access = usage?.access;
  const checking = loading || (!usageLoaded && !account);
  const canUseAnalyzer = access ? access.allowed : Boolean(account?.features?.research_analyzer?.allowed);
  const gate = canUseAnalyzer ? null : (access?.code === 'auth_required' || !account ? 'signed-out' : 'premium');

  return (
    <section className="rp-studio-page rp-ra-page">
      <div className="rp-studio-wrap">
        {checking && (
          <>
            <AnalyzerGateHeader state="loading" />
            <div className="rp-ra-gate rp-ra-gate-loading" role="status">
              <div className="rp-ra-gate-icon"><ShieldCheck size={28} /></div>
              <div className="rp-ra-gate-copy">
                <p className="rh-label">Checking access</p>
                <h2>Preparing your analyzer workspace</h2>
                <p>We are confirming your account and feature permissions.</p>
              </div>
            </div>
          </>
        )}
        {!checking && gate && (
          <>
            <AnalyzerGateHeader state={gate} />
            <AnalyzerAccessGate type={gate} />
          </>
        )}
        {!checking && canUseAnalyzer && !account && (
          <p className="rp-ra-usage" role="status">You are using the analyzer as a guest. Your file is kept privately while you work and deleted afterwards; <Link to="/sign-in?next=%2Ftools%2Fresearch-analyzer">sign in</Link> to keep your work linked to your account.</p>
        )}
        {!checking && canUseAnalyzer && usageLine && <p className="rp-ra-usage" role="status">{usageLine}</p>}
        {!checking && canUseAnalyzer && <AnalyzerStudio />}
      </div>
      <ToolGuide path="/tools/research-analyzer" />
    </section>
  );
}
