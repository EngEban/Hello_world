export default function AdminNotice({ type = 'info', children }) {
  const role = type === 'error' ? 'alert' : 'status';
  return (
    <p className={`admin-notice admin-notice-${type}`} role={role} aria-live={type === 'error' ? 'assertive' : 'polite'}>
      {children}
    </p>
  );
}
