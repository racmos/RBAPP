import { useId, type ReactNode } from 'react';
import styles from './SettingsCard.module.css';

type SettingsCardProps = { title: string; description?: string; children: ReactNode };

/** A group of related settings: a named region whose rows are the controls. */
export function SettingsCard({ title, description, children }: SettingsCardProps) {
  const headingId = useId();
  return (
    <section className={styles.card} aria-labelledby={headingId}>
      <h2 id={headingId} className={styles.title}>
        {title}
      </h2>
      {description && <p className={styles.description}>{description}</p>}
      <div className={styles.rows}>{children}</div>
    </section>
  );
}

/** One setting: its name (and hint) on the left, its control on the right (below on a phone). */
export function SettingsRow({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={[styles.row, className].filter(Boolean).join(' ')}>{children}</div>;
}
