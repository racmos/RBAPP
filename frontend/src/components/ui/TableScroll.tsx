import type { ComponentProps } from 'react';
import styles from './TableScroll.module.css';

export type TableScrollProps = ComponentProps<'div'>;

/**
 * The scroll box of a data table. It scrolls both ways, capped below the topbar, and its
 * `thead th` stick to its own top: a sticky header inside an `overflow` box sticks to that box,
 * never to the page, so a page offset (the topbar height) would push it over the first rows.
 */
export function TableScroll({ className, children, ...rest }: TableScrollProps) {
  return (
    <div
      data-slot="table-scroll"
      className={[styles.scroll, className].filter(Boolean).join(' ')}
      {...rest}
    >
      {children}
    </div>
  );
}
