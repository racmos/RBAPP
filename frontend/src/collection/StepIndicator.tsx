import styles from './StepIndicator.module.css';

type StepIndicatorProps<K extends string> = {
  /** Accessible name of the list. */
  label: string;
  steps: readonly { key: K; label: string }[];
  current: K;
};

/** Where a multi-step flow is: numbered steps, the current one with `aria-current="step"`. */
export function StepIndicator<K extends string>({ label, steps, current }: StepIndicatorProps<K>) {
  const index = steps.findIndex((step) => step.key === current);
  return (
    <ol className={styles.steps} aria-label={label}>
      {steps.map((step, position) => (
        <li
          key={step.key}
          className={styles.step}
          aria-current={position === index ? 'step' : undefined}
          data-done={position < index || undefined}
        >
          <span className={styles.number} aria-hidden="true">
            {position + 1}
          </span>
          <span className={styles.label}>{step.label}</span>
        </li>
      ))}
    </ol>
  );
}
