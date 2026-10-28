import { useCallback, useEffect, useId, useMemo, useRef, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, Outlet, useLocation, useNavigate, useParams, useSearchParams } from 'react-router';
import type { CardListParams, CardSummary } from '@/api/types';
import { BanBadge, CardImage, DomainPips, PriceTag, RarityDot } from '@/components/card';
import { Button } from '@/components/ui/Button';
import { FilterChip } from '@/components/ui/FilterChip';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { PageHeader } from '@/components/ui/PageHeader';
import { Pagination } from '@/components/ui/Pagination';
import { Sheet } from '@/components/ui/Sheet';
import { Skeleton } from '@/components/ui/Skeleton';
import { useDocumentTitle, useEnumLabel } from '@/i18n';
import { up } from '@/lib/breakpoints';
import { readStorage, removeStorage, writeStorage } from '@/lib/storage';
import { useMediaQuery } from '@/lib/useMediaQuery';
import { legacyHref } from '@/shell/legacyRoutes';
import { CatalogFilters } from './CatalogFilters';
import { CatalogPreview } from './CatalogPreview';
import { CatalogTable } from './CatalogTable';
import { CatalogToolbar } from './CatalogToolbar';
import type { CardDetailOutletContext } from './context';
import {
  DEFAULT_DIR,
  DEFAULT_PAGE,
  DEFAULT_SORT,
  parseCatalogSearch,
  serializeCatalogParams,
  withChange,
} from './params';
import { useCardList, useGameMeta } from './queries';
import { DebouncedInput } from './DebouncedInput';
import styles from './CatalogPage.module.css';

const SEARCH_DEBOUNCE_MS = 300;
const VIEW_STORAGE_KEY = 'rb_cards_view';
const SCROLL_STORAGE_KEY = 'rb_cards_scroll';
type ViewMode = 'grid' | 'list' | 'table';

function readView(): ViewMode {
  const stored = readStorage(VIEW_STORAGE_KEY);
  return stored === 'list' || stored === 'table' ? stored : 'grid';
}

function writeView(view: ViewMode): void {
  writeStorage(VIEW_STORAGE_KEY, view);
}

function scrollKey(search: string): string {
  return `${SCROLL_STORAGE_KEY}:${search}`;
}

function useCatalogParams() {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();

  const params = useMemo(() => parseCatalogSearch(searchParams), [searchParams]);

  const setParams = useCallback(
    (patch: Partial<CardListParams>, opts: { replace?: boolean } = {}) => {
      const next = withChange(params, patch);
      const query = serializeCatalogParams(next);
      navigate(
        {
          pathname: location.pathname,
          search: query ? `?${query}` : '',
        },
        { replace: opts.replace },
      );
    },
    [params, navigate, location.pathname],
  );

  return [params, setParams] as const;
}

export function CatalogPage() {
  const { t } = useTranslation('cards');
  useDocumentTitle(t('catalog.title'));

  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const { setId } = useParams<{ setId?: string; cardId?: string }>();
  const isMd = useMediaQuery(up('md'));
  const isXl = useMediaQuery(up('xl'));
  const isWide = useMediaQuery(up('2xl'));
  const [params, setParams] = useCatalogParams();
  const metaQuery = useGameMeta();
  const listQuery = useCardList(params);
  const resultsRef = useRef<HTMLHeadingElement>(null);

  const [filterOpen, setFilterOpen] = useState(false);
  const [view, setView] = useState<ViewMode>(readView());

  // Scroll restoration: save before leaving to a detail page, restore when back.
  useEffect(() => {
    if (setId) return;
    const key = scrollKey(location.search);
    const saved = readStorage(key, 'session');
    if (saved !== null) {
      const y = Number(saved);
      if (Number.isFinite(y)) {
        window.scrollTo({ top: y });
      }
      removeStorage(key, 'session');
    }
  }, [setId, location.search]);

  const listData = listQuery.data;
  const total = listData?.meta?.total ?? 0;
  const pages = listData?.meta?.pages ?? 0;
  const page = listData?.meta?.page ?? params.page ?? DEFAULT_PAGE;
  const perPage = listData?.meta?.per_page ?? params.per_page ?? 48;
  const facets = listData?.meta?.facets ?? {};
  const items = useMemo(() => listData?.data.items ?? [], [listData]);

  const meta = metaQuery.data;
  const isLoading = listQuery.isLoading;
  const isFetching = listQuery.isFetching;
  const isError = listQuery.isError;
  // S6: the sidebar dims its counts only when a refetch lasts longer than
  // 300 ms, so fast refetches never flicker. The results region keeps the
  // immediate `aria-busy` (F2-h behaviour).
  const [sidebarBusy, setSidebarBusy] = useState(false);
  /* eslint-disable react-hooks/set-state-in-effect -- delayed busy flag reset */
  useEffect(() => {
    if (!isFetching) {
      setSidebarBusy(false);
      return;
    }
    const timer = setTimeout(() => setSidebarBusy(true), 300);
    return () => clearTimeout(timer);
  }, [isFetching]);
  /* eslint-enable react-hooks/set-state-in-effect */

  const activeCount = useMemo(() => countActiveFilters(params), [params]);

  const siblings = useMemo(
    () => items.map((item) => ({ setId: item.set_id, cardId: item.card_id })),
    [items],
  );

  const onClose = useCallback(() => {
    navigate({ pathname: '/cards', search: location.search }, { replace: true });
  }, [navigate, location.search]);

  const context: CardDetailOutletContext =
    setId && isMd ? { presentation: 'modal', siblings, onClose } : { presentation: 'page' };

  const handleViewChange = (value: ViewMode) => {
    setView(value);
    writeView(value);
  };

  const handlePerPageChange = (nextPerPage: 48 | 96 | 192) => {
    setParams({ per_page: nextPerPage });
  };

  const handleSearchChange = (value: string) => {
    setParams({ q: value || undefined }, { replace: true });
  };

  const handlePageChange = (nextPage: number) => {
    setParams({ page: nextPage });
    resultsRef.current?.focus();
    resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const handleClearFilters = () => {
    setParams({
      q: undefined,
      text: undefined,
      set: undefined,
      domain: undefined,
      type: undefined,
      supertype: undefined,
      exclude_supertype: undefined,
      rarity: undefined,
      tag: undefined,
      domain_match: 'any',
      energy_min: undefined,
      energy_max: undefined,
      power_min: undefined,
      power_max: undefined,
      might_min: undefined,
      might_max: undefined,
      price_min: undefined,
      price_max: undefined,
      owned: 'any',
      banned_in: undefined,
      base_only: undefined,
    });
  };

  // Wide preview selection.
  const selectedParam = searchParams.get('selected');
  const selectedKey = useMemo(() => {
    if (!isWide || view === 'table') return null;
    const found = items.find((card) => card.key === selectedParam);
    return found?.key ?? items[0]?.key ?? null;
  }, [items, selectedParam, isWide, view]);

  const selectedCard = useMemo(
    () => (selectedKey ? (items.find((card) => card.key === selectedKey) ?? null) : null),
    [items, selectedKey],
  );

  const handleSelectCard = useCallback(
    (card: CardSummary) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          next.set('selected', card.key);
          return next;
        },
        { replace: true },
      );
    },
    [setSearchParams],
  );

  const showCatalog = !setId || isMd;
  const effectiveView: 'grid' | 'list' | 'table' =
    view === 'table' && isMd ? 'table' : view === 'list' ? 'list' : 'grid';

  return (
    <>
      {showCatalog && (
        <div className={styles.page}>
          <PageHeader
            title={t('catalog.title')}
            subtitle={
              total === 1
                ? t('catalog.count_one', { count: total })
                : t('catalog.count_other', { count: total })
            }
            actions={
              <a href={legacyHref('cards')} className={styles.classic}>
                {t('catalog.classic')}
              </a>
            }
          />

          <div
            className={styles.layout}
            data-wide={isWide && effectiveView !== 'table' ? 'true' : undefined}
          >
            {isXl && (
              <CatalogFilters
                mode="sidebar"
                params={params}
                setParams={setParams}
                meta={meta}
                facets={facets}
                total={total}
                activeCount={activeCount}
                onClear={handleClearFilters}
                isBusy={sidebarBusy}
              />
            )}

            <div className={styles.mainColumn}>
              <SearchInput value={params.q ?? ''} onChange={handleSearchChange} />

              <CatalogToolbar
                activeCount={activeCount}
                total={total}
                showSidebar={isXl}
                showPageSize={isXl}
                sort={params.sort ?? DEFAULT_SORT}
                dir={params.dir ?? DEFAULT_DIR}
                view={view}
                perPage={perPage as 48 | 96 | 192}
                tableEnabled={isMd}
                onOpenFilters={() => setFilterOpen(true)}
                onSortChange={(sort) => setParams({ sort })}
                onDirChange={(dir) => setParams({ dir })}
                onViewChange={handleViewChange}
                onPerPageChange={handlePerPageChange}
              />

              <ActiveFilters
                params={params}
                facets={facets}
                setParams={setParams}
                onClear={handleClearFilters}
              />

              <h2 ref={resultsRef} tabIndex={-1} className="sr-only">
                {t('catalog.results')}
              </h2>

              <section
                className={styles.results}
                aria-busy={isFetching || undefined}
                aria-live="polite"
                data-dimmed={isFetching && !isLoading ? 'true' : undefined}
              >
                {isLoading && !isError && (
                  <div className={styles.loading}>
                    <span className="sr-only">{t('catalog.loading')}</span>
                    <CardGridSkeleton />
                  </div>
                )}

                {!isLoading && isError && (
                  <ErrorState
                    message={listQuery.error?.message ?? t('catalog.loading')}
                    onRetry={() => listQuery.refetch()}
                  />
                )}

                {!isLoading && !isError && total === 0 && (
                  <EmptyState
                    icon="info"
                    title={t('catalog.empty.title')}
                    body={t('catalog.empty.body')}
                    action={{ label: t('catalog.filters.clearAll'), onAction: handleClearFilters }}
                  />
                )}

                {!isLoading && !isError && total > 0 && (
                  <>
                    {effectiveView === 'table' ? (
                      <CatalogTable
                        items={items}
                        sort={params.sort ?? DEFAULT_SORT}
                        dir={params.dir ?? DEFAULT_DIR}
                        onSort={(sort, dir) => setParams({ sort, dir })}
                        isWide={isXl}
                      />
                    ) : effectiveView === 'grid' ? (
                      <CardGrid
                        items={items}
                        search={location.search}
                        onBeforeNavigate={saveScroll}
                        selectable={isWide}
                        selectedKey={selectedCard?.key ?? null}
                        onSelect={handleSelectCard}
                      />
                    ) : (
                      <CardList
                        items={items}
                        search={location.search}
                        onBeforeNavigate={saveScroll}
                        selectable={isWide}
                        selectedKey={selectedCard?.key ?? null}
                        onSelect={handleSelectCard}
                      />
                    )}
                    {pages > 1 && (
                      <div className={styles.pagination}>
                        <Pagination page={page} pages={pages} onChange={handlePageChange} />
                      </div>
                    )}
                  </>
                )}
              </section>
            </div>

            {isWide && effectiveView !== 'table' && (
              <CatalogPreview card={selectedCard} items={items} search={location.search} />
            )}
          </div>

          {!isXl && (
            <Sheet
              open={filterOpen}
              onClose={() => setFilterOpen(false)}
              title={t('catalog.filters.title')}
            >
              <CatalogFilters
                mode="sheet"
                params={params}
                setParams={setParams}
                meta={meta}
                facets={facets}
                total={total}
                activeCount={activeCount}
                onClear={handleClearFilters}
                resultsRef={resultsRef}
                onClose={() => setFilterOpen(false)}
              />
              <div className={styles.sheetFooter}>
                <Button variant="ghost" onClick={handleClearFilters}>
                  {t('catalog.filters.clear')}
                </Button>
                <Button
                  onClick={() => {
                    setFilterOpen(false);
                    resultsRef.current?.focus();
                    resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
                  }}
                >
                  {total === 1
                    ? t('catalog.filters.show_one', { count: total })
                    : t('catalog.filters.show_other', { count: total })}
                </Button>
              </div>
            </Sheet>
          )}
        </div>
      )}

      <Outlet context={context} />
    </>
  );
}

function saveScroll(): void {
  writeStorage(scrollKey(window.location.search), String(window.scrollY), 'session');
}

function countActiveFilters(params: CardListParams): number {
  let count = 0;
  if (params.q) count++;
  if (params.text) count++;
  count += params.set?.length ?? 0;
  count += params.domain?.length ?? 0;
  count += params.type?.length ?? 0;
  count += params.supertype?.length ?? 0;
  count += params.exclude_supertype?.length ?? 0;
  count += params.rarity?.length ?? 0;
  count += params.tag?.length ?? 0;
  if (params.domain_match && params.domain_match !== 'any') count++;
  if (params.energy_min !== undefined) count++;
  if (params.energy_max !== undefined) count++;
  if (params.power_min !== undefined) count++;
  if (params.power_max !== undefined) count++;
  if (params.might_min !== undefined) count++;
  if (params.might_max !== undefined) count++;
  if (params.price_min !== undefined) count++;
  if (params.price_max !== undefined) count++;
  if (params.owned && params.owned !== 'any') count++;
  if (params.banned_in) count++;
  if (params.base_only) count++;
  return count;
}

type SearchInputProps = {
  value: string;
  onChange: (value: string) => void;
};

function SearchInput({ value, onChange }: SearchInputProps) {
  const { t } = useTranslation('cards');
  const id = useId();

  return (
    <form
      onSubmit={(event: FormEvent<HTMLFormElement>) => event.preventDefault()}
      className={styles.search}
    >
      <label htmlFor={id} className="sr-only">
        {t('catalog.search.label')}
      </label>
      <DebouncedInput
        id={id}
        type="search"
        enterKeyHint="search"
        placeholder={t('catalog.search.placeholder')}
        value={value}
        delay={SEARCH_DEBOUNCE_MS}
        onCommit={onChange}
      />
    </form>
  );
}

type ActiveFiltersProps = {
  params: CardListParams;
  facets: import('@/api/types').CardFacets;
  setParams: (patch: Partial<CardListParams>) => void;
  onClear: () => void;
};

function ActiveFilters({ params, setParams, onClear }: ActiveFiltersProps) {
  const { t } = useTranslation('cards');
  const { label } = useEnumLabel();
  const translate = useCallback((key: string) => (t as (key: string) => string)(key), [t]);
  const chips = useMemo(() => buildChips(params, label, translate), [params, label, translate]);

  if (chips.length === 0) return null;

  return (
    <div className={styles.activeFilters}>
      <div
        className={styles.chipList}
        role="list"
        aria-label={t('catalog.filters.active_other', { count: chips.length })}
      >
        {chips.map((chip) => (
          <span key={chip.key} role="listitem">
            <FilterChip
              label={chip.label}
              onRemove={{
                'aria-label': t('catalog.filters.remove', { label: chip.label }),
                onClick: () => setParams(chip.remove()),
              }}
            />
          </span>
        ))}
      </div>
      <Button variant="ghost" size="sm" onClick={onClear}>
        {t('catalog.filters.clearAll')}
      </Button>
    </div>
  );
}

type ChipDef = {
  key: string;
  label: string;
  remove: () => Partial<CardListParams>;
};

function buildChips(
  params: CardListParams,
  translateValue: (kind: 'domain' | 'type' | 'supertype' | 'rarity', value: string) => string,
  t: (key: string, options?: Record<string, unknown>) => string,
): ChipDef[] {
  const chips: ChipDef[] = [];

  if (params.q) {
    chips.push({ key: 'q', label: `"${params.q}"`, remove: () => ({ q: undefined }) });
  }
  if (params.text) {
    chips.push({ key: 'text', label: `"${params.text}"`, remove: () => ({ text: undefined }) });
  }

  const listChip = (
    key: keyof CardListParams,
    values: string[] | undefined,
    translateValue: (v: string) => string,
  ) => {
    if (!values) return;
    for (const value of values) {
      chips.push({
        key: `${key}:${value}`,
        label: translateValue(value),
        remove: () => ({ [key]: values.filter((v) => v !== value) }),
      });
    }
  };

  listChip('set', params.set, (v) => v);
  listChip('domain', params.domain, (v) => translateValue('domain', v));
  listChip('type', params.type, (v) => translateValue('type', v));
  listChip('supertype', params.supertype, (v) => translateValue('supertype', v));
  listChip('rarity', params.rarity, (v) => translateValue('rarity', v));
  listChip('tag', params.tag, (v) => v);

  if (params.domain_match && params.domain_match !== 'any') {
    chips.push({
      key: 'domain_match',
      label: t(`catalog.facet.${params.domain_match}` as never),
      remove: () => ({ domain_match: 'any' }),
    });
  }

  const rangeChip = (
    key:
      | 'energy_min'
      | 'energy_max'
      | 'power_min'
      | 'power_max'
      | 'might_min'
      | 'might_max'
      | 'price_min'
      | 'price_max',
    labelKey: string,
  ) => {
    const value = params[key];
    if (value === undefined) return;
    const isMin = key.endsWith('_min');
    const label = t(`catalog.facet.${labelKey}` as never);
    chips.push({
      key,
      label: t(isMin ? 'catalog.chip.min' : 'catalog.chip.max', { label, value }),
      remove: () => ({ [key]: undefined }),
    });
  };

  rangeChip('energy_min', 'energy');
  rangeChip('energy_max', 'energy');
  rangeChip('power_min', 'power');
  rangeChip('power_max', 'power');
  rangeChip('might_min', 'might');
  rangeChip('might_max', 'might');
  rangeChip('price_min', 'price');
  rangeChip('price_max', 'price');

  if (params.owned && params.owned !== 'any') {
    chips.push({
      key: 'owned',
      label: t(`catalog.facet.owned${params.owned === 'owned' ? 'Owned' : 'Missing'}` as never),
      remove: () => ({ owned: 'any' }),
    });
  }

  if (params.banned_in) {
    chips.push({
      key: 'banned_in',
      label: t(
        `catalog.facet.banned${params.banned_in === '1v1' ? '1v1' : params.banned_in === '2v2' ? '2v2' : 'Any'}` as never,
      ),
      remove: () => ({ banned_in: undefined }),
    });
  }

  if (params.base_only) {
    chips.push({
      key: 'base_only',
      label: t('catalog.facet.baseOnly'),
      remove: () => ({ base_only: undefined }),
    });
  }

  return chips;
}

type CardGridProps = {
  items: CardSummary[];
  search: string;
  onBeforeNavigate: () => void;
  selectable?: boolean;
  selectedKey?: string | null;
  onSelect?: (card: CardSummary) => void;
};

function CardGrid({
  items,
  search,
  onBeforeNavigate,
  selectable,
  selectedKey,
  onSelect,
}: CardGridProps) {
  const { t } = useTranslation('cards');
  return (
    <ul className={styles.grid} aria-label={t('catalog.results')} data-view="grid">
      {items.map((card) => {
        const isSelected = selectable && selectedKey === card.key;
        return (
          <li key={card.key}>
            {selectable ? (
              <button
                type="button"
                className={styles.tile}
                aria-pressed={isSelected}
                onClick={() => onSelect?.(card)}
              >
                <div className={styles.tileImage}>
                  <CardImage card={card} size="tile" decorative />
                  {card.owned.total > 0 && (
                    <span className={styles.ownedBadge} aria-hidden="true">
                      ×{card.owned.total}
                    </span>
                  )}
                  {card.owned.total > 0 && (
                    <span className="sr-only">
                      {t('catalog.owned', { count: card.owned.total })}
                    </span>
                  )}
                  <span className={styles.banBadge}>
                    <BanBadge bans={card.bans} variant="compact" />
                  </span>
                </div>
                <span className={styles.tileName}>{card.name}</span>
                <span className={styles.tileId}>
                  {card.set_id} · #{card.card_id}
                </span>
                <div className={styles.tileFooter}>
                  <DomainPips domains={card.domains} size={16} />
                  <PriceTag price={card.price} size="sm" />
                </div>
              </button>
            ) : (
              <Link
                className={styles.tile}
                to={{ pathname: `/cards/${card.set_id}/${card.card_id}`, search }}
                onClick={onBeforeNavigate}
              >
                <div className={styles.tileImage}>
                  <CardImage card={card} size="tile" decorative />
                  {card.owned.total > 0 && (
                    <span className={styles.ownedBadge} aria-hidden="true">
                      ×{card.owned.total}
                    </span>
                  )}
                  {card.owned.total > 0 && (
                    <span className="sr-only">
                      {t('catalog.owned', { count: card.owned.total })}
                    </span>
                  )}
                  <span className={styles.banBadge}>
                    <BanBadge bans={card.bans} variant="compact" />
                  </span>
                </div>
                <span className={styles.tileName}>{card.name}</span>
                <span className={styles.tileId}>
                  {card.set_id} · #{card.card_id}
                </span>
                <div className={styles.tileFooter}>
                  <DomainPips domains={card.domains} size={16} />
                  <PriceTag price={card.price} size="sm" />
                </div>
              </Link>
            )}
          </li>
        );
      })}
    </ul>
  );
}

function CardList({
  items,
  search,
  onBeforeNavigate,
  selectable,
  selectedKey,
  onSelect,
}: CardGridProps) {
  const { t } = useTranslation('cards');
  const { typeLabel } = useEnumLabel();

  return (
    <ul className={styles.list} aria-label={t('catalog.results')} data-view="list">
      {items.map((card) => {
        const isSelected = selectable && selectedKey === card.key;
        return (
          <li key={card.key}>
            {selectable ? (
              <button
                type="button"
                className={styles.row}
                aria-pressed={isSelected}
                onClick={() => onSelect?.(card)}
              >
                <CardImage card={card} size="thumb" decorative />
                <div className={styles.rowMain}>
                  <span className={styles.rowName}>{card.name}</span>
                  <span className={styles.rowMeta}>
                    {card.set_id} · #{card.card_id} · {typeLabel(card.supertype, card.type)}
                  </span>
                </div>
                <div className={styles.rowPips}>
                  <DomainPips domains={card.domains} size={16} />
                </div>
                <RarityDot rarity={card.rarity} />
                <PriceTag price={card.price} size="sm" trend="7d" />
                {card.owned.total > 0 && (
                  <span
                    className={styles.rowOwned}
                    aria-label={t('catalog.owned', { count: card.owned.total })}
                  >
                    ×{card.owned.total}
                  </span>
                )}
                <BanBadge bans={card.bans} variant="compact" />
              </button>
            ) : (
              <Link
                className={styles.row}
                to={{ pathname: `/cards/${card.set_id}/${card.card_id}`, search }}
                onClick={onBeforeNavigate}
              >
                <CardImage card={card} size="thumb" decorative />
                <div className={styles.rowMain}>
                  <span className={styles.rowName}>{card.name}</span>
                  <span className={styles.rowMeta}>
                    {card.set_id} · #{card.card_id} · {typeLabel(card.supertype, card.type)}
                  </span>
                </div>
                <div className={styles.rowPips}>
                  <DomainPips domains={card.domains} size={16} />
                </div>
                <RarityDot rarity={card.rarity} />
                <PriceTag price={card.price} size="sm" trend="7d" />
                {card.owned.total > 0 && (
                  <span
                    className={styles.rowOwned}
                    aria-label={t('catalog.owned', { count: card.owned.total })}
                  >
                    ×{card.owned.total}
                  </span>
                )}
                <BanBadge bans={card.bans} variant="compact" />
              </Link>
            )}
          </li>
        );
      })}
    </ul>
  );
}

function CardGridSkeleton() {
  return (
    <ul className={styles.grid}>
      {Array.from({ length: 12 }).map((_, index) => (
        <li key={index} className={styles.skeletonTile}>
          <Skeleton label="" lines={3} />
        </li>
      ))}
    </ul>
  );
}
