import { useCallback, useEffect, useState } from 'react';
import { UsageApi, usageSummary } from '../api/usageApi';

// Reads the server's allowance for one feature so a tool can show
// "x of 10 used today". Display only: limits are enforced by the API.
export default function useToolUsage(feature, accountKey = '') {
  const [usage, setUsage] = useState(null);
  const [loaded, setLoaded] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const data = await UsageApi.getFeature(feature);
      setUsage(data.usage || null);
    } catch {
      // Usage display is optional; never block a tool because it failed.
    } finally {
      setLoaded(true);
    }
  }, [feature]);

  useEffect(() => { refresh(); }, [refresh, accountKey]);

  return { usage, setUsage, refresh, loaded, summary: usageSummary(usage) };
}
