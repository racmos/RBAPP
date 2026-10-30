import { useState } from 'react';
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router';
import { useSearchNavigation } from '@/catalog';
import { ApiError } from '@/api/errors';
import {
  listAdminProducts,
  patchAdminProduct,
  type AdminProduct,
  type AdminProductPatch,
} from '@/api/endpoints';
import { PRODUCT_KINDS } from '@/api/types';
import { fieldErrorsFromDetails } from '@/auth/formHelpers';
import { DebouncedInput, useGameMeta } from '@/catalog';
import { Badge } from '@/components/ui/Badge';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { ChipGroup, FilterChip } from '@/components/ui/FilterChip';
import { Modal } from '@/components/ui/Modal';
import { PageHeader } from '@/components/ui/PageHeader';
import { Pagination } from '@/components/ui/Pagination';
import { Select } from '@/components/ui/Select';
import { Sheet } from '@/components/ui/Sheet';
import { Skeleton } from '@/components/ui/Skeleton';
import { Switch } from '@/components/ui/Switch';
import { pushToast } from '@/components/ui/toastStore';
import { translateError, useDocumentTitle } from '@/i18n';
import { down, up } from '@/lib/breakpoints';
import { formatDateTime, formatMoney, type Lang } from '@/lib/format';
import { useMediaQuery } from '@/lib/useMediaQuery';
import { useOnline } from '@/lib/useOnline';
import { ProductEditor, ProductThumb } from './ProductEditor';
import { SidePanel } from '@/components/ui/SidePanel';
import { TableScroll } from '@/components/ui/TableScroll';
import styles from './ProductsAdminPage.module.css';

const FIELDS = ['kind', 'set_id', 'hidden'] as const;
const TRISTATE = ['yes', 'no'] as const;

/** Products admin (F14-d S5): filters in the URL, table or cards, drawer or panel editor. */
export function ProductsAdminPage() {
  const { t, i18n } = useTranslation('admin');
  const { t: tp } = useTranslation('products');
  const { t: common } = useTranslation('common');
  const lang: Lang = i18n.language.split('-')[0] === 'en' ? 'en' : 'es';
  const offline = !useOnline();
  const phone = useMediaQuery(down('md'));
  const wide = useMediaQuery(up('2xl'));
  const queryClient = useQueryClient();
  const [params] = useSearchParams();
  // latest search asked for, not the rendered one: quick changes in a row must all stay (L6)
  const { setSearchParams: setParams } = useSearchNavigation();
  const [editor, setEditor] = useState<AdminProduct | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Partial<Record<(typeof FIELDS)[number], string>>>(
    {},
  );
  const [formError, setFormError] = useState<string | null>(null);
  const gameMeta = useGameMeta();
  useDocumentTitle(t('products.title'));

  const query = useQuery({
    queryKey: ['admin', 'products', params.toString()],
    queryFn: ({ signal }) => listAdminProducts(params.toString(), signal),
    // Keep the filters bar mounted while the next page loads (it holds the typed search).
    placeholderData: keepPreviousData,
  });

  const save = useMutation({
    mutationFn: ({ product, patch }: { product: AdminProduct; patch: AdminProductPatch }) =>
      patchAdminProduct(product.id, patch),
    onSuccess: () => {
      pushToast({ kind: 'success', message: t('products.saved') });
      setEditor(null);
      setFieldErrors({});
      setFormError(null);
      void queryClient.invalidateQueries({ queryKey: ['admin'] });
    },
    onError: (error: unknown) => {
      const mapped =
        error instanceof ApiError && error.kind === 'http' && error.status === 400
          ? fieldErrorsFromDetails(error.details, i18n, FIELDS)
          : {};
      setFieldErrors(mapped);
      setFormError(Object.keys(mapped).length > 0 ? null : translateError(error, i18n));
    },
  });

  const update = (change: (next: URLSearchParams) => void) =>
    setParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        change(next);
        next.delete('page');
        return next;
      },
      { replace: true },
    );
  const setParam = (key: string, value: string | null) =>
    update((next) => {
      if (value === null || value === '') next.delete(key);
      else next.set(key, value);
    });
  const kinds = params.getAll('kind');
  const toggleKind = (kind: string) =>
    update((next) => {
      const now = next.getAll('kind');
      const chosen = now.includes(kind) ? now.filter((k) => k !== kind) : [...now, kind];
      next.delete('kind');
      for (const value of PRODUCT_KINDS) if (chosen.includes(value)) next.append('kind', value);
    });

  const header = <PageHeader title={t('products.title')} subtitle={t('products.subtitle')} />;

  if (query.isPending) {
    return (
      <>
        {header}
        <Skeleton label={t('products.title')} lines={4} />
      </>
    );
  }

  if (query.isError) {
    return (
      <>
        {header}
        <ErrorState message={common('errorState.title')} onRetry={() => void query.refetch()} />
      </>
    );
  }

  const { items, meta } = query.data;
  const sets = gameMeta.data?.sets ?? [];
  const yesNo = (value: boolean) => (value ? t('products.yes') : t('products.no'));
  const price = (product: AdminProduct) =>
    product.price ? formatMoney(product.price.value, lang) : '—';

  const openEditor = (product: AdminProduct) => {
    setFieldErrors({});
    setFormError(null);
    setEditor(product);
  };

  const editorPane = editor && (
    <ProductEditor
      key={editor.id}
      product={editor}
      sets={sets}
      fieldErrors={fieldErrors}
      formError={formError}
      pending={save.isPending}
      offline={offline}
      offlineHint={common('offline.editDisabled')}
      onSave={(patch) => save.mutate({ product: editor, patch })}
      onCancel={() => setEditor(null)}
    />
  );

  const pagination = (
    <Pagination
      page={meta.page}
      pages={meta.pages}
      onChange={(page) =>
        setParams((previous) => {
          const next = new URLSearchParams(previous);
          next.set('page', String(page));
          return next;
        })
      }
    />
  );

  return (
    <>
      {header}
      <div className={styles.filters}>
        <label className={styles.filterField}>
          {t('products.filters.search')}
          <DebouncedInput
            aria-label={t('products.filters.search')}
            value={params.get('q') ?? ''}
            onCommit={(next) => setParam('q', next.trim() || null)}
          />
        </label>
        {(['hidden', 'listed'] as const).map((key) => (
          <label key={key} className={styles.filterField}>
            {t(`products.filters.${key}`)}
            <Select
              aria-label={t(`products.filters.${key}`)}
              value={params.get(key) ?? ''}
              onChange={(event) => setParam(key, event.target.value || null)}
            >
              <option value="">{t('products.any')}</option>
              {TRISTATE.map((value) => (
                <option key={value} value={value}>
                  {t(`products.${value}`)}
                </option>
              ))}
            </Select>
          </label>
        ))}
        <Switch
          label={t('products.filters.noSet')}
          checked={params.get('no_set') === 'true'}
          onCheckedChange={(checked) => setParam('no_set', checked ? 'true' : null)}
        />
        <Switch
          label={t('products.filters.noImage')}
          checked={params.get('no_image') === 'true'}
          onCheckedChange={(checked) => setParam('no_image', checked ? 'true' : null)}
        />
        {!phone && (
          <label className={styles.filterField}>
            {t('cards.filters.pageSize')}
            <Select
              aria-label={t('cards.filters.pageSize')}
              value={params.get('per_page') ?? '50'}
              onChange={(event) => setParam('per_page', event.target.value)}
            >
              {['50', '100', '200'].map((size) => (
                <option key={size} value={size}>
                  {size}
                </option>
              ))}
            </Select>
          </label>
        )}
        <ChipGroup legend={t('products.columns.kind')}>
          {PRODUCT_KINDS.map((kind) => (
            <FilterChip
              key={kind}
              label={tp(`kind.${kind}`)}
              pressed={kinds.includes(kind)}
              onClick={() => toggleKind(kind)}
            />
          ))}
        </ChipGroup>
      </div>
      {items.length === 0 ? (
        <EmptyState title={t('products.title')} body={t('products.empty')} />
      ) : !phone ? (
        <div className={wide ? styles.layout : undefined}>
          <div>
            <TableScroll>
              <table className={styles.table}>
                <caption className="sr-only">{t('products.caption')}</caption>
                <thead>
                  <tr>
                    <th scope="col">{t('products.columns.image')}</th>
                    <th scope="col">{t('products.columns.name')}</th>
                    <th scope="col">{t('products.columns.kind')}</th>
                    <th scope="col">{t('products.columns.set')}</th>
                    <th scope="col">{t('products.columns.price')}</th>
                    <th scope="col">{t('products.columns.listed')}</th>
                    <th scope="col">{t('products.columns.hidden')}</th>
                    <th scope="col">{t('products.columns.updated')}</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <tr key={item.id} data-selected={editor?.id === item.id || undefined}>
                      <td>
                        <ProductThumb src={item.image_src} />
                      </td>
                      <td>
                        <button
                          type="button"
                          className={styles.nameButton}
                          disabled={offline}
                          onClick={() => openEditor(item)}
                        >
                          {item.name}
                        </button>
                      </td>
                      <td>{tp(`kind.${item.kind}`)}</td>
                      <td>{item.set_id ?? '—'}</td>
                      <td>{price(item)}</td>
                      <td>{yesNo(item.listed)}</td>
                      <td>
                        {item.hidden ? (
                          <Badge tone="warning">{t('products.yes')}</Badge>
                        ) : (
                          t('products.no')
                        )}
                      </td>
                      <td>{item.updated_at ? formatDateTime(item.updated_at, lang) : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </TableScroll>
            {pagination}
          </div>
          {wide && (
            <SidePanel
              id="admin-products-editor"
              kind="editor"
              side="end"
              label={t('panels.editor')}
              className={styles.editorPanel}
            >
              {editorPane ?? <p>{t('products.pickOne')}</p>}
            </SidePanel>
          )}
        </div>
      ) : (
        <div className={styles.rows}>
          {items.map((item) => (
            <button
              key={item.id}
              type="button"
              className={styles.row}
              disabled={offline}
              onClick={() => openEditor(item)}
            >
              <ProductThumb src={item.image_src} />
              <span>
                <span className={styles.rowTitle}>{item.name}</span>
                <span className={styles.rowMeta}>
                  {tp(`kind.${item.kind}`)} · {item.set_id ?? '—'} · {price(item)}
                  {item.hidden && ` · ${t('products.columns.hidden')}`}
                </span>
              </span>
            </button>
          ))}
          {pagination}
        </div>
      )}
      {!wide && editor && (
        <EditorDialog phone={phone} title={editor.name} onClose={() => setEditor(null)}>
          {editorPane}
        </EditorDialog>
      )}
    </>
  );
}

function EditorDialog({
  phone,
  title,
  onClose,
  children,
}: {
  phone: boolean;
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  return phone ? (
    <Sheet open title={title} onClose={onClose}>
      {children}
    </Sheet>
  ) : (
    <Modal open title={title} onClose={onClose} variant="side">
      {children}
    </Modal>
  );
}
