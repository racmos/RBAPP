import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';
import { useDocumentTitle } from '@/i18n';

/** The 404 view (SHELL-8 refines it in unit e): unknown paths and admin-only routes. */
export function NotFound() {
  const { t } = useTranslation('nav');
  useDocumentTitle(t('notFound.title'));
  return (
    <main
      style={{ display: 'grid', placeItems: 'center', minHeight: '60dvh', padding: 'var(--pad)' }}
    >
      <div style={{ textAlign: 'center', maxWidth: '44ch' }}>
        <h1>{t('notFound.title')}</h1>
        <p>{t('notFound.body')}</p>
        <Link to="/">{t('notFound.home')}</Link>
      </div>
    </main>
  );
}
