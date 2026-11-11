import type { ReactNode } from 'react';
import { NavLink } from 'react-router';
import { isSpa, type NavEntry } from './navRegistry';

type NavItemProps = {
  entry: NavEntry;
  className?: string;
  /** Tooltip, for an entry whose text is visually hidden (the topbar below 2xl). */
  title?: string;
  /** Runs when the entry is activated (the "More" sheet closes itself here). */
  onActivate?: () => void;
  children: ReactNode;
};

/**
 * One navigation entry (SHELL-5): `spa` is a router link that marks the current page with
 * `aria-current="page"` (also below its path when the entry is `nested`).
 */
export function NavItem({ entry, className, title, onActivate, children }: NavItemProps) {
  if (isSpa(entry)) {
    return (
      <NavLink
        to={entry.to}
        end={!entry.nested}
        className={className}
        title={title}
        onClick={onActivate}
      >
        {children}
      </NavLink>
    );
  }
  return null; // planned entries are not rendered
}
