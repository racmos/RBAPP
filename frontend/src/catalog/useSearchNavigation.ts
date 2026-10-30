import { useCallback, useLayoutEffect, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router';

/**
 * URL search changes built on the latest search asked for, not on the rendered one. The router
 * applies a navigation inside a React transition (and after the route loaders), so for a while
 * `useSearchParams` still shows the old URL; a change built from it drops the change made just
 * before (L6: a typed search was lost when a filter changed before the page rendered it).
 * `current()` is the search of the last `go()`; the page rendering the searches it asked for, one
 * by one, never takes it back to an earlier one. A location it did not ask for (back, forward, a
 * link) takes over.
 */
export function useSearchNavigation() {
  const navigate = useNavigate();
  const { pathname, search } = useLocation();
  const latest = useRef(search);
  // searches asked for by `go()` that the page has not rendered yet, oldest first
  const pending = useRef<string[]>([]);
  const rendered = useRef(search);

  useLayoutEffect(() => {
    const index = pending.current.indexOf(search);
    if (index >= 0) {
      // the router renders queued navigations one by one: an intermediate one must not take
      // `latest` back while later ones are still on their way
      pending.current.splice(0, index + 1);
      if (pending.current.length > 0) return;
    } else {
      // a location this hook did not ask for (back, forward, a link) takes over
      pending.current = [];
    }
    latest.current = search;
  }, [search]);
  useLayoutEffect(() => {
    rendered.current = search;
  }, [search]);

  const current = useCallback(() => new URLSearchParams(latest.current), []);

  /** Navigate to `next` (without the leading `?`) on the current path. */
  const go = useCallback(
    (next: string, options: { replace?: boolean } = {}) => {
      latest.current = next ? `?${next}` : '';
      // a navigation to the search already on screen renders nothing new: nothing to wait for
      if (pending.current.length > 0 || latest.current !== rendered.current) {
        pending.current.push(latest.current);
      }
      void navigate({ pathname, search: latest.current }, { replace: options.replace });
    },
    [navigate, pathname],
  );

  /**
   * `useSearchParams`' setter, built on `current()` instead of the rendered search: its function
   * form gets the latest search asked for, so two quick changes both stay. A change that leaves
   * the search as it is navigates nowhere.
   */
  const setSearchParams = useCallback(
    (
      nextInit: URLSearchParams | ((previous: URLSearchParams) => URLSearchParams),
      options: { replace?: boolean } = {},
    ) => {
      const previous = current();
      const next =
        typeof nextInit === 'function' ? nextInit(new URLSearchParams(previous)) : nextInit;
      // a navigation to the same search still remounts the route and drops open dialogs
      if (next.toString() === previous.toString()) return;
      go(next.toString(), options);
    },
    [current, go],
  );

  return { current, go, setSearchParams };
}
