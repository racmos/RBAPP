import { useId, useRef, useState, type KeyboardEvent } from 'react';
import { useTranslation } from 'react-i18next';
import type { CardSummary } from '@/api/types';
import { CardImage } from '@/components/card';
import { ErrorState } from '@/components/ui/ErrorState';
import { Pagination } from '@/components/ui/Pagination';
import { Skeleton } from '@/components/ui/Skeleton';
import { DebouncedInput, useCardList, useGameMeta } from '@/catalog';
import {
  NO_FILTERS,
  mergeFilters,
  pruneFilters,
  scopeOf,
  type BrowserFilters,
} from './browserFilters';
import { copiesInDeck, toDeckCard } from './editor';
import { pickFilters } from './DeckSections';
import { ActiveFilters, FilterPanel } from './FilterPanel';
import type { DeckEditor } from './useDeckEditor';
import styles from './CardBrowser.module.css';

/** The tabs of the browser in the owner's order; each one is the zone a tile fills. */
const TABS = ['legend', 'champion', 'main', 'battlefields', 'sideboard', 'runes'] as const;
type Tab = (typeof TABS)[number];
const PER_PAGE = 48;

const isSlot = (tab: Tab): tab is 'legend' | 'champion' => tab === 'legend' || tab === 'champion';
/** The zones of units, spells and gear: the cost and tag filters apply only there. */
const COSTED: readonly Tab[] = ['champion', 'main', 'sideboard'];

/** One card: a button that adds it to the tab's zone, or says why the rules refuse it. */
function Tile({ card, tab, editor }: { card: CardSummary; tab: Tab; editor: DeckEditor }) {
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
    <li>
      <button
        type="button"
        className={styles.tile}
        aria-label={label}
        aria-disabled={reason ? true : undefined}
        aria-describedby={reason ? id : undefined}
        title={reason ?? label}
        onClick={() => {
          if (!reason) editor.pick(card, tab);
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
      {reason && (
        <span id={id} className="sr-only">
          {reason}
        </span>
      )}
    </li>
  );
}

/**
 * The left pane of the desktop editor (F5-i step 2): tabs choose the zone being filled, and the
 * grid lists the cards that zone takes (the same `GET /cards` filters as the section searches).
 * The filter panel (step 3) narrows that list; the zone and legend filters always apply. A tab
 * change keeps the filters that apply to the new zone and drops the rest.
 */
export function CardBrowser({ editor }: { editor: DeckEditor }) {
  const { t } = useTranslation('decks');
  const id = useId();
  const [tab, setTab] = useState<Tab>('main');
  const [q, setQ] = useState('');
  const [page, setPage] = useState(1);
  const [chosen, setChosen] = useState<BrowserFilters>(NO_FILTERS);
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
            <FilterPanel
              filters={filters}
              scope={scope}
              base={base}
              facets={list?.facets}
              meta={meta}
              onChange={changeFilters}
            />
          </div>
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
              <Tile key={card.key} card={card} tab={tab} editor={editor} />
            ))}
          </ul>
        )}
        {list && list.pages > 1 && (
          <Pagination page={list.page} pages={list.pages} onChange={setPage} />
        )}
      </div>
    </section>
  );
}
