export default function AdminPageHeader({ eyebrow = 'Dashboard', title, text, actions }) {
  // The generic "Dashboard" eyebrow repeats the breadcrumb, so only a page-specific eyebrow is shown.
  const showEyebrow = eyebrow && eyebrow !== 'Dashboard';
  return (
    <header className="admin-page-header">
      <div>
        <span className={showEyebrow ? 'admin-page-eyebrow' : 'admin-page-eyebrow admin-page-eyebrow-hidden'}>{eyebrow}</span>
        <h1>{title}</h1>
        {text && <p>{text}</p>}
      </div>
      {actions && <div className="admin-page-actions">{actions}</div>}
    </header>
  );
}
