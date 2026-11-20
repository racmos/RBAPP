import { useId, useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import type {
  CardmarketExpansionItem,
  CardmarketExpansionProduct,
  CardmarketExpansionProducts,
  ExpansionProductKind,
} from '@/api/endpoints';
import { DebouncedInput } from '@/catalog';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { Select } from '@/components/ui/Select';
import { Skeleton } from '@/components/ui/Skeleton';
import { TableScroll } from '@/components/ui/TableScroll';
import { up } from '@/lib/breakpoints';
import { formatDate, formatMoney, formatNumber } from '@/lib/format';
import { useMediaQuery } from '@/lib/useMediaQuery';
import { useSetText, useSlotRef } from './parts';
import { useExpansionProducts } from './queries';
import styles from './MatchingPage.module.css';

type KindFilter = 'all' | ExpansionProductKind;
type KindCount = CardmarketExpansionProducts['meta']['kinds'][number];
type ProductSort = 'price' | 'name' | 'added';

/** The price columns of a product, in the order the table shows them. */
const PRICE_KEYS = ['low', 'trend', 'avg7', 'avg30', 'avg', 'low_foil', 'trend_foil'] as const;
const COLUMNS = ['product', 'type', 'added', 'price', ...PRICE_KEYS, 'linked', 'catalog'] as const;

/** The query of the filters, the defaults left out (`kind=all`, `sort=price`). */
function productsQuery(q: string, kind: KindFilter, sort: ProductSort): string {
  const params = new URLSearchParams();
  if (q) params.set('q', q);
  if (kind !== 'all') params.set('kind', kind);
  if (sort !== 'price') params.set('sort', sort);
  return params.toString();
}

/**
 * The options of the Kind filter (CM-g): All, then each kind the expansion has with its count
 * (the counts of the whole expansion, whatever the filters). Before the first answer the list
 * row tells the cards apart. The chosen kind is always there, so the group keeps a checked
 * radio.
 */
function useKindOptions(
  kinds: KindCount[] | undefined,
  item: CardmarketExpansionItem,
  chosen: KindFilter,
) {
  const { t } = useTranslation('admin');
  const { t: tp } = useTranslation('products');
  const counts: KindCount[] =
    kinds ?? (item.singles_count > 0 ? [{ kind: 'card', count: item.singles_count }] : []);
  const all = kinds ? kinds.reduce((sum, one) => sum + one.count, 0) : item.products_count;
  const shown =
    chosen === 'all' || counts.some((one) => one.kind === chosen)
      ? counts
      : [...counts, { kind: chosen, count: 0 }];
  const option = (label: string, count: number) =>
    t('matching.expansions.products.kindOption', { label, amount: formatNumber(count) });
  return [
    { value: 'all' as KindFilter, label: option(t('matching.expansions.products.kindAll'), all) },
    ...shown.map((one) => ({
      value: one.kind as KindFilter,
      label: option(tp(`kind.${one.kind}`), one.count),
    })),
  ];
}

/** The texts of one product, shared by the table and the cards. */
function useProductText() {
  const { t } = useTranslation('admin');
  const { t: tp } = useTranslation('products');
  const slotRef = useSlotRef();
  const none = t('matching.expansions.products.none');
  const money = (value: number | null | undefined) =>
    value === null || value === undefined ? none : formatMoney(value);
  return {
    none,
    money,
    type: (product: CardmarketExpansionProduct) =>
      t(`matching.expansions.products.${product.type}`),
    /** One product's kind: "Card" for a single, else the products' kind label. */
    kind: (product: CardmarketExpansionProduct) =>
      product.kind === 'card'
        ? t('matching.expansions.products.cardBadge')
        : tp(`kind.${product.kind}`),
    price: (product: CardmarketExpansionProduct) =>
      product.price === null || product.price_source === null
        ? t('matching.expansions.noPrice')
        : t('matching.expansions.products.priceSource', {
            price: formatMoney(product.price),
            source: t(`matching.expansions.products.source.${product.price_source}`),
          }),
    linked: (product: CardmarketExpansionProduct) =>
      product.linked === null ? null : slotRef(product.linked),
    catalog: (product: CardmarketExpansionProduct) =>
      product.catalog === null
        ? null
        : t('matching.expansions.products.catalogRef', {
            kind: product.catalog.kind ?? t('matching.expansions.products.noKind'),
            set: product.catalog.set_id ?? t('matching.expansions.products.noSet'),
          }),
  };
}

/** From 860 px: one row a product, every field a column. */
function ProductsTable({
  items,
  caption,
}: {
  items: CardmarketExpansionProduct[];
  caption: string;
}) {
  const { t } = useTranslation('admin');
  const text = useProductText();
  return (
    <table className={styles.table}>
      <caption className="sr-only">{caption}</caption>
      <thead>
        <tr>
          {COLUMNS.map((key) => (
            <th key={key} scope="col">
              {t(`matching.expansions.products.columns.${key}`)}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {items.map((product) => (
          <tr key={product.id_product}>
            <td>
              <div className={styles.cellStack}>
                <span>{product.name}</span>
                <span className={styles.kindLine}>
                  <Badge>{text.kind(product)}</Badge>
                  <span className={styles.muted}>
                    {product.category === null
                      ? t('matching.expansions.products.identityNoCategory', {
                          id: product.id_product,
                        })
                      : t('matching.expansions.products.identity', {
                          id: product.id_product,
                          category: product.category,
                        })}
                  </span>
                </span>
              </div>
            </td>
            <td>{text.type(product)}</td>
            <td className={styles.nowrap}>
              {product.date_added === null ? text.none : formatDate(product.date_added)}
            </td>
            <td className={styles.nowrap}>{text.price(product)}</td>
            {PRICE_KEYS.map((key) => (
              <td key={key} className={styles.nowrap}>
                {text.money(product.prices?.[key])}
              </td>
            ))}
            <td className={styles.nowrap}>{text.linked(product) ?? text.none}</td>
            <td className={styles.nowrap}>{text.catalog(product) ?? text.none}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** Below 860 px: one card a product, the prices it has as a list of pairs. */
function ProductCards({ items, label }: { items: CardmarketExpansionProduct[]; label: string }) {
  const { t } = useTranslation('admin');
  const text = useProductText();
  return (
    <ul aria-label={label} className={styles.rows}>
      {items.map((product) => {
        const facts = {
          type: text.type(product),
          id: product.id_product,
          category: product.category ?? '',
        };
        const linked = text.linked(product);
        const catalog = text.catalog(product);
        const prices = PRICE_KEYS.filter((key) => (product.prices?.[key] ?? null) !== null);
        return (
          <li key={product.id_product} className={styles.row}>
            <p className={styles.rowTitle}>{product.name}</p>
            <p className={styles.kindLine}>
              <Badge>{text.kind(product)}</Badge>
              <span className={styles.muted}>
                {product.category === null
                  ? t('matching.expansions.products.factsNoCategory', facts)
                  : t('matching.expansions.products.facts', facts)}
              </span>
            </p>
            {product.date_added !== null && (
              <p className={styles.muted}>
                {t('matching.expansions.products.added', { date: formatDate(product.date_added) })}
              </p>
            )}
            <p className={styles.current}>
              {t('matching.expansions.products.price', { price: text.price(product) })}
            </p>
            {prices.length > 0 && (
              <dl className={styles.pricePairs}>
                {prices.map((key) => (
                  <div key={key}>
                    <dt>{t(`matching.expansions.products.columns.${key}`)}</dt>
                    <dd>{text.money(product.prices?.[key])}</dd>
                  </div>
                ))}
              </dl>
            )}
            {linked !== null && (
              <p className={styles.muted}>
                {t('matching.expansions.products.linkedTo', { ref: linked })}
              </p>
            )}
            {catalog !== null && (
              <p className={styles.muted}>
                {t('matching.expansions.products.catalogLine', { ref: catalog })}
              </p>
            )}
          </li>
        );
      })}
    </ul>
  );
}

export type MapFormSlot = (options: { startNew: boolean; onCancel: () => void }) => ReactNode;

/**
 * "View products" (CM-f): every product of an expansion on the latest load, read-only, so an
 * expansion Cardmarket gives no name can be told apart. The figures of the whole expansion on
 * top, then the search, the Kind filter (CM-g: All and each kind the expansion has, with its
 * count; Cards first when it has cards) and the sort, the list (it scrolls inside the dialog: a
 * table from 860 px, cards below; each row with its kind badge) with "Show more", and at the
 * bottom the map form of the row (`renderMap`), opened under the list so the owner decides
 * while looking at it.
 */
export function ExpansionProducts({
  item,
  offline,
  renderMap,
}: {
  item: CardmarketExpansionItem;
  offline: boolean;
  renderMap: MapFormSlot;
}) {
  const { t } = useTranslation('admin');
  const { t: common } = useTranslation('common');
  const setText = useSetText();
  const wide = useMediaQuery(up('md'));
  const mapTitleId = useId();
  const [q, setQ] = useState('');
  // the cards first when the expansion has some, else every product
  const [kind, setKind] = useState<KindFilter>(item.singles_count > 0 ? 'card' : 'all');
  const [sort, setSort] = useState<ProductSort>('price');
  const [mapping, setMapping] = useState<'set' | 'new' | null>(null);
  const query = useExpansionProducts(item.id, productsQuery(q, kind, sort));
  const listLabel = t('matching.expansions.products.list');

  const first = query.data?.pages[0]?.meta;
  const singles = first?.singles ?? item.singles_count;
  const products = first ? first.singles + first.sealed : item.products_count;
  const range = first ? first.price_range : item.price_range;
  const firstSeen = first ? first.first_seen : item.first_seen;
  const items = query.data?.pages.flatMap((page) => page.items) ?? [];
  const total = query.data?.pages.at(-1)?.meta.total ?? 0;
  const kindOptions = useKindOptions(first?.kinds, item, kind);
  // nothing at all on the latest load, or only nothing that matches the filters
  const filtered = (first?.kinds.length ?? 0) > 0;

  let list;
  if (query.isPending) {
    list = offline ? (
      <p className={styles.help}>{t('matching.expansions.products.offline')}</p>
    ) : (
      <Skeleton label={listLabel} lines={6} />
    );
  } else if (query.isError && items.length === 0) {
    list = <ErrorState message={common('errorState.title')} onRetry={() => void query.refetch()} />;
  } else if (items.length === 0) {
    list = filtered ? (
      <EmptyState
        title={t('matching.expansions.products.noMatchTitle')}
        body={t('matching.expansions.products.noMatchBody')}
      />
    ) : (
      <EmptyState
        title={t('matching.expansions.products.emptyTitle')}
        body={t('matching.expansions.products.emptyBody')}
      />
    );
  } else {
    list = (
      <>
        {wide ? (
          <ProductsTable items={items} caption={listLabel} />
        ) : (
          <ProductCards items={items} label={listLabel} />
        )}
        {query.isFetchNextPageError && (
          <ErrorState
            message={common('errorState.title')}
            onRetry={() => void query.fetchNextPage()}
          />
        )}
        {query.hasNextPage && !query.isFetchNextPageError && (
          <div className={styles.showMore}>
            <Button
              variant="ghost"
              pending={query.isFetchingNextPage}
              onClick={() => void query.fetchNextPage()}
            >
              {t('matching.expansions.products.showMore')}
            </Button>
          </div>
        )}
      </>
    );
  }

  return (
    <div className={wide ? styles.products : `${styles.products} ${styles.productsStacked}`}>
      <div className={styles.dialog}>
        <div className={styles.meta}>
          <span>
            {t('matching.expansions.products.products', {
              count: products,
              formatted: formatNumber(products),
            })}
          </span>
          <span>
            {t('matching.expansions.products.cards', {
              count: singles,
              formatted: formatNumber(singles),
            })}
          </span>
          {range && (
            <span>
              {t('matching.expansions.products.cardsRange', {
                min: formatMoney(range.min),
                max: formatMoney(range.max),
              })}
            </span>
          )}
          {firstSeen && (
            <span>{t('matching.expansions.firstSeen', { date: formatDate(firstSeen) })}</span>
          )}
          {first?.date && (
            <span>
              {t('matching.expansions.products.latest', { date: formatDate(first.date) })}
            </span>
          )}
        </div>
        <p className={styles.current}>
          {item.mapped_set_id === null
            ? t('matching.expansions.products.notMapped')
            : t('matching.expansions.current', {
                set: setText(item.mapped_set_id, item.mapped_set_name),
              })}
        </p>
        <p className={styles.help}>{t('matching.expansions.products.hint')}</p>
        <div className={styles.filters}>
          <label className={styles.filterField}>
            {t('matching.expansions.products.search')}
            <DebouncedInput
              aria-label={t('matching.expansions.products.search')}
              value={q}
              onCommit={(next) => setQ(next.trim())}
            />
          </label>
          <SegmentedControl<KindFilter>
            label={t('matching.expansions.products.kind')}
            showLabel
            value={kind}
            onChange={setKind}
            options={kindOptions}
          />
          <label className={styles.filterField}>
            {t('matching.expansions.products.sort')}
            <Select
              aria-label={t('matching.expansions.products.sort')}
              value={sort}
              onChange={(event) => setSort(event.target.value as ProductSort)}
            >
              <option value="price">{t('matching.expansions.products.sortPrice')}</option>
              <option value="name">{t('matching.expansions.products.sortName')}</option>
              <option value="added">{t('matching.expansions.products.sortAdded')}</option>
            </Select>
          </label>
        </div>
        {query.data && (
          <p className={styles.meta} aria-live="polite">
            {t('matching.expansions.products.showing', { shown: items.length, count: total })}
          </p>
        )}
      </div>
      {/* the list scrolls on its own, so the keyboard must reach it (WCAG 2.1.1) */}
      <TableScroll
        role="region"
        aria-label={listLabel}
        tabIndex={0}
        className={styles.productsScroll}
      >
        {list}
      </TableScroll>
      {mapping === null ? (
        <div className={styles.rowActions}>
          <Button
            variant="ghost"
            disabled={offline}
            title={offline ? common('offline.editDisabled') : undefined}
            onClick={() => setMapping('set')}
          >
            {item.mapped_set_id === null
              ? t('matching.expansions.products.map')
              : t('matching.expansions.products.change')}
          </Button>
          <Button
            variant="ghost"
            disabled={offline}
            title={offline ? common('offline.editDisabled') : undefined}
            onClick={() => setMapping('new')}
          >
            {t('matching.expansions.products.newSet')}
          </Button>
        </div>
      ) : (
        <section aria-labelledby={mapTitleId} className={styles.section}>
          <h3 id={mapTitleId} className={styles.sectionTitle}>
            {t('matching.expansions.products.mapTitle')}
          </h3>
          <div key={mapping}>
            {renderMap({ startNew: mapping === 'new', onCancel: () => setMapping(null) })}
          </div>
        </section>
      )}
    </div>
  );
}
