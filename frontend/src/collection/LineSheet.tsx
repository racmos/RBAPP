import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { CollectionGroup, CollectionLine, GameMeta } from '@/api/types';
import { Button } from '@/components/ui/Button';
import { Checkbox } from '@/components/ui/Checkbox';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { Sheet } from '@/components/ui/Sheet';
import { Switch } from '@/components/ui/Switch';
import { pushToast } from '@/components/ui/toastStore';
import { translateError } from '@/i18n';
import { MoneyField } from './MoneyField';
import { OptionSelect } from './OptionSelect';
import { useAddLine, useDeleteLine, useKeepPlayset, useSplitLine } from './queries';
import { Stepper } from './Stepper';
import { useLineSaver } from './useLineSaver';
import styles from './LineSheet.module.css';

type Options = { conditions: string[]; languages: string[] };

type LineSheetProps = {
  group: CollectionGroup;
  open: boolean;
  onClose: () => void;
  meta: Pick<GameMeta, 'conditions' | 'languages'> | undefined;
  playsetSize: number;
  offline: boolean;
};

function SplitForm({
  line,
  options,
  disabled,
  onDone,
}: {
  line: CollectionLine;
  options: Options;
  disabled: boolean;
  onDone: () => void;
}) {
  const { t, i18n } = useTranslation('collection');
  const split = useSplitLine();
  const [qty, setQty] = useState(1);
  const [condition, setCondition] = useState<string | null>(line.condition);
  const [language, setLanguage] = useState<string | null>(line.language);
  const [sellPrice, setSellPrice] = useState<number | null>(line.sell_price);

  const submit = () =>
    split.mutate(
      { id: line.id, body: { qty, condition, language, sell_price: sellPrice } },
      {
        onSuccess: () => {
          pushToast({ kind: 'success', message: t('line.split_done') });
          onDone();
        },
        onError: (error) => pushToast({ kind: 'error', message: translateError(error, i18n) }),
      },
    );

  return (
    <div className={styles.split}>
      <Stepper
        label={t('line.splitQty')}
        value={qty}
        min={1}
        max={Math.max(1, line.qty - 1)}
        disabled={disabled}
        onCommit={setQty}
      />
      <OptionSelect
        kind="condition"
        label={t('line.condition')}
        value={condition}
        options={options.conditions}
        disabled={disabled}
        onChange={setCondition}
      />
      <OptionSelect
        kind="language"
        label={t('line.language')}
        value={language}
        options={options.languages}
        disabled={disabled}
        onChange={setLanguage}
      />
      <MoneyField
        label={t('line.sellPrice')}
        value={sellPrice}
        disabled={disabled}
        onCommit={setSellPrice}
      />
      <Button onClick={submit} pending={split.isPending} disabled={disabled}>
        {t('line.splitSubmit')}
      </Button>
    </div>
  );
}

function LineEditor({
  group,
  line,
  index,
  options,
  offline,
}: {
  group: CollectionGroup;
  line: CollectionLine;
  index: number;
  options: Options;
  offline: boolean;
}) {
  const { t, i18n } = useTranslation('collection');
  const { t: tCommon } = useTranslation('common');
  const save = useLineSaver(line);
  const remove = useDeleteLine();
  const add = useAddLine();
  const [splitting, setSplitting] = useState(false);
  const [confirming, setConfirming] = useState(false);

  const undo = (deleted: CollectionLine) =>
    add
      .mutateAsync({
        set_id: group.card.set_id,
        card_id: group.card.card_id,
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

  const confirmDelete = () => {
    setConfirming(false);
    remove.mutate(line.id, {
      onSuccess: ({ deleted }) =>
        pushToast({
          kind: 'success',
          message: t('line.deleted'),
          duration: 8000,
          action: { label: t('line.undo'), onAction: () => void undo(deleted) },
        }),
      onError: (error) => pushToast({ kind: 'error', message: translateError(error, i18n) }),
    });
  };

  return (
    <fieldset className={styles.line}>
      <legend className={styles.legend}>{t('line.legend', { index: index + 1 })}</legend>
      <Stepper
        label={t('line.qty')}
        value={line.qty}
        min={1}
        max={9999}
        disabled={offline}
        onCommit={(qty) => void save({ qty })}
      />
      <OptionSelect
        kind="condition"
        label={t('line.condition')}
        value={line.condition}
        options={options.conditions}
        disabled={offline}
        onChange={(condition) => void save({ condition })}
      />
      <OptionSelect
        kind="language"
        label={t('line.language')}
        value={line.language}
        options={options.languages}
        disabled={offline}
        onChange={(language) => void save({ language })}
      />
      <MoneyField
        label={t('line.purchasePrice')}
        value={line.purchase_price}
        disabled={offline}
        onCommit={(purchase_price) => void save({ purchase_price })}
      />
      <Switch
        label={t('line.selling')}
        checked={line.selling}
        disabled={offline}
        onCheckedChange={(selling) => void save({ selling })}
      />
      <Stepper
        label={t('line.sellQty')}
        value={line.sell_qty}
        min={0}
        max={line.qty}
        disabled={offline}
        onCommit={(sell_qty) => void save({ sell_qty })}
      />
      <MoneyField
        label={t('line.sellPrice')}
        value={line.sell_price}
        disabled={offline}
        onCommit={(sell_price) => void save({ sell_price })}
      />
      <div className={styles.actions}>
        <Button
          variant="ghost"
          size="sm"
          disabled={offline || line.qty < 2}
          aria-expanded={splitting}
          onClick={() => setSplitting((open) => !open)}
        >
          {t('line.split')}
        </Button>
        <Button
          variant="danger"
          size="sm"
          disabled={offline}
          pending={remove.isPending}
          onClick={() => setConfirming(true)}
        >
          {t('line.delete')}
        </Button>
      </div>
      {splitting && (
        <SplitForm
          line={line}
          options={options}
          disabled={offline}
          onDone={() => setSplitting(false)}
        />
      )}
      <ConfirmDialog
        open={confirming}
        title={t('line.confirmDelete.title')}
        message={t('line.confirmDelete.body', { count: line.qty })}
        confirmLabel={t('line.delete')}
        cancelLabel={tCommon('actions.cancel')}
        danger
        onConfirm={confirmDelete}
        onCancel={() => setConfirming(false)}
      />
    </fieldset>
  );
}

/** The lines of one printing and foil, editable in place (F3-g S6). */
export function LineSheet({ group, open, onClose, meta, playsetSize, offline }: LineSheetProps) {
  const { t, i18n } = useTranslation('collection');
  const { t: tCommon } = useTranslation('common');
  const keep = useKeepPlayset();
  const options: Options = {
    conditions: meta?.conditions ?? [],
    languages: meta?.languages ?? [],
  };
  const name = group.foil ? `${group.card.name} (${t('foil')})` : group.card.name;

  return (
    <Sheet open={open} onClose={onClose} title={t('line.title', { name })}>
      <div className={styles.body}>
        {offline && <p className={styles.offline}>{tCommon('offline.editDisabled')}</p>}
        <Checkbox
          label={t('playset.keep')}
          checked={group.keep_playset}
          disabled={offline || keep.isPending}
          onChange={(event) =>
            keep.mutate(
              {
                set_id: group.card.set_id,
                card_id: group.card.card_id,
                keep: event.target.checked,
              },
              {
                onError: (error) =>
                  pushToast({ kind: 'error', message: translateError(error, i18n) }),
              },
            )
          }
        />
        {group.playset_short && (
          <p className={styles.warning}>
            {t('playset.warning', { kept: group.kept, size: playsetSize })}
          </p>
        )}
        {group.lines.map((line, index) => (
          <LineEditor
            key={line.id}
            group={group}
            line={line}
            index={index}
            options={options}
            offline={offline}
          />
        ))}
      </div>
    </Sheet>
  );
}
