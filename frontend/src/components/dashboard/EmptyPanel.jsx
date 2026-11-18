export default function EmptyPanel({ title, text }) {
  return <div className="admin-empty"><h3>{title}</h3>{text && <p>{text}</p>}</div>;
}
