import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';
import { Icon } from '@/components/ui/Icon';
import { useDocumentTitle } from '@/i18n';
import styles from './NotFound.module.css';

/**
 * The 404 view (SHELL-8): a SPA route for unknown paths and admin-only routes. It is a section,
 * not a landmark: the shell (or `RouteError`) supplies the `main`.
 */
export function NotFound() {
  const { t } = useTranslation('nav');
  useDocumentTitle(t('notFound.title'));
  return (
    <section className={styles.notFound}>
      <Icon name="search" size={34} className={styles.icon} />
      <h1 className={styles.title}>{t('notFound.title')}</h1>
      <p className={styles.body}>{t('notFound.body')}</p>
      <Link to="/" className={styles.home}>
        {t('notFound.home')}
      </Link>
    </section>
  );
}
