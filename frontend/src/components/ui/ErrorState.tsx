import { useTranslation } from 'react-i18next';
import { Button } from './Button';
import styles from './ErrorState.module.css';
import { Icon } from './Icon';

type ErrorStateProps = { message: string; onRetry?: () => void };

/** A failure with a way out. `role="alert"` makes it announce when it appears. */
export function ErrorState({ message, onRetry }: ErrorStateProps) {
  const { t } = useTranslation('common');
  return (
    <div className={styles.state} role="alert">
      <Icon name="warning" size={28} className={styles.icon} />
      <p className={styles.message}>{message}</p>
      {onRetry && (
        <Button variant="ghost" onClick={onRetry}>
          {t('actions.retry')}
        </Button>
      )}
    </div>
  );
}
