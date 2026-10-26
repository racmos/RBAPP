import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { ApiError } from '@/api/errors';
import {
  createAdminSet,
  deleteAdminSet,
  listAdminSets,
  patchAdminSet,
  type AdminSet,
} from '@/api/endpoints';
import { fieldErrorsFromDetails } from '@/auth/formHelpers';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { Modal } from '@/components/ui/Modal';
import { PageHeader } from '@/components/ui/PageHeader';
import { Sheet } from '@/components/ui/Sheet';
import { Skeleton } from '@/components/ui/Skeleton';
import { pushToast } from '@/components/ui/toastStore';
import { translateError } from '@/i18n';
import { formatDate, formatDateTime, type Lang } from '@/lib/format';
import { up } from '@/lib/breakpoints';
import { useMediaQuery } from '@/lib/useMediaQuery';
import { useOnline } from '@/lib/useOnline';
import { useDocumentTitle } from '@/i18n';
import { SetEditor, type SetForm } from './SetEditor';
import styles from './SetsPage.module.css';

type SortKey = 'id' | 'name' | 'releaseDate';
type EditorTarget = { mode: 'create' } | { mode: 'edit'; set: AdminSet };

/** Sets admin (F13-f S4-S6): table on desktop, cards on phones, editor aside. */
export function SetsPage() {
  const { t, i18n } = useTranslation('admin');
  const { t: common } = useTranslation('common');
  const lang = i18n.language.split('-')[0] === 'en' ? 'en' : 'es';
  const offline = !useOnline();
  const wide = useMediaQuery(up('2xl'));
  const desktop = useMediaQuery(up('lg'));
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ['admin', 'sets'],
    queryFn: ({ signal }) => listAdminSets(signal),
  });
  const [sort, setSort] = useState<{ key: SortKey; dir: 'asc' | 'desc' }>({
    key: 'id',
    dir: 'asc',
  });
  const [editor, setEditor] = useState<EditorTarget | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<AdminSet | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  useDocumentTitle(t('sets.title'));

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['admin'] });

  const save = useMutation({
    mutationFn: async ({ target, form }: { target: EditorTarget; form: SetForm }) => {
      const declared =
        form.declaredCount.trim() === '' ? null : Number.parseInt(form.declaredCount, 10);
      if (target.mode === 'create') {
        return createAdminSet({
          id: form.id,
          name: form.name,
          release_date: form.releaseDate,
          declared_count: declared,
        });
      }
      const patch: Record<string, unknown> = {};
      if (form.id !== target.set.id) patch.id = form.id;
      if (form.name !== target.set.name) patch.name = form.name;
      if ((form.releaseDate || null) !== target.set.release_date)
        patch.release_date = form.releaseDate || null;
      if (declared !== target.set.declared_count) patch.declared_count = declared;
      return patchAdminSet(target.set.id, patch);
    },
    onSuccess: () => {
      pushToast({ kind: 'success', message: t('sets.saved') });
      setEditor(null);
      setFieldErrors({});
      setFormError(null);
      void refresh();
    },
    onError: (error: unknown) => {
      if (error instanceof ApiError && error.kind === 'http' && error.status === 400) {
        const raw = fieldErrorsFromDetails(error.details, i18n, [
          'id',
          'name',
          'release_date',
          'declared_count',
        ] as const);
        const mapped: Partial<Record<'id' | 'name' | 'releaseDate' | 'declaredCount', string>> = {
          ...(raw.id ? { id: raw.id } : {}),
          ...(raw.name ? { name: raw.name } : {}),
          ...(raw.release_date ? { releaseDate: raw.release_date } : {}),
          ...(raw.declared_count ? { declaredCount: raw.declared_count } : {}),
        };
        setFieldErrors(mapped);
        setFormError(null);
      } else {
        setFieldErrors({});
        setFormError(translateError(error, i18n));
      }
    },
  });

  const remove = useMutation({
    mutationFn: (id: string) => deleteAdminSet(id),
    onSuccess: () => {
      setDeleting(null);
      setDeleteError(null);
      void refresh();
    },
    onError: (error: unknown) => setDeleteError(translateError(error, i18n)),
  });

  if (query.isPending) {
    return (
      <>
        <PageHeader title={t('sets.title')} subtitle={t('sets.subtitle')} />
        <Skeleton label={t('sets.title')} lines={4} />
      </>
    );
  }

  if (query.isError) {
    return (
      <>
        <PageHeader title={t('sets.title')} subtitle={t('sets.subtitle')} />
        <ErrorState message={common('errorState.title')} onRetry={() => void query.refetch()} />
      </>
    );
  }

  const rows = [...query.data];
  const dir = sort.dir === 'asc' ? 1 : -1;
  rows.sort((a, b) => {
    const left =
      sort.key === 'releaseDate' ? (a.release_date ?? '') : a[sort.key === 'id' ? 'id' : 'name'];
    const right =
      sort.key === 'releaseDate' ? (b.release_date ?? '') : b[sort.key === 'id' ? 'id' : 'name'];
    return String(left).localeCompare(String(right)) * dir;
  });

  const toggleSort = (key: SortKey) =>
    setSort((current) =>
      current.key === key
        ? { key, dir: current.dir === 'asc' ? 'desc' : 'asc' }
        : { key, dir: 'asc' },
    );

  const openEditor = (target: EditorTarget) => {
    setFieldErrors({});
    setFormError(null);
    setEditor(target);
  };
  const editorKey = editor?.mode === 'edit' ? editor.set.id : 'new';

  const editorPane = () => (
    <>
      {editor && (
        <SetEditor
          key={editorKey}
          initial={editor.mode === 'edit' ? editor.set : null}
          fieldErrors={fieldErrors}
          formError={formError}
          pending={save.isPending}
          offline={offline}
          offlineHint={common('offline.editDisabled')}
          onSave={(form) => save.mutate({ target: editor, form })}
          onCancel={() => setEditor(null)}
        />
      )}
    </>
  );

  const newButton = (
    <Button
      disabled={offline}
      title={offline ? common('offline.editDisabled') : undefined}
      onClick={() => openEditor({ mode: 'create' })}
    >
      {t('sets.new')}
    </Button>
  );

  return (
    <>
      <PageHeader title={t('sets.title')} subtitle={t('sets.subtitle')} actions={newButton} />
      {rows.length === 0 ? (
        <EmptyState title={t('sets.title')} body={t('sets.empty')} />
      ) : desktop ? (
        <div className={wide ? styles.layout : undefined}>
          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <caption className="sr-only">{t('sets.caption')}</caption>
              <thead>
                <tr>
                  {(
                    [
                      ['id', t('sets.columns.id')],
                      ['name', t('sets.columns.name')],
                      ['releaseDate', t('sets.columns.releaseDate')],
                    ] as Array<[SortKey, string]>
                  ).map(([key, label]) => (
                    <th
                      key={key}
                      aria-sort={
                        sort.key === key
                          ? sort.dir === 'asc'
                            ? 'ascending'
                            : 'descending'
                          : 'none'
                      }
                    >
                      <button
                        type="button"
                        className={styles.sortButton}
                        onClick={() => toggleSort(key)}
                      >
                        {label}
                      </button>
                    </th>
                  ))}
                  <th scope="col">{t('sets.columns.cards')}</th>
                  <th scope="col">{t('sets.columns.window')}</th>
                  <th scope="col">{t('sets.columns.nextRun')}</th>
                  <th scope="col">{t('sets.columns.actions')}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td>{row.id}</td>
                    <td>{row.name}</td>
                    <td>{row.release_date ? formatDate(row.release_date, lang as Lang) : '—'}</td>
                    <td>
                      {t('sets.cardsValue', {
                        count: row.card_count,
                        declared: row.declared_count ?? '—',
                      })}
                    </td>
                    <td>
                      <Badge>
                        {t(
                          `window.${row.window as 'pre_release' | 'post_release' | 'monthly' | 'none'}`,
                        )}
                      </Badge>
                    </td>
                    <td>{row.next_run_at ? formatDateTime(row.next_run_at, lang as Lang) : '—'}</td>
                    <td>
                      <span className={styles.actions}>
                        <button
                          type="button"
                          className={styles.iconButton}
                          aria-label={t('sets.edit', { id: row.id })}
                          disabled={offline}
                          title={offline ? common('offline.editDisabled') : undefined}
                          onClick={() => openEditor({ mode: 'edit', set: row })}
                        >
                          ✎
                        </button>
                        <button
                          type="button"
                          className={styles.iconButton}
                          aria-label={t('sets.delete', { id: row.id })}
                          disabled={offline}
                          title={offline ? common('offline.editDisabled') : undefined}
                          onClick={() => {
                            setDeleteError(null);
                            setDeleting(row);
                          }}
                        >
                          🗑
                        </button>
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {wide && (
            <div className={styles.editorPanel}>
              {editor?.mode === 'edit' ? (
                <>
                  <h2 className={styles.editorTitle}>{editor.set.name}</h2>
                  {editorPane()}
                </>
              ) : (
                <p>{t('sets.pickOne')}</p>
              )}
            </div>
          )}
        </div>
      ) : (
        <div className={styles.cards}>
          {rows.map((row) => (
            <article key={row.id} className={styles.card}>
              <h2 className={styles.cardTitle}>
                {row.id} · {row.name}
              </h2>
              <p className={styles.cardMeta}>
                {row.release_date ? formatDate(row.release_date, lang as Lang) : '—'} ·{' '}
                <Badge>
                  {t(`window.${row.window as 'pre_release' | 'post_release' | 'monthly' | 'none'}`)}
                </Badge>
              </p>
              <details className={styles.menu}>
                <summary>{t('sets.columns.actions')}</summary>
                <div className={styles.actions}>
                  <button
                    type="button"
                    className={styles.iconButton}
                    aria-label={t('sets.edit', { id: row.id })}
                    disabled={offline}
                    onClick={() => openEditor({ mode: 'edit', set: row })}
                  >
                    ✎
                  </button>
                  <button
                    type="button"
                    className={styles.iconButton}
                    aria-label={t('sets.delete', { id: row.id })}
                    disabled={offline}
                    onClick={() => {
                      setDeleteError(null);
                      setDeleting(row);
                    }}
                  >
                    🗑
                  </button>
                </div>
              </details>
            </article>
          ))}
        </div>
      )}
      {!wide && editor && (
        <EditorDialog
          phone={!desktop}
          title={editor.mode === 'create' ? t('sets.new') : editor.set.name}
          onClose={() => setEditor(null)}
        >
          {editorPane()}
        </EditorDialog>
      )}
      <ConfirmDialog
        open={deleting !== null}
        title={deleting ? t('sets.confirmDelete.title', { id: deleting.id }) : ''}
        message={deleting ? t('sets.confirmDelete.body') : ''}
        confirmLabel={common('actions.delete')}
        cancelLabel={common('actions.cancel')}
        danger
        onConfirm={() => {
          if (deleting) remove.mutate(deleting.id);
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
