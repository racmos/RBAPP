import { useId } from 'react';
import styles from './Switch.module.css';

type SwitchProps = {
  label: string;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  disabled?: boolean;
};

/** An on/off setting. A native button, so Space and Enter work; the state is `aria-checked`. */
export function Switch({ label, checked, onCheckedChange, disabled }: SwitchProps) {
  const labelId = useId();
  return (
    <span className={styles.row}>
      <span id={labelId} className={styles.label}>
        {label}
      </span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-labelledby={labelId}
        className={styles.track}
        disabled={disabled}
        onClick={() => onCheckedChange(!checked)}
      >
        <span className={styles.thumb} aria-hidden="true" />
      </button>
    </span>
  );
}
