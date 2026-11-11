import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { WishlistLine } from '@/api/types';
import { DebouncedInput } from '@/catalog';
import { CollectionTabs, TabLinks } from '@/collection/CollectionTabs';
import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { Icon } from '@/components/ui/Icon';
import { PageHeader } from '@/components/ui/PageHeader';
import { Sheet } from '@/components/ui/Sheet';
import { Skeleton } from '@/components/ui/Skeleton';
import { up } from '@/lib/breakpoints';
import { formatMoney } from '@/lib/format';
import { useMediaQuery } from '@/lib/useMediaQuery';
import { AddLineSheet } from './AddLineSheet';
import { LineCards, LinesTable } from './Lines';
import { useListActions } from './ListSheets';
import { ListsMenu, type ListActions } from './ListsMenu';
import { MoveSheet } from './MoveSheet';
import { useWishlistsScreen, type WishlistsScreen } from './useWishlistsScreen';
import styles from './Wishlists.module.css';

const SEARCH_DELAY_MS = 300;

/** "Lists | Price alerts": the two screens of the wishlist area (F3-j). */
export function WishlistTabs() {
  const { t } = useTranslation('wishlists');
  return (
    <TabLinks
      label={t('tabs.sections')}
      size="sm"
      links={[
        { to: '/collection/wishlists', label: t('tabs.lists') },
        { to: '/collection/wishlists/alerts', label: t('tabs.alerts') },
      ]}
    />
  );
}

/** Cards "3 of 100", the market value and the unpriced lines of what the search shows. */
function Summary({ s }: { s: WishlistsScreen }) {
  const { t } = s;
  const meta = s.lines.data?.meta;
  if (!meta) return null;
  return (
    <dl className={styles.summary}>
      <div>
        <dt>{t('summary.lines')}</dt>
        <dd>{t('summary.linesValue', { count: meta.line_count, max: meta.max_lines })}</dd>
      </div>
      <div>
        <dt>{t('summary.value')}</dt>
        <dd>{formatMoney(meta.market_total)}</dd>
      </div>
      <div>
        <dt>{t('summary.unpriced')}</dt>
        <dd>{meta.unpriced}</dd>
      </div>
    </dl>
  );
}

function Search({ s }: { s: WishlistsScreen }) {
  const { t } = s;
  return (
    <form role="search" className={styles.search} onSubmit={(event) => event.preventDefault()}>
      <label htmlFor="wishlist-search" className="sr-only">
        {t('search.label')}
      </label>
      <DebouncedInput
        id="wishlist-search"
        type="search"
        enterKeyHint="search"
        placeholder={t('search.placeholder')}
        value={s.q}
        delay={SEARCH_DELAY_MS}
        onCommit={(q) => s.setQuery(q)}
      />
    </form>
  );
}

/** Loading, failure, empty or the lines (cards on a phone, a table on a desktop). */
function Results({
  s,
  desktop,
  onMove,
}: {
  s: WishlistsScreen;
  desktop: boolean;
  onMove: (line: WishlistLine) => void;
}) {
  const { t, lines, selected, offline, q } = s;
  if (!selected) return null;
  if (lines.isPending) return <Skeleton label={t('linesLoading')} lines={6} />;
  if (lines.isError && !lines.data) {
    return <ErrorState message={t('linesError')} onRetry={() => void lines.refetch()} />;
  }
  const items = lines.data?.items ?? [];
  if (items.length === 0 && !q) {
    return (
      <EmptyState
        icon="bookmark"
        title={t('empty.title')}
        body={t('empty.body')}
        action={offline ? undefined : { label: t('add.open'), onAction: () => s.setAddOpen(true) }}
      />
    );
  }
  if (items.length === 0) {
    return (
      <EmptyState
        icon="search"
        title={t('emptySearch')}
        action={{ label: t('clearSearch'), onAction: () => s.setQuery('') }}
      />
    );
  }
  const Layout = desktop ? LinesTable : LineCards;
  return (
    <Layout
      lines={items}
      listName={selected.name}
      busy={lines.isFetching}
      offline={offline}
      onMove={onMove}
    />
  );
}

/** The add button, left out while the list is empty: the empty state offers it then. */
function AddButton({ s }: { s: WishlistsScreen }) {
  const { t, lines, q, offline } = s;
  const empty = (lines.data?.items.length ?? 0) === 0 && !q;
  if (!lines.data || empty) return null;
  return (
    <Button onClick={() => s.setAddOpen(true)} disabled={offline}>
      <Icon name="plus" size={16} />
      {t('add.open')}
    </Button>
  );
}

/** Below 1240 px: a list switcher that opens the lists in a sheet, then the lines as cards. */
function WishlistsMobile({
  s,
  actions,
  onMove,
}: {
  s: WishlistsScreen;
  actions: ListActions;
  onMove: (line: WishlistLine) => void;
}) {
  const { t, selected, menuOpen, setMenuOpen } = s;
  if (!selected) return null;
  return (
    <>
      <div className={styles.bar}>
        <button
          type="button"
          className={styles.switcher}
          aria-haspopup="dialog"
          onClick={() => setMenuOpen(true)}
        >
          <span className={styles.switcherName}>{selected.name}</span>
          {selected.is_default && (
            <>
              <Icon name="star" size={16} className={styles.starIcon} />
              <span className="sr-only">{`(${t('menu.default')})`}</span>
            </>
          )}
          <span className={styles.listCount}>{t('count', { count: selected.line_count })}</span>
          <span className="sr-only">{t('menu.change')}</span>
          <Icon name="arrow-down" size={16} />
        </button>
        <AddButton s={s} />
      </div>
      <section aria-labelledby="wishlist-name">
        <h2 id="wishlist-name" className="sr-only">
          {selected.name}
        </h2>
        <Summary s={s} />
        <Search s={s} />
        <Results s={s} desktop={false} onMove={onMove} />
      </section>
      <Sheet open={menuOpen} onClose={() => setMenuOpen(false)} title={t('menu.title')}>
        <ListsMenu s={s} actions={actions} onOpened={() => setMenuOpen(false)} />
      </Sheet>
    </>
  );
}

/** From 1240 px: the lists in a rail (drag to reorder), the lines as a table. */
function WishlistsDesktop({
  s,
  actions,
  onMove,
}: {
  s: WishlistsScreen;
  actions: ListActions;
  onMove: (line: WishlistLine) => void;
}) {
  const { t, selected } = s;
  const pointer = useMediaQuery('(pointer: fine)');
  if (!selected) return null;
  return (
    <div className={styles.layout}>
      <section className={styles.rail} aria-labelledby="wishlists-rail">
        <h2 id="wishlists-rail" className={styles.railTitle}>
          {t('menu.title')}
        </h2>
        <ListsMenu s={s} actions={actions} draggable={pointer} />
      </section>
      <section className={styles.main} aria-labelledby="wishlist-name">
        <div className={styles.bar}>
          <h2 id="wishlist-name" className={styles.listTitle}>
            {selected.name}
            {selected.is_default && (
              <Icon name="star" size={18} className={styles.starIcon} title={t('menu.default')} />
            )}
          </h2>
          <AddButton s={s} />
        </div>
        <Summary s={s} />
        <Search s={s} />
        <Results s={s} desktop onMove={onMove} />
      </section>
    </div>
  );
}

/** `/collection/wishlists` (F3-j): the user's wishlists and the cards of the open one. */
export function WishlistsPage() {
  const desktop = useMediaQuery(up('xl'));
  const s = useWishlistsScreen();
  const { t, lists, offline, selected } = s;
  const { t: tCommon } = useTranslation('common');
  const [moving, setMoving] = useState<WishlistLine | null>(null);
  const { actions, sheets } = useListActions({
    offline,
    onCreated: (list) => {
      s.setMenuOpen(false);
      s.openList(list.id);
    },
  });

  let body;
  if (lists.isPending) body = <Skeleton label={t('loading')} lines={6} />;
  else if (lists.isError && !lists.data) {
    body = <ErrorState message={t('error')} onRetry={() => void lists.refetch()} />;
  } else if (desktop) {
    body = <WishlistsDesktop s={s} actions={actions} onMove={setMoving} />;
  } else {
    body = <WishlistsMobile s={s} actions={actions} onMove={setMoving} />;
  }

  return (
    <div className={styles.page} data-wide={desktop || undefined}>
      <CollectionTabs />
      <PageHeader title={t('title')} />
      <WishlistTabs />
      {offline && <p className={styles.note}>{tCommon('offline.editDisabled')}</p>}
      {body}
      {sheets}
      {moving && (
        <MoveSheet
          line={moving}
          lists={s.items}
          offline={offline}
          onClose={() => setMoving(null)}
        />
      )}
      {s.addOpen && selected && (
        <AddLineSheet list={selected} offline={offline} onClose={() => s.setAddOpen(false)} />
      )}
    </div>
  );
}
