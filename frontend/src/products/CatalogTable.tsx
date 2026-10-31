import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';
import type { ProductListSort, ProductSummary } from '@/api/types';
import { Badge } from '@/components/ui/Badge';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { Pagination } from '@/components/ui/Pagination';
import { Select } from '@/components/ui/Select';
import { Skeleton } from '@/components/ui/Skeleton';
import { TableScroll } from '@/components/ui/TableScroll';
import { formatMoney } from '@/lib/format';
import { DEFAULT_PAGE, DEFAULT_PER_PAGE, activeFilterCount, type ProductsParams } from './params';
import { ProductThumb } from './ProductThumb';
import { useProductList } from './queries';
import { Signed, SortHeader } from './tableParts';
import styles from './ProductTable.module.css';

const PAGE_SIZES = [DEFAULT_PER_PAGE, 96];

type CatalogTableProps = {
  params: ProductsParams;
  setParams: (patch: Partial<ProductsParams>) => void;
  /** From 1600 px the name selects the product for the panel; below it opens the product page. */
  wide: boolean;
  selected: number | null;
  onActivate: (id: number) => void;
};

function Row({
  product,
  wide,
  selected,
  onActivate,
}: {
  product: ProductSummary;
  wide: boolean;
  selected: boolean;
  onActivate: (id: number) => void;
}) {
  const { t } = useTranslation('products');
  const { price } = product;
  return (
    <tr data-active={selected || undefined} onClick={() => onActivate(product.id)}>
      <td>
        <span className={styles.thumb}>
          <ProductThumb product={product} size="thumb" decorative />
        </span>
      </td>
      <td onClick={(event) => event.stopPropagation()}>
        {wide ? (
          <button
            type="button"
            className={styles.nameButton}
            aria-pressed={selected}
            onClick={() => onActivate(product.id)}
          >
            {product.name}
          </button>
        ) : (
          <Link className={styles.name} to={`/products/${product.id}`}>
            {product.name}
          </Link>
        )}
      </td>
      <td>{product.kind ? t(`kind.${product.kind}`) : '—'}</td>
      <td>{product.set_id ?? '—'}</td>
      <td className={styles.numeric}>{price ? formatMoney(price.value) : t('unpriced')}</td>
      <td className={styles.numeric}>
        <Signed value={price?.change_7d_pct} kind="pct" />
      </td>
      <td className={styles.numeric}>
        <Signed value={price?.change_30d_pct} kind="pct" />
      </td>
      <td className={styles.numeric}>
        {product.owned_qty > 0 ? (
          <>
            <span aria-hidden="true">×{product.owned_qty}</span>
            <span className="sr-only">{t('owned', { count: product.owned_qty })}</span>
          </>
        ) : (
          '—'
        )}
      </td>
      <td>{!product.listed && <Badge tone="warning">{t('table.notListed')}</Badge>}</td>
    </tr>
  );
}

/** "Catalog" from 1240 px (F14-f S2): page size, the table with sortable headers, the pages. */
export function CatalogTable({ params, setParams, wide, selected, onActivate }: CatalogTableProps) {
  const { t } = useTranslation('products');
  const list = useProductList(params);
  const meta = list.data?.meta;
  const items = list.data?.data.items ?? [];
  const dir = params.dir ?? 'asc';
  const perPage = params.per_page ?? DEFAULT_PER_PAGE;
  const sizes = PAGE_SIZES.includes(perPage) ? PAGE_SIZES : [...PAGE_SIZES, perPage];
  const column = (key: string) => t(`table.columns.${key}` as 'table.columns.name');

  const onSort = (sort: ProductListSort) =>
    setParams(
      sort === params.sort
        ? { dir: dir === 'desc' ? 'asc' : 'desc' }
        : { sort, dir: sort === 'name' ? 'asc' : 'desc' },
    );
  const sortHeader = (key: string, sort: ProductListSort) => (
    <SortHeader label={column(key)} sortKey={sort} sort={params.sort} dir={dir} onSort={onSort} />
  );

  let results;
  if (list.isPending) {
    results = <Skeleton label={t('loading')} lines={8} />;
  } else if (list.isError && !list.data) {
    results = <ErrorState message={t('error')} onRetry={() => void list.refetch()} />;
  } else if (items.length === 0) {
    results = (
      <EmptyState
        icon="search"
        title={t('empty.catalog')}
        action={
          activeFilterCount(params) > 0 || params.q
            ? {
                label: t('clearFilters'),
                onAction: () =>
                  setParams({ q: undefined, kind: undefined, set: undefined, owned: undefined }),
              }
            : undefined
        }
      />
    );
  } else {
    results = (
      <TableScroll>
        <table className={styles.table} aria-busy={list.isFetching || undefined}>
          <caption className="sr-only">{t('table.caption')}</caption>
          <thead>
            <tr>
              <th scope="col">
                <span className="sr-only">{column('image')}</span>
              </th>
              {sortHeader('name', 'name')}
              <th scope="col">{column('kind')}</th>
              <th scope="col">{column('set')}</th>
              {sortHeader('price', 'price')}
              {sortHeader('change7d', 'change_7d')}
              {sortHeader('change30d', 'change_30d')}
              <th scope="col">{column('owned')}</th>
              <th scope="col">{column('listed')}</th>
            </tr>
          </thead>
          <tbody>
            {items.map((product) => (
              <Row
                key={product.id}
                product={product}
                wide={wide}
                selected={selected === product.id}
                onActivate={onActivate}
              />
            ))}
          </tbody>
        </table>
      </TableScroll>
    );
  }

  return (
    <>
      <div className={styles.toolbar}>
        <label className={styles.pageSize}>
          <span>{t('filters.pageSize')}</span>
          <Select
            value={perPage}
            onChange={(event) => setParams({ per_page: Number(event.target.value) })}
          >
            {sizes.map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </Select>
        </label>
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
