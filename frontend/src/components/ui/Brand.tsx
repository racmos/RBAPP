import markUrl from '@/assets/brand/mark.svg';
import wordmarkUrl from '@/assets/brand/wordmark.svg';
import styles from './Brand.module.css';

const SOURCES = { mark: markUrl, wordmark: wordmarkUrl } as const;

type BrandProps = {
  variant: keyof typeof SOURCES;
  className?: string;
};

/** The brand image. Both variants carry the accessible name "Rift Manager" (DS-9). */
export function Brand({ variant, className }: BrandProps) {
  const classes = [styles.brand, styles[variant], className].filter(Boolean).join(' ');
  return <img className={classes} src={SOURCES[variant]} alt="Rift Manager" draggable={false} />;
}
