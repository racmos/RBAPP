import styles from './Skeleton.module.css';

type SkeletonProps = { label: string; lines?: number };

/** A loading placeholder. The label is for assistive technology; the bars are decoration. */
export function Skeleton({ label, lines = 3 }: SkeletonProps) {
  return (
    <div className={styles.skeleton} aria-busy="true">
      <span className="sr-only">{label}</span>
      {Array.from({ length: lines }, (_, index) => (
        <span key={index} className={styles.line} data-skeleton-line aria-hidden="true" />
      ))}
    </div>
  );
}
