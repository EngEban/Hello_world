import { Globe, Linkedin, ExternalLink } from 'lucide-react';
import { Link } from 'react-router-dom';
import { initials, plainText, safeExternalUrl } from '../../utils/articleContent';
import { optimizedImageUrl } from '../../utils/optimizedImages';

export function ContributorAvatar({ author }) {
  return <span className="publication-avatar">{author.avatar && <img src={optimizedImageUrl(author.avatar, true)} alt="" loading="lazy" decoding="async" onError={event => { event.currentTarget.hidden = true; }} />}<span aria-hidden="true">{initials(author.display_name)}</span></span>;
}

export default function ContributorCard({ author, headingLevel = 'h3', hideHeading = false }) {
  const Heading = headingLevel;
  const name = [author.prefix, plainText(author.display_name)].filter(Boolean).join(' ');
  const links = [['website', 'Website', Globe], ['linkedin', 'LinkedIn', Linkedin], ['orcid', 'ORCID', ExternalLink], ['google_scholar', 'Google Scholar', ExternalLink], ['researchgate', 'ResearchGate', ExternalLink], ['twitter', 'X / Twitter', ExternalLink]];
  return <div className="publication-contributor">
    <ContributorAvatar author={author} />
    <div>{!hideHeading && <Heading>{author.slug && headingLevel !== 'h1' ? <Link className="publication-profile-link" to={`/authors/${author.slug}`}>{name}</Link> : name}{author.credentials && <span>, {plainText(author.credentials)}</span>}</Heading>}
      {(author.role_label || author.role) && <p className="publication-credit">{author.role_label || author.role}</p>}
      {[author.position, author.institution, author.specialty, author.country].some(Boolean) && <p className="publication-affiliation">{[author.position, author.institution, author.specialty, author.country].filter(Boolean).join(' · ')}</p>}
      {(author.short_bio || author.bio) && <p>{plainText(author.short_bio || author.bio)}</p>}
      {author.contribution_note && <p>{author.contribution_note}</p>}
      <div className="publication-profile-links">{links.map(([key, label, Icon]) => safeExternalUrl(author[key]) && <a href={safeExternalUrl(author[key])} key={key} target="_blank" rel="noopener noreferrer"><Icon size={14} aria-hidden="true" />{label}</a>)}</div>
    </div>
  </div>;
}
