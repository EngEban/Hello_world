import { AlertTriangle, ArrowRight, ArrowUpRight, BookOpen, BriefcaseBusiness, CalendarDays, CheckCircle2, Clock3, ClipboardList, FilePlus2, FileText, Images, Inbox, PencilLine, Plus, Settings, Sparkles, Upload, UserCog, Users } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, useOutletContext } from 'react-router-dom';
import { DashboardApi } from '../../../api/dashboardApi';
import AdminNotice from '../../../components/dashboard/AdminNotice';
import { DashboardCard, DonutSummary, Meter, SimpleBarChart, StatCard, StateBlock, TrendChart } from '../../../components/dashboard/DashboardPrimitives';
import StatusBadge from '../../../components/dashboard/StatusBadge';
import { editorialStatus } from '../posts/workspace';
import OptimizationHealth from './OptimizationHealth';
import { permissionsAllow } from '../users/adminShared';

const snapshot = [
  ['team_members','Users',Users,'/dashboard/users'],['total_posts','Articles',BookOpen,'/dashboard/posts'],
  ['new_service_requests','Requests',ClipboardList,'/dashboard/services?tab=requests'],['open_opportunities','Opportunities',BriefcaseBusiness,'/dashboard/opportunities'],
  ['new_contacts','Messages',Inbox,'/dashboard/contacts'],['total_media','Media',Images,'/dashboard/media'],
];
const shortcuts = [
  [Images,'Media library','/dashboard/media'],[FileText,'Website content','/dashboard/content-studio'],[Users,'Authors & contributors','/dashboard/authors'],
  [UserCog,'User management','/dashboard/users'],[BriefcaseBusiness,'Create opportunity','/dashboard/opportunities?new=1'],
  [ClipboardList,'Add service','/dashboard/services?new=1'],[Sparkles,'Premium controls','/dashboard/premium-controls'],[Settings,'Workspace settings','/dashboard/settings'],
];
const createActions = [
  [PencilLine,'New article','Write and publish research','/dashboard/posts?new=post','content.create'],
  [FilePlus2,'New page','Add a standalone page','/dashboard/posts?new=page','content.create'],
  [Upload,'Upload media','Images for articles and pages','/dashboard/media','media.create'],
];
const taskIcons = { 'New contacts': Inbox, 'Team applications': Users, 'Service requests': ClipboardList, 'Draft articles': FileText };
const shortDate = value => new Date(value).toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
const relative = value => {
  const minutes = Math.round((Date.now() - new Date(value).getTime()) / 60000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.round(hours / 24);
  return days < 30 ? `${days} d ago` : shortDate(value);
};

export default function DashboardHomePage() {
  const [payload,setPayload] = useState(null);
  const [error,setError] = useState('');
  const {user,bootstrap} = useOutletContext();
  const can=permission=>permissionsAllow(bootstrap?.permissions,permission,user?.is_superuser);
  const canWrite=can('content.create');
  const canReadContent=can('content.view');
  const load=()=>{setError('');DashboardApi.getStats().then(setPayload).catch(e=>setError(e.message));};
  useEffect(()=>{load();},[]);
  const stats=payload?.stats||{};
  const loading=!payload&&!error;
  // A username that is an email address reads badly in a greeting, so leave it out.
  const firstName=[user?.display_name,user?.first_name,user?.username].map(name=>(name||'').trim().split(/\s+/)[0]).find(name=>name&&!name.includes('@'))||'';
  const hour=new Date().getHours();
  const greeting=hour<12?'Good morning':hour<18?'Good afternoon':'Good evening';
  const today=new Date().toLocaleDateString(undefined,{weekday:'long',day:'numeric',month:'long'});
  const tasks=(payload?.pending_tasks||[]);
  // Drafts are work in progress, not something waiting on someone else.
  const openTasks=tasks.filter(task=>task.label!=='Draft articles').reduce((sum,task)=>sum+(task.count||0),0);
  const health=payload?.content_health;
  const trend=(payload?.publishing_trend||[]).map(item=>({label:shortDate(item.week),count:item.count}));

  return <div className="dash-overview">
    <header className="dash-overview-hero">
      <div>
        <span className="dash-eyebrow">{today}</span>
        <h1>{firstName?`${greeting}, ${firstName}.`:`${greeting}.`}</h1>
        <p>{loading?'Loading your workspace…':openTasks?`${openTasks} ${openTasks===1?'item needs':'items need'} your attention today.`:'Everything is up to date. A clear view of your publishing and operations.'}</p>
      </div>
      <div className="dash-overview-actions">
        {canWrite&&<Link className="admin-button" to="/dashboard/posts?new=post"><Plus size={16}/> New article</Link>}
        <a className="admin-button admin-button-secondary" href="/" target="_blank" rel="noreferrer">View website <ArrowUpRight size={16}/></a>
      </div>
    </header>
    {error&&<AdminNotice type="error">{error} <button type="button" className="admin-button admin-button-secondary" onClick={load}>Try again</button></AdminNotice>}

    <section className="dash-stat-grid" aria-label="Publishing overview">
      <StatCard icon={CheckCircle2} label="Published" value={stats.published_articles??0} hint={payload?`${stats.posts_this_week||0} this week`:''} to="/dashboard/posts?status=publish" loading={loading}/>
      <StatCard icon={FileText} label="Drafts" value={stats.draft_articles??0} hint="Not yet public" to="/dashboard/posts?status=draft" loading={loading}/>
      <StatCard icon={Clock3} label="In review" value={stats.review_articles??0} hint="Waiting for approval" to="/dashboard/posts?status=pending" loading={loading} tone={stats.review_articles?'amber':'blue'}/>
      <StatCard icon={CalendarDays} label="Scheduled" value={stats.scheduled_articles??0} hint="Publishes automatically" to="/dashboard/posts?status=scheduled" loading={loading}/>
    </section>

    {loading&&<StateBlock type="loading" title="Loading workspace" text="Fetching your latest publishing and operations data."/>}
    {payload&&<>
      <div className="dash-overview-grid">
        <DashboardCard title="Needs attention" className="dash-span-4">
          {tasks.length?<div className="dash-task-list">{tasks.map(task=>{const Icon=taskIcons[task.label]||AlertTriangle;return <Link key={task.label} to={task.route} className={task.count?'has-items':''}><span className="dash-task-icon"><Icon size={17}/></span><span>{task.label}</span><strong>{task.count}</strong><ArrowRight size={14}/></Link>;})}</div>:<StateBlock type="empty" title="Nothing waiting" text="New messages, applications and requests appear here."/>}
        </DashboardCard>
        <DashboardCard title="Publishing trend" eyebrow="Last 12 weeks" className="dash-span-5" actions={<Link to="/dashboard/reports">Reports <ArrowRight size={13}/></Link>}>
          <div className="dash-trend-summary"><span><strong>{stats.posts_this_week||0}</strong><small>published this week</small></span><span><strong>{stats.posts_this_month||0}</strong><small>last 30 days</small></span><span><strong>{stats.subscribers||0}</strong><small>subscribers</small></span></div>
          {trend.length?<TrendChart data={trend} label="Articles published per week"/>:<StateBlock type="empty" title="No trend yet" text="Published articles will be charted here."/>}
        </DashboardCard>
        <DashboardCard title="Create" className="dash-span-3">
          <div className="dash-create-list">{createActions.filter(([, , , , permission])=>can(permission)).map(([Icon,label,text,to])=><Link key={to} to={to}><span className="dash-create-icon"><Icon size={18}/></span><span><strong>{label}</strong><small>{text}</small></span></Link>)}</div>
        </DashboardCard>

        <DashboardCard title="Publishing queue" eyebrow="In review and scheduled" className="dash-span-6" actions={canReadContent&&<Link to="/dashboard/posts">All articles <ArrowRight size={13}/></Link>}>
          {payload.editorial_queue?.length?<div className="dash-queue">{payload.editorial_queue.map(post=>{const status=editorialStatus(post);return <Link to={`/dashboard/posts?edit=${post.id}`} key={post.id}><span className={`dash-queue-dot is-${status}`} aria-hidden="true"/><span className="dash-queue-title"><strong>{post.title}</strong><small>{status==='scheduled'?`Publishes ${new Date(post.published_at).toLocaleString()}`:`Updated ${relative(post.updated_at)}`}</small></span><StatusBadge value={status}/></Link>;})}</div>:<StateBlock type="empty" title={canReadContent?'No articles waiting':'Content access is restricted'} text={canReadContent?'Articles awaiting review or scheduled for publication appear here.':'Your other permitted workspace sections remain available.'}/>}
        </DashboardCard>
        <DashboardCard title="Continue editing" eyebrow="Recent drafts" className="dash-span-6" actions={canReadContent&&<Link to="/dashboard/posts?status=draft">All drafts <ArrowRight size={13}/></Link>}>
          {payload.recent_drafts?.length?<div className="dash-queue">{payload.recent_drafts.map(post=><Link to={`/dashboard/posts?${post.post_type==='page'?'type=page&':''}edit=${post.id}`} key={post.id}><span className="dash-queue-dot is-draft" aria-hidden="true"/><span className="dash-queue-title"><strong>{post.title||'Untitled draft'}</strong><small>{post.post_type==='page'?'Page':'Article'} · edited {relative(post.updated_at)}</small></span><PencilLine size={15} className="dash-queue-action"/></Link>)}</div>:<StateBlock type="empty" title="No drafts" text="Drafts you start are listed here so you can pick them up quickly."/>}
        </DashboardCard>

        {canReadContent&&<OptimizationHealth/>}
        {health&&<DashboardCard title="Content health" eyebrow={`${health.total} articles`} className="dash-span-4">
          <p className="dash-card-note">Articles missing details that help readers and search engines. Click a line to fix them.</p>
          <div className="dash-meter-list">
            <Meter label="Missing SEO title or description" value={health.missing_seo} total={health.total} to="/dashboard/posts?needs=seo" tone="amber"/>
            <Meter label="Missing featured image" value={health.missing_image} total={health.total} to="/dashboard/posts?needs=image" tone="amber"/>
            <Meter label="Missing excerpt" value={health.missing_excerpt} total={health.total} to="/dashboard/posts?needs=excerpt"/>
            <Meter label="No category" value={health.uncategorized} total={health.total} to="/dashboard/posts?needs=category"/>
          </div>
        </DashboardCard>}
        <DashboardCard title="Platform snapshot" className={health?'dash-span-4':'dash-span-6'}>
          <div className="dash-snapshot">{snapshot.map(([key,label,Icon,to])=><Link key={key} to={to}><Icon size={18}/><span><small>{label}</small><strong>{stats[key]??0}</strong></span></Link>)}</div>
        </DashboardCard>
        <DashboardCard title="Recent activity" className={health?'dash-span-4':'dash-span-6'} actions={<Link to="/dashboard/reports">Reports <ArrowRight size={13}/></Link>}>
          {payload.recent_activity?.length?<ol className="dash-activity">{payload.recent_activity.slice(0,6).map(item=><li key={item.id}><span className="dash-activity-module">{item.module}</span><strong>{item.message}</strong><small>{item.actor||'System'} · {relative(item.created_at)}</small></li>)}</ol>:<StateBlock type="empty" title="No activity available" text="Actions are recorded in the audit trail. Visibility depends on your permissions."/>}
        </DashboardCard>
      </div>

      <section className="dash-section">
        <h2 className="dash-section-title">Activity and service insights</h2>
        <div className="dash-overview-grid">
          <DashboardCard title="Publishing activity" className="dash-span-4"><SimpleBarChart data={[{status:'Published this week',count:stats.posts_this_week||0},{status:'Published this month',count:stats.posts_this_month||0},{status:'Draft content',count:stats.draft_content||0},{status:'Subscribers',count:stats.subscribers||0}]}/></DashboardCard>
          <DashboardCard title="Service request status" className="dash-span-4"><DonutSummary data={payload.charts?.service_status||[]} totalLabel="Requests"/></DashboardCard>
          <DashboardCard title="Content status" className="dash-span-4"><DonutSummary data={payload.charts?.content_status||[]} totalLabel="Content"/></DashboardCard>
        </div>
      </section>

      <section className="dash-section">
        <h2 className="dash-section-title">Workspace shortcuts</h2>
        <div className="dash-shortcuts">{shortcuts.map(([Icon,label,to])=><Link key={to} to={to}><Icon size={18}/><span>{label}</span><ArrowRight size={14}/></Link>)}</div>
      </section>
    </>}
  </div>;
}
