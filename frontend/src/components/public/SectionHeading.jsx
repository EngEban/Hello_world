export default function SectionHeading({ eyebrow, title, text, align = 'left', id, children }) {
  return (
    <header className={`rh-intro rh-intro-${align === 'center' ? 'center' : 'left'}`} data-reveal>
      {eyebrow && <span className="rh-label">{eyebrow}</span>}
      <h2 id={id}>{title}</h2>
      {text && <p>{text}</p>}
      {children}
    </header>
  );
}
