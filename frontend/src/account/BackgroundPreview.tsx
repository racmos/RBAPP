import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/Badge';
import { Panel } from '@/components/ui/Panel';
import styles from './BackgroundPreview.module.css';

/**
 * A miniature of the app on the chosen background (SHELL-7, xl and up). It reads the same CSS
 * variables as the page (`--bg-image-*`, `--accent`, `--row-h`), so it follows every control
 * with no state of its own. It is decoration: assistive technology skips the sample.
 */
export function BackgroundPreview() {
  const { t } = useTranslation('prefs');
  return (
    <Panel title={t('interface.preview.title')} className={styles.panel}>
      <div className={styles.frame} aria-hidden="true">
        <div className={styles.sample}>
          <p className={styles.heading}>{t('interface.preview.heading')}</p>
          <p className={styles.body}>{t('interface.preview.body')}</p>
          <span className={styles.button}>{t('interface.preview.button')}</span>
          <div className={styles.row}>
            <span>{t('interface.preview.row')}</span>
            <Badge tone="accent">{t('interface.preview.badge')}</Badge>
          </div>
        </div>
      </div>
    </Panel>
  );
}
