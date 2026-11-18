import { createContext, useContext, useEffect, useState } from 'react';
import { AccountApi } from '../api/accountApi';
import { UNAUTHORIZED_EVENT } from '../api/apiClient';

const AccountContext = createContext(null);

export function AccountProvider({ children }) {
  const [account, setAccount] = useState(null);
  const [loading, setLoading] = useState(true);
  const refresh = async () => {
    try { setAccount((await AccountApi.getMe()).account); }
    catch { setAccount(null); }
    finally { setLoading(false); }
  };
  useEffect(() => { refresh(); }, []);
  // Session expired somewhere in the public site: forget the account so
  // RequireAccount sends the user to /sign-in?next=<current page>.
  useEffect(() => {
    const onUnauthorized = event => { if (event.detail?.area === 'account') setAccount(null); };
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
  }, []);
  const logout = async () => { await AccountApi.logout(); setAccount(null); };
  return <AccountContext.Provider value={{ account, loading, refresh, logout, setAccount }}>{children}</AccountContext.Provider>;
}

export function useAccount() {
  return useContext(AccountContext);
}
