import { useEffect, useRef, useState } from 'react';
import { AccountApi } from '../../api/accountApi';

let googleScriptPromise;
function loadGoogleScript() {
  if (window.google?.accounts?.id) return Promise.resolve();
  if (!googleScriptPromise) {
    googleScriptPromise = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = 'https://accounts.google.com/gsi/client';
      script.async = true; script.defer = true;
      script.onload = resolve; script.onerror = reject;
      document.head.appendChild(script);
    });
  }
  return googleScriptPromise;
}

export default function GoogleSignInButton({ onSuccess, onError }) {
  const container = useRef(null);
  const [enabled, setEnabled] = useState(false);
  // Parents pass new callback functions on every render; keep the latest in a
  // ref so the config request and Google button set-up run only once.
  const callbacks = useRef({ onSuccess, onError });
  useEffect(() => { callbacks.current = { onSuccess, onError }; }, [onSuccess, onError]);
  useEffect(() => {
    let active = true;
    AccountApi.getConfig().then(async config => {
      if (!active || !config.google_enabled) return;
      setEnabled(true);
      await loadGoogleScript();
      if (!active || !container.current) return;
      window.google.accounts.id.initialize({
        client_id: config.google_client_id,
        callback: async response => {
          try { callbacks.current.onSuccess((await AccountApi.googleLogin(response.credential)).account); }
          catch (error) { callbacks.current.onError(error.message); }
        },
      });
      window.google.accounts.id.renderButton(container.current, { theme: 'outline', size: 'large', text: 'continue_with', width: Math.max(220, Math.min(400, Math.floor(container.current.offsetWidth || 340))) });
    }).catch(() => {});
    return () => { active = false; };
  }, []);
  if (!enabled) return null;
  return <><div className="rp-auth-divider"><span>or</span></div><div className="rp-auth-google google-signin" ref={container} /></>;
}
