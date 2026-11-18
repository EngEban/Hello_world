import { Check, KeyRound, Lock, Minus, Plus, RotateCcw, Save, Search, ShieldCheck, Trash2, UserMinus, UserPlus, Users } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Link, useOutletContext, useSearchParams } from 'react-router-dom';
import { DashboardApi } from '../../../api/dashboardApi';
import AdminNotice from '../../../components/dashboard/AdminNotice';
import AdminPageHeader from '../../../components/dashboard/AdminPageHeader';
import { StateBlock } from '../../../components/dashboard/DashboardPrimitives';
import '../../../styles/dashboard/dash-admin.css';
import { hasPermission, initials } from './adminShared';

const BASE_PERMISSION = 'dashboard.view';
const blankRole = { id: null, code: '', label: '', description: '', is_active: true, permissions: [BASE_PERMISSION], members: [], member_count: 0, builtin: false, locked: false, full_access: false, is_current: false };
const sameSet = (a, b) => a.length === b.length && a.every(item => b.includes(item));

/** Adds or removes one permission, keeping "view" in step with the module's other actions. */
function togglePermission(current, module, action, on) {
  const code = `${module.id}.${action}`;
  let next = current.filter(item => item !== code);
  if (on) {
    next.push(code);
    if (action !== 'view') next.push(`${module.id}.view`);
  } else if (action === 'view') {
    // Without View the section is hidden, so its other actions go too.
    next = next.filter(item => !item.startsWith(`${module.id}.`));
  }
  return [...new Set(next)];
}

export default function DashboardRolesPage() {
  const { user, bootstrap } = useOutletContext() || {};
  const [searchParams, setSearchParams] = useSearchParams();
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [draft, setDraft] = useState(null);
  const [saving, setSaving] = useState(false);
  const [userQuery, setUserQuery] = useState('');
  const [userResults, setUserResults] = useState([]);
  const canSearchUsers = hasPermission(user, bootstrap, 'users.view');

  const load = (selectCode) => DashboardApi.getRolesPermissions()
    .then(payload => {
      setData(payload);
      const wanted = selectCode ?? searchParams.get('role');
      const role = payload.roles.find(item => item.code === wanted) || payload.roles.find(item => !item.locked) || payload.roles[0];
      if (role) setDraft({ ...role });
    })
    .catch(err => setError(err.message));

  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const original = useMemo(() => (draft?.id ? data?.roles.find(role => role.id === draft.id) : blankRole), [data, draft?.id]);
  const dirty = Boolean(draft && original && (
    draft.label !== original.label || draft.description !== original.description
    || draft.is_active !== original.is_active || !sameSet(draft.permissions, original.permissions)
  ));
  const ownPermissions = useMemo(() => new Set(data?.current_permissions || []), [data]);
  const fullAccessEditor = Boolean(data?.is_superuser || (data && data.modules.every(module => module.permissions.every(code => ownPermissions.has(code)))));
  const isNew = Boolean(draft && !draft.id);
  const canSave = isNew ? data?.can.create : data?.can.edit;
  // You hold this role yourself: the server refuses access changes, so the matrix is read-only.
  const ownRole = Boolean(draft?.is_current && !data?.is_superuser);
  const accessLocked = Boolean(!canSave || draft?.locked || ownRole);
  const groups = useMemo(() => {
    const result = [];
    (data?.modules || []).forEach(module => {
      const group = result.find(item => item.label === module.group);
      if (group) group.modules.push(module); else result.push({ label: module.group, modules: [module] });
    });
    return result;
  }, [data]);
  const visibleSections = (data?.modules || []).filter(module => draft?.full_access || draft?.permissions.includes(`${module.id}.view`));

  const selectRole = role => {
    if (dirty && !window.confirm('Discard the unsaved changes to this role?')) return;
    setDraft({ ...role });
    setNotice('');
    setError('');
    setUserQuery('');
    setUserResults([]);
    setSearchParams(role.code ? { role: role.code } : {}, { replace: true });
  };

  const setPermission = (module, action, on) => setDraft(current => ({ ...current, permissions: togglePermission(current.permissions, module, action, on) }));
  const setModule = (module, on) => setDraft(current => {
    let permissions = current.permissions.filter(code => !code.startsWith(`${module.id}.`));
    if (on) permissions = permissions.concat(module.permissions.filter(code => fullAccessEditor || ownPermissions.has(code) || current.permissions.includes(code)));
    return { ...current, permissions: module.id === 'dashboard' ? [...new Set([...permissions, BASE_PERMISSION])] : permissions };
  });

  const save = async event => {
    event?.preventDefault();
    setSaving(true);
    setError('');
    setNotice('');
    try {
      const payload = { label: draft.label, description: draft.description, is_active: draft.is_active };
      if (!draft.locked) payload.permissions = draft.permissions;
      const result = await DashboardApi.saveRole(payload, draft.id);
      setNotice(`${result.role.label} saved. People with this role see the change on their next page load.`);
      await load(result.role.code);
      setSearchParams({ role: result.role.code }, { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    if (!window.confirm(`Delete the role “${draft.label}”? This cannot be undone.`)) return;
    try {
      await DashboardApi.deleteRole(draft.id);
      setNotice(`${draft.label} deleted.`);
      setSearchParams({}, { replace: true });
      setDraft(null);
      await load('');
    } catch (err) {
      setError(err.message);
    }
  };

  const changeMember = async (person, action) => {
    setError('');
    setNotice('');
    try {
      const result = await DashboardApi.changeRoleMember(draft.id, { user_id: person.id, action });
      setNotice(action === 'add' ? `${person.name || person.email} now has the ${draft.label} role.` : `${person.name || person.email} was removed from ${draft.label}.`);
      setData(current => ({ ...current, roles: current.roles.map(role => (role.id === result.role.id ? result.role : role)) }));
      setDraft(current => ({ ...current, members: result.role.members, member_count: result.role.member_count }));
      setUserResults(results => results.filter(item => item.id !== person.id));
    } catch (err) {
      setError(err.message);
    }
  };

  useEffect(() => {
    const term = userQuery.trim();
    if (!canSearchUsers || term.length < 2) { setUserResults([]); return undefined; }
    let active = true;
    const timer = setTimeout(() => {
      DashboardApi.getUsers({ q: term, per_page: 6 })
        .then(payload => { if (active) setUserResults(payload.results || []); })
        .catch(() => { if (active) setUserResults([]); });
    }, 250);
    return () => { active = false; clearTimeout(timer); };
  }, [userQuery, canSearchUsers]);

  if (!data) {
    return <div className="dash-adm-page">{error ? <AdminNotice type="error">{error}</AdminNotice> : <StateBlock type="loading" title="Loading roles" text="Reading roles and permissions…" />}</div>;
  }

  const memberIds = new Set((draft?.members || []).map(member => member.id));

  return (
    <div className="dash-adm-page dash-roles-page">
      <AdminPageHeader
        eyebrow="System"
        title="Roles & Permissions"
        text="Choose a role, then decide which dashboard sections it sees and what it may do in each. Changes apply without code changes, and the server checks every request."
        actions={data.can.create && <button type="button" className="admin-button" onClick={() => selectRole(blankRole)}><Plus size={15} /> New role</button>}
      />
      {notice && <AdminNotice type="success">{notice}</AdminNotice>}
      {error && <AdminNotice type="error">{error}</AdminNotice>}

      <div className="dash-roles-layout">
        <nav className="dashboard-card dash-roles-list" aria-label="Roles">
          <h2>Roles</h2>
          <ul>
            {data.roles.map(role => (
              <li key={role.id}>
                <button type="button" className={draft?.id === role.id ? 'is-selected' : ''} aria-current={draft?.id === role.id ? 'true' : undefined} onClick={() => selectRole(role)}>
                  <span className="dash-roles-list-name">
                    <strong>{role.label}</strong>
                    <small>{role.full_access ? 'Full access' : `${role.permissions.length} permissions`} · {role.member_count} {role.member_count === 1 ? 'person' : 'people'}</small>
                  </span>
                  <span className="dash-roles-list-flags">
                    {role.is_current && <span className="dash-adm-pill is-info">You</span>}
                    {role.locked && <Lock size={13} aria-label="Locked" />}
                    {!role.is_active && <span className="dash-adm-pill is-off">Off</span>}
                  </span>
                </button>
              </li>
            ))}
            {isNew && <li><button type="button" className="is-selected" aria-current="true"><span className="dash-roles-list-name"><strong>{draft.label || 'New role'}</strong><small>Not saved yet</small></span></button></li>}
          </ul>
          <p className="dash-adm-hint">Superusers always keep full access, whatever their role.</p>
        </nav>

        {draft ? (
          <form className="dash-roles-detail" onSubmit={save}>
            <section className="dashboard-card dash-adm-card dash-roles-identity">
              <div className="dash-roles-identity-head">
                <span className="dash-roles-badge" aria-hidden="true"><KeyRound size={18} /></span>
                <div>
                  <h2>{isNew ? 'New role' : draft.label}</h2>
                  <p className="dash-adm-muted">{isNew ? 'Name the role and pick its permissions.' : <>Code <code>{draft.code}</code>{draft.builtin ? ' · built-in role' : ' · custom role'}</>}</p>
                </div>
                <label className="dash-roles-active">
                  <input type="checkbox" checked={draft.is_active} disabled={accessLocked} onChange={event => setDraft(current => ({ ...current, is_active: event.target.checked }))} />
                  <span>{draft.is_active ? 'Active' : 'Inactive: people with this role cannot open the dashboard'}</span>
                </label>
                {data.can.delete && !draft.builtin && !isNew && !ownRole && <button type="button" className="dash-adm-link dash-roles-delete" onClick={remove}><Trash2 size={14} /> Delete role</button>}
              </div>
              <div className="dash-roles-fields">
                <label>Name<input required maxLength={120} value={draft.label} disabled={!canSave || draft.locked} onChange={event => setDraft(current => ({ ...current, label: event.target.value }))} /></label>
                <label>Description<textarea rows={2} maxLength={1000} value={draft.description} disabled={!canSave} onChange={event => setDraft(current => ({ ...current, description: event.target.value }))} placeholder="What this role is for" /></label>
              </div>
              {draft.locked && <AdminNotice type="info"><Lock size={14} /> {draft.label} always has every permission, so nobody can be locked out of the dashboard. It cannot be edited or deleted.</AdminNotice>}
              {ownRole && !draft.locked && <AdminNotice type="info"><ShieldCheck size={14} /> This is your own role. To protect you from locking yourself out, another administrator has to change its access.</AdminNotice>}
              {!canSave && !draft.locked && <AdminNotice type="info">Your role can view roles but not change them.</AdminNotice>}
            </section>

            <section className="dashboard-card dash-adm-card">
              <div className="dash-adm-section-head">
                <div><h2>Sections and actions</h2><p>View shows the section in the sidebar. The other actions unlock its buttons and API calls.</p></div>
              </div>
              <div className="dash-roles-matrix-wrap">
                <table className="dash-roles-matrix">
                  <thead>
                    <tr><th scope="col">Section</th>{data.actions.map(action => <th scope="col" key={action.id}>{action.label}</th>)}<th scope="col"><span className="sr-only">Whole section</span></th></tr>
                  </thead>
                  {groups.map(group => (
                    <tbody key={group.label}>
                      <tr className="dash-roles-group"><th colSpan={data.actions.length + 2} scope="colgroup">{group.label}</th></tr>
                      {group.modules.map(module => {
                        const held = module.permissions.filter(code => draft.full_access || draft.permissions.includes(code));
                        const isBase = module.id === 'dashboard';
                        return (
                          <tr key={module.id} className={held.length ? 'is-on' : ''}>
                            <th scope="row">
                              <strong>{module.label}</strong>
                              <small>{module.description}</small>
                            </th>
                            {data.actions.map(action => {
                              const help = module.actions[action.id];
                              if (!help) return <td key={action.id} className="dash-roles-na"><Minus size={13} aria-label="Not applicable" /></td>;
                              const code = `${module.id}.${action.id}`;
                              const checked = draft.full_access || draft.permissions.includes(code);
                              const beyondOwn = !fullAccessEditor && !ownPermissions.has(code) && !checked;
                              const disabled = accessLocked || (isBase && action.id === 'view') || beyondOwn;
                              return (
                                <td key={action.id}>
                                  <label className="dash-roles-cell" title={beyondOwn ? `${help} (your own role does not have this, so you cannot grant it)` : help}>
                                    <input type="checkbox" checked={checked} disabled={disabled} onChange={event => setPermission(module, action.id, event.target.checked)} aria-label={`${module.label}: ${help}`} />
                                  </label>
                                </td>
                              );
                            })}
                            <td className="dash-roles-row-toggle">
                              {!accessLocked && !isBase && <button type="button" className="dash-adm-link" onClick={() => setModule(module, held.length < module.permissions.length)}>{held.length < module.permissions.length ? 'All' : 'None'}</button>}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  ))}
                </table>
              </div>
            </section>

            <div className="dash-roles-columns">
              <section className="dashboard-card dash-adm-card">
                <h2 className="dash-roles-subhead">Sidebar for this role</h2>
                <p className="dash-adm-hint">Sections a person with this role sees. Everything else is hidden and refused by the server.</p>
                <ul className="dash-roles-chips">
                  {visibleSections.map(module => <li key={module.id}><Check size={12} /> {module.label}</li>)}
                </ul>
              </section>

              {!isNew && (
                <section className="dashboard-card dash-adm-card">
                  <h2 className="dash-roles-subhead"><Users size={16} /> People with this role <span className="dash-adm-pill">{draft.member_count}</span></h2>
                  {draft.members?.length ? (
                    <ul className="dash-roles-people">
                      {draft.members.map(person => (
                        <li key={person.id}>
                          <span className="dash-roles-avatar" aria-hidden="true">{initials(person.name || person.email)}</span>
                          <span><strong>{person.name}</strong><small>{person.email}{!person.is_active && ' · inactive'}</small></span>
                          {data.can.manage && person.id !== user?.id && <button type="button" className="dash-adm-link" onClick={() => changeMember(person, 'remove')} title="Return them to their plan role"><UserMinus size={14} /> Remove</button>}
                        </li>
                      ))}
                    </ul>
                  ) : <p className="dash-adm-hint">Nobody has this role yet.</p>}
                  {draft.member_count > (draft.members?.length || 0) && <p className="dash-adm-hint">Showing {draft.members.length} of {draft.member_count}. <Link to={`/dashboard/users?role=${draft.code}`}>See everyone</Link></p>}
                  {data.can.manage && canSearchUsers && draft.is_active && (
                    <div className="dash-roles-add">
                      <label className="dash-roles-search"><Search size={15} aria-hidden="true" /><input value={userQuery} onChange={event => setUserQuery(event.target.value)} placeholder="Add someone: search by name or email" aria-label="Search people to add to this role" /></label>
                      {userResults.length > 0 && (
                        <ul className="dash-roles-people">
                          {userResults.filter(person => !memberIds.has(person.id)).map(person => (
                            <li key={person.id}>
                              <span className="dash-roles-avatar" aria-hidden="true">{initials(person.display_name || person.email)}</span>
                              <span><strong>{person.display_name}</strong><small>{person.email} · now {person.is_superuser ? 'superuser' : person.role}</small></span>
                              {person.id === user?.id || person.is_superuser
                                ? <small className="dash-adm-muted">{person.id === user?.id ? 'Your own account' : 'Superuser'}</small>
                                : <button type="button" className="dash-adm-link" onClick={() => changeMember({ id: person.id, name: person.display_name, email: person.email }, 'add')}><UserPlus size={14} /> Add</button>}
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )}
                </section>
              )}
            </div>

            {canSave && (dirty || isNew) && (
              <div className="dash-adm-savebar is-dirty dash-roles-savebar">
                <span className="dash-adm-savebar-status"><span><i />{isNew ? 'New role, not saved yet' : 'Unsaved changes to this role'}</span></span>
                <span className="dash-adm-savebar-actions">
                  <button type="button" className="admin-button admin-button-secondary" onClick={() => (isNew ? selectRole(data.roles[0]) : setDraft({ ...original }))}><RotateCcw size={15} /> {isNew ? 'Cancel' : 'Discard'}</button>
                  <button className="admin-button" disabled={saving || !dirty || !draft.label.trim()}><Save size={15} /> {saving ? 'Saving…' : isNew ? 'Create role' : 'Save role'}</button>
                </span>
              </div>
            )}
          </form>
        ) : <StateBlock type="empty" title="Choose a role" text="Pick a role on the left to see what it can do." />}
      </div>
    </div>
  );
}
