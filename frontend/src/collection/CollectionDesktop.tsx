import { useState } from 'react';
import { Link } from 'react-router';
import { DebouncedInput } from '@/catalog';
import type { CollectionGroup, CollectionSort } from '@/api/types';
import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { FilterChip } from '@/components/ui/FilterChip';
import { PageHeader } from '@/components/ui/PageHeader';
import { Pagination } from '@/components/ui/Pagination';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { Select } from '@/components/ui/Select';
import { Skeleton } from '@/components/ui/Skeleton';
import { pushToast } from '@/components/ui/toastStore';
import { translateError } from '@/i18n';
import { up } from '@/lib/breakpoints';
import { useMediaQuery } from '@/lib/useMediaQuery';
import { legacyHref } from '@/shell/legacyRoutes';
import { AddSheet } from './AddSheet';
import { BulkBar } from './BulkBar';
import { CollectionFilters } from './CollectionFilters';
import { CollectionItem } from './CollectionItem';
import { CollectionPanel } from './CollectionPanel';
import { CollectionTable } from './CollectionTable';
import { ExportDialog } from './ExportDialog';
import { LineSheet } from './LineSheet';
import { DEFAULT_PAGE, serializeCollectionParams } from './params';
import { fetchFilteredLineIds, MAX_SELECTION } from './queries';
import { SummaryBand } from './SummaryBand';
import { useSelection } from './useSelection';
import type { CollectionScreen } from './useCollectionScreen';
import styles from './CollectionDesktop.module.css';

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
const PAGE_SIZES = [25, 50, 100, 200];
const SEARCH_DELAY_MS = 300;

/** The layout from 1240 px (F3-h): facet sidebar, summary band, table or grid, bulk bar, wide panel. */
export function CollectionDesktop({ s }: { s: CollectionScreen }) {
  const {
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
    view: storedView,
    setView,
    addOpen,
    setAddOpen,
    exportOpen,
    setExportOpen,
    open,
    setOpen,
    openGroup,
    clearFilters,
  } = s;
  const wide = useMediaQuery(up('2xl'));
  const view: 'grid' | 'table' = storedView === 'grid' ? 'grid' : 'table';
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const [loadingIds, setLoadingIds] = useState(false);

  const scope = serializeCollectionParams({
    ...params,
    page: undefined,
    sort: undefined,
    dir: undefined,
    per_page: undefined,
  });
  const selection = useSelection(scope);

  const active: CollectionGroup | null = wide
    ? (items.find((group) => group.key === activeKey) ?? items[0] ?? null)
    : null;
  const pageIds = items.flatMap((group) => group.lines.map((line) => line.id));
  const wholePage = pageIds.length > 0 && pageIds.every((id) => selection.ids.has(id));
  const moreThanPage = (meta?.total_groups ?? 0) > (meta?.per_page ?? 0);
  const tooMany = (totals?.lines ?? 0) > MAX_SELECTION;

  const selectAllFiltered = async () => {
    setLoadingIds(true);
    try {
      selection.replace(await fetchFilteredLineIds(params));
    } catch (error) {
      pushToast({ kind: 'error', message: translateError(error, i18n) });
    } finally {
      setLoadingIds(false);
    }
  };

  const noCollection =
    !list.isLoading && !list.isError && totals?.lines === 0 && filterCount === 0 && !params.q;

  let results;
  if (list.isLoading) {
    results = <Skeleton label={t('loading')} lines={8} />;
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
  } else if (view === 'table') {
    results = (
      <CollectionTable
        groups={items}
        playsetSize={playsetSize}
        lang={lang}
        sort={params.sort ?? 'number'}
        dir={params.dir ?? 'asc'}
        onSort={(sort) =>
          setParams(
            sort === params.sort
              ? { dir: params.dir === 'desc' ? 'asc' : 'desc' }
              : { sort, dir: sort === 'name' || sort === 'number' ? 'asc' : 'desc' },
          )
        }
        selection={{ has: (id) => selection.ids.has(id), toggle: selection.toggle }}
        activeKey={active?.key ?? null}
        onActivate={(group) => setActiveKey(group.key)}
        conditions={gameMeta.data?.conditions ?? []}
        languages={gameMeta.data?.languages ?? []}
        offline={offline}
      />
    );
  } else {
    results = (
      <ul className={styles.grid} aria-busy={list.isFetching || undefined}>
        {items.map((group) => (
          <li key={group.key}>
            <CollectionItem
              group={group}
              variant="tile"
              playsetSize={playsetSize}
              lang={lang}
              onOpen={() => {
                setActiveKey(group.key);
                setOpen({ key: group.key, group });
              }}
            />
          </li>
        ))}
      </ul>
    );
  }

  const chips = [
    ...(['set', 'domain', 'type', 'rarity', 'condition', 'language'] as const).flatMap((key) =>
      (params[key] ?? []).map((value) => {
        const text = key === 'set' ? value : label(key, value);
        return (
          <FilterChip
            key={`${key}:${value}`}
            label={text}
            pressed
            onRemove={{
              'aria-label': t('filters.remove', { label: text }),
              onClick: () => setParams({ [key]: (params[key] ?? []).filter((v) => v !== value) }),
            }}
          />
        );
      }),
    ),
  ];

  return (
    <div className={styles.page}>
      <div className={styles.layout} data-wide={wide || undefined}>
        <aside className={styles.sidebar} aria-label={t('filters.title')}>
          <CollectionFilters
            variant="sidebar"
            params={params}
            setParams={setParams}
            meta={gameMeta.data}
            facets={meta?.facets ?? {}}
            total={meta?.total_groups ?? 0}
            onClear={() => clearFilters()}
          />
        </aside>

        <div className={styles.main}>
          <PageHeader
            title={t('title')}
            actions={
              <>
                <Button onClick={() => setAddOpen(true)} disabled={offline}>
                  {t('add.open')}
                </Button>
                <Button variant="ghost" onClick={() => setExportOpen(true)} disabled={offline}>
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
          {totals && <SummaryBand totals={totals} lang={lang} />}

          <div className={styles.toolbar}>
            <form role="search" className={styles.search} onSubmit={(e) => e.preventDefault()}>
              <label htmlFor="collection-search" className="sr-only">
                {t('search.label')}
              </label>
              <DebouncedInput
                id="collection-search"
                type="search"
                placeholder={t('search.placeholder')}
                value={params.q ?? ''}
                delay={SEARCH_DELAY_MS}
                onCommit={(q) => setParams({ q: q || undefined }, { replace: true })}
              />
            </form>
            <p className={styles.count} aria-live="polite">
              {meta ? t('desktop.groups', { count: meta.total_groups }) : ''}
            </p>
            <label className={styles.field}>
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
            <label className={styles.field}>
              <span className="sr-only">{t('desktop.pageSize')}</span>
              <Select
                value={params.per_page}
                onChange={(event) => setParams({ per_page: Number(event.target.value) })}
              >
                {PAGE_SIZES.map((size) => (
                  <option key={size} value={size}>
                    {`${t('desktop.pageSize')}: ${size}`}
                  </option>
                ))}
              </Select>
            </label>
            <SegmentedControl
              label={t('view.label')}
              options={[
                { value: 'grid', label: t('view.grid') },
                { value: 'table', label: t('view.table') },
              ]}
              value={view}
              onChange={setView}
            />
          </div>

          {chips.length > 0 && <div className={styles.chips}>{chips}</div>}

          {view === 'table' && wholePage && moreThanPage && (
            <p className={styles.selectAll}>
              {tooMany ? (
                <span>{t('bulk.tooMany')}</span>
              ) : (
                <Button
                  variant="ghost"
                  size="sm"
                  pending={loadingIds}
                  onClick={() => void selectAllFiltered()}
                >
                  {t('bulk.selectAllFiltered', { count: totals?.lines ?? 0 })}
                </Button>
              )}
            </p>
          )}

          <section aria-label={t('title')}>{results}</section>

          {selection.ids.size > 0 && (
            <BulkBar
              ids={[...selection.ids]}
              conditions={gameMeta.data?.conditions ?? []}
              languages={gameMeta.data?.languages ?? []}
              offline={offline}
              onClear={selection.clear}
            />
          )}

          {meta && meta.pages > 1 && (
            <Pagination
              page={meta.page ?? DEFAULT_PAGE}
              pages={meta.pages}
              onChange={(page) => setParams({ page })}
            />
          )}
        </div>

        {wide && <CollectionPanel group={active} lang={lang} />}
      </div>

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
      {open && openGroup && (
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
