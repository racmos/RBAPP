import type { ComponentProps } from 'react';
import styles from './TableScroll.module.css';

export type TableScrollProps = ComponentProps<'div'> & {
  /** Scroll with the page instead of inside the box (no vertical cap, header sticks below the topbar). */
  fit?: boolean;
};

/**
 * The scroll box of a data table. It scrolls both ways, capped below the topbar, and its
 * `thead th` stick to its own top: a sticky header inside an `overflow` box sticks to that box,
 * never to the page, so a page offset (the topbar height) would push it over the first rows.
 *
 * `fit` is for a table whose columns wrap to the width: the box is no scroll container
 * (`overflow-x: clip`), so the page is the only scroll and the `thead` sticks below the topbar.
 */
export function TableScroll({ className, children, fit = false, ...rest }: TableScrollProps) {
  return (
    <div
      data-slot="table-scroll"
      data-fit={fit ? '' : undefined}
      className={[fit ? styles.fit : styles.scroll, className].filter(Boolean).join(' ')}
      {...rest}
    >
      {children}
    </div>
  );
}
