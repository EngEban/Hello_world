import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { PublicWebsiteApi } from '../api/publicWebsiteApi';
import { DEFAULT_SITE_SETTINGS } from '../config/editableSettings';
import { optimizedImageData } from '../utils/optimizedImages';

const SiteSettingsContext = createContext(DEFAULT_SITE_SETTINGS);

export function SiteSettingsProvider({ children }) {
  const [remoteSettings, setRemoteSettings] = useState({});
  useEffect(() => {
    let active = true;
    PublicWebsiteApi.getSiteSettings().then(data => {
      if (active) setRemoteSettings(data.settings || {});
    }).catch(() => {});
    return () => { active = false; };
  }, []);
  const value = useMemo(() => optimizedImageData({ ...DEFAULT_SITE_SETTINGS, ...remoteSettings }), [remoteSettings]);
  return <SiteSettingsContext.Provider value={value}>{children}</SiteSettingsContext.Provider>;
}

export const useSiteSettings = () => useContext(SiteSettingsContext);
