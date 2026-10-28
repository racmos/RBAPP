import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { CardSummary, GameMeta } from '@/api/types';
import { CardCombobox } from '@/catalog';
import { Button } from '@/components/ui/Button';
import { Sheet } from '@/components/ui/Sheet';
import { Switch } from '@/components/ui/Switch';
import { pushToast } from '@/components/ui/toastStore';
import { translateError } from '@/i18n';
import { MoneyField } from './MoneyField';
import { OptionSelect } from './OptionSelect';
import { useAddLine } from './queries';
import { Stepper } from './Stepper';
import styles from './AddSheet.module.css';

type AddSheetProps = {
  open: boolean;
  onClose: () => void;
  meta: Pick<GameMeta, 'conditions' | 'languages'> | undefined;
  offline: boolean;
};

/** Adds a card to the collection; stays open for the next one (F3-g S7). */
export function AddSheet({ open, onClose, meta, offline }: AddSheetProps) {
  const { t, i18n } = useTranslation('collection');
  const { t: tCommon } = useTranslation('common');
  const add = useAddLine();
  const [card, setCard] = useState<CardSummary | null>(null);
  const [foil, setFoil] = useState(false);
  const [qty, setQty] = useState(1);
  const [condition, setCondition] = useState<string | null>(null);
  const [language, setLanguage] = useState<string | null>(null);
  const [purchase, setPurchase] = useState<number | null>(null);
  const [selling, setSelling] = useState(false);

  const choose = (chosen: CardSummary) => {
    setCard(chosen);
    if (!chosen.foilable) setFoil(false);
  };

  const submit = () => {
    if (!card) return;
    add.mutate(
      {
        set_id: card.set_id,
        card_id: card.card_id,
        foil: foil && card.foilable,
        qty,
        condition,
        language,
        purchase_price: purchase,
        selling,
      },
      {
        onSuccess: ({ merged }) => {
          pushToast({ kind: 'success', message: t(merged ? 'add.merged' : 'add.added') });
          setCard(null);
          setFoil(false);
          setQty(1);
        },
        onError: (error) => pushToast({ kind: 'error', message: translateError(error, i18n) }),
      },
    );
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
        <CardCombobox label={t('add.card')} onSelect={choose} />
        <p className={styles.chosen} aria-live="polite">
          {card ? t('add.chosen', { name: card.name }) : t('add.chooseFirst')}
        </p>
        <Switch
          label={t('add.foil')}
          checked={foil}
          disabled={offline || !card || !card.foilable}
          onCheckedChange={setFoil}
        />
        {card && !card.foilable && <p className={styles.hint}>{t('add.foilNotAvailable')}</p>}
        <Stepper label={t('line.qty')} value={qty} min={1} max={9999} onCommit={setQty} />
        <OptionSelect
          kind="condition"
          label={t('line.condition')}
          value={condition}
          options={meta?.conditions ?? []}
          disabled={offline}
          onChange={setCondition}
        />
        <OptionSelect
          kind="language"
          label={t('line.language')}
          value={language}
          options={meta?.languages ?? []}
          disabled={offline}
          onChange={setLanguage}
        />
        <MoneyField
          label={t('line.purchasePrice')}
          value={purchase}
          disabled={offline}
          onCommit={setPurchase}
        />
        <Switch
          label={t('line.selling')}
          checked={selling}
          disabled={offline}
          onCheckedChange={setSelling}
        />
        <Button type="submit" block pending={add.isPending} disabled={offline || !card}>
          {t('add.submit')}
        </Button>
      </form>
    </Sheet>
  );
}
