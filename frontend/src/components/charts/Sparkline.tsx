import { type ReactNode } from 'react';
import styles from './Sparkline.module.css';

type SparklineProps = {
  values: (number | null)[];
  label: string;
  className?: string;
};

const WIDTH = 120;
const HEIGHT = 34;
const PAD = 2;

/**
 * Compact line chart for small spaces. Nulls are skipped; the stroke is green when the
 * last non-null value is greater than or equal to the first, red otherwise.
 */
export function Sparkline({ values, label, className }: SparklineProps) {
  const data = values.filter((v): v is number => v !== null);
  if (data.length === 0) return null;

  const first = data[0];
  const last = data[data.length - 1];
  const trend = last >= first ? 'up' : 'down';

  let content: ReactNode;
  if (data.length === 1) {
    content = (
      <>
        <line x1={0} y1={HEIGHT / 2} x2={WIDTH} y2={HEIGHT / 2} className={styles.line} />
        <circle cx={WIDTH / 2} cy={HEIGHT / 2} r={2.5} className={styles.dot} />
      </>
    );
  } else {
    const min = Math.min(...data);
    const max = Math.max(...data);
    const yFor = (value: number) => {
      if (max === min) return HEIGHT / 2;
      return HEIGHT - PAD - ((value - min) / (max - min)) * (HEIGHT - PAD * 2);
    };
    const xFor = (index: number) => (index / (data.length - 1)) * WIDTH;
    const points = data.map((value, index) => `${xFor(index)},${yFor(value)}`).join(' ');
    content = <polyline points={points} fill="none" className={styles.line} />;
  }

  const classes = [styles.sparkline, styles[trend], className].filter(Boolean).join(' ');
  return (
    <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className={classes} role="img" aria-label={label}>
      {content}
    </svg>
  );
}
