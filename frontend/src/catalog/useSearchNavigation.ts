import { useCallback, useLayoutEffect, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router';

/**
 * URL search changes built on the latest search asked for, not on the rendered one. The router
 * applies a navigation inside a React transition (and after the route loaders), so for a while
 * `useSearchParams` still shows the old URL; a change built from it drops the change made just
 * before (L6: a typed search was lost when a filter changed before the page rendered it).
 * `current()` is the search of the last `go()` until the rendered location changes again (back,
 * forward, a link), which then takes over.
 */
export function useSearchNavigation() {
  const navigate = useNavigate();
  const { pathname, search } = useLocation();
  const latest = useRef(search);

  useLayoutEffect(() => {
    latest.current = search;
  }, [search]);

  const current = useCallback(() => new URLSearchParams(latest.current), []);

  /** Navigate to `next` (without the leading `?`) on the current path. */
  const go = useCallback(
    (next: string, options: { replace?: boolean } = {}) => {
      latest.current = next ? `?${next}` : '';
      void navigate({ pathname, search: latest.current }, { replace: options.replace });
    },
    [navigate, pathname],
  );

  return { current, go };
}
