import { useCallback, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation, useNavigate, useSearchParams } from 'react-router';
import type { CollectionGroup, CollectionParams } from '@/api/types';
import { useGameMeta } from '@/catalog';
import { useOffline } from '@/auth';
import { useDocumentTitle, useEnumLabel } from '@/i18n';
import type { Lang } from '@/lib/format';
import { usePrefs } from '@/prefs';
import {
  activeFilterCount,
  parseCollectionSearch,
  serializeCollectionParams,
  withChange,
} from './params';
import { useCollectionList } from './queries';

function useCollectionParams() {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const params = useMemo(() => parseCollectionSearch(searchParams), [searchParams]);
  const setParams = useCallback(
    (patch: Partial<CollectionParams>, options: { replace?: boolean } = {}) => {
      const query = serializeCollectionParams(withChange(params, patch));
      navigate(
        { pathname: location.pathname, search: query ? `?${query}` : '' },
        { replace: options.replace },
      );
    },
    [params, navigate, location.pathname],
  );
  return [params, setParams] as const;
}

/** Everything the two layouts of `/collection` share: URL params, the list, the open sheets. */
export function useCollectionScreen(desktop: boolean) {
  const { t, i18n } = useTranslation('collection');
  useDocumentTitle(t('title'));
  const lang: Lang = i18n.language.split('-')[0] === 'en' ? 'en' : 'es';
  const offline = useOffline();
  const { prefs } = usePrefs();
  const { label } = useEnumLabel();
  const [params, setParams] = useCollectionParams();
  const gameMeta = useGameMeta();
  const list = useCollectionList(params);

  const [view, setView] = useState<'grid' | 'list' | 'table'>(() =>
    prefs.collection_view === 'grid'
      ? 'grid'
      : prefs.collection_view === 'table' || desktop
        ? 'table'
        : 'grid',
  );
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [open, setOpen] = useState<{ key: string; group: CollectionGroup } | null>(null);

  const data = list.data;
  const items = useMemo(() => data?.data.items ?? [], [data]);
  const meta = data?.meta;
  const totals = meta?.totals;
  const playsetSize = meta?.playset_size ?? 3;
  const filterCount = activeFilterCount(params);

  // The open sheet follows its group through the reloads that saving causes; if the group is not
  // in the list any more once the list is up to date (deleted, or filtered out), it goes away.
  const live = open ? items.find((group) => group.key === open.key) : undefined;
  const openGroup = open && (live ?? (list.isFetching ? open.group : undefined));

  const clearFilters = (alsoSearch = false) =>
    setParams({
      ...(alsoSearch ? { q: undefined } : {}),
      set: undefined,
      domain: undefined,
      type: undefined,
      rarity: undefined,
      condition: undefined,
      language: undefined,
      foil: undefined,
      selling: undefined,
      has_purchase: undefined,
    });

  return {
    t,
    i18n,
    lang,
    offline,
    label,
    params,
    setParams,
    gameMeta,
    list,
    items,
    meta,
    totals,
    playsetSize,
    filterCount,
    view,
    setView,
    filtersOpen,
    setFiltersOpen,
    addOpen,
    setAddOpen,
    open,
    setOpen,
    openGroup,
    clearFilters,
  };
}

export type CollectionScreen = ReturnType<typeof useCollectionScreen>;
