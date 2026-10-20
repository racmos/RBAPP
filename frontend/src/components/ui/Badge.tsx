import type { ReactNode } from 'react';
import styles from './Badge.module.css';

type BadgeProps = {
  tone?: 'neutral' | 'accent' | 'success' | 'warning' | 'danger';
  children: ReactNode;
};

/** A short status label. Colour is never the only signal: the text says it. */
export function Badge({ tone = 'neutral', children }: BadgeProps) {
  return <span className={[styles.badge, styles[tone]].join(' ')}>{children}</span>;
}
