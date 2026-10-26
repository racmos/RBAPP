import { useTranslation } from 'react-i18next';
import styles from './Pagination.module.css';

type PaginationProps = {
  page: number;
  pages: number;
  onChange: (page: number) => void;
};

/** Page switcher (F13-f S2, reused by F2-h): prev/next with the page text. */
export function Pagination({ page, pages, onChange }: PaginationProps) {
  const { t } = useTranslation('common');
  return (
    <nav aria-label={t('pagination.label')} className={styles.nav}>
      <button
        type="button"
        className={styles.button}
        disabled={page <= 1}
        onClick={() => onChange(page - 1)}
      >
        {t('pagination.prev')}
      </button>
      <span className={styles.page}>{t('pagination.page', { page, pages })}</span>
      <button
        type="button"
        className={styles.button}
        disabled={page >= pages}
        onClick={() => onChange(page + 1)}
      >
        {t('pagination.next')}
      </button>
    </nav>
  );
}
