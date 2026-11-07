import { useMutation } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { unignoreCardmarketProduct, type CardmarketIgnored } from '@/api/endpoints';
import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { Skeleton } from '@/components/ui/Skeleton';
import { TableScroll } from '@/components/ui/TableScroll';
import { pushToast } from '@/components/ui/toastStore';
import { translateError } from '@/i18n';
import { formatMoney } from '@/lib/format';
import { formatStamp } from '@/admin/cardmarket/parts';
import type { PanelProps } from './MatchingPage';
import { useIgnored, useUndoToasts } from './queries';
import styles from './MatchingPage.module.css';

/** "Ignored": the products kept out of the list to link; Restore puts one back (CM-b). */
export function IgnoredPanel({ offline }: PanelProps) {
  const { t, i18n } = useTranslation('admin');
  const { t: common } = useTranslation('common');
  const query = useIgnored();
  const toasts = useUndoToasts();
  const restore = useMutation({
    mutationFn: (item: CardmarketIgnored) => unignoreCardmarketProduct(item.id_product, item.name),
    onSuccess: (_result, item) => toasts.restored(item.id_product, item.name),
    onError: (error: unknown) => pushToast({ kind: 'error', message: translateError(error, i18n) }),
  });

  if (query.isPending) return <Skeleton label={t('matching.ignoredTab.caption')} lines={4} />;
  if (query.isError) {
    return <ErrorState message={common('errorState.title')} onRetry={() => void query.refetch()} />;
  }
  if (query.data.items.length === 0) {
    return (
      <EmptyState
        title={t('matching.ignoredTab.emptyTitle')}
        body={t('matching.ignoredTab.emptyBody')}
      />
    );
  }
  return (
    <TableScroll>
      <table className={styles.table}>
        <caption className="sr-only">{t('matching.ignoredTab.caption')}</caption>
        <thead>
          <tr>
            <th scope="col">{t('matching.ignoredTab.columns.product')}</th>
            <th scope="col">{t('matching.ignoredTab.columns.id')}</th>
            <th scope="col">{t('matching.ignoredTab.columns.price')}</th>
            <th scope="col">{t('matching.ignoredTab.columns.since')}</th>
            <th scope="col">{t('matching.ignoredTab.columns.actions')}</th>
          </tr>
        </thead>
        <tbody>
          {query.data.items.map((item) => (
            <tr key={`${item.id_product}-${item.name}`}>
              <td>{item.name}</td>
              <td>{item.id_product}</td>
              <td className={styles.nowrap}>
                {item.low_price === null ? '—' : formatMoney(item.low_price)}
              </td>
              <td className={styles.nowrap}>{formatStamp(item.ignored_at)}</td>
              <td>
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={offline || restore.isPending}
                  aria-label={t('matching.ignoredTab.restoreFor', { name: item.name })}
                  onClick={() => restore.mutate(item)}
                >
                  {t('matching.ignoredTab.restore')}
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </TableScroll>
  );
}
