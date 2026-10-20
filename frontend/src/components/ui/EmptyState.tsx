import { Button } from './Button';
import styles from './EmptyState.module.css';
import { Icon } from './Icon';
import type { IconName } from './icons';

type EmptyStateProps = {
  icon?: IconName;
  title: string;
  body?: string;
  action?: { label: string; onAction: () => void };
};

/** Nothing here yet: say so, and point to the next step. */
export function EmptyState({ icon = 'info', title, body, action }: EmptyStateProps) {
  return (
    <div className={styles.state}>
      <Icon name={icon} size={30} className={styles.icon} />
      <h2 className={styles.title}>{title}</h2>
      {body && <p className={styles.body}>{body}</p>}
      {action && (
        <Button variant="ghost" onClick={action.onAction}>
          {action.label}
        </Button>
      )}
    </div>
  );
}
