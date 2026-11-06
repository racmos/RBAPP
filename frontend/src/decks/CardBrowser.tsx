import { useId, useRef, useState, type KeyboardEvent } from 'react';
import { useTranslation } from 'react-i18next';
import type { CardSummary } from '@/api/types';
import { CardImage } from '@/components/card';
import { ErrorState } from '@/components/ui/ErrorState';
import { Icon } from '@/components/ui/Icon';
import { Pagination } from '@/components/ui/Pagination';
import { Skeleton } from '@/components/ui/Skeleton';
import { DebouncedInput, useCardList, useGameMeta } from '@/catalog';
import {
  NO_FILTERS,
  mergeFilters,
  pickFilters,
  pruneFilters,
  scopeOf,
  type BrowserFilters,
} from './browserFilters';
import { CardZoom } from './CardZoom';
import { copiesInDeck, toDeckCard } from './editor';
import { ActiveFilters, FilterPanel, FilterToggle, InlineFilters } from './FilterPanel';
import type { DeckEditor } from './useDeckEditor';
import styles from './CardBrowser.module.css';

/** The tabs of the browser in the owner's order; each one is the zone a tile fills. */
const TABS = ['legend', 'champion', 'main', 'battlefields', 'sideboard', 'runes'] as const;
type Tab = (typeof TABS)[number];
/** A zone the browser fills: each tab of the desktop pane, or the zone of a mobile sheet. */
export type BrowserZone = Tab;
const PER_PAGE = 48;

const isSlot = (tab: Tab): tab is 'legend' | 'champion' => tab === 'legend' || tab === 'champion';
/** The zones of units, spells and gear: the cost and tag filters apply only there. */
const COSTED: readonly Tab[] = ['champion', 'main', 'sideboard'];

type TileProps = { card: CardSummary; tab: Tab; editor: DeckEditor; onChosen?: () => void };

/** One card: a button that adds it to the tab's zone, or says why the rules refuse it; the
 *  magnifier over its corner, a sibling of that button, zooms the card without adding it. */
function Tile({ card, tab, editor, onChosen }: TileProps) {
  const { t } = useTranslation('decks');
  const id = useId();
  const ref = { set: card.set_id, id: card.card_id };
  const book = editor.book[card.key]
    ? editor.book
    : { ...editor.book, [card.key]: toDeckCard(card) };
  const reason = isSlot(tab) ? null : editor.addReason(ref, tab, book);
  const copies = copiesInDeck(editor.content, ref);
  const label = t(isSlot(tab) ? 'browser.choose' : 'browser.add', { name: card.name });
  return (
    <li className={styles.tileItem}>
      <button
        type="button"
        className={styles.tile}
        aria-label={label}
        aria-disabled={reason ? true : undefined}
        aria-describedby={reason ? id : undefined}
        title={reason ?? label}
        onClick={() => {
          if (reason) return;
          // a slot holds one card: choosing it is the end of the task
          if (editor.pick(card, tab) && isSlot(tab)) onChosen?.();
        }}
      >
        <CardImage card={card} size="tile" decorative />
        {card.energy !== null && (
          <span className={styles.energy} data-slot="energy">
            {card.energy}
          </span>
        )}
        {card.might !== null && (
          <span className={styles.might} data-slot="might">
            {card.might}
          </span>
        )}
        {copies > 0 && (
          <span className={styles.copies} data-slot="copies">
            {t('row.qty', { qty: copies })}
          </span>
        )}
      </button>
      <CardZoom card={card} name={card.name} className={styles.zoom}>
        <Icon name="search" size={16} />
      </CardZoom>
      {reason && (
        <span id={id} className="sr-only">
          {reason}
        </span>
      )}
    </li>
  );
}

type BrowserProps = {
  editor: DeckEditor;
  /** A fixed zone without tabs, and the filters inline (the mobile sheet, F5-i decision 4). */
  zone?: BrowserZone;
  /** A legend or champion was chosen (the mobile sheet closes). */
  onChosen?: () => void;
};

/**
 * The card browser (F5-i step 2). On the desktop it is the left pane of the editor and its tabs
 * choose the zone being filled; in the mobile sheet it fills one fixed `zone`. The grid lists
 * the cards that zone takes (`pickFilters`). The filter panel (step 3) narrows that list; the
 * zone and legend filters always apply. A tab change keeps the filters that apply to the new
 * zone and drops the rest.
 */
export function CardBrowser({ editor, zone: fixed, onChosen }: BrowserProps) {
  const { t } = useTranslation('decks');
  const id = useId();
  const [picked, setTab] = useState<Tab>('main');
  const tab = fixed ?? picked;
  const [q, setQ] = useState('');
  const [page, setPage] = useState(1);
  const [chosen, setChosen] = useState<BrowserFilters>(NO_FILTERS);
  const [showFilters, setShowFilters] = useState(false);
  const tabRefs = useRef<Partial<Record<Tab, HTMLButtonElement | null>>>({});
  const meta = useGameMeta().data;
  const scopeFor = (name: Tab) => scopeOf(pickFilters(name, editor), COSTED.includes(name));
  const base = pickFilters(tab, editor);
  // pruned on every render too: a new legend may take values away
  const scope = scopeFor(tab);
  const filters = pruneFilters(chosen, scope);
  const query = useCardList({
    ...mergeFilters(base, filters),
    ...(q ? { q } : {}),
    sort: 'name',
    per_page: PER_PAGE,
    page,
  });
  const items = query.data?.data.items ?? [];
  const list = query.data?.meta;
  const zone = t(`section.${tab}`);

  const choose = (next: Tab) => {
    setTab(next);
    setChosen((current) => pruneFilters(current, scopeFor(next)));
    setPage(1);
  };
  const changeFilters = (next: BrowserFilters) => {
    setChosen(next);
    setPage(1);
  };
  const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    const index = TABS.indexOf(tab);
    let next: Tab | undefined;
    if (event.key === 'ArrowRight') next = TABS[(index + 1) % TABS.length];
    else if (event.key === 'ArrowLeft') next = TABS[(index - 1 + TABS.length) % TABS.length];
    else if (event.key === 'Home') next = TABS[0];
    else if (event.key === 'End') next = TABS[TABS.length - 1];
    if (!next) return;
    event.preventDefault();
    choose(next);
    tabRefs.current[next]?.focus();
  };

  const filterProps = {
    filters,
    scope,
    base,
    facets: list?.facets,
    meta,
    onChange: changeFilters,
  };
  const content = (
    <>
      <div className={styles.toolbar}>
        <label className="sr-only" htmlFor={`${id}-search`}>
          {t('browser.search', { section: zone })}
        </label>
        <div className={styles.searchRow}>
          <DebouncedInput
            id={`${id}-search`}
            type="search"
            className={styles.search}
            placeholder={t('browser.searchPlaceholder', { section: zone })}
            value={q}
            onCommit={(next) => {
              setQ(next.trim());
              setPage(1);
            }}
          />
          {fixed ? (
            <FilterToggle
              filters={filters}
              expanded={showFilters}
              controls={`${id}-filters`}
              onToggle={() => setShowFilters((shown) => !shown)}
            />
          ) : (
            <FilterPanel {...filterProps} />
          )}
        </div>
        {fixed && showFilters && <InlineFilters id={`${id}-filters`} {...filterProps} />}
        <ActiveFilters filters={filters} meta={meta} onChange={changeFilters} />
        {list && !query.isPlaceholderData && (
          <p className={styles.count} aria-live="polite">
            {t('browser.count', { count: list.total, section: zone })}
          </p>
        )}
      </div>
      {query.isPending ? (
        <Skeleton label={t('browser.loading')} lines={6} />
      ) : query.isError && !query.data ? (
        <ErrorState message={t('browser.error')} onRetry={() => void query.refetch()} />
      ) : items.length === 0 ? (
        <p className={styles.empty}>{t('browser.empty')}</p>
      ) : (
        <ul className={styles.grid} aria-label={t('browser.results', { section: zone })}>
          {items.map((card) => (
            <Tile key={card.key} card={card} tab={tab} editor={editor} onChosen={onChosen} />
          ))}
        </ul>
      )}
      {list && list.pages > 1 && (
        <Pagination page={list.page} pages={list.pages} onChange={setPage} />
      )}
    </>
  );

  // the sheet's title names the zone: no tabs, no second heading
  if (fixed) return <div className={styles.panel}>{content}</div>;

  return (
    <section className={styles.browser} aria-labelledby={`${id}-title`}>
      <h2 id={`${id}-title`} className="sr-only">
        {t('browser.title')}
      </h2>
      <div role="tablist" aria-label={t('browser.zones')} className={styles.tabs}>
        {TABS.map((name) => (
          <button
            key={name}
            ref={(node) => {
              tabRefs.current[name] = node;
            }}
            type="button"
            role="tab"
            id={`${id}-tab-${name}`}
            aria-controls={`${id}-panel`}
            aria-selected={tab === name}
            tabIndex={tab === name ? 0 : -1}
            className={styles.tab}
            onClick={() => choose(name)}
            onKeyDown={onKeyDown}
          >
            {t(`section.${name}`)}
          </button>
        ))}
      </div>
      <div
        role="tabpanel"
        id={`${id}-panel`}
        aria-labelledby={`${id}-tab-${tab}`}
        className={styles.panel}
      >
        {content}
      </div>
    </section>
  );
}
