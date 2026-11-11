import { useCallback, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router';
import type { Wishlist } from '@/api/types';
import { useOffline } from '@/auth';
import { useSearchNavigation } from '@/catalog';
import { pushToast } from '@/components/ui/toastStore';
import { useDocumentTitle } from '@/i18n';
import { useWishlistError } from './errors';
import { useReorderWishlists, useWishlistLines, useWishlists } from './queries';

/** `?list=<id>&q=<text>` of `/collection/wishlists`; no list = the default (starred) one. */
function useWishlistParams() {
  const [searchParams] = useSearchParams();
  const { current, go } = useSearchNavigation();
  const raw = searchParams.get('list');
  const listParam = raw && /^\d+$/.test(raw) ? Number(raw) : null;
  const q = searchParams.get('q') ?? '';
  const set = useCallback(
    (patch: { list?: number | null; q?: string }, options: { replace?: boolean } = {}) => {
      const next = current();
      if ('list' in patch) {
        if (patch.list === null || patch.list === undefined) next.delete('list');
        else next.set('list', String(patch.list));
      }
      if ('q' in patch) {
        if (patch.q) next.set('q', patch.q);
        else next.delete('q');
      }
      go(next.toString(), options);
    },
    [current, go],
  );
  return { listParam, q, set };
}

/** Everything the two layouts of `/collection/wishlists` share: the lists, the open list, sheets. */
export function useWishlistsScreen() {
  const { t } = useTranslation('wishlists');
  useDocumentTitle(t('title'));
  const offline = useOffline();
  const message = useWishlistError();
  const lists = useWishlists();
  const reorder = useReorderWishlists();
  const { listParam, q, set } = useWishlistParams();
  const [menuOpen, setMenuOpen] = useState(false);
  const [addOpen, setAddOpen] = useState(false);

  const items = useMemo(() => lists.data?.items ?? [], [lists.data]);
  const defaultList = items.find((item) => item.is_default) ?? items[0] ?? null;
  const selected: Wishlist | null =
    (listParam !== null ? items.find((item) => item.id === listParam) : undefined) ?? defaultList;
  const lines = useWishlistLines(selected?.id ?? null, q);

  /** Opens a list: its id in the URL, and no search. */
  const openList = (id: number) => set({ list: id, q: '' });
  const setQuery = (next: string) => set({ q: next }, { replace: true });

  /** Puts the list `id` at `index` and saves the whole order. */
  const moveTo = (id: number, index: number) => {
    const from = items.findIndex((item) => item.id === id);
    if (offline || from < 0 || index < 0 || index >= items.length || from === index) return;
    const ids = items.map((item) => item.id);
    ids.splice(from, 1);
    ids.splice(index, 0, id);
    reorder.mutate(ids, {
      onError: (error) => pushToast({ kind: 'error', message: message(error) }),
    });
  };
  const moveBy = (id: number, delta: -1 | 1) =>
    moveTo(id, items.findIndex((item) => item.id === id) + delta);

  return {
    t,
    offline,
    lists,
    items,
    defaultList,
    selected,
    lines,
    q,
    openList,
    setQuery,
    moveTo,
    moveBy,
    menuOpen,
    setMenuOpen,
    addOpen,
    setAddOpen,
  };
}

export type WishlistsScreen = ReturnType<typeof useWishlistsScreen>;
