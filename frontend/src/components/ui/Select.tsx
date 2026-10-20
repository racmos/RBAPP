import type { ComponentProps } from 'react';
import styles from './Select.module.css';

export type SelectProps = ComponentProps<'select'>;

/** A native `<select>` in the look of `Input`; wire it to a label through `Field`. */
export function Select({ className, children, ...rest }: SelectProps) {
  return (
    <select className={[styles.select, className].filter(Boolean).join(' ')} {...rest}>
      {children}
    </select>
  );
}
