import type { ComponentProps, ReactNode } from 'react';
import styles from './Checkbox.module.css';

type CheckboxProps = Omit<ComponentProps<'input'>, 'type'> & { label: ReactNode };

/** A native checkbox with its label: keyboard, focus and screen-reader behaviour come from the browser. */
export function Checkbox({ label, className, ...rest }: CheckboxProps) {
  return (
    <label className={[styles.checkbox, className].filter(Boolean).join(' ')}>
      <input type="checkbox" className={styles.box} {...rest} />
      <span>{label}</span>
    </label>
  );
}
