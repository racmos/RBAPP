import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { CollectionBulkSet, CollectionLineWithCard } from '@/api/types';
import { Button } from '@/components/ui/Button';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { Select } from '@/components/ui/Select';
import { pushToast } from '@/components/ui/toastStore';
import { translateError, useEnumLabel } from '@/i18n';
import { useAddLine, useBulkDelete, useBulkSet } from './queries';
import styles from './BulkBar.module.css';

type BulkBarProps = {
  ids: number[];
  conditions: string[];
  languages: string[];
  offline: boolean;
  onClear: () => void;
};

type Rule = '' | 'all' | 'none' | 'keep';

function numberOrNull(text: string): number | null | undefined {
  if (text.trim() === '') return undefined;
  const value = Number(text);
  return Number.isFinite(value) && value >= 0 ? value : undefined;
}

/** The bar that appears while lines are selected: one change for all of them, or delete (F3-h S5). */
export function BulkBar({ ids, conditions, languages, offline, onClear }: BulkBarProps) {
  const { t, i18n } = useTranslation('collection');
  const { label } = useEnumLabel();
  const bulkSet = useBulkSet();
  const bulkDelete = useBulkDelete();
  const add = useAddLine();
  const [condition, setCondition] = useState('');
  const [language, setLanguage] = useState('');
  const [selling, setSelling] = useState<'' | 'yes' | 'no'>('');
  const [rule, setRule] = useState<Rule>('');
  const [keep, setKeep] = useState('3');
  const [sellPrice, setSellPrice] = useState('');
  const [purchase, setPurchase] = useState('');
  const [confirm, setConfirm] = useState<'apply' | 'delete' | null>(null);
  const [empty, setEmpty] = useState(false);

  const change = (): CollectionBulkSet => {
    const set: CollectionBulkSet = {};
    if (condition) set.condition = condition;
    if (language) set.language = language;
    if (selling) set.selling = selling === 'yes';
    if (rule === 'all' || rule === 'none') set.sell_qty_rule = rule;
    if (rule === 'keep') {
      const count = Number(keep);
      if (Number.isInteger(count) && count >= 1 && count <= 9) {
        set.sell_qty_rule = 'keep_n';
        set.keep = count;
      }
    }
    const sale = numberOrNull(sellPrice);
    if (sale !== undefined) set.sell_price = sale;
    const bought = numberOrNull(purchase);
    if (bought !== undefined) set.purchase_price = bought;
    return set;
  };

  const askApply = () => {
    if (Object.keys(change()).length === 0) {
      setEmpty(true);
      return;
    }
    setEmpty(false);
    setConfirm('apply');
  };

  const apply = () => {
    setConfirm(null);
    bulkSet.mutate(
      { ids, set: change() },
      {
        onSuccess: () => pushToast({ kind: 'success', message: t('bulk.applied') }),
        onError: (error) => pushToast({ kind: 'error', message: translateError(error, i18n) }),
      },
    );
  };

  const undo = async (deleted: CollectionLineWithCard[]) => {
    try {
      for (const line of deleted) {
        await add.mutateAsync({
          set_id: line.set_id,
          card_id: line.card_id,
          foil: line.foil,
          qty: line.qty,
          condition: line.condition,
          language: line.language,
          purchase_price: line.purchase_price,
          selling: line.selling,
          sell_qty: line.sell_qty,
          sell_price: line.sell_price,
        });
      }
      pushToast({ kind: 'success', message: t('line.restored') });
    } catch (error) {
      pushToast({ kind: 'error', message: translateError(error, i18n) });
    }
  };

  const remove = () => {
    setConfirm(null);
    bulkDelete.mutate(ids, {
      onSuccess: ({ deleted }) => {
        onClear();
        pushToast({
          kind: 'success',
          message: t('bulk.deleted', { count: deleted.length }),
          duration: 8000,
          action: { label: t('line.undo'), onAction: () => void undo(deleted) },
        });
      },
      onError: (error) => pushToast({ kind: 'error', message: translateError(error, i18n) }),
    });
  };

  const options = (kind: 'condition' | 'language', values: string[]) =>
    values.map((value) => (
      <option key={value} value={value}>
        {label(kind, value)}
      </option>
    ));

  return (
    <section className={styles.bar} aria-label={t('bulk.selected', { count: ids.length })}>
      <p className={styles.count} role="status">
        {t('bulk.selected', { count: ids.length })}
      </p>
      <label>
        <span>{t('bulk.condition')}</span>
        <Select value={condition} disabled={offline} onChange={(e) => setCondition(e.target.value)}>
          <option value="">{t('bulk.keepUnchanged')}</option>
          {options('condition', conditions)}
        </Select>
      </label>
      <label>
        <span>{t('bulk.language')}</span>
        <Select value={language} disabled={offline} onChange={(e) => setLanguage(e.target.value)}>
          <option value="">{t('bulk.keepUnchanged')}</option>
          {options('language', languages)}
        </Select>
      </label>
      <label>
        <span>{t('bulk.selling')}</span>
        <Select
          value={selling}
          disabled={offline}
          onChange={(e) => setSelling(e.target.value as '' | 'yes' | 'no')}
        >
          <option value="">{t('bulk.keepUnchanged')}</option>
          <option value="yes">{t('filters.yes')}</option>
          <option value="no">{t('filters.no')}</option>
        </Select>
      </label>
      <label>
        <span>{t('bulk.sellRuleLabel')}</span>
        <Select value={rule} disabled={offline} onChange={(e) => setRule(e.target.value as Rule)}>
          <option value="">{t('bulk.keepUnchanged')}</option>
          <option value="all">{t('bulk.sellRule.all')}</option>
          <option value="none">{t('bulk.sellRule.none')}</option>
          <option value="keep">{t('bulk.sellRule.keep')}</option>
        </Select>
      </label>
      {rule === 'keep' && (
        <label>
          <span>{t('bulk.keep')}</span>
          <input
            type="number"
            min={1}
            max={9}
            value={keep}
            disabled={offline}
            className={styles.small}
            onChange={(e) => setKeep(e.target.value)}
          />
        </label>
      )}
      <label>
        <span>{t('bulk.sellPrice')}</span>
        <input
          type="number"
          min={0}
          step="0.01"
          value={sellPrice}
          disabled={offline}
          className={styles.small}
          onChange={(e) => setSellPrice(e.target.value)}
        />
      </label>
      <label>
        <span>{t('bulk.purchasePrice')}</span>
        <input
          type="number"
          min={0}
          step="0.01"
          value={purchase}
          disabled={offline}
          className={styles.small}
          onChange={(e) => setPurchase(e.target.value)}
        />
      </label>
      <div className={styles.actions}>
        {empty && <span className={styles.hint}>{t('bulk.nothingToApply')}</span>}
        <Button onClick={askApply} disabled={offline} pending={bulkSet.isPending}>
          {t('bulk.apply')}
        </Button>
        <Button
          variant="danger"
          onClick={() => setConfirm('delete')}
          disabled={offline}
          pending={bulkDelete.isPending}
        >
          {t('bulk.delete')}
        </Button>
        <Button variant="ghost" onClick={onClear}>
          {t('bulk.clear')}
        </Button>
      </div>
      <ConfirmDialog
        open={confirm === 'apply'}
        title={t('bulk.apply')}
        message={t('bulk.confirm.apply', { count: ids.length })}
        confirmLabel={t('bulk.apply')}
        cancelLabel={i18n.t('actions.cancel', { ns: 'common' })}
        onConfirm={apply}
        onCancel={() => setConfirm(null)}
      />
      <ConfirmDialog
        open={confirm === 'delete'}
        title={t('bulk.delete')}
        message={t('bulk.confirm.delete', { count: ids.length })}
        confirmLabel={t('bulk.delete')}
        cancelLabel={i18n.t('actions.cancel', { ns: 'common' })}
        danger
        onConfirm={remove}
        onCancel={() => setConfirm(null)}
      />
    </section>
  );
}
