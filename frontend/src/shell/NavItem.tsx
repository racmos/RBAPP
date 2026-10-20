import type { ReactNode } from 'react';
import { NavLink } from 'react-router';
import { isLegacy, isSpa, type NavEntry } from './navRegistry';
import { legacyHref } from './legacyRoutes';

type NavItemProps = {
  entry: NavEntry;
  className?: string;
  /** Runs when the entry is activated (the "Más" sheet closes itself here). */
  onActivate?: () => void;
  children: ReactNode;
};

/**
 * One navigation entry (SHELL-5): `spa` is a router link that marks the current page with
 * `aria-current="page"`; `legacy` is a plain anchor, a full navigation to the Jinja page.
 */
export function NavItem({ entry, className, onActivate, children }: NavItemProps) {
  if (isSpa(entry)) {
    return (
      <NavLink to={entry.to} end className={className} onClick={onActivate}>
        {children}
      </NavLink>
    );
  }
  if (isLegacy(entry)) {
    return (
      <a href={legacyHref(entry.legacy)} className={className} onClick={onActivate}>
        {children}
      </a>
    );
  }
  return null; // planned entries are not rendered
}
