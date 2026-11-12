import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import type { CardSummary, WishFoil, Wishlist } from '@/api/types';
import { CardCombobox } from '@/catalog';
import { MoneyField } from '@/collection/MoneyField';
import { Stepper } from '@/collection/Stepper';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { Sheet } from '@/components/ui/Sheet';
import { Switch } from '@/components/ui/Switch';
import { pushToast } from '@/components/ui/toastStore';
import { useWishlistError } from './errors';
import { FINISHES, NOTE_MAX, QTY_MAX, QTY_MIN, cleanNote } from './lineParts';
import { useAddWishlistLine } from './queries';
import styles from './Wishlists.module.css';

/**
 * Adds a card to a list (F3-j): a printing, or with "Any printing" the card name; the finish, the
 * copies wanted, an optional alert price and note. It stays open for the next card; the same
 * target merges into its line (the toast says so).
 */
export function AddLineSheet({
  list,
  offline,
  onClose,
}: {
  list: Wishlist;
  offline: boolean;
  onClose: () => void;
}) {
  const { t } = useTranslation('wishlists');
  const { t: tCommon } = useTranslation('common');
  const message = useWishlistError();
  const add = useAddWishlistLine();
  const search = useRef<HTMLInputElement>(null);
  const [card, setCard] = useState<CardSummary | null>(null);
  const [anyPrinting, setAnyPrinting] = useState(false);
  const [finish, setFinish] = useState<WishFoil>('any');
  const [qty, setQty] = useState(1);
  const [maxPrice, setMaxPrice] = useState<number | null>(null);
  const [note, setNote] = useState('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => search.current?.focus(), []);

  const foilBlocked = card !== null && !card.foilable && !anyPrinting;
  const chosenFinish: WishFoil = foilBlocked && finish === 'S' ? 'any' : finish;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!card || offline) return;
    setError(null);
    const target = anyPrinting
      ? { name: card.name }
      : { set_id: card.set_id, card_id: card.card_id };
    add
      .mutateAsync({
        listId: list.id,
        body: {
          ...target,
          foil: chosenFinish,
          qty,
          max_price: maxPrice,
          note: cleanNote(note),
        },
      })
      .then(({ line, merged }) => {
        pushToast({
          kind: 'success',
          message: merged ? t('add.merged') : t('add.added', { name: line.name }),
        });
        setCard(null);
        setMaxPrice(null);
        setNote('');
        search.current?.focus();
      })
      .catch((failure) => setError(message(failure)));
  };

  const chosen = card
    ? t('add.chosen', {
        name: anyPrinting ? card.name : `${card.name} (${card.set_id} #${card.card_id})`,
      })
    : t('add.chooseFirst');

  return (
    <Sheet open onClose={onClose} title={t('add.title', { name: list.name })}>
      <form className={styles.form} onSubmit={submit} noValidate>
        {offline && <p className={styles.note}>{tCommon('offline.editDisabled')}</p>}
        <CardCombobox
          label={t('add.card')}
          inputRef={search}
          onSelect={(picked) => {
            setCard(picked);
            setError(null);
          }}
        />
        <p className={styles.chosen} aria-live="polite">
          {chosen}
        </p>
        <Switch
          label={t('add.anyPrinting')}
          checked={anyPrinting}
          disabled={offline}
          onCheckedChange={setAnyPrinting}
        />
        <p className={styles.note}>{t('add.anyPrintingHint')}</p>
        <SegmentedControl
          label={t('add.finish')}
          showLabel
          options={FINISHES.map((value) => ({
            value,
            label: t(`line.finish.${value}`),
            disabled: value === 'S' && foilBlocked,
          }))}
          value={chosenFinish}
          disabled={offline}
          onChange={setFinish}
        />
        {foilBlocked && <p className={styles.note}>{t('add.foilNotAvailable')}</p>}
        <div className={styles.choices}>
          <Stepper
            label={t('add.qty')}
            value={qty}
            min={QTY_MIN}
            max={QTY_MAX}
            disabled={offline}
            onCommit={setQty}
          />
          <MoneyField
            label={t('add.maxPrice')}
            value={maxPrice}
            disabled={offline}
            onCommit={setMaxPrice}
          />
        </div>
        <Field label={t('add.note')}>
          {(control) => (
            <Input
              {...control}
              value={note}
              maxLength={NOTE_MAX}
              disabled={offline}
              onChange={(event) => setNote(event.target.value)}
            />
          )}
        </Field>
        {error && (
          <p role="alert" className={styles.alert}>
            {error}
          </p>
        )}
        <Button type="submit" block disabled={offline || !card} pending={add.isPending}>
          {t('add.submit')}
        </Button>
      </form>
    </Sheet>
  );
}
