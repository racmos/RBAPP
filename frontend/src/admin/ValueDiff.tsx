import { useTranslation } from 'react-i18next';
import styles from './ValueDiff.module.css';

type ValueDiffProps = {
  oldValue: string | null;
  newValue: string | null;
  layout: 'inline' | 'stacked' | 'side';
};

/** Old vs new value (F13-g S6): colour never carries the meaning alone. */
export function ValueDiff({ oldValue, newValue, layout }: ValueDiffProps) {
  const { t } = useTranslation('admin');
  const show = (value: string | null) =>
    value === null || value === '' ? (
      <span className={styles.empty}>{t('changes.empty')}</span>
    ) : (
      value
    );
  const old = (
    <span>
      <span className={styles.prefix}>{t('changes.old')}</span>
      <del className={styles.old}>{show(oldValue)}</del>
    </span>
  );
  const fresh = (
    <span className={styles.newValue}>
      <span className={styles.prefix}>{t('changes.new')}</span>
      {show(newValue)}
    </span>
  );
  if (layout === 'stacked') {
    return (
      <span className={styles.stacked}>
        {old}
        {fresh}
      </span>
    );
  }
  if (layout === 'side') {
    return (
      <span className={styles.side}>
        {old}
        {fresh}
      </span>
    );
  }
  return (
    <span className={styles.diff}>
      {old} → {fresh}
    </span>
  );
}
