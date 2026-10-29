import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router';
import { ApiError } from '@/api/errors';
import {
  createAdminCard,
  deleteAdminCard,
  listAdminCards,
  listAdminSets,
  patchAdminCard,
  type AdminCard,
} from '@/api/endpoints';
import { fieldErrorsFromDetails } from '@/auth/formHelpers';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { Input } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import { PageHeader } from '@/components/ui/PageHeader';
import { Pagination } from '@/components/ui/Pagination';
import { Select } from '@/components/ui/Select';
import { Sheet } from '@/components/ui/Sheet';
import { Skeleton } from '@/components/ui/Skeleton';
import { Switch } from '@/components/ui/Switch';
import { pushToast } from '@/components/ui/toastStore';
import { translateError } from '@/i18n';
import { useDocumentTitle } from '@/i18n';
import { up } from '@/lib/breakpoints';
import { useMediaQuery } from '@/lib/useMediaQuery';
import { useOnline } from '@/lib/useOnline';
import { CardEditor, type CardForm } from './CardEditor';
import { TableScroll } from '@/components/ui/TableScroll';
import styles from './CardsAdminPage.module.css';

const RARITIES = ['Common', 'Uncommon', 'Rare', 'Epic', 'Showcase'];
const FIELDS = [
  'name',
  'domain',
  'type',
  'tags',
  'energy',
  'power',
  'might',
  'ability',
  'rarity',
  'artist',
  'image_url',
] as const;

type EditorTarget = { mode: 'create' } | { mode: 'edit'; card: AdminCard };

/** Cards admin (F13-f S7, S8): filters in the URL, table or list, drawer editor. */
export function CardsAdminPage() {
  const { t, i18n } = useTranslation('admin');
  const { t: common } = useTranslation('common');
  const offline = !useOnline();
  const desktop = useMediaQuery(up('lg'));
  const wide = useMediaQuery(up('2xl'));
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();
  const [search, setSearch] = useState(params.get('q') ?? '');
  const [editor, setEditor] = useState<EditorTarget | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<AdminCard | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  useDocumentTitle(t('cards.title'));

  useEffect(() => {
    const timer = setTimeout(() => {
      setParams(
        (previous) => {
          const next = new URLSearchParams(previous);
          if (search) next.set('q', search);
          else next.delete('q');
          next.delete('page');
          // Skip no-op navigations: they remount and drop element handles.
          if (next.toString() === previous.toString()) return previous;
          return next;
        },
        { replace: true },
      );
    }, 300);
    return () => clearTimeout(timer);
  }, [search, setParams]);

  const query = useQuery({
    queryKey: ['admin', 'cards', params.toString()],
    queryFn: ({ signal }) => {
      const queryParams: Record<string, string | string[]> = {};
      for (const [key, value] of params.entries()) {
        const current = queryParams[key];
        if (current === undefined) queryParams[key] = value;
        else if (Array.isArray(current)) current.push(value);
        else queryParams[key] = [current, value];
      }
      return listAdminCards(queryParams, signal);
    },
  });
  const setsQuery = useQuery({
    queryKey: ['admin', 'sets'],
    queryFn: ({ signal }) => listAdminSets(signal),
  });

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['admin'] });

  const save = useMutation({
    mutationFn: async ({ target, form }: { target: EditorTarget; form: CardForm }) => {
      const numbers: Record<string, number | null> = {};
      for (const field of ['energy', 'power', 'might']) {
        const raw = form[field].trim();
        numbers[field] = raw === '' ? null : Number.parseInt(raw, 10);
      }
      if (target.mode === 'create') {
        return createAdminCard({
          set_id: form.set_id,
          card_id: form.card_id,
          name: form.name,
          domain: form.domain || null,
          type: form.type || null,
          tags: form.tags || null,
          ...numbers,
          ability: form.ability || null,
          rarity: form.rarity || null,
          artist: form.artist || null,
          image_url: form.image_url || null,
        });
      }
      return patchAdminCard(target.card.set_id, target.card.card_id, {
        name: form.name,
        domain: form.domain || null,
        type: form.type || null,
        tags: form.tags || null,
        ...numbers,
        ability: form.ability || null,
        rarity: form.rarity || null,
        artist: form.artist || null,
        image_url: form.image_url || null,
      });
    },
    onSuccess: () => {
      pushToast({ kind: 'success', message: t('cards.saved') });
      setEditor(null);
      setFieldErrors({});
      setFormError(null);
      void refresh();
    },
    onError: (error: unknown) => {
      if (error instanceof ApiError && error.kind === 'http' && error.status === 400) {
        setFieldErrors(fieldErrorsFromDetails(error.details, i18n, FIELDS));
        setFormError(null);
      } else {
        setFieldErrors({});
        setFormError(translateError(error, i18n));
      }
    },
  });

  const remove = useMutation({
    mutationFn: (card: AdminCard) => deleteAdminCard(card.set_id, card.card_id),
    onSuccess: () => {
      setDeleting(null);
      setDeleteError(null);
      void refresh();
    },
    onError: (error: unknown) => setDeleteError(translateError(error, i18n)),
  });

  const setParam = (key: string, value: string | null) =>
    setParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        next.delete('page');
        if (value === null || value === '') next.delete(key);
        else next.set(key, value);
        return next;
      },
      { replace: true },
    );

  if (query.isPending) {
    return (
      <>
        <PageHeader title={t('cards.title')} subtitle={t('cards.subtitle')} />
        <Skeleton label={t('cards.title')} lines={4} />
      </>
    );
  }

  if (query.isError) {
    return (
      <>
        <PageHeader title={t('cards.title')} subtitle={t('cards.subtitle')} />
        <ErrorState message={common('errorState.title')} onRetry={() => void query.refetch()} />
      </>
    );
  }

  const { items, meta } = query.data;
  const sets = setsQuery.data ?? [];
  const editorKey = editor?.mode === 'edit' ? editor.card.key : 'new';

  const openEditor = (target: EditorTarget) => {
    setFieldErrors({});
    setFormError(null);
    setEditor(target);
  };

  const editorPane = editor && (
    <CardEditor
      key={editorKey}
      initial={editor.mode === 'edit' ? editor.card : null}
      fieldErrors={fieldErrors}
      formError={formError}
      pending={save.isPending}
      offline={offline}
      offlineHint={common('offline.editDisabled')}
      onSave={(form) => save.mutate({ target: editor, form })}
      onCancel={() => setEditor(null)}
      onDelete={() => {
        if (editor.mode === 'edit') {
          setDeleteError(null);
          setDeleting(editor.card);
        }
      }}
    />
  );

  return (
    <>
      <PageHeader
        title={t('cards.title')}
        subtitle={t('cards.subtitle')}
        actions={
          <Button
            disabled={offline}
            title={offline ? common('offline.editDisabled') : undefined}
            onClick={() => openEditor({ mode: 'create' })}
          >
            {t('cards.new')}
          </Button>
        }
      />
      <div className={styles.filters}>
        <label className={styles.filterField}>
          {t('cards.filters.allSets')}
          <Select
            aria-label={t('cards.filters.allSets')}
            value={params.get('set') ?? ''}
            disabled={offline}
            onChange={(event) => setParam('set', event.target.value || null)}
          >
            <option value="">{t('cards.filters.allSets')}</option>
            {sets.map((set) => (
              <option key={set.id} value={set.id}>
                {set.id}
              </option>
            ))}
          </Select>
        </label>
        <label className={styles.filterField}>
          {t('cards.filters.allRarities')}
          <Select
            aria-label={t('cards.filters.allRarities')}
            value={params.get('rarity') ?? ''}
            disabled={offline}
            onChange={(event) => setParam('rarity', event.target.value || null)}
          >
            <option value="">{t('cards.filters.allRarities')}</option>
            {RARITIES.map((rarity) => (
              <option key={rarity} value={rarity}>
                {rarity}
              </option>
            ))}
          </Select>
        </label>
        <label className={styles.filterField}>
          {t('cards.filters.type')}
          <Input
            aria-label={t('cards.filters.type')}
            value={params.get('type') ?? ''}
            disabled={offline}
            onChange={(event) => setParam('type', event.target.value || null)}
          />
        </label>
        <label className={styles.filterField}>
          {t('cards.filters.search')}
          <Input
            aria-label={t('cards.filters.search')}
            value={search}
            disabled={offline}
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
        <Switch
          label={t('cards.filters.missingImage')}
          checked={params.get('missing_image') === 'true'}
          disabled={offline}
          onCheckedChange={(checked) => setParam('missing_image', checked ? 'true' : null)}
        />
        {desktop && (
          <label className={styles.filterField}>
            {t('cards.filters.pageSize')}
            <Select
              aria-label={t('cards.filters.pageSize')}
              value={params.get('per_page') ?? '50'}
              disabled={offline}
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
      </div>
      {items.length === 0 ? (
        <EmptyState title={t('cards.title')} body={t('cards.empty')} />
      ) : desktop ? (
        <div className={wide ? styles.layout : undefined}>
          <TableScroll>
            <table className={styles.table}>
              <caption className="sr-only">{t('cards.caption')}</caption>
              <thead>
                <tr>
                  <th scope="col">{t('cards.columns.image')}</th>
                  <th scope="col">{t('cards.columns.set')}</th>
                  <th scope="col">{t('cards.columns.number')}</th>
                  <th scope="col">{t('cards.columns.name')}</th>
                  <th scope="col">{t('cards.columns.type')}</th>
                  <th scope="col">{t('cards.columns.rarity')}</th>
                  <th scope="col">{t('sets.columns.actions')}</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.key}>
                    <td>
                      {item.image ? (
                        <img src={item.image_src ?? ''} alt="" className={styles.thumb} />
                      ) : (
                        <Badge>{t('cards.noImage')}</Badge>
                      )}
                    </td>
                    <td>{item.set_id}</td>
                    <td>{item.card_id}</td>
                    <td>{item.name}</td>
                    <td>{item.type}</td>
                    <td>{item.rarity}</td>
                    <td>
                      <span className={styles.actions}>
                        <button
                          type="button"
                          className={styles.iconButton}
                          aria-label={t('cards.edit', { name: item.name })}
                          disabled={offline}
                          onClick={() => openEditor({ mode: 'edit', card: item })}
                        >
                          ✎<span className="sr-only">{t('cards.edit', { name: item.name })}</span>
                        </button>
                        <button
                          type="button"
                          className={styles.iconButton}
                          aria-label={t('cards.delete', { name: item.name })}
                          disabled={offline}
                          onClick={() => {
                            setDeleteError(null);
                            setDeleting(item);
                          }}
                        >
                          🗑<span className="sr-only">{t('cards.delete', { name: item.name })}</span>
                        </button>
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableScroll>
          <Pagination
            page={meta.page}
            pages={meta.pages}
            onChange={(page) => setParam('page', String(page))}
          />
          {wide && (
            <div className={styles.editorPanel}>
              {editor?.mode === 'edit' ? editorPane : <p>{t('sets.pickOne')}</p>}
            </div>
          )}
        </div>
      ) : (
        <div className={styles.rows}>
          {items.map((item) => (
            <button
              key={item.key}
              type="button"
              className={styles.row}
              onClick={() => openEditor({ mode: 'edit', card: item })}
            >
              {item.image ? (
                <img src={item.image_src ?? ''} alt="" className={styles.thumb} />
              ) : null}
              <span>
                <span className={styles.rowTitle}>{item.name}</span>
                <span className={styles.rowMeta}>
                  {item.set_id} · #{item.card_id} · {item.type}
                </span>
              </span>
            </button>
          ))}
          <Pagination
            page={meta.page}
            pages={meta.pages}
            onChange={(page) => setParam('page', String(page))}
          />
        </div>
      )}
      {!wide && editor && (
        <EditorDialog
          phone={!desktop}
          title={editor.mode === 'edit' ? editor.card.name : t('cards.new')}
          onClose={() => setEditor(null)}
        >
          {editorPane}
        </EditorDialog>
      )}
      <ConfirmDialog
        open={deleting !== null}
        title={deleting ? t('cards.confirmDelete.title', { name: deleting.name }) : ''}
        message={deleting ? t('cards.confirmDelete.body') : ''}
        confirmLabel={common('actions.delete')}
        cancelLabel={common('actions.cancel')}
        danger
        onConfirm={() => {
          if (deleting) remove.mutate(deleting);
        }}
        onCancel={() => {
          setDeleting(null);
          setDeleteError(null);
        }}
      />
      {deleteError && (
        <p role="alert" className={styles.formError}>
          {deleteError}
        </p>
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
