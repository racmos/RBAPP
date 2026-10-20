import type { ReactNode } from 'react';
import styles from './PageHeader.module.css';

type PageHeaderProps = { title: string; subtitle?: string; actions?: ReactNode };

/** The `h1` of a page, with an optional subtitle and actions. */
export function PageHeader({ title, subtitle, actions }: PageHeaderProps) {
  return (
    <div className={styles.header}>
      <div className={styles.text}>
        <h1 className={styles.title}>{title}</h1>
        {subtitle && <p className={styles.subtitle}>{subtitle}</p>}
      </div>
      {actions && <div className={styles.actions}>{actions}</div>}
    </div>
  );
}
