import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { PAGE_TITLES } from '../../config/site';

export default function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'auto' });
    document.title = PAGE_TITLES[pathname] || 'ResRef';
  }, [pathname]);
  return null;
}
