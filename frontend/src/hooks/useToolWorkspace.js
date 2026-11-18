import { useEffect, useRef, useState } from 'react';
import { AccountApi } from '../api/accountApi';

/**
 * Keeps a tool's workspace in localStorage and, for signed-in users, in the
 * account (GET once after sign-in, then debounced autosave).
 *
 * The page owns `workspace` state; the hook only syncs it. Options keep the
 * small behavioural differences between tools:
 * - `adoptEmptyRemote`: also take the server copy when the local workspace is
 *   empty (reference generator, sample size calculator).
 * - `markSyncingImmediately`: show "syncing" as soon as something changes
 *   instead of when the debounced save starts.
 * - `serialize`: shrink the normalized workspace before it is sent to the
 *   account (the server copy is passed through `normalize` again on load).
 */
export default function useToolWorkspace({
  toolKey,
  account,
  accountLoading,
  workspace,
  setWorkspace,
  normalize,
  hasContent,
  persistLocal,
  onRemoteLoaded,
  adoptEmptyRemote = false,
  markSyncingImmediately = false,
  serialize = null,
  debounceMs = 850,
}) {
  const [cloudReady, setCloudReady] = useState(false);
  const [syncStatus, setSyncStatus] = useState('local');
  const [syncError, setSyncError] = useState('');
  const [lastSynced, setLastSynced] = useState(null);
  const workspaceRef = useRef(workspace);
  const accountId = account?.id || null;
  // Callbacks change identity every render; keep the latest without
  // re-running the sign-in effect.
  const latest = useRef({ normalize, hasContent, onRemoteLoaded, setWorkspace, adoptEmptyRemote, serialize });
  latest.current = { normalize, hasContent, onRemoteLoaded, setWorkspace, adoptEmptyRemote, serialize };
  const toPayload = value => {
    const normalized = latest.current.normalize(value);
    return latest.current.serialize ? latest.current.serialize(normalized) : normalized;
  };

  useEffect(() => {
    workspaceRef.current = workspace;
    persistLocal(workspace);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspace]);

  useEffect(() => {
    if (accountLoading) return undefined;
    if (!accountId) {
      setCloudReady(false);
      setSyncStatus('local');
      setSyncError('');
      setLastSynced(null);
      return undefined;
    }

    let cancelled = false;
    setCloudReady(false);
    setSyncStatus('loading');
    setSyncError('');

    AccountApi.getToolWorkspace(toolKey)
      .then(async response => {
        if (cancelled) return;
        const { normalize: norm, hasContent: has, onRemoteLoaded: loaded, setWorkspace: set, adoptEmptyRemote: adoptEmpty } = latest.current;
        const localWorkspace = norm(workspaceRef.current);
        const remoteWorkspace = norm(response.data);
        const hasRemote = Boolean(response.updated_at);
        const adopt = remote => { set(remote); if (loaded) loaded(remote); };
        if (hasRemote && (has(remoteWorkspace) || (adoptEmpty && !has(localWorkspace)))) {
          adopt(remoteWorkspace);
        } else if (!hasRemote && has(localWorkspace)) {
          await AccountApi.saveToolWorkspace(toolKey, toPayload(localWorkspace));
        } else if (adoptEmpty && !has(localWorkspace)) {
          adopt(remoteWorkspace);
        }
        if (cancelled) return;
        setCloudReady(true);
        setSyncStatus('synced');
        setLastSynced(response.updated_at ? new Date(response.updated_at) : new Date());
      })
      .catch(error => {
        if (cancelled) return;
        setCloudReady(false);
        setSyncStatus('error');
        setSyncError(error.message);
      });

    return () => { cancelled = true; };
  }, [accountId, accountLoading, toolKey]);

  useEffect(() => {
    if (!accountId || !cloudReady) return undefined;
    const eagerPayload = markSyncingImmediately ? toPayload(workspace) : null;
    if (markSyncingImmediately) {
      setSyncStatus('syncing');
      setSyncError('');
    }
    const timeout = window.setTimeout(async () => {
      try {
        if (!markSyncingImmediately) setSyncStatus('syncing');
        const payload = eagerPayload || toPayload(workspaceRef.current);
        const response = await AccountApi.saveToolWorkspace(toolKey, payload);
        setSyncStatus('synced');
        setLastSynced(response.updated_at ? new Date(response.updated_at) : new Date());
      } catch (error) {
        setSyncStatus('error');
        setSyncError(error.message);
      }
    }, debounceMs);
    return () => window.clearTimeout(timeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspace, accountId, cloudReady]);

  return { cloudReady, syncStatus, syncError, lastSynced };
}
