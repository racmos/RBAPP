import type { ComponentProps } from 'react';
import styles from './Button.module.css';

type ButtonProps = Omit<ComponentProps<'button'>, 'type'> & {
  type?: 'button' | 'submit' | 'reset';
  variant?: 'primary' | 'ghost' | 'danger';
  size?: 'md' | 'sm';
  block?: boolean;
  /** An action is in progress: the button is disabled and marked busy (FAUTH-2). */
  pending?: boolean;
};

export function Button({
  type = 'button',
  variant = 'primary',
  size = 'md',
  block = false,
  pending = false,
  disabled,
  className,
  ...rest
}: ButtonProps) {
  const classes = [
    styles.button,
    styles[variant],
    size === 'sm' && styles.sm,
    block && styles.block,
    className,
  ]
    .filter(Boolean)
    .join(' ');
  return (
    <button
      type={type}
      className={classes}
      disabled={disabled || pending}
      aria-busy={pending || undefined}
      {...rest}
    />
  );
}
