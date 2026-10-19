import { Icon } from '@/components/ui/Icon';
import styles from './AuthForm.module.css';

/** A form-level error. `role="alert"` makes it announce the moment it is rendered. */
export function FormAlert({ message }: { message: string }) {
  return (
    <div role="alert" className={styles.alert}>
      <Icon name="warning" className={styles.alertIcon} />
      <span>{message}</span>
    </div>
  );
}
