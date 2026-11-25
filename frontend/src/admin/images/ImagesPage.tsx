import {
  useRef,
  useState,
  type DragEvent,
  type KeyboardEvent,
  type ReactNode,
  type RefObject,
} from 'react';
import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router';
import { DebouncedInput, useSearchNavigation } from '@/catalog';
import {
  getAdminImagesSummary,
  listAdminCards,
  listAdminProducts,
  listAdminSets,
  type AdminCard,
  type AdminProduct,
} from '@/api/endpoints';
import { PRODUCT_KINDS } from '@/api/types';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { Icon } from '@/components/ui/Icon';
import { PageHeader } from '@/components/ui/PageHeader';
import { Pagination } from '@/components/ui/Pagination';
import { Select } from '@/components/ui/Select';
import { Skeleton } from '@/components/ui/Skeleton';
import { Switch } from '@/components/ui/Switch';
import { TableScroll } from '@/components/ui/TableScroll';
import { useDocumentTitle } from '@/i18n';
import { down } from '@/lib/breakpoints';
import { useMediaQuery } from '@/lib/useMediaQuery';
import { useOnline } from '@/lib/useOnline';
import { BulkUploadDialog } from './BulkUploadDialog';
import { IMAGE_ACCEPT, type ImageTab } from './matchFiles';
import { UploadDialog, type PickedImage } from './UploadDialog';
import { cardTarget, productTarget, type UploadResult, type UploadTarget } from './uploadImage';
import styles from './ImagesPage.module.css';

const TABS: readonly ImageTab[] = ['cards', 'products'];
const PAGE_SIZES = ['50', '100', '200'];

/** One row of either tab. */
type ImageItem = {
  id: string;
  name: string;
  code: string;
  set: string | null;
  src: string | null;
  /** The row names a file that is not on disk. */
  lost: boolean;
  target: UploadTarget;
};

const cardItem = (card: AdminCard): ImageItem => ({
  id: card.key,
  name: card.name,
  code: card.key,
  set: card.set_id,
  src: card.has_image ? card.image_src : null,
  lost: Boolean(card.image) && !card.has_image,
  target: cardTarget(card),
});

/** The list request of a tab, from the URL (`files=off` = the switch off, S1). */
function listQuery(tab: ImageTab, params: URLSearchParams): URLSearchParams {
  const query = new URLSearchParams();
  query.set('image', params.get('files') === 'off' ? 'empty' : 'missing');
  for (const key of ['q', 'page', 'per_page', tab === 'cards' ? 'set' : 'kind']) {
    const value = params.get(key);
    if (value) query.set(key, value);
  }
  return query;
}

/**
 * Admin → Images (F13-h S1-S3, S6): the cards and products without a usable image, a file
 * picker or a drop per row, and the bulk upload by file name.
 */
export function ImagesPage() {
  const { t } = useTranslation('admin');
  const { t: tp } = useTranslation('products');
  const { t: common } = useTranslation('common');
  const offline = !useOnline();
  const phone = useMediaQuery(down('md'));
  const queryClient = useQueryClient();
  const [params] = useSearchParams();
  // latest search asked for, not the rendered one: quick changes in a row must all stay (L6)
  const { setSearchParams: setParams } = useSearchNavigation();
  const [picked, setPicked] = useState<PickedImage | null>(null);
  const [bulk, setBulk] = useState(false);
  const tab: ImageTab = params.get('tab') === 'products' ? 'products' : 'cards';
  useDocumentTitle(t('images.title'));

  const summary = useQuery({
    queryKey: ['admin', 'images', 'summary'],
    queryFn: ({ signal }) => getAdminImagesSummary(signal),
  });
  const sets = useQuery({
    queryKey: ['admin', 'sets'],
    queryFn: ({ signal }) => listAdminSets(signal),
    enabled: tab === 'cards',
  });
  const request = listQuery(tab, params);
  const listKey = ['admin', 'images', tab, request.toString()];
  const list = useQuery({
    queryKey: listKey,
    queryFn: async ({ signal }): Promise<{ items: ImageItem[]; page: number; pages: number }> => {
      if (tab === 'cards') {
        const data = await listAdminCards(Object.fromEntries(request), signal);
        return { items: data.items.map(cardItem), page: data.meta.page, pages: data.meta.pages };
      }
      const data = await listAdminProducts(request.toString(), signal);
      return {
        items: data.items.map((product: AdminProduct): ImageItem => ({
          id: String(product.id),
          name: product.name,
          code: tp(`kind.${product.kind}`),
          set: product.set_id,
          src: product.has_image ? product.image_src : null,
          lost: Boolean(product.image) && !product.has_image,
          target: productTarget(product),
        })),
        page: data.meta.page,
        pages: data.meta.pages,
      };
    },
    placeholderData: keepPreviousData,
  });

  const update = (change: (next: URLSearchParams) => void, keepPage = false) =>
    setParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        change(next);
        if (!keepPage) next.delete('page');
        return next;
      },
      { replace: true },
    );
  const setParam = (key: string, value: string | null) =>
    update((next) => {
      if (value === null || value === '') next.delete(key);
      else next.set(key, value);
    });
  const chooseTab = (next: ImageTab) =>
    update((query) => {
      for (const key of ['q', 'set', 'kind']) query.delete(key);
      if (next === 'cards') query.delete('tab');
      else query.set('tab', next);
    });

  /** S3: the row shows its new image at once; it leaves the list at the next refetch. */
  const onUploaded = (target: UploadTarget, result: UploadResult) => {
    const id =
      target.type === 'card' ? `${target.setId}-${target.cardId}` : String(target.productId);
    queryClient.setQueryData<{ items: ImageItem[]; page: number; pages: number }>(
      listKey,
      (current) =>
        current && {
          ...current,
          items: current.items.map((item) =>
            item.id === id ? { ...item, src: result.image_src, lost: false } : item,
          ),
        },
    );
    void queryClient.invalidateQueries({ queryKey: ['admin'], refetchType: 'none' });
    void queryClient.invalidateQueries({ queryKey: ['admin', 'images', 'summary'] });
  };

  const counts = summary.data?.[tab];
  const header = <PageHeader title={t('images.title')} subtitle={t('images.subtitle')} />;

  let body: ReactNode;
  if (list.isPending) {
    body = <Skeleton label={t('images.title')} lines={4} />;
  } else if (list.isError) {
    body = <ErrorState message={common('errorState.title')} onRetry={() => void list.refetch()} />;
  } else if (list.data.items.length === 0) {
    body = <EmptyState title={t(`images.tabs.${tab}`)} body={t('images.empty')} />;
  } else {
    const rowProps = (item: ImageItem) => ({
      item,
      offline,
      onPick: (file: File) => setPicked({ target: item.target, file }),
    });
    body = (
      <>
        {phone ? (
          <ul className={styles.cards} aria-label={t(`images.caption.${tab}`)}>
            {list.data.items.map((item) => (
              <ImageCard key={item.id} {...rowProps(item)} />
            ))}
          </ul>
        ) : (
          <TableScroll>
            <table className={styles.table}>
              <caption className="sr-only">{t(`images.caption.${tab}`)}</caption>
              <thead>
                <tr>
                  <th scope="col">{t('images.columns.image')}</th>
                  <th scope="col">{t('images.columns.name')}</th>
                  <th scope="col">
                    {tab === 'cards' ? t('images.columns.code') : t('images.columns.kind')}
                  </th>
                  <th scope="col">{t('images.columns.set')}</th>
                  <th scope="col">{t('images.columns.file')}</th>
                </tr>
              </thead>
              <tbody>
                {list.data.items.map((item) => (
                  <ImageTableRow key={item.id} {...rowProps(item)} />
                ))}
              </tbody>
            </table>
          </TableScroll>
        )}
        <Pagination
          page={list.data.page}
          pages={list.data.pages}
          onChange={(page) => update((next) => next.set('page', String(page)), true)}
        />
      </>
    );
  }

  return (
    <>
      {header}
      <Tabs tab={tab} choose={chooseTab} missing={(name) => summary.data?.[name].missing} />
      <div
        role="tabpanel"
        id={`images-panel-${tab}`}
        aria-labelledby={`images-tab-${tab}`}
        className={styles.panel}
      >
        {counts && (
          <p className={styles.counter}>
            {t('images.counter', { missing: counts.missing, total: counts.total })}
          </p>
        )}
        <div className={styles.filters}>
          <label className={styles.filterField}>
            {t('images.filters.search')}
            <DebouncedInput
              aria-label={t('images.filters.search')}
              value={params.get('q') ?? ''}
              onCommit={(next) => setParam('q', next.trim() || null)}
            />
          </label>
          {tab === 'cards' ? (
            <label className={styles.filterField}>
              {t('images.filters.set')}
              <Select
                aria-label={t('images.filters.set')}
                value={params.get('set') ?? ''}
                onChange={(event) => setParam('set', event.target.value || null)}
              >
                <option value="">{t('images.filters.allSets')}</option>
                {(sets.data ?? []).map((set) => (
                  <option key={set.id} value={set.id}>
                    {set.id} · {set.name}
                  </option>
                ))}
              </Select>
            </label>
          ) : (
            <label className={styles.filterField}>
              {t('images.filters.kind')}
              <Select
                aria-label={t('images.filters.kind')}
                value={params.get('kind') ?? ''}
                onChange={(event) => setParam('kind', event.target.value || null)}
              >
                <option value="">{t('images.filters.allKinds')}</option>
                {PRODUCT_KINDS.map((kind) => (
                  <option key={kind} value={kind}>
                    {tp(`kind.${kind}`)}
                  </option>
                ))}
              </Select>
            </label>
          )}
          <label className={styles.filterField}>
            {t('images.filters.pageSize')}
            <Select
              aria-label={t('images.filters.pageSize')}
              value={params.get('per_page') ?? '50'}
              onChange={(event) => setParam('per_page', event.target.value)}
            >
              {PAGE_SIZES.map((size) => (
                <option key={size} value={size}>
                  {size}
                </option>
              ))}
            </Select>
          </label>
          <Switch
            label={t('images.filters.includeMissingFiles')}
            checked={params.get('files') !== 'off'}
            onCheckedChange={(checked) => setParam('files', checked ? null : 'off')}
          />
          <Button variant="ghost" disabled={offline} onClick={() => setBulk(true)}>
            {t('images.bulk.open')}
          </Button>
        </div>
        <p className={styles.hint}>
          {t(`images.limits.${tab}`)} {t('images.dropHint')}
        </p>
        {body}
      </div>
      <UploadDialog
        picked={picked}
        offline={offline}
        onClose={() => setPicked(null)}
        onUploaded={onUploaded}
      />
      {bulk && (
        <BulkUploadDialog
          tab={tab}
          offline={offline}
          onClose={() => {
            setBulk(false);
            void queryClient.invalidateQueries({ queryKey: ['admin'] });
          }}
        />
      )}
    </>
  );
}

/** Cards | Products as tabs: arrows, Home and End move between them. */
function Tabs({
  tab,
  choose,
  missing,
}: {
  tab: ImageTab;
  choose: (tab: ImageTab) => void;
  missing: (tab: ImageTab) => number | undefined;
}) {
  const { t } = useTranslation('admin');
  const refs = useRef<Partial<Record<ImageTab, HTMLButtonElement | null>>>({});
  const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    const index = TABS.indexOf(tab);
    let next: ImageTab | undefined;
    if (event.key === 'ArrowRight') next = TABS[(index + 1) % TABS.length];
    else if (event.key === 'ArrowLeft') next = TABS[(index - 1 + TABS.length) % TABS.length];
    else if (event.key === 'Home') next = TABS[0];
    else if (event.key === 'End') next = TABS[TABS.length - 1];
    if (!next) return;
    event.preventDefault();
    choose(next);
    refs.current[next]?.focus();
  };
  return (
    <div role="tablist" aria-label={t('images.tabsLabel')} className={styles.tabs}>
      {TABS.map((name) => {
        const count = missing(name);
        return (
          <button
            key={name}
            ref={(node) => {
              refs.current[name] = node;
            }}
            type="button"
            role="tab"
            id={`images-tab-${name}`}
            aria-controls={`images-panel-${name}`}
            aria-selected={tab === name}
            tabIndex={tab === name ? 0 : -1}
            className={styles.tab}
            onClick={() => choose(name)}
            onKeyDown={onKeyDown}
          >
            {t(`images.tabs.${name}`)}
            {count !== undefined && <span className={styles.tabCount}>{count}</span>}
          </button>
        );
      })}
    </div>
  );
}

type RowProps = { item: ImageItem; offline: boolean; onPick: (file: File) => void };

/** The hidden file input, its Choose file button and the drop handlers of one row (S3). */
function usePicker({ offline, onPick }: Omit<RowProps, 'item'>) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const drop = {
    onDragOver: (event: DragEvent) => {
      if (offline) return;
      event.preventDefault();
      setOver(true);
    },
    onDragLeave: () => setOver(false),
    onDrop: (event: DragEvent) => {
      event.preventDefault();
      setOver(false);
      const file = event.dataTransfer?.files?.[0];
      if (file && !offline) onPick(file);
    },
  };
  return { input, over, drop };
}

function Picker({
  item,
  offline,
  onPick,
  input,
}: RowProps & { input: RefObject<HTMLInputElement | null> }) {
  const { t } = useTranslation('admin');
  return (
    <>
      <Button
        size="sm"
        variant="ghost"
        disabled={offline}
        aria-label={t('images.chooseFor', { name: item.name })}
        onClick={() => input.current?.click()}
      >
        {t('images.choose')}
      </Button>
      <input
        ref={input}
        type="file"
        accept={IMAGE_ACCEPT}
        hidden
        tabIndex={-1}
        disabled={offline}
        onChange={(event) => {
          const file = event.target.files?.[0];
          event.target.value = ''; // the same file can be chosen again
          if (file) onPick(file);
        }}
      />
    </>
  );
}

function Thumb({ item }: { item: ImageItem }) {
  const { t } = useTranslation('admin');
  return item.src ? (
    <img src={item.src} alt="" className={styles.thumb} />
  ) : (
    <span className={styles.placeholder} title={t('images.noImage')}>
      <Icon name={item.target.type === 'card' ? 'image' : 'gift'} size={20} />
    </span>
  );
}

function StatusBadge({ item }: { item: ImageItem }) {
  const { t } = useTranslation('admin');
  if (item.src) return null;
  return item.lost ? (
    <Badge tone="warning">{t('images.fileMissing')}</Badge>
  ) : (
    <Badge tone="muted">{t('images.noImage')}</Badge>
  );
}

function ImageTableRow(props: RowProps) {
  const { item } = props;
  const { input, over, drop } = usePicker(props);
  return (
    <tr className={styles.dropTarget} data-over={over || undefined} {...drop}>
      <td>
        <Thumb item={item} />
      </td>
      <td>
        {item.name} <StatusBadge item={item} />
      </td>
      <td>{item.code}</td>
      <td>{item.set ?? '—'}</td>
      <td>
        <Picker {...props} input={input} />
      </td>
    </tr>
  );
}

function ImageCard(props: RowProps) {
  const { item } = props;
  const { input, over, drop } = usePicker(props);
  return (
    <li
      className={[styles.card, styles.dropTarget].join(' ')}
      data-over={over || undefined}
      {...drop}
    >
      <Thumb item={item} />
      <span className={styles.cardText}>
        <span className={styles.cardTitle}>{item.name}</span>
        <span className={styles.cardMeta}>
          {item.code} · {item.set ?? '—'} <StatusBadge item={item} />
        </span>
      </span>
      <Picker {...props} input={input} />
    </li>
  );
}
