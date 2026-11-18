import { useEffect, useState } from 'react';
import { PublicWebsiteApi } from '../../api/publicWebsiteApi';

function usePreview(load) {
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState({ status: 'loading', data: null });
  useEffect(() => {
    let active = true;
    setState({ status: 'loading', data: null });
    load().then(data => { if (active) setState({ status: 'ready', data }); })
      .catch(() => { if (active) setState({ status: 'error', data: null }); });
    return () => { active = false; };
  }, [load, attempt]);
  return [state, () => setAttempt(value => value + 1)];
}
const loadLibrary = () => PublicWebsiteApi.getHomeContent();
const loadOpportunities = () => PublicWebsiteApi.getOpportunities({ per_page: 3, current: 'true' });
export function useHomeResources() {
  const [library, reloadLibrary] = usePreview(loadLibrary);
  const [opportunities, reloadOpportunities] = usePreview(loadOpportunities);
  return { library, opportunities, reloadLibrary, reloadOpportunities };
}
