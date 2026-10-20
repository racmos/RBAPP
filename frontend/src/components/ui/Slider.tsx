import { useId } from 'react';
import styles from './Slider.module.css';

type SliderProps = {
  label: string;
  value: number;
  onChange: (value: number) => void;
  /** The user is done: pointer released, key released or focus left. */
  onCommit?: (value: number) => void;
  min?: number;
  max?: number;
  step?: number;
  unit?: string;
  disabled?: boolean;
};

/** A labelled range input with its value always visible. The platform gives keyboard steps. */
export function Slider({
  label,
  value,
  onChange,
  onCommit,
  min = 0,
  max = 100,
  step = 1,
  unit = '',
  disabled,
}: SliderProps) {
  const id = useId();
  const text = `${value}${unit}`;
  const commit = (target: HTMLInputElement) => onCommit?.(Number(target.value));
  return (
    <div className={styles.slider}>
      <label htmlFor={id} className={styles.label}>
        {label}
      </label>
      <input
        id={id}
        type="range"
        className={styles.range}
        min={min}
        max={max}
        step={step}
        value={value}
        disabled={disabled}
        aria-valuetext={text}
        onChange={(event) => onChange(Number(event.target.value))}
        onPointerUp={(event) => commit(event.currentTarget)}
        onKeyUp={(event) => commit(event.currentTarget)}
        onBlur={(event) => commit(event.currentTarget)}
      />
      <output htmlFor={id} className={styles.value}>
        {text}
      </output>
    </div>
  );
}
