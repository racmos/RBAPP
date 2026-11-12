import { useId, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useSearchParams } from 'react-router';
import type { CardMini, WishlistAlert } from '@/api/types';
import { useOffline } from '@/auth';
import { useSearchNavigation } from '@/catalog';
import { CollectionTabs } from '@/collection/CollectionTabs';
import { CardImage } from '@/components/card';
import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { Icon } from '@/components/ui/Icon';
import { PageHeader } from '@/components/ui/PageHeader';
import { Skeleton } from '@/components/ui/Skeleton';
import { Switch } from '@/components/ui/Switch';
import { pushToast } from '@/components/ui/toastStore';
import { useDocumentTitle } from '@/i18n';
import { formatDate, formatMoney } from '@/lib/format';
import { useAlertLists, useMarkAlertsRead, useWishlistAlerts } from './alertQueries';
import { WishlistTabs } from './WishlistsPage';
import styles from './Alerts.module.css';
import pageStyles from './Wishlists.module.css';

const imageCard = (card: CardMini) => ({ ...card, energy: null, might: null });

/** `?unread=true` of the alerts screen. */
function useUnreadParam() {
  const [searchParams] = useSearchParams();
  const { current, go } = useSearchNavigation();
  const unread = searchParams.get('unread') === 'true';
  const setUnread = (next: boolean) => {
    const params = current();
    if (next) params.set('unread', 'true');
    else params.delete('unread');
    go(params.toString(), { replace: true });
  };
  return { unread, setUnread };
}

/** The lists that hold the alert's card now, each a link to that wishlist. */
function AlertLists({ alert, id }: { alert: WishlistAlert; id: string }) {
  const { t } = useTranslation('wishlists');
  const lists = useAlertLists(alert.id, true);
  let body;
  if (lists.isPending) body = <Skeleton label={t('alerts.listsLoading')} lines={2} />;
  else if (lists.isError) {
    body = <ErrorState message={t('alerts.listsError')} onRetry={() => void lists.refetch()} />;
  } else if (lists.data.items.length === 0) {
    body = <p className={styles.muted}>{t('alerts.noLists')}</p>;
  } else {
    body = (
      <ul className={styles.lists} aria-label={t('alerts.lists')}>
        {lists.data.items.map((list) => (
          <li key={list.id} className={styles.listRow}>
            <Link to={`/collection/wishlists?list=${list.id}`} className={styles.listLink}>
              {list.name}
            </Link>
            {list.is_default && (
              <Icon
                name="star"
                size={14}
                className={pageStyles.starIcon}
                title={t('menu.default')}
              />
            )}
            <span className={styles.muted}>
              {list.max_price === null
                ? t('alerts.wanted', { qty: list.qty })
                : t('alerts.wantedMax', { qty: list.qty, price: formatMoney(list.max_price) })}
            </span>
          </li>
        ))}
      </ul>
    );
  }
  return (
    <div id={id} className={styles.panel}>
      {body}
    </div>
  );
}

/** One alert: the card, the price it reached and the day; expanding it shows its lists. */
function AlertItem({
  alert,
  offline,
  onOpen,
}: {
  alert: WishlistAlert;
  offline: boolean;
  onOpen: (alert: WishlistAlert) => void;
}) {
  const { t } = useTranslation('wishlists');
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const unread = alert.read_at === null;
  const toggle = () => {
    if (!open && unread && !offline) onOpen(alert);
    setOpen(!open);
  };
  return (
    <li className={styles.item} data-unread={unread || undefined}>
      <div className={styles.row}>
        <div className={styles.art}>
          {alert.card && <CardImage card={imageCard(alert.card)} size="thumb" decorative />}
        </div>
        <div className={styles.body}>
          <div className={styles.title}>
            {unread && (
              <span className={styles.dot}>
                <span className="sr-only">{t('alerts.unread')}</span>
              </span>
            )}
            <h2 className={styles.name}>{alert.name}</h2>
          </div>
          <p className={styles.meta}>
            {alert.set_id !== null && alert.card_id !== null
              ? t('line.printing', { set: alert.set_id, card: alert.card_id })
              : t('line.anyPrinting')}
          </p>
          <p className={styles.reached}>
            {t('alerts.reached', {
              price: formatMoney(alert.price),
              max: formatMoney(alert.max_price),
            })}
          </p>
          <p className={styles.muted}>{t('alerts.date', { date: formatDate(alert.price_date) })}</p>
        </div>
      </div>
      <button
        type="button"
        className={styles.toggle}
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
        onClick={toggle}
      >
        {t('alerts.lists')}
        <Icon name={open ? 'arrow-up' : 'arrow-down'} size={16} />
      </button>
      {open && <AlertLists alert={alert} id={panelId} />}
    </li>
  );
}

/**
 * `/collection/wishlists/alerts` (F4-g-2): the price alerts newest first, 25 a page. Opening the
 * screen marks nothing; an alert is marked read when it is expanded, and "Mark all as read" marks
 * every one. "Unread only" lives in the URL (`?unread=true`). Offline it is read-only.
 */
export function AlertsPage() {
  const { t } = useTranslation('wishlists');
  const { t: tCommon } = useTranslation('common');
  useDocumentTitle(t('alerts.title'));
  const offline = useOffline();
  const { unread, setUnread } = useUnreadParam();
  const alerts = useWishlistAlerts(unread);
  const mark = useMarkAlertsRead();
  const pages = alerts.data?.pages ?? [];
  const items = pages.flatMap((page) => page.items);
  const unreadCount = pages[0]?.meta.unread_count ?? 0;

  const markRead = (ids?: number[]) =>
    mark.mutate(ids, {
      onSuccess: () => {
        if (!ids) pushToast({ kind: 'success', message: t('alerts.markedAll') });
      },
      onError: () => pushToast({ kind: 'error', message: t('alerts.markError') }),
    });

  let body;
  if (alerts.isPending) body = <Skeleton label={t('alerts.loading')} lines={6} />;
  else if (alerts.isError && !alerts.data) {
    body = <ErrorState message={t('alerts.error')} onRetry={() => void alerts.refetch()} />;
  } else if (items.length === 0 && unread) {
    body = (
      <EmptyState
        icon="clock"
        title={t('alerts.emptyUnread.title')}
        action={{ label: t('alerts.emptyUnread.action'), onAction: () => setUnread(false) }}
      />
    );
  } else if (items.length === 0) {
    body = (
      <EmptyState icon="clock" title={t('alerts.empty.title')} body={t('alerts.empty.body')} />
    );
  } else {
    body = (
      <>
        <ul className={styles.items} aria-label={t('alerts.list')} aria-busy={alerts.isFetching}>
          {items.map((alert) => (
            <AlertItem
              key={alert.id}
              alert={alert}
              offline={offline}
              onOpen={(opened) => markRead([opened.id])}
            />
          ))}
        </ul>
        {alerts.hasNextPage && (
          <div className={styles.more}>
            <Button
              variant="ghost"
              disabled={alerts.isFetchingNextPage}
              onClick={() => void alerts.fetchNextPage()}
            >
              {t('alerts.showMore')}
            </Button>
          </div>
        )}
      </>
    );
  }

  return (
    <div className={pageStyles.page}>
      <CollectionTabs />
      <PageHeader title={t('alerts.title')} subtitle={t('alerts.intro')} />
      <WishlistTabs />
      {offline && <p className={pageStyles.note}>{tCommon('offline.editDisabled')}</p>}
      <div className={pageStyles.bar}>
        <Switch label={t('alerts.unreadOnly')} checked={unread} onCheckedChange={setUnread} />
        <Button
          variant="ghost"
          disabled={offline || unreadCount === 0 || mark.isPending}
          onClick={() => markRead()}
        >
          <Icon name="check" size={16} />
          {t('alerts.markAll')}
        </Button>
      </div>
      {body}
    </div>
  );
}
