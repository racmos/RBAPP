import type { ComponentProps } from 'react';
import styles from './Input.module.css';

export type InputProps = ComponentProps<'input'>;

export function Input({ className, ...rest }: InputProps) {
  return <input className={[styles.input, className].filter(Boolean).join(' ')} {...rest} />;
}
