import { useId, type ReactNode } from 'react';
import styles from './Panel.module.css';

type PanelProps = {
  /** A title makes the panel a named region (`h2`). */
  title?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
};

/** The glass card of the design: border, radius and padding follow the density tokens. */
export function Panel({ title, actions, children, className }: PanelProps) {
  const headingId = useId();
  const classes = [styles.panel, className].filter(Boolean).join(' ');
  if (!title) return <div className={classes}>{children}</div>;
  return (
    <section className={classes} aria-labelledby={headingId}>
      <div className={styles.head}>
        <h2 id={headingId} className={styles.title}>
          {title}
        </h2>
        {actions}
      </div>
      {children}
    </section>
  );
}
