import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { OwnedProductLine } from '@/api/types';
import { DebouncedInput } from '@/catalog';
import { MoneyField } from '@/collection/MoneyField';
import { Stepper } from '@/collection/Stepper';
import { Button } from '@/components/ui/Button';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { Field } from '@/components/ui/Field';
import { Sheet } from '@/components/ui/Sheet';
import { pushToast } from '@/components/ui/toastStore';
import { translateError } from '@/i18n';
import { formatMoney } from '@/lib/format';
import { langOf } from './format';
import { ProductThumb } from './ProductThumb';
import { useAddProduct, useDeleteProduct } from './queries';
import { useProductLineSaver } from './useProductLineSaver';
import styles from './ProductLineSheet.module.css';

const UNDO_MS = 8000;
const NOTE_MAX = 200;

type ProductLineSheetProps = {
  line: OwnedProductLine;
  onClose: () => void;
  offline: boolean;
};

/** One owned line: quantity, purchase price, note and delete with undo (F14-e S2). */
export function ProductLineSheet({ line, onClose, offline }: ProductLineSheetProps) {
  const { t, i18n } = useTranslation('products');
  const { t: tCommon } = useTranslation('common');
  const lang = langOf(i18n.language);
  const save = useProductLineSaver(line.id);
  const remove = useDeleteProduct();
  const add = useAddProduct();
  const [confirming, setConfirming] = useState(false);
  const { product } = line;

  const undo = (deleted: OwnedProductLine) =>
    add
      .mutateAsync({
        product_id: deleted.product.id,
        quantity: deleted.quantity,
        purchase_price: deleted.purchase_price,
        note: deleted.note,
      })
      .catch((error) => pushToast({ kind: 'error', message: translateError(error, i18n) }));

  // A promise, not `mutate` callbacks: they would be lost if the sheet closes meanwhile.
  const confirmDelete = () => {
    setConfirming(false);
    remove
      .mutateAsync(line.id)
      .then(({ deleted }) => {
        pushToast({
          kind: 'success',
          message: t('line.deleted'),
          duration: UNDO_MS,
          action: { label: t('line.undo'), onAction: () => void undo(deleted) },
        });
        onClose();
      })
      .catch((error) => pushToast({ kind: 'error', message: translateError(error, i18n) }));
  };

  return (
    <>
      <Sheet open onClose={onClose} title={product.name}>
        <div className={styles.body}>
          {offline && <p className={styles.offline}>{tCommon('offline.editDisabled')}</p>}
          <div className={styles.head}>
            <ProductThumb product={product} size="thumb" decorative />
            <span className={styles.kind}>{product.kind ? t(`kind.${product.kind}`) : ''}</span>
          </div>
          <Stepper
            label={t('line.quantity')}
            value={line.quantity}
            min={1}
            max={9999}
            disabled={offline}
            onCommit={(quantity) => void save({ quantity })}
          />
          <MoneyField
            label={t('line.purchasePrice')}
            value={line.purchase_price}
            disabled={offline}
            onCommit={(purchase_price) => void save({ purchase_price })}
          />
          <Field label={t('line.note')}>
            {(control) => (
              <DebouncedInput
                {...control}
                maxLength={NOTE_MAX}
                disabled={offline}
                value={line.note ?? ''}
                delay={500}
                onCommit={(next) => void save({ note: next.trim() || null })}
              />
            )}
          </Field>
          <dl className={styles.value}>
            <dt>{t('line.value')}</dt>
            <dd>{line.value === null ? t('unpriced') : formatMoney(line.value, lang)}</dd>
          </dl>
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
      </Sheet>
      {/* Outside the sheet: a nested dialog's close event would close the sheet too. */}
      <ConfirmDialog
        open={confirming}
        title={t('line.confirmDelete')}
        message={product.name}
        confirmLabel={t('line.delete')}
        cancelLabel={tCommon('actions.cancel')}
        danger
        onConfirm={confirmDelete}
        onCancel={() => setConfirming(false)}
      />
    </>
  );
}
