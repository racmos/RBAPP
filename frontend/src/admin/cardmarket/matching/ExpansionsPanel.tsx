import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { ApiError } from '@/api/errors';
import {
  mapCardmarketExpansion,
  unmapCardmarketExpansion,
  type CardmarketExpansionItem,
  type CardmarketExpansionSet,
  type CardmarketNewSet,
} from '@/api/endpoints';
import { fieldErrorsFromDetails } from '@/auth/formHelpers';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Checkbox } from '@/components/ui/Checkbox';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { Field } from '@/components/ui/Field';
import { Modal } from '@/components/ui/Modal';
import { Select } from '@/components/ui/Select';
import { Skeleton } from '@/components/ui/Skeleton';
import { TableScroll } from '@/components/ui/TableScroll';
import { pushToast } from '@/components/ui/toastStore';
import { translateError } from '@/i18n';
import { formatNumber } from '@/lib/format';
import { FormAlert } from '@/admin/FormAlert';
import { SetEditor, type SetForm } from '@/admin/SetEditor';
import type { PanelProps } from './MatchingPage';
import { useExpansionToasts, useExpansions } from './queries';
import styles from './MatchingPage.module.css';

/** The select value that opens the new set fields instead of choosing a set. */
const NEW_SET = '__new__';

/** "Origins (OGN)", or "GONE (not a set)" when the mapped id is not one of our sets. */
function useSetText() {
  const { t } = useTranslation('admin');
  return (id: string, name: string | null) =>
    name === null
      ? t('matching.expansions.setMissing', { id })
      : t('matching.expansions.setRef', { name, id });
}

function useExpansionName() {
  const { t } = useTranslation('admin');
  return (item: CardmarketExpansionItem) =>
    item.name ?? t('matching.expansions.unnamed', { id: item.id });
}

/**
 * "Expansions" (CM-d): every Cardmarket expansion with its products on the latest load and the
 * set of ours it maps to. Map, Change and Unmap each leave an Undo toast. "Not mapped only" is
 * on unless the URL says `show=all`.
 */
export function ExpansionsPanel({ params, setParam, offline }: PanelProps) {
  const { t, i18n } = useTranslation('admin');
  const { t: common } = useTranslation('common');
  const unmappedOnly = params.get('show') !== 'all';
  const query = useExpansions(unmappedOnly);
  const toasts = useExpansionToasts();
  const setText = useSetText();
  const nameOf = useExpansionName();
  const [mapping, setMapping] = useState<CardmarketExpansionItem | null>(null);
  const unmap = useMutation({
    mutationFn: (item: CardmarketExpansionItem) => unmapCardmarketExpansion(item.id),
    onSuccess: ({ previous }, item) => toasts.unmapped(item.id, nameOf(item), previous),
    onError: (error: unknown) => pushToast({ kind: 'error', message: translateError(error, i18n) }),
  });
  const busy = offline || unmap.isPending;

  const filters = (
    <div className={styles.filters}>
      <Checkbox
        label={t('matching.expansions.unmappedOnly')}
        checked={unmappedOnly}
        onChange={(event) => setParam('show', event.target.checked ? null : 'all')}
      />
    </div>
  );

  let body;
  if (query.isPending) {
    body = <Skeleton label={t('matching.expansions.caption')} lines={4} />;
  } else if (query.isError) {
    body = <ErrorState message={common('errorState.title')} onRetry={() => void query.refetch()} />;
  } else if (query.data.items.length === 0) {
    body = unmappedOnly ? (
      <EmptyState
        title={t('matching.expansions.emptyTitle')}
        body={t('matching.expansions.emptyBody')}
      />
    ) : (
      <EmptyState
        title={t('matching.expansions.emptyAllTitle')}
        body={t('matching.expansions.emptyAllBody')}
      />
    );
  } else {
    body = (
      <>
        <p className={styles.meta}>
          {t('matching.expansions.total', { count: query.data.meta.total })}
        </p>
        <TableScroll>
          <table className={styles.table}>
            <caption className="sr-only">{t('matching.expansions.caption')}</caption>
            <thead>
              <tr>
                <th scope="col">{t('matching.expansions.columns.expansion')}</th>
                <th scope="col">{t('matching.expansions.columns.id')}</th>
                <th scope="col">{t('matching.expansions.columns.products')}</th>
                <th scope="col">{t('matching.expansions.columns.singles')}</th>
                <th scope="col">{t('matching.expansions.columns.sealed')}</th>
                <th scope="col">{t('matching.expansions.columns.set')}</th>
                <th scope="col">{t('matching.expansions.columns.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {query.data.items.map((item) => {
                const name = nameOf(item);
                return (
                  <tr key={item.id}>
                    <td>{name}</td>
                    <td>{item.id}</td>
                    <td>{formatNumber(item.products_count)}</td>
                    <td>{formatNumber(item.singles_count)}</td>
                    <td>{formatNumber(item.sealed_count)}</td>
                    <td>
                      {item.mapped_set_id === null ? (
                        <Badge tone="warning">{t('matching.expansions.notMapped')}</Badge>
                      ) : (
                        setText(item.mapped_set_id, item.mapped_set_name)
                      )}
                    </td>
                    <td>
                      <span className={styles.rowActions}>
                        {item.mapped_set_id === null ? (
                          <Button
                            size="sm"
                            variant="ghost"
                            disabled={busy}
                            aria-label={t('matching.expansions.mapFor', { name })}
                            onClick={() => setMapping(item)}
                          >
                            {t('matching.expansions.map')}
                          </Button>
                        ) : (
                          <>
                            <Button
                              size="sm"
                              variant="ghost"
                              disabled={busy}
                              aria-label={t('matching.expansions.changeFor', { name })}
                              onClick={() => setMapping(item)}
                            >
                              {t('matching.expansions.change')}
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              disabled={busy}
                              aria-label={t('matching.expansions.unmapFor', { name })}
                              onClick={() => unmap.mutate(item)}
                            >
                              {t('matching.expansions.unmap')}
                            </Button>
                          </>
                        )}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </TableScroll>
      </>
    );
  }

  return (
    <>
      <p className={styles.help}>{t('matching.expansions.help')}</p>
      {filters}
      {body}
      <Modal
        open={mapping !== null}
        title={mapping ? t('matching.expansions.dialogTitle', { name: nameOf(mapping) }) : ''}
        onClose={() => setMapping(null)}
      >
        {mapping && query.data && (
          <MapForm
            key={mapping.id}
            item={mapping}
            sets={query.data.sets}
            offline={offline}
            onDone={() => setMapping(null)}
          />
        )}
      </Modal>
    </>
  );
}

type SetFieldErrors = Partial<Record<'id' | 'name' | 'releaseDate' | 'declaredCount', string>>;

/** Choose one of our sets, or create one with the fields of the sets admin, and map to it. */
function MapForm({
  item,
  sets,
  offline,
  onDone,
}: {
  item: CardmarketExpansionItem;
  sets: CardmarketExpansionSet[];
  offline: boolean;
  onDone: () => void;
}) {
  const { t, i18n } = useTranslation('admin');
  const { t: common } = useTranslation('common');
  const toasts = useExpansionToasts();
  const setText = useSetText();
  const name = useExpansionName()(item);
  const current = item.mapped_set_id;
  const [choice, setChoice] = useState(() =>
    sets.some((one) => one.id === current) ? (current ?? '') : '',
  );
  const [fieldErrors, setFieldErrors] = useState<SetFieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: ({ setId, createSet }: { setId: string; createSet?: CardmarketNewSet }) =>
      mapCardmarketExpansion(item.id, setId, createSet),
    onSuccess: ({ expansion, previous, created_set: created }) => {
      onDone();
      const set = expansion.mapped_set_id ?? '';
      if (created) toasts.createdAndMapped(item.id, name, set, previous);
      else toasts.mapped(item.id, name, set, previous);
    },
    onError: (error: unknown) => {
      setFieldErrors({});
      setFormError(null);
      if (error instanceof ApiError && error.status === 409 && error.code === 'already_exists') {
        setFieldErrors({ id: t('matching.expansions.setExists') });
        return;
      }
      if (error instanceof ApiError && error.kind === 'http' && error.status === 400) {
        const raw = fieldErrorsFromDetails(error.details, i18n, [
          'set_id',
          'create_set.name',
          'create_set.release_date',
          'create_set.declared_count',
        ] as const);
        const mapped: SetFieldErrors = {
          ...(raw.set_id ? { id: raw.set_id } : {}),
          ...(raw['create_set.name'] ? { name: raw['create_set.name'] } : {}),
          ...(raw['create_set.release_date']
            ? { releaseDate: raw['create_set.release_date'] }
            : {}),
          ...(raw['create_set.declared_count']
            ? { declaredCount: raw['create_set.declared_count'] }
            : {}),
        };
        if (Object.keys(mapped).length > 0 && choice === NEW_SET) {
          setFieldErrors(mapped);
          return;
        }
      }
      setFormError(translateError(error, i18n));
    },
  });

  const createAndMap = (form: SetForm) => {
    const declared =
      form.declaredCount.trim() === '' ? null : Number.parseInt(form.declaredCount, 10);
    save.mutate({
      setId: form.id,
      createSet: { name: form.name, release_date: form.releaseDate, declared_count: declared },
    });
  };

  return (
    <div className={styles.dialog}>
      {current !== null && (
        <p className={styles.current}>
          {t('matching.expansions.current', { set: setText(current, item.mapped_set_name) })}
        </p>
      )}
      <Field label={t('matching.expansions.set')}>
        {(control) => (
          <Select
            {...control}
            value={choice}
            disabled={save.isPending}
            onChange={(event) => {
              setChoice(event.target.value);
              setFieldErrors({});
              setFormError(null);
            }}
          >
            <option value="">{t('matching.expansions.choose')}</option>
            {sets.map((one) => (
              <option key={one.id} value={one.id}>
                {setText(one.id, one.name)}
              </option>
            ))}
            <option value={NEW_SET}>{t('matching.expansions.newSet')}</option>
          </Select>
        )}
      </Field>
      {choice === NEW_SET ? (
        <>
          <p className={styles.help}>{t('matching.expansions.newSetHelp')}</p>
          <SetEditor
            initial={null}
            fieldErrors={fieldErrors}
            formError={formError}
            pending={save.isPending}
            offline={offline}
            offlineHint={common('offline.editDisabled')}
            onSave={createAndMap}
            onCancel={() => {
              setChoice('');
              setFieldErrors({});
              setFormError(null);
            }}
          />
        </>
      ) : (
        <>
          {formError && <FormAlert message={formError} />}
          <div className={styles.rowActions}>
            <Button
              disabled={offline || choice === '' || choice === current}
              pending={save.isPending}
              title={offline ? common('offline.editDisabled') : undefined}
              onClick={() => save.mutate({ setId: choice })}
            >
              {t('matching.expansions.submit')}
            </Button>
            <Button variant="ghost" onClick={onDone}>
              {common('actions.cancel')}
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
