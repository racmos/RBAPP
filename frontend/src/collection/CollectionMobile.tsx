import { Link } from 'react-router';
import { DebouncedInput } from '@/catalog';
import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { FilterChip } from '@/components/ui/FilterChip';
import { Icon } from '@/components/ui/Icon';
import { PageHeader } from '@/components/ui/PageHeader';
import { Pagination } from '@/components/ui/Pagination';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { Select } from '@/components/ui/Select';
import { Sheet } from '@/components/ui/Sheet';
import { Skeleton } from '@/components/ui/Skeleton';
import type { CollectionSort } from '@/api/types';
import { formatMoney } from '@/lib/format';
import { legacyHref } from '@/shell/legacyRoutes';
import { AddSheet } from './AddSheet';
import { CollectionFilters } from './CollectionFilters';
import { CollectionItem } from './CollectionItem';
import { ExportDialog } from './ExportDialog';
import { LineSheet } from './LineSheet';
import { DEFAULT_PAGE } from './params';
import type { CollectionScreen } from './useCollectionScreen';
import styles from './CollectionPage.module.css';

const SORTS: CollectionSort[] = [
  'number',
  'name',
  'price',
  'qty',
  'value',
  'pl',
  'trend_7d',
  'updated',
  'rarity',
];
const SEARCH_DELAY_MS = 300;

/** The layout below 1240 px (F3-g). */
export function CollectionMobile({ s }: { s: CollectionScreen }) {
  const {
    t,
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
    view: storedView,
    setView,
    filtersOpen,
    setFiltersOpen,
    addOpen,
    setAddOpen,
    exportOpen,
    setExportOpen,
    setOpen,
    openGroup,
    clearFilters,
  } = s;
  const view: 'grid' | 'list' = storedView === 'grid' ? 'grid' : 'list';
  const chip = (key: string, text: string, remove: () => void) => (
    <FilterChip
      key={key}
      label={text}
      pressed
      onRemove={{ 'aria-label': t('filters.remove', { label: text }), onClick: remove }}
    />
  );

  const chips = () => {
    const out = [];
    const lists = [
      ['set', (v: string) => v],
      ['domain', (v: string) => label('domain', v)],
      ['type', (v: string) => label('type', v)],
      ['rarity', (v: string) => label('rarity', v)],
      ['condition', (v: string) => label('condition', v)],
      ['language', (v: string) => label('language', v)],
    ] as const;
    for (const [key, text] of lists) {
      for (const value of params[key] ?? []) {
        out.push(
          chip(`${key}:${value}`, text(value), () =>
            setParams({ [key]: (params[key] ?? []).filter((item) => item !== value) }),
          ),
        );
      }
    }
    if (params.foil && params.foil !== 'any') {
      out.push(
        chip('foil', t(params.foil === 'foil' ? 'filters.foilOnly' : 'filters.nonfoilOnly'), () =>
          setParams({ foil: undefined }),
        ),
      );
    }
    if (params.selling && params.selling !== 'any') {
      out.push(
        chip(
          'selling',
          `${t('filters.selling')}: ${t(params.selling === 'yes' ? 'filters.yes' : 'filters.no')}`,
          () => setParams({ selling: undefined }),
        ),
      );
    }
    if (params.has_purchase && params.has_purchase !== 'any') {
      out.push(
        chip(
          'has_purchase',
          `${t('filters.hasPurchase')}: ${t(params.has_purchase === 'yes' ? 'filters.yes' : 'filters.no')}`,
          () => setParams({ has_purchase: undefined }),
        ),
      );
    }
    return out;
  };

  const noCollection =
    !list.isLoading && !list.isError && meta?.totals.lines === 0 && filterCount === 0 && !params.q;

  let results;
  if (list.isLoading) {
    results = <Skeleton label={t('loading')} lines={6} />;
  } else if (list.isError) {
    results = <ErrorState message={t('error')} onRetry={() => void list.refetch()} />;
  } else if (noCollection) {
    results = (
      <>
        <EmptyState
          icon="collection"
          title={t('empty.title')}
          body={t('empty.body')}
          action={{ label: t('add.open'), onAction: () => setAddOpen(true) }}
        />
        <p className={styles.importLink}>
          <Link to="/collection/import">{t('empty.import')}</Link>
        </p>
      </>
    );
  } else if (items.length === 0) {
    results = (
      <EmptyState
        icon="search"
        title={t('emptyFilters')}
        action={{ label: t('clearFilters'), onAction: () => clearFilters(true) }}
      />
    );
  } else {
    results = (
      <ul className={styles[view]} aria-busy={list.isFetching || undefined}>
        {items.map((group) => (
          <li key={group.key}>
            <CollectionItem
              group={group}
              variant={view === 'grid' ? 'tile' : 'row'}
              playsetSize={playsetSize}
              onOpen={() => setOpen({ key: group.key, group })}
            />
          </li>
        ))}
      </ul>
    );
  }

  return (
    <div className={styles.page}>
      <PageHeader
        title={t('title')}
        subtitle={
          totals
            ? t('summary.line', {
                qty: totals.qty,
                unique: totals.unique,
                value: formatMoney(totals.value),
              })
            : undefined
        }
        actions={
          <>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setExportOpen(true)}
              disabled={offline}
            >
              {t('export.open')}
            </Button>
            <Link className={styles.tool} to="/collection/import">
              {t('import.open')}
            </Link>
            <a className={styles.classic} href={legacyHref('collection')}>
              {t('classic')}
            </a>
          </>
        }
      />

      {totals && (
        <dl className={styles.summary}>
          <div>
            <dt>{t('summary.copies')}</dt>
            <dd>{totals.qty}</dd>
          </div>
          <div>
            <dt>{t('summary.unique')}</dt>
            <dd>{totals.unique}</dd>
          </div>
          <div>
            <dt>{t('summary.value')}</dt>
            <dd>{formatMoney(totals.value)}</dd>
          </div>
        </dl>
      )}

      <form role="search" className={styles.search} onSubmit={(event) => event.preventDefault()}>
        <label htmlFor="collection-search" className="sr-only">
          {t('search.label')}
        </label>
        <DebouncedInput
          id="collection-search"
          type="search"
          enterKeyHint="search"
          placeholder={t('search.placeholder')}
          value={params.q ?? ''}
          delay={SEARCH_DELAY_MS}
          onCommit={(q) => setParams({ q: q || undefined }, { replace: true })}
        />
      </form>

      <div className={styles.toolbar}>
        <Button variant="ghost" onClick={() => setFiltersOpen(true)}>
          <Icon name="filter" size={16} />
          {t('filters.open')}
          {filterCount > 0 && <span className={styles.count}>{filterCount}</span>}
        </Button>
        <label className={styles.sort}>
          <span className="sr-only">{t('sort.label')}</span>
          <Select
            value={params.sort}
            onChange={(event) => setParams({ sort: event.target.value as CollectionSort })}
          >
            {SORTS.map((key) => (
              <option key={key} value={key}>
                {t(`sort.${key}`)}
              </option>
            ))}
          </Select>
        </label>
        <Button
          variant="ghost"
          aria-label={t('sort.direction')}
          aria-pressed={params.dir === 'desc'}
          onClick={() => setParams({ dir: params.dir === 'desc' ? 'asc' : 'desc' })}
        >
          {params.dir === 'desc' ? '↓' : '↑'}
        </Button>
        <SegmentedControl
          label={t('view.label')}
          options={[
            { value: 'grid', label: t('view.grid') },
            { value: 'list', label: t('view.list') },
          ]}
          value={view}
          onChange={setView}
        />
      </div>

      {filterCount > 0 && <div className={styles.chips}>{chips()}</div>}

      <section aria-label={t('title')}>{results}</section>

      {meta && meta.pages > 1 && (
        <Pagination
          page={meta.page ?? DEFAULT_PAGE}
          pages={meta.pages}
          onChange={(page) => setParams({ page })}
        />
      )}

      {!noCollection && (
        <div data-slot="fab-dock" className={styles.fabDock}>
          <button
            type="button"
            className={styles.fab}
            disabled={offline}
            title={offline ? undefined : t('add.open')}
            aria-label={t('add.open')}
            onClick={() => setAddOpen(true)}
          >
            <Icon name="plus" size={22} />
          </button>
        </div>
      )}

      <Sheet open={filtersOpen} onClose={() => setFiltersOpen(false)} title={t('filters.title')}>
        <CollectionFilters
          params={params}
          setParams={setParams}
          meta={gameMeta.data}
          facets={meta?.facets ?? {}}
          total={meta?.total_groups ?? 0}
          onClear={() => clearFilters()}
          onClose={() => setFiltersOpen(false)}
        />
      </Sheet>
      <ExportDialog
        open={exportOpen}
        onClose={() => setExportOpen(false)}
        params={params}
        offline={offline}
      />
      <AddSheet
        open={addOpen}
        onClose={() => setAddOpen(false)}
        meta={gameMeta.data}
        offline={offline}
      />
      {openGroup && (
        <LineSheet
          group={openGroup}
          open
          onClose={() => setOpen(null)}
          meta={gameMeta.data}
          playsetSize={playsetSize}
          offline={offline}
        />
      )}
    </div>
  );
}
