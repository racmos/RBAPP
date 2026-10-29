import { useEffect, useId, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { CardSummary, CollectionLineWithCard, GameMeta } from '@/api/types';
import { CardCombobox } from '@/catalog';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { Select } from '@/components/ui/Select';
import { Sheet } from '@/components/ui/Sheet';
import { Switch } from '@/components/ui/Switch';
import { pushToast } from '@/components/ui/toastStore';
import { translateError } from '@/i18n';
import { MoneyField } from './MoneyField';
import { OptionSelect } from './OptionSelect';
import { useAddLine, useDeleteLine, usePatchLine } from './queries';
import { readChoices, writeChoices, type QuickAddChoices } from './quickAdd';
import { Stepper } from './Stepper';
import styles from './AddSheet.module.css';

type AddSheetProps = {
  open: boolean;
  onClose: () => void;
  meta: Pick<GameMeta, 'conditions' | 'languages' | 'sets'> | undefined;
  offline: boolean;
};

/** A line added while the sheet was in use; `created` is false when the copies were merged. */
type SessionRow = {
  card: CardSummary;
  line: CollectionLineWithCard;
  qty: number;
  created: boolean;
};

const SESSION_ROWS = 10;

/**
 * Adds cards to the collection (F3-g S7). It stays open for the next card, keeps the set,
 * foil, quantity, condition, language, price and selling choices for the session, adds the
 * highlighted card on Enter and lists what was added with an undo per row (owner feedback S9).
 */
export function AddSheet({ open, onClose, meta, offline }: AddSheetProps) {
  const { t, i18n } = useTranslation('collection');
  const { t: tCommon } = useTranslation('common');
  const { t: tErrors } = useTranslation('errors');
  const add = useAddLine();
  const remove = useDeleteLine();
  const patch = usePatchLine();
  const search = useRef<HTMLInputElement>(null);
  const sessionTitle = useId();
  const [card, setCard] = useState<CardSummary | null>(null);
  const [choices, setChoices] = useState<QuickAddChoices>(readChoices);
  const [rows, setRows] = useState<SessionRow[]>([]);
  const [undoing, setUndoing] = useState<number | null>(null);

  const change = (patchChoices: Partial<QuickAddChoices>) =>
    setChoices((current) => ({ ...current, ...patchChoices }));

  useEffect(() => writeChoices(choices), [choices]);

  // After the dialog has opened (its own effect runs first): the search is where adding starts.
  useEffect(() => {
    if (open) search.current?.focus();
  }, [open]);

  const sets = meta?.sets ?? [];
  const setId =
    choices.set !== null && (!meta || sets.some((set) => set.id === choices.set))
      ? choices.set
      : null;

  const submit = (target: CardSummary | null = card) => {
    if (!target || offline || add.isPending) return;
    if (choices.foil && !target.foilable) {
      pushToast({ kind: 'error', message: tErrors('code.foil_not_allowed') });
      return;
    }
    const { qty, foil } = choices;
    add.mutate(
      {
        set_id: target.set_id,
        card_id: target.card_id,
        foil,
        qty,
        condition: choices.condition,
        language: choices.language,
        purchase_price: choices.purchase_price,
        selling: choices.selling,
      },
      {
        onSuccess: ({ line, merged }) => {
          pushToast({ kind: 'success', message: t(merged ? 'add.merged' : 'add.added') });
          setRows((current) => {
            const known = current.find((row) => row.line.id === line.id);
            const row = known
              ? { ...known, line, qty: known.qty + qty }
              : { card: target, line, qty, created: !merged };
            return [row, ...current.filter((other) => other !== known)].slice(0, SESSION_ROWS);
          });
          setCard(null);
          search.current?.focus();
        },
        onError: (error) => pushToast({ kind: 'error', message: translateError(error, i18n) }),
      },
    );
  };

  const putBack = (deleted: CollectionLineWithCard) =>
    add
      .mutateAsync({
        set_id: deleted.set_id,
        card_id: deleted.card_id,
        foil: deleted.foil,
        qty: deleted.qty,
        condition: deleted.condition,
        language: deleted.language,
        purchase_price: deleted.purchase_price,
        selling: deleted.selling,
        sell_qty: deleted.sell_qty,
        sell_price: deleted.sell_price,
      })
      .then(() => pushToast({ kind: 'success', message: t('line.restored') }))
      .catch((error) => pushToast({ kind: 'error', message: translateError(error, i18n) }));

  // A line this session created is deleted (and can be put back); copies merged into a line
  // that was already there are taken off it, guarded by the change time the add returned.
  const undo = (row: SessionRow) => {
    setUndoing(row.line.id);
    const done = row.created
      ? remove.mutateAsync(row.line.id).then(({ deleted }) =>
          pushToast({
            kind: 'success',
            message: t('add.undone'),
            duration: 8000,
            action: { label: t('line.undo'), onAction: () => void putBack(deleted) },
          }),
        )
      : patch
          .mutateAsync({
            id: row.line.id,
            body: { qty: row.line.qty - row.qty, if_updated_at: row.line.updated_at },
          })
          .then(() => pushToast({ kind: 'success', message: t('add.undone') }));
    done
      .then(() => setRows((current) => current.filter((other) => other !== row)))
      .catch((error) => pushToast({ kind: 'error', message: translateError(error, i18n) }))
      .finally(() => setUndoing(null));
  };

  return (
    <Sheet open={open} onClose={onClose} title={t('add.title')}>
      <form
        className={styles.form}
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
      >
        {offline && <p className={styles.offline}>{tCommon('offline.editDisabled')}</p>}
        <Field label={t('add.set')}>
          {(control) => (
            <Select
              {...control}
              value={setId ?? ''}
              onChange={(event) => change({ set: event.target.value || null })}
            >
              <option value="">{t('add.allSets')}</option>
              {sets.map((set) => (
                <option key={set.id} value={set.id}>
                  {`${set.name} (${set.id})`}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <CardCombobox
          label={t('add.card')}
          filters={setId ? { set: [setId] } : undefined}
          inputRef={search}
          onSelect={setCard}
          onEnterSelect={(chosen) => submit(chosen)}
        />
        <p className={styles.hint}>{t('add.enterHint')}</p>
        <p className={styles.chosen} aria-live="polite">
          {card ? t('add.chosen', { name: card.name }) : t('add.chooseFirst')}
        </p>
        <Switch
          label={t('add.foil')}
          checked={choices.foil}
          disabled={offline}
          onCheckedChange={(foil) => change({ foil })}
        />
        {card && !card.foilable && <p className={styles.hint}>{t('add.foilNotAvailable')}</p>}
        <div className={styles.choices}>
          <Stepper
            label={t('line.qty')}
            value={choices.qty}
            min={1}
            max={9999}
            disabled={offline}
            onCommit={(qty) => change({ qty })}
          />
          <OptionSelect
            kind="condition"
            label={t('line.condition')}
            value={choices.condition}
            options={meta?.conditions ?? []}
            disabled={offline}
            onChange={(condition) => change({ condition })}
          />
          <OptionSelect
            kind="language"
            label={t('line.language')}
            value={choices.language}
            options={meta?.languages ?? []}
            disabled={offline}
            onChange={(language) => change({ language })}
          />
          <MoneyField
            label={t('line.purchasePrice')}
            value={choices.purchase_price}
            disabled={offline}
            onCommit={(purchase_price) => change({ purchase_price })}
          />
        </div>
        <Switch
          label={t('line.selling')}
          checked={choices.selling}
          disabled={offline}
          onCheckedChange={(selling) => change({ selling })}
        />
        <Button type="submit" block pending={add.isPending} disabled={offline || !card}>
          {t('add.submit')}
        </Button>
      </form>
      {rows.length > 0 && (
        <section className={styles.session} aria-labelledby={sessionTitle}>
          <h3 id={sessionTitle} className={styles.sessionTitle}>
            {t('add.session')}
          </h3>
          <ul className={styles.rows} aria-labelledby={sessionTitle}>
            {rows.map((row) => (
              <li key={row.line.id} className={styles.row}>
                <span className={styles.rowBody}>
                  <span className={styles.rowName}>{row.card.name}</span>
                  <span className={styles.rowMeta}>
                    {`${row.card.set_id} #${row.card.card_id}`}
                    {row.line.foil && ` · ${t('add.foil')}`}
                    {` · ${t('add.copies', { count: row.qty })}`}
                  </span>
                </span>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  aria-label={t('add.undoRow', { name: row.card.name })}
                  disabled={offline || undoing !== null}
                  pending={undoing === row.line.id}
                  onClick={() => undo(row)}
                >
                  {t('line.undo')}
                </Button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </Sheet>
  );
}
