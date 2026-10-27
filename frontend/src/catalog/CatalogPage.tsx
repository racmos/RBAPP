import { useCallback, useEffect, useId, useMemo, useRef, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, Outlet, useLocation, useNavigate, useParams, useSearchParams } from 'react-router';
import type { CardListParams, CardSummary } from '@/api/types';
import { BanBadge, CardImage, DomainPips, PriceTag, RarityDot } from '@/components/card';
import { Button } from '@/components/ui/Button';
import { Checkbox } from '@/components/ui/Checkbox';
import { ChipGroup, FilterChip } from '@/components/ui/FilterChip';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { Field } from '@/components/ui/Field';
import { Icon } from '@/components/ui/Icon';
import { Input } from '@/components/ui/Input';
import { PageHeader } from '@/components/ui/PageHeader';
import { Pagination } from '@/components/ui/Pagination';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { Select } from '@/components/ui/Select';
import { Sheet } from '@/components/ui/Sheet';
import { Skeleton } from '@/components/ui/Skeleton';
import { Switch } from '@/components/ui/Switch';
import { useDocumentTitle, useEnumLabel } from '@/i18n';
import { up } from '@/lib/breakpoints';
import { domainColor, rarityColor } from '@/lib/domains';
import { readStorage, removeStorage, writeStorage } from '@/lib/storage';
import { useMediaQuery } from '@/lib/useMediaQuery';
import { legacyHref } from '@/shell/legacyRoutes';
import {
  DEFAULT_DIR,
  DEFAULT_PAGE,
  DEFAULT_SORT,
  parseCatalogSearch,
  serializeCatalogParams,
  withChange,
} from './params';
import { useCardList, useGameMeta } from './queries';
import type { CardDetailOutletContext } from './context';
import styles from './CatalogPage.module.css';

const SEARCH_DEBOUNCE_MS = 300;
const INPUT_DEBOUNCE_MS = 300;
const VIEW_STORAGE_KEY = 'rb_cards_view';
const SCROLL_STORAGE_KEY = 'rb_cards_scroll';

const SORT_KEYS: Array<NonNullable<CardListParams['sort']>> = [
  'number',
  'name',
  'price',
  'trend_7d',
  'trend_30d',
  'rarity',
  'energy',
  'power',
  'might',
];

type ViewMode = 'grid' | 'list';

function readView(): ViewMode {
  const stored = readStorage(VIEW_STORAGE_KEY);
  return stored === 'list' ? 'list' : 'grid';
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

function useDebouncedCallback<T extends (...args: never[]) => void>(callback: T, delay: number) {
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  return useCallback(
    (...args: Parameters<T>) => {
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => callback(...args), delay);
    },
    [callback, delay],
  );
}

export function CatalogPage() {
  const { t } = useTranslation('cards');
  useDocumentTitle(t('catalog.title'));

  const navigate = useNavigate();
  const location = useLocation();
  const { setId } = useParams<{ setId?: string; cardId?: string }>();
  const isMd = useMediaQuery(up('md'));
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
  const facets = listData?.meta?.facets ?? {};

  const meta = metaQuery.data;
  const isLoading = listQuery.isLoading;
  const isFetching = listQuery.isFetching;
  const isError = listQuery.isError;

  const activeCount = useMemo(() => countActiveFilters(params), [params]);

  const siblings = useMemo(
    () => listData?.data.items.map((item) => ({ setId: item.set_id, cardId: item.card_id })) ?? [],
    [listData],
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

  const handleSearchChange = useDebouncedCallback((value: string) => {
    setParams({ q: value || undefined }, { replace: true });
  }, SEARCH_DEBOUNCE_MS);

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

  const showCatalog = !setId || isMd;

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

          <SearchInput value={params.q ?? ''} onChange={handleSearchChange} />

          <CatalogToolbar
            activeCount={activeCount}
            onOpenFilters={() => setFilterOpen(true)}
            sort={params.sort ?? DEFAULT_SORT}
            dir={params.dir ?? DEFAULT_DIR}
            view={view}
            onSortChange={(sort) => setParams({ sort })}
            onDirChange={(dir) => setParams({ dir })}
            onViewChange={handleViewChange}
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
                {view === 'grid' ? (
                  <CardGrid
                    items={listData?.data.items ?? []}
                    search={location.search}
                    onBeforeNavigate={saveScroll}
                  />
                ) : (
                  <CardList
                    items={listData?.data.items ?? []}
                    search={location.search}
                    onBeforeNavigate={saveScroll}
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

          <FilterSheet
            open={filterOpen}
            onClose={() => setFilterOpen(false)}
            params={params}
            setParams={setParams}
            meta={meta}
            facets={facets}
            total={total}
            resultsRef={resultsRef}
          />
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
  const [local, setLocal] = useState(value);
  const id = useId();

  /* eslint-disable react-hooks/set-state-in-effect -- derived reset on prop change */
  useEffect(() => {
    setLocal(value);
  }, [value]);
  /* eslint-enable react-hooks/set-state-in-effect */

  useEffect(() => {
    const timer = setTimeout(() => {
      if (local !== (value ?? '')) {
        onChange(local);
      }
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [local, onChange, value]);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onChange(local);
  };

  return (
    <form onSubmit={handleSubmit} className={styles.search}>
      <label htmlFor={id} className="sr-only">
        {t('catalog.search.label')}
      </label>
      <Input
        id={id}
        type="search"
        enterKeyHint="search"
        placeholder={t('catalog.search.placeholder')}
        value={local}
        onChange={(event) => setLocal(event.target.value)}
      />
    </form>
  );
}

type CatalogToolbarProps = {
  activeCount: number;
  onOpenFilters: () => void;
  sort: string;
  dir: 'asc' | 'desc';
  view: ViewMode;
  onSortChange: (sort: CardListParams['sort']) => void;
  onDirChange: (dir: 'asc' | 'desc') => void;
  onViewChange: (view: ViewMode) => void;
};

function CatalogToolbar({
  activeCount,
  onOpenFilters,
  sort,
  dir,
  view,
  onSortChange,
  onDirChange,
  onViewChange,
}: CatalogToolbarProps) {
  const { t } = useTranslation('cards');

  const translateKey = (key: string) => (t as (key: string) => string)(key);
  const sortOptions = SORT_KEYS.map((key) => ({
    value: key,
    label: translateKey(`catalog.sort.${key}`),
  }));

  return (
    <div className={styles.toolbar}>
      <Button variant="ghost" size="sm" onClick={onOpenFilters} className={styles.filterButton}>
        {t('catalog.filters.open')}
        {activeCount > 0 && (
          <span className={styles.badge}>
            {activeCount === 1
              ? t('catalog.filters.active_one', { count: activeCount })
              : t('catalog.filters.active_other', { count: activeCount })}
          </span>
        )}
      </Button>

      <Field label={t('catalog.sort.label')}>
        {(props) => (
          <Select
            {...props}
            value={sort}
            onChange={(event) => onSortChange(event.target.value as CardListParams['sort'])}
          >
            {sortOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        )}
      </Field>

      <button
        type="button"
        className={styles.dirButton}
        aria-pressed={dir === 'desc'}
        aria-label={t('catalog.sort.dirLabel')}
        onClick={() => onDirChange(dir === 'asc' ? 'desc' : 'asc')}
      >
        <Icon name="arrow" size={16} className={dir === 'desc' ? styles.dirDesc : styles.dirAsc} />
      </button>

      <SegmentedControl
        label={t('catalog.view.label')}
        options={[
          { value: 'grid', label: t('catalog.view.grid') },
          { value: 'list', label: t('catalog.view.list') },
        ]}
        value={view}
        onChange={onViewChange}
      />
    </div>
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
};

function CardGrid({ items, search, onBeforeNavigate }: CardGridProps) {
  const { t } = useTranslation('cards');
  return (
    <ul className={styles.grid} aria-label={t('catalog.results')} data-view="grid">
      {items.map((card) => (
        <li key={card.key}>
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
                <span className="sr-only">{t('catalog.owned', { count: card.owned.total })}</span>
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
        </li>
      ))}
    </ul>
  );
}

function CardList({ items, search, onBeforeNavigate }: CardGridProps) {
  const { t } = useTranslation('cards');
  const { typeLabel } = useEnumLabel();

  return (
    <ul className={styles.list} aria-label={t('catalog.results')} data-view="list">
      {items.map((card) => (
        <li key={card.key}>
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
        </li>
      ))}
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

type FilterSheetProps = {
  open: boolean;
  onClose: () => void;
  params: CardListParams;
  setParams: (patch: Partial<CardListParams>) => void;
  meta: import('@/api/types').GameMeta | undefined;
  facets: import('@/api/types').CardFacets;
  total: number;
  resultsRef: React.RefObject<HTMLHeadingElement | null>;
};

function FilterSheet({
  open,
  onClose,
  params,
  setParams,
  meta,
  facets,
  total,
  resultsRef,
}: FilterSheetProps) {
  const { t } = useTranslation('cards');
  const { label } = useEnumLabel();
  const debouncedSetParams = useDebouncedCallback(setParams, INPUT_DEBOUNCE_MS);

  const toggleArray = (
    key: 'set' | 'domain' | 'type' | 'supertype' | 'exclude_supertype' | 'rarity' | 'tag',
    value: string,
  ) => {
    const current = params[key] ?? [];
    if (current.includes(value)) {
      setParams({ [key]: current.filter((v) => v !== value) });
    } else {
      setParams({ [key]: [...current, value] });
    }
  };

  const showCount = (
    facet: Record<string, number> | undefined,
    value: string,
  ): number | undefined => {
    const count = facet?.[value];
    return count === undefined ? undefined : count;
  };

  return (
    <Sheet open={open} onClose={onClose} title={t('catalog.filters.title')}>
      <div className={styles.sheetBody}>
        <fieldset className={styles.group}>
          <legend className={styles.legend}>{t('catalog.facet.set')}</legend>
          <div className={styles.checkList}>
            {meta?.sets.map((set) => (
              <Checkbox
                key={set.id}
                label={`${set.name} (${showCount(facets.set, set.id) ?? 0})`}
                checked={params.set?.includes(set.id) ?? false}
                onChange={() => toggleArray('set', set.id)}
              />
            ))}
          </div>
        </fieldset>

        <div className={styles.group}>
          <ChipGroup legend={t('catalog.facet.domain')}>
            {meta?.domains.map((domain) => {
              const selected = params.domain?.includes(domain) ?? false;
              const count = showCount(facets.domain, domain);
              return (
                <FilterChip
                  key={domain}
                  label={label('domain', domain)}
                  count={count}
                  pressed={selected}
                  color={domainColor(domain)}
                  onClick={() => toggleArray('domain', domain)}
                />
              );
            })}
          </ChipGroup>
          <div className={styles.matchControl}>
            <SegmentedControl
              label={t('catalog.facet.domainMatch')}
              options={[
                { value: 'any', label: t('catalog.facet.any') },
                { value: 'all', label: t('catalog.facet.all') },
                { value: 'subset', label: t('catalog.facet.subset') },
              ]}
              value={params.domain_match ?? 'any'}
              onChange={(value) => setParams({ domain_match: value as 'any' | 'all' | 'subset' })}
            />
          </div>
        </div>

        <ChipGroup legend={t('catalog.facet.type')}>
          {meta?.types.map((type) => {
            const selected = params.type?.includes(type) ?? false;
            return (
              <FilterChip
                key={type}
                label={label('type', type)}
                count={showCount(facets.type, type)}
                pressed={selected}
                onClick={() => toggleArray('type', type)}
              />
            );
          })}
        </ChipGroup>

        <ChipGroup legend={t('catalog.facet.supertype')}>
          {meta?.supertypes.map((supertype) => {
            const selected = params.supertype?.includes(supertype) ?? false;
            return (
              <FilterChip
                key={supertype}
                label={label('supertype', supertype)}
                count={showCount(facets.supertype, supertype)}
                pressed={selected}
                onClick={() => toggleArray('supertype', supertype)}
              />
            );
          })}
        </ChipGroup>

        <ChipGroup legend={t('catalog.facet.rarity')}>
          {meta?.rarities.map((rarity) => {
            const selected = params.rarity?.includes(rarity) ?? false;
            return (
              <FilterChip
                key={rarity}
                label={label('rarity', rarity)}
                count={showCount(facets.rarity, rarity)}
                pressed={selected}
                color={rarityColor(rarity)}
                onClick={() => toggleArray('rarity', rarity)}
              />
            );
          })}
        </ChipGroup>

        <RangeGroup
          label={t('catalog.facet.energy')}
          minKey="energy_min"
          maxKey="energy_max"
          min={params.energy_min}
          max={params.energy_max}
          onChange={(patch) => debouncedSetParams(patch)}
        />

        <RangeGroup
          label={t('catalog.facet.power')}
          minKey="power_min"
          maxKey="power_max"
          min={params.power_min}
          max={params.power_max}
          onChange={(patch) => debouncedSetParams(patch)}
        />

        <RangeGroup
          label={t('catalog.facet.might')}
          minKey="might_min"
          maxKey="might_max"
          min={params.might_min}
          max={params.might_max}
          onChange={(patch) => debouncedSetParams(patch)}
        />

        <RangeGroup
          label={t('catalog.facet.price')}
          minKey="price_min"
          maxKey="price_max"
          min={params.price_min}
          max={params.price_max}
          step={0.01}
          onChange={(patch) => debouncedSetParams(patch)}
        />

        <div className={styles.group}>
          <span className={styles.legend}>{t('catalog.facet.owned')}</span>
          <SegmentedControl
            options={[
              { value: 'any', label: t('catalog.facet.ownedAny') },
              { value: 'owned', label: t('catalog.facet.ownedOwned') },
              { value: 'missing', label: t('catalog.facet.ownedMissing') },
            ]}
            value={params.owned ?? 'any'}
            onChange={(value) => setParams({ owned: value as 'any' | 'owned' | 'missing' })}
          />
        </div>

        <div className={styles.group}>
          <label htmlFor="banned_in" className={styles.legend}>
            {t('catalog.facet.banned')}
          </label>
          <Select
            id="banned_in"
            value={params.banned_in ?? ''}
            onChange={(event) =>
              setParams({
                banned_in: event.target.value
                  ? (event.target.value as '1v1' | '2v2' | 'any')
                  : undefined,
              })
            }
          >
            <option value="">{t('catalog.facet.bannedNone')}</option>
            <option value="1v1">{t('catalog.facet.banned1v1')}</option>
            <option value="2v2">{t('catalog.facet.banned2v2')}</option>
            <option value="any">{t('catalog.facet.bannedAny')}</option>
          </Select>
        </div>

        <div className={styles.group}>
          <Switch
            label={t('catalog.facet.baseOnly')}
            checked={params.base_only ?? false}
            onCheckedChange={(checked) => setParams({ base_only: checked || undefined })}
          />
        </div>

        <div className={styles.group}>
          <Field label={t('catalog.facet.text')}>
            {(props) => (
              <Input
                {...props}
                type="search"
                value={params.text ?? ''}
                onChange={(event) => debouncedSetParams({ text: event.target.value || undefined })}
              />
            )}
          </Field>
        </div>

        <ChipGroup legend={t('catalog.facet.tags')}>
          {facets.tag?.map(({ tag, count }) => {
            const selected = params.tag?.includes(tag) ?? false;
            return (
              <FilterChip
                key={tag}
                label={tag}
                count={count}
                pressed={selected}
                onClick={() => toggleArray('tag', tag)}
              />
            );
          })}
        </ChipGroup>
      </div>

      <div className={styles.sheetFooter}>
        <Button variant="ghost" onClick={() => setParams({})}>
          {t('catalog.filters.clear')}
        </Button>
        <Button
          onClick={() => {
            onClose();
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
  );
}

type RangeGroupProps = {
  label: string;
  minKey: 'energy_min' | 'power_min' | 'might_min' | 'price_min';
  maxKey: 'energy_max' | 'power_max' | 'might_max' | 'price_max';
  min: number | undefined;
  max: number | undefined;
  step?: number;
  onChange: (patch: Partial<CardListParams>) => void;
};

function RangeGroup({ label, minKey, maxKey, min, max, step, onChange }: RangeGroupProps) {
  const { t } = useTranslation('cards');
  const debounced = useDebouncedCallback(onChange, INPUT_DEBOUNCE_MS);

  return (
    <fieldset className={styles.group}>
      <legend className={styles.legend}>{label}</legend>
      <div className={styles.range}>
        <Field label={t('catalog.facet.min')}>
          {(props) => (
            <Input
              {...props}
              type="number"
              min={0}
              max={99}
              step={step}
              value={min ?? ''}
              onChange={(event) =>
                debounced({
                  [minKey]: event.target.value === '' ? undefined : Number(event.target.value),
                })
              }
            />
          )}
        </Field>
        <Field label={t('catalog.facet.max')}>
          {(props) => (
            <Input
              {...props}
              type="number"
              min={0}
              max={99}
              step={step}
              value={max ?? ''}
              onChange={(event) =>
                debounced({
                  [maxKey]: event.target.value === '' ? undefined : Number(event.target.value),
                })
              }
            />
          )}
        </Field>
      </div>
    </fieldset>
  );
}
