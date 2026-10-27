import { useId, type ReactNode } from 'react';
import { contrast } from '@/lib/contrast';
import { Icon } from './Icon';
import styles from './FilterChip.module.css';

type FilterChipProps = {
  label: ReactNode;
  pressed?: boolean;
  count?: number;
  color?: string;
  onClick?: () => void;
  /** When provided the chip renders a remove button with the given accessible name. */
  onRemove?: { 'aria-label': string; onClick: () => void };
};

function foregroundFor(background: string): string {
  try {
    return contrast('#ffffff', background) >= 4.5 ? '#ffffff' : '#06222c';
  } catch {
    return 'inherit';
  }
}

/** A toggle or removable chip (F2-h S11). */
export function FilterChip({ label, pressed, count, color, onClick, onRemove }: FilterChipProps) {
  const style = color
    ? ({ ['--chip-bg']: color, color: foregroundFor(color) } as React.CSSProperties)
    : undefined;
  const ariaLabel =
    typeof label === 'string' ? `${label}${count !== undefined ? ` (${count})` : ''}` : undefined;

  return (
    <span className={styles.chip} data-pressed={pressed || undefined} style={style}>
      <button
        type="button"
        className={styles.toggle}
        aria-pressed={pressed}
        aria-label={ariaLabel}
        onClick={onClick}
        disabled={!onClick}
      >
        <span className={styles.label} aria-hidden={ariaLabel ? 'true' : undefined}>
          {label}
        </span>
        {count !== undefined && (
          <span className={styles.count} aria-hidden={ariaLabel ? 'true' : undefined}>
            ({count})
          </span>
        )}
      </button>
      {onRemove && (
        <button
          type="button"
          className={styles.remove}
          aria-label={onRemove['aria-label']}
          onClick={onRemove.onClick}
        >
          <Icon name="close" size={12} />
        </button>
      )}
    </span>
  );
}

type ChipGroupProps = {
  legend: ReactNode;
  children: ReactNode;
};

/** A group of chips named by its legend (F2-h S11). */
export function ChipGroup({ legend, children }: ChipGroupProps) {
  const legendId = useId();
  return (
    <div role="group" aria-labelledby={legendId} className={styles.group}>
      <div id={legendId} className={styles.legend}>
        {legend}
      </div>
      <div className={styles.items}>{children}</div>
    </div>
  );
}
