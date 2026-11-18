import { Link, useLocation } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';
import { mobileHeroImage, pageHeroImage } from '../../config/heroImages';
import { useSiteSettings } from '../../contexts/SiteSettingsContext';

/**
 * Shared page header in the homepage style: navy gradient with a soft photo
 * layer, breadcrumb, serif title and optional kicker/actions. The title, text
 * and image stay editable through `<settingPrefix>_hero_*` site settings.
 */
export default function PageHero({ title, text, settingPrefix = '', imageUrl, kicker, breadcrumb, children }) {
  const settings = useSiteSettings();
  const { pathname } = useLocation();
  const editableTitle = settingPrefix ? settings[`${settingPrefix}_hero_title`] : '';
  const editableText = settingPrefix ? settings[`${settingPrefix}_hero_text`] : '';
  const finalTitle = editableTitle || title;
  const finalText = editableText || text;
  const imageSrc = pageHeroImage(settings, settingPrefix, imageUrl, pathname);
  const heroStyle = {
    ...(imageSrc ? { '--page-hero-image': `url("${imageSrc}")` } : {}),
    ...(imageSrc ? { '--page-hero-image-mobile': `url("${mobileHeroImage(imageSrc)}")` } : {}),
    '--page-hero-title-size': settings.page_hero_title_size || undefined,
    '--page-hero-text-size': settings.page_hero_text_size || undefined,
  };
  const crumbs = breadcrumb === false ? null : (Array.isArray(breadcrumb) ? breadcrumb : [[breadcrumb || finalTitle]]);

  return (
    <section className="rh-page-hero" style={heroStyle}>
      <div className="rh-page-hero-backdrop" aria-hidden="true">
        {imageSrc && <span className="rh-page-hero-photo" />}
        <span className="rh-page-hero-glow" />
      </div>
      <div className="rh-container rh-page-hero-inner">
        {crumbs && (
          <nav className="rh-breadcrumb" aria-label="Breadcrumb">
            <Link to="/">Home</Link>
            {crumbs.map(([label, to], index) => (
              <span className="rh-breadcrumb-item" key={`${label}-${index}`}>
                <ChevronRight size={14} aria-hidden="true" />
                {to && index < crumbs.length - 1 ? <Link to={to}>{label}</Link> : <span aria-current={index === crumbs.length - 1 ? 'page' : undefined}>{label}</span>}
              </span>
            ))}
          </nav>
        )}
        {kicker && <span className="rh-hero-kicker"><span className="rh-pulse" aria-hidden="true" />{kicker}</span>}
        <h1>{finalTitle}</h1>
        {finalText && <p className="rh-page-hero-text">{finalText}</p>}
        {children && <div className="rh-actions rh-page-hero-actions">{children}</div>}
      </div>
    </section>
  );
}
