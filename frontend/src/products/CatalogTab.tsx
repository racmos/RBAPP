import { useTranslation } from 'react-i18next';
import { PRODUCT_KINDS, type ProductListParams, type ProductListSort } from '@/api/types';
import { DebouncedInput, useGameMeta } from '@/catalog';
import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { ChipGroup, FilterChip } from '@/components/ui/FilterChip';
import { Pagination } from '@/components/ui/Pagination';
import { Select } from '@/components/ui/Select';
import { Skeleton } from '@/components/ui/Skeleton';
import { DEFAULT_PAGE, activeFilterCount } from './params';
import { ProductTile } from './ProductTile';
import { useProductList } from './queries';
import styles from './ProductsPage.module.css';

const SORTS: ProductListSort[] = ['name', 'price', 'change_7d', 'change_30d'];
const SEARCH_DELAY_MS = 300;

type CatalogTabProps = {
  params: ProductListParams;
  setParams: (patch: Partial<ProductListParams>, options?: { replace?: boolean }) => void;
};

/** "Catálogo": search, kind chips, set, sort, the tiles and the pages (F14-e S2). */
export function CatalogTab({ params, setParams }: CatalogTabProps) {
  const { t } = useTranslation('products');
  const list = useProductList(params);
  const gameMeta = useGameMeta();
  const meta = list.data?.meta;
  const items = list.data?.data.items ?? [];
  const facets = meta?.facets ?? { kind: {}, set: {} };
  const kinds = params.kind ?? [];
  const setNames = new Map((gameMeta.data?.sets ?? []).map((set) => [set.id, set.name]));
  const setIds = [...new Set([...Object.keys(facets.set), ...(params.set ?? [])])];

  const toggleKind = (kind: (typeof PRODUCT_KINDS)[number]) =>
    setParams({
      kind: kinds.includes(kind) ? kinds.filter((item) => item !== kind) : [...kinds, kind],
    });
  const clearFilters = () => setParams({ q: undefined, kind: undefined, set: undefined });

  let results;
  if (list.isPending) {
    results = <Skeleton label={t('loading')} lines={6} />;
  } else if (list.isError && !list.data) {
    results = <ErrorState message={t('error')} onRetry={() => void list.refetch()} />;
  } else if (items.length === 0) {
    results = (
      <EmptyState
        icon="search"
        title={t('empty.catalog')}
        action={
          activeFilterCount(params) > 0 || params.q
            ? { label: t('clearFilters'), onAction: clearFilters }
            : undefined
        }
      />
    );
  } else {
    results = (
      <ul className={styles.grid} aria-busy={list.isFetching || undefined}>
        {items.map((product) => (
          <li key={product.id}>
            <ProductTile product={product} />
          </li>
        ))}
      </ul>
    );
  }

  return (
    <>
      <form role="search" className={styles.search} onSubmit={(event) => event.preventDefault()}>
        <label htmlFor="products-search" className="sr-only">
          {t('search.label')}
        </label>
        <DebouncedInput
          id="products-search"
          type="search"
          enterKeyHint="search"
          placeholder={t('search.placeholder')}
          value={params.q ?? ''}
          delay={SEARCH_DELAY_MS}
          onCommit={(q) => setParams({ q: q || undefined }, { replace: true })}
        />
      </form>

      <ChipGroup legend={t('filters.kind')}>
        {PRODUCT_KINDS.filter((kind) => kind in facets.kind || kinds.includes(kind)).map((kind) => (
          <FilterChip
            key={kind}
            label={t(`kind.${kind}`)}
            count={facets.kind[kind] ?? 0}
            pressed={kinds.includes(kind)}
            onClick={() => toggleKind(kind)}
          />
        ))}
      </ChipGroup>

      <div className={styles.toolbar}>
        <label className={styles.select}>
          <span className={styles.selectLabel}>{t('filters.set')}</span>
          <Select
            value={params.set?.[0] ?? ''}
            onChange={(event) =>
              setParams({ set: event.target.value ? [event.target.value] : undefined })
            }
          >
            <option value="">{t('filters.allSets')}</option>
            {setIds.map((id) => (
              <option key={id} value={id}>
                {setNames.get(id) ? `${id} · ${setNames.get(id)}` : id}
                {facets.set[id] !== undefined ? ` (${facets.set[id]})` : ''}
              </option>
            ))}
          </Select>
        </label>
        <label className={styles.select}>
          <span className={styles.selectLabel}>{t('sort.label')}</span>
          <Select
            value={params.sort}
            onChange={(event) => setParams({ sort: event.target.value as ProductListSort })}
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
      </div>

      {results}

      {meta && meta.pages > 1 && (
        <Pagination
          page={meta.page ?? DEFAULT_PAGE}
          pages={meta.pages}
          onChange={(page) => setParams({ page })}
        />
      )}
    </>
  );
}
