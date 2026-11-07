import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { ApiError } from '@/api/errors';
import {
  createAdminCard,
  createCardmarketLink,
  listAdminSets,
  type AdminCard,
  type CardmarketFoil,
} from '@/api/endpoints';
import { fieldErrorsFromDetails } from '@/auth/formHelpers';
import { Button } from '@/components/ui/Button';
import { ErrorState } from '@/components/ui/ErrorState';
import { Field } from '@/components/ui/Field';
import { Select } from '@/components/ui/Select';
import { Skeleton } from '@/components/ui/Skeleton';
import { translateError } from '@/i18n';
import { sortSetsNewestFirst } from '@/lib/sets';
import { CARD_FIELDS, CardFields, cardInput, toForm, type CardForm } from '@/admin/CardEditor';
import { FormAlert } from '@/admin/FormAlert';
import { cardNameFrom, cardRef, defaultFoil, firstQuery, typeFromCategory } from './format';
import type { CardmarketItemFacts, LinkSubject } from './LinkDialog';
import { useLinkErrorText } from './parts';
import { useCandidates, useUndoToasts } from './queries';
import styles from './MatchingPage.module.css';

type CreateCardFormProps = {
  subject: LinkSubject;
  offline: boolean;
  onClose: () => void;
  /** Back to the search; `q` is its text (the id of a card that exists already). */
  onSearch: (q?: string) => void;
};

/**
 * Create the card a Cardmarket item has no match for and link the item to it (CM-c). The
 * facts of the item come from the list that opened the form, else from the candidates.
 */
export function CreateCardForm({ subject, ...props }: CreateCardFormProps) {
  const { t } = useTranslation('admin');
  const { t: common } = useTranslation('common');
  const q = firstQuery(subject.name).trim();
  const query = useCandidates(subject.id_product, q.length === 1 ? '' : q, !subject.facts);
  const product = query.data?.product;
  const facts =
    subject.facts ??
    (product ? { category: product.category, expansion: product.expansion } : null);

  if (facts) return <CreateCardBody subject={subject} facts={facts} {...props} />;
  if (query.isError) {
    return <ErrorState message={common('errorState.title')} onRetry={() => void query.refetch()} />;
  }
  return <Skeleton label={t('matching.create.loading')} lines={6} />;
}

function CreateCardBody({
  subject,
  facts,
  offline,
  onClose,
  onSearch,
}: CreateCardFormProps & { facts: CardmarketItemFacts }) {
  const { t, i18n } = useTranslation('admin');
  const { t: common } = useTranslation('common');
  const queryClient = useQueryClient();
  const toasts = useUndoToasts();
  const linkErrorText = useLinkErrorText();
  const mappedSet = facts.expansion?.set_id ?? '';
  const [form, setForm] = useState<CardForm>(() => ({
    ...toForm(null),
    set_id: mappedSet,
    name: cardNameFrom(subject.name),
    type: typeFromCategory(facts.category),
  }));
  // the slot follows the rarity and type until it is chosen by hand
  const [chosenFoil, setChosenFoil] = useState<CardmarketFoil | undefined>(undefined);
  const [fieldErrors, setFieldErrors] = useState<Partial<Record<string, string>>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [existing, setExisting] = useState<string | null>(null);
  const [created, setCreated] = useState<AdminCard | null>(null);
  const [linkError, setLinkError] = useState<unknown>(null);
  const foil =
    chosenFoil !== undefined
      ? chosenFoil
      : defaultFoil({ rarity: form.rarity || null, type: form.type || null }, []);

  const sets = useQuery({
    queryKey: ['admin', 'sets'],
    queryFn: ({ signal }) => listAdminSets(signal),
  });
  const setOptions = sortSetsNewestFirst(sets.data ?? [], (set) => set.release_date);

  const link = useMutation({
    mutationFn: ({ card, foil }: { card: AdminCard; foil: CardmarketFoil }) =>
      createCardmarketLink(subject.id_product, {
        card: { set_id: card.set_id, card_id: card.card_id },
        foil,
      }),
    onSuccess: (done) => {
      onClose();
      toasts.createdAndLinked(done);
    },
    onError: (error: unknown) => setLinkError(error),
  });

  const create = useMutation({
    mutationFn: (values: CardForm) =>
      createAdminCard({ set_id: values.set_id, card_id: values.card_id, ...cardInput(values) }),
    onSuccess: (card) => {
      setCreated(card);
      setFieldErrors({});
      setFormError(null);
      void queryClient.invalidateQueries({ queryKey: ['admin', 'cards'] });
      void queryClient.invalidateQueries({ queryKey: ['admin', 'sets'] });
      link.mutate({ card, foil });
    },
    onError: (error: unknown, values) => {
      setExisting(null);
      if (error instanceof ApiError && error.status === 409 && error.code === 'already_exists') {
        const ref = cardRef(values.set_id, values.card_id.trim().toLowerCase());
        setFieldErrors({ card_id: t('matching.create.exists', { ref }) });
        setFormError(null);
        setExisting(ref);
      } else if (error instanceof ApiError && error.kind === 'http' && error.status === 400) {
        const mapped = fieldErrorsFromDetails(error.details, i18n, CARD_FIELDS);
        setFieldErrors(mapped);
        setFormError(Object.keys(mapped).length === 0 ? translateError(error, i18n) : null);
      } else {
        setFieldErrors({});
        setFormError(translateError(error, i18n));
      }
    },
  });

  const pending = create.isPending || link.isPending;
  const locked = offline || pending || created !== null;
  const expansion = facts.expansion;
  let setHint = t('matching.create.setNone');
  if (expansion?.set_id) setHint = t('matching.create.setMapped', { name: expansion.name });
  else if (expansion) setHint = t('matching.create.setUnmapped', { name: expansion.name });

  return (
    <form
      className={styles.dialog}
      onSubmit={(event) => {
        event.preventDefault();
        if (!locked) create.mutate(form);
      }}
    >
      <p className={styles.muted}>
        {[`#${subject.id_product}`, facts.category, expansion?.name].filter(Boolean).join(' · ')}
      </p>
      <p className={styles.help}>{t('matching.create.intro')}</p>
      <CardFields
        form={form}
        onChange={(patch) => setForm((current) => ({ ...current, ...patch }) as CardForm)}
        errors={fieldErrors}
        disabled={locked}
        creating
        hints={{ set_id: setHint, card_id: t('matching.create.numberHint') }}
        setControl={(control) => (
          <Select
            {...control}
            value={form.set_id}
            disabled={locked}
            onChange={(event) => setForm((current) => ({ ...current, set_id: event.target.value }))}
          >
            <option value="">{t('matching.create.chooseSet')}</option>
            {mappedSet && !setOptions.some((set) => set.id === mappedSet) && (
              <option value={mappedSet}>{mappedSet}</option>
            )}
            {setOptions.map((set) => (
              <option key={set.id} value={set.id}>
                {t('matching.create.setOption', { id: set.id, name: set.name })}
              </option>
            ))}
          </Select>
        )}
      />
      <Field label={t('matching.create.slot')} hint={t('matching.slotHelp')}>
        {(control) => (
          <Select
            {...control}
            value={foil ?? ''}
            disabled={offline || pending}
            onChange={(event) => {
              const value = event.target.value;
              setChosenFoil(value === 'N' || value === 'S' ? value : null);
            }}
          >
            <option value="">{t('matching.slotOption.none')}</option>
            <option value="N">{t('matching.slotOption.N')}</option>
            <option value="S">{t('matching.slotOption.S')}</option>
          </Select>
        )}
      </Field>
      {formError && <FormAlert message={formError} />}
      {created && linkError !== null && (
        <div role="alert" className={styles.alert}>
          <span>
            {t('matching.create.linkFailed', {
              message: linkErrorText(linkError, {
                set_id: created.set_id,
                card_id: created.card_id,
                foil,
              }),
            })}
          </span>
          <Button
            size="sm"
            disabled={offline}
            pending={link.isPending}
            onClick={() => link.mutate({ card: created, foil })}
          >
            {t('matching.create.linkAgain')}
          </Button>
        </div>
      )}
      <div className={styles.rowActions}>
        {created === null && (
          <Button type="submit" disabled={locked} pending={create.isPending}>
            {t('matching.create.submit')}
          </Button>
        )}
        {existing && created === null && (
          <Button type="button" variant="ghost" onClick={() => onSearch(existing)}>
            {t('matching.create.useExisting')}
          </Button>
        )}
        <Button type="button" variant="ghost" onClick={() => onSearch()}>
          {t('matching.create.search')}
        </Button>
        <Button type="button" variant="ghost" onClick={onClose}>
          {common('actions.cancel')}
        </Button>
      </div>
      {offline && <span className="sr-only">{common('offline.editDisabled')}</span>}
    </form>
  );
}
