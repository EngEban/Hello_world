import { FilePlus2, Plus } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useOutletContext, useSearchParams } from 'react-router-dom';
import { DashboardApi } from '../../../api/dashboardApi';
import AdminNotice from '../../../components/dashboard/AdminNotice';
import AdminPageHeader from '../../../components/dashboard/AdminPageHeader';
import { StateBlock } from '../../../components/dashboard/DashboardPrimitives';
import '../../../styles/dashboard/dash-articles.css';
import ArticleEditor from './ArticleEditor';
import ArticleLibrary from './ArticleLibrary';
import { createEmptyPost, normalizePost } from './editorModel';
import { permissionsAllow } from '../users/adminShared';
import { articleFilters, LIST_KEYS } from './workspace';

export default function DashboardPostsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { user, bootstrap } = useOutletContext();
  const can = permission => permissionsAllow(bootstrap?.permissions, permission, user?.is_superuser);
  const canCreate = can('content.create');
  const canEdit = can('content.edit');
  const canDelete = can('content.delete');
  const canUploadMedia = can('media.create');
  const [posts, setPosts] = useState([]);
  const [pagination, setPagination] = useState(null);
  const [summary, setSummary] = useState(null);
  const [attention, setAttention] = useState(null);
  const [categories, setCategories] = useState([]);
  const [tags, setTags] = useState([]);
  const [authors, setAuthors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editorPost, setEditorPost] = useState(null);
  const [editorKey, setEditorKey] = useState(0);
  const [opening, setOpening] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const requestSequence = useRef(0);
  // Only list-related URL parameters trigger a list reload; ?edit= and ?new= drive the editor.
  const listKey = LIST_KEYS.map(key => `${key}=${searchParams.get(key) || ''}`).join('&');
  const filters = useMemo(() => articleFilters(new URLSearchParams(listKey)), [listKey]);
  const editParam = searchParams.get('edit');
  const newParam = searchParams.get('new');

  const load = async (nextFilters = filters) => {
    const sequence = ++requestSequence.current;
    setLoading(true);
    try {
      const postData = await DashboardApi.getPosts({ ...nextFilters, summary_only: 'true' });
      if (sequence !== requestSequence.current) return;
      setPosts(postData.results || []);
      setPagination(postData.pagination);
      setSummary(postData.summary || null);
      setAttention(postData.attention ? { ...postData.attention, pending: postData.optimization_pending || 0 } : null);
    } catch (err) {
      if (sequence === requestSequence.current) setError(err.message);
    } finally {
      if (sequence === requestSequence.current) setLoading(false);
    }
  };

  useEffect(() => {
    let active = true;
    Promise.all([DashboardApi.getCategories(), DashboardApi.getTags(), DashboardApi.getAuthors()]).then(([categoryData, tagData, authorData]) => {
      if (active) { setCategories(categoryData.results || []); setTags(tagData.results || []); setAuthors(authorData.results || []); }
    }).catch(err => { if (active) setError(err.message); });
    return () => { active = false; };
  }, []);

  // eslint-disable-next-line react-hooks/exhaustive-deps -- reload only when list parameters change
  useEffect(() => { load(filters); }, [listKey]);

  const setParams = (mutate, replace = false) => {
    const next = new URLSearchParams(searchParams);
    mutate(next);
    setSearchParams(next, { replace });
  };
  const showEditor = post => { setEditorPost(post); setEditorKey(key => key + 1); };
  const fetchRecord = async (id, type) => {
    setOpening(true);
    try {
      const data = await DashboardApi.getPosts({ type, id });
      if (data.results?.[0]) return data.results[0];
      setError('This content no longer exists. Refresh the library.');
      return null;
    } catch (err) { setError(err.message); return null; } finally { setOpening(false); }
  };
  const openEditor = async post => {
    setNotice(''); setError('');
    const full = Object.hasOwn(post, 'content') ? post : await fetchRecord(post.id, post.post_type);
    if (!full) return;
    showEditor(normalizePost(full));
    setParams(next => { next.set('edit', full.id); if (full.post_type === 'page') next.set('type', 'page'); else next.delete('type'); });
  };
  const startCreate = type => { setNotice(''); setError(''); showEditor(createEmptyPost(type)); };
  const closeEditor = () => { setEditorPost(null); if (searchParams.has('edit')) setParams(next => next.delete('edit')); };

  // Deep links (?edit=<id>), browser back/forward and quick actions (?new=post|page).
  useEffect(() => {
    let active = true;
    if (editParam && Number(editParam) !== editorPost?.id) {
      fetchRecord(editParam, filters.type).then(post => { if (active && post) showEditor(normalizePost(post)); });
    } else if (!editParam && editorPost?.id) {
      setEditorPost(null);
    }
    return () => { active = false; };
  // eslint-disable-next-line react-hooks/exhaustive-deps -- react to URL changes only, not to the editor's own state
  }, [editParam]);
  useEffect(() => {
    if (!newParam) return;
    if (canCreate) startCreate(newParam);
    setParams(next => next.delete('new'), true);
  // eslint-disable-next-line react-hooks/exhaustive-deps -- one-shot handling of ?new=
  }, [newParam, canCreate]);

  const onSaved = (post, created) => {
    if (post && created) setParams(next => { next.set('edit', post.id); if (post.post_type === 'page') next.set('type', 'page'); }, true);
    if (post) setEditorPost(post);
    load();
  };
  const afterRemoval = message => { setEditorPost(null); setParams(next => next.delete('edit')); setNotice(message); load(); };
  const applyFilters = values => setSearchParams(Object.fromEntries(Object.entries(values).filter(([, value]) => value !== '' && value !== undefined && value !== null)));
  const isPages = filters.type === 'page';
  // A new draft needs create rights; saving an existing one needs edit rights.
  const canWrite = editorPost && !editorPost.id ? canCreate : canEdit;

  return <div className="dart-page">
    {!editorPost && <AdminPageHeader title={isPages ? 'Pages' : 'Articles'} text={isPages ? 'Standalone website pages. Draft, review and publish them like articles.' : 'Your publishing workspace. From first draft to published research.'} actions={canCreate && <><button className="admin-button" onClick={() => startCreate('post')}><Plus size={16} /> New article</button><button className="admin-button admin-button-secondary" onClick={() => startCreate('page')}><FilePlus2 size={16} /> New page</button></>} />}
    {notice && <AdminNotice type="success">{notice}</AdminNotice>}{error && <AdminNotice type="error">{error}</AdminNotice>}
    {!editorPost && opening && <StateBlock type="loading" title="Opening editor" text="Loading the latest saved version…" />}
    {!editorPost && <ArticleLibrary posts={posts} summary={summary} attention={attention} pagination={pagination} categories={categories} tags={tags} authors={authors} filters={filters} onFilters={applyFilters} onEdit={openEditor} onCreate={startCreate} onReload={() => load()} loading={loading} onNotice={setNotice} onError={setError} />}
    {editorPost && <ArticleEditor key={editorKey} initialPost={editorPost} categories={categories} tags={tags} authors={authors} setAuthors={setAuthors} setTags={setTags} canWrite={canWrite} canDelete={canDelete} canUploadMedia={canUploadMedia} userId={user?.id} onClose={closeEditor} onSaved={onSaved} onTrashed={() => afterRemoval('Content moved to Trash. You can restore it from the Trash view.')} onDeleted={() => afterRemoval('Trashed content permanently deleted. Restore is no longer available.')} onNotice={setNotice} onError={setError} />}
  </div>;
}
