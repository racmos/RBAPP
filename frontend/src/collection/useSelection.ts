import { useCallback, useMemo, useState } from 'react';

/**
 * The selected line ids (F3-h S4). They belong to one set of filters: when `scope` changes the
 * selection is empty again, without an effect.
 */
export function useSelection(scope: string) {
  const [state, setState] = useState<{ scope: string; ids: ReadonlySet<number> }>({
    scope,
    ids: new Set(),
  });
  const ids = useMemo(
    () => (state.scope === scope ? state.ids : new Set<number>()),
    [state, scope],
  );

  const toggle = useCallback(
    (changed: number[], on: boolean) =>
      setState((current) => {
        const next = new Set(current.scope === scope ? current.ids : []);
        for (const id of changed) {
          if (on) next.add(id);
          else next.delete(id);
        }
        return { scope, ids: next };
      }),
    [scope],
  );
  const replace = useCallback((all: number[]) => setState({ scope, ids: new Set(all) }), [scope]);
  const clear = useCallback(() => setState({ scope, ids: new Set() }), [scope]);

  return { ids, toggle, replace, clear };
}
