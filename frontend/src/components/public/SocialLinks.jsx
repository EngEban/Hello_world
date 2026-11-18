import { Camera, CirclePlay, MessageCircle, Send } from 'lucide-react';
import { SOCIAL_LINKS } from '../../siteData';

const items = [
  ['facebook', 'f'],
  ['twitter', 'X'],
  ['youtube', CirclePlay],
  ['instagram', Camera],
  ['linkedin', 'in'],
  ['telegram', Send],
  ['whatsapp', MessageCircle],
];

export default function SocialLinks({ light = false }) {
  return (
    <div className={`social-links ${light ? 'social-links-light' : ''}`}>
      {items.map(([key, Icon]) => (
        <a key={key} href={SOCIAL_LINKS[key]} target="_blank" rel="noreferrer" aria-label={key}>
          {typeof Icon === 'string'
            ? <span className={`social-glyph social-glyph-${key}`}>{Icon}</span>
            : <Icon size={14} />}
        </a>
      ))}
    </div>
  );
}
