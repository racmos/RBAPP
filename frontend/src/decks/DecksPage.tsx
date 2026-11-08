import { useId, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useSearchParams } from 'react-router';
import type { DeckListItem, GameMode } from '@/api/types';
import { useOffline } from '@/auth';
import { useSearchNavigation } from '@/catalog';
import { CardImage, DomainPips } from '@/components/card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { Icon } from '@/components/ui/Icon';
import { PageHeader } from '@/components/ui/PageHeader';
import { Skeleton } from '@/components/ui/Skeleton';
import { useDocumentTitle } from '@/i18n';
import { up } from '@/lib/breakpoints';
import { formatDate, formatMoney } from '@/lib/format';
import { useMediaQuery } from '@/lib/useMediaQuery';
import { DeckCardActions } from './DeckCardActions';
import { ImportDeckModal, NewDeckModal } from './DeckCreate';
import { DeckListToolbar } from './DeckListToolbar';
import {
  DEFAULT_DECK_LIST_PARAMS,
  parseDeckListParams,
  selectDecks,
  serializeDeckListParams,
  type DeckListParams,
} from './deckListParams';
import { issueShort } from './issues';
import { cardLabel } from './labels';
import { useDeckRules, useDecks } from './queries';
import type { RulesContext } from './rules';
import styles from './DecksPage.module.css';

const REASONS_SHOWN = 3;
/** From 860 px the decks are a grid of cards; below it, one column of the same cards. */
const GRID = up('md');

/** One legality badge: legal is a plain badge; not legal opens its first reasons on a tap. */
function LegalityBadge({ deck, mode }: { deck: DeckListItem; mode: GameMode }) {
  const { t } = useTranslation('decks');
  const [open, setOpen] = useState(false);
  const id = useId();
  if (deck.legal[mode]) return <Badge tone="success">{t('legal.yes', { mode })}</Badge>;
  const codes = deck.issues[mode] ?? [];
  const more = codes.length - REASONS_SHOWN;
  return (
    <span className={styles.legality}>
      <button
        type="button"
        className={styles.notLegal}
        aria-expanded={open}
        aria-controls={open ? id : undefined}
        onClick={() => setOpen((value) => !value)}
      >
        {t('legal.no', { mode })}
      </button>
      {open && (
        <ul id={id} className={styles.reasons} aria-label={t('legal.reasons', { mode })}>
          {codes.slice(0, REASONS_SHOWN).map((code) => (
            <li key={code}>{issueShort(t, code)}</li>
          ))}
          {more > 0 && <li>{t('legal.more', { count: more })}</li>}
        </ul>
      )}
    </span>
  );
}

function DeckItem({
  deck,
  rules,
  offline,
}: {
  deck: DeckListItem;
  rules: RulesContext | null;
  offline: boolean;
}) {
  const { t } = useTranslation('decks');
  const need = rules?.deck;
  const count = (key: 'main' | 'runes' | 'battlefields' | 'sideboard', max?: number) =>
    t(`counts.${key}`, { have: deck.counts[key], need: max ?? '—' });
  const modes = Object.keys(deck.legal) as GameMode[];
  const sharing = deck.share ? 'shared' : deck.visibility === 'public' ? 'public' : 'private';
  return (
    <li className={styles.item}>
      <div className={styles.head}>
        <div className={styles.art} data-slot="art">
          {deck.legend ? (
            <CardImage card={deck.legend} size="tile" decorative />
          ) : (
            <span className={styles.noArt}>
              <Icon name="decks" size={26} />
            </span>
          )}
        </div>
        <div className={styles.headText}>
          <h2 className={styles.name}>
            <Link to={`/decks/${deck.id}`}>{deck.name}</Link>
          </h2>
          <p className={styles.tags}>
            <Badge tone="accent">{deck.mode}</Badge>
            <span className={styles.sharing}>
              <Icon name={sharing === 'private' ? 'lock' : 'link'} size={14} />
              {t(`sharing.${sharing}`)}
            </span>
          </p>
          <p className={styles.identity}>
            <DomainPips domains={deck.domains} size={18} />
            <span className={deck.legend ? undefined : styles.muted}>
              {deck.legend ? cardLabel(deck.legend) : t('noLegend')}
            </span>
            <span aria-hidden="true">·</span>
            <span className={deck.champion ? undefined : styles.muted}>
              {deck.champion ? deck.champion.name : t('noChampion')}
            </span>
          </p>
        </div>
      </div>
      <p className={styles.counts}>
        <span>{count('main', need?.main_size)}</span>
        <span>{count('runes', need?.runes)}</span>
        <span>{count('battlefields', need?.battlefields)}</span>
        <span>{count('sideboard', need?.sideboard)}</span>
      </p>
      <div className={styles.badges}>
        {modes.map((mode) => (
          <LegalityBadge key={mode} deck={deck} mode={mode} />
        ))}
      </div>
      <p className={styles.meta}>
        <span className={styles.value}>
          <span className="sr-only">{t('value')} </span>
          <span>{formatMoney(deck.value)}</span>
        </span>
        {deck.value_unpriced > 0 && (
          <span className={styles.muted}>{t('unpriced', { count: deck.value_unpriced })}</span>
        )}
        <span className={styles.muted}>{t('updated', { date: formatDate(deck.updated_at) })}</span>
      </p>
      <div className={styles.footer}>
        <Link
          className={styles.open}
          to={`/decks/${deck.id}`}
          aria-label={t('card.openLabel', { name: deck.name })}
        >
          {t('card.open')}
        </Link>
        <DeckCardActions deck={deck} offline={offline} />
      </div>
    </li>
  );
}

/** The toolbar state of the URL; changes are built on the latest search asked for (L6). */
function useDeckListParams() {
  const [searchParams] = useSearchParams();
  const { current, go } = useSearchNavigation();
  const params = useMemo(() => parseDeckListParams(searchParams), [searchParams]);
  const change = (patch: Partial<DeckListParams>, options: { replace?: boolean } = {}) => {
    const base = current();
    go(serializeDeckListParams({ ...parseDeckListParams(base), ...patch }, base), options);
  };
  const clear = () => {
    const { q, mode, legal } = DEFAULT_DECK_LIST_PARAMS;
    change({ q, mode, legal });
  };
  return { params, change, clear };
}

/** `/decks` (F5-h): the user's decks as cards, a grid from 860 px and one column below, with
 *  a toolbar (search, mode, legality, sort in the URL), New deck, Import and per-deck actions. */
export function DecksPage() {
  const { t } = useTranslation('decks');
  const { t: tCommon } = useTranslation('common');
  useDocumentTitle(t('title'));
  const offline = useOffline();
  const query = useDecks();
  const { rules, pending: rulesPending } = useDeckRules();
  const [creating, setCreating] = useState<null | 'new' | 'import'>(null);
  const grid = useMediaQuery(GRID);
  const { params, change, clear } = useDeckListParams();
  const items = useMemo(() => query.data?.items ?? [], [query.data]);
  const shown = useMemo(() => selectDecks(items, params), [items, params]);

  const actions = (
    <>
      <Button disabled={offline} onClick={() => setCreating('new')}>
        <Icon name="plus" size={16} />
        {t('new')}
      </Button>
      <Button variant="ghost" disabled={offline} onClick={() => setCreating('import')}>
        {t('import')}
      </Button>
    </>
  );

  let body;
  if (query.isPending || (query.data && rulesPending)) {
    body = <Skeleton label={t('loading')} lines={6} />;
  } else if (query.isError && !query.data) {
    body = <ErrorState message={t('error')} onRetry={() => void query.refetch()} />;
  } else if (items.length === 0) {
    body = <EmptyState icon="decks" title={t('empty.title')} body={t('empty.body')} />;
  } else {
    body = (
      <>
        <DeckListToolbar
          params={params}
          modes={rules?.modes ?? ['1v1', '2v2']}
          shown={shown.length}
          total={items.length}
          onChange={change}
          onClear={clear}
        />
        {shown.length === 0 ? (
          <EmptyState
            icon="search"
            title={t('noMatch.title')}
            body={t('noMatch.body')}
            action={{ label: t('toolbar.clear'), onAction: clear }}
          />
        ) : (
          <ul
            className={grid ? styles.grid : styles.list}
            data-layout={grid ? 'grid' : 'column'}
            aria-label={t('list')}
            aria-busy={query.isFetching || undefined}
          >
            {shown.map((deck) => (
              <DeckItem key={deck.id} deck={deck} rules={rules} offline={offline} />
            ))}
          </ul>
        )}
      </>
    );
  }

  return (
    <div className={[styles.page, grid && styles.wide].filter(Boolean).join(' ')}>
      <PageHeader title={t('title')} subtitle={t('subtitle')} actions={actions} />
      {offline && <p className={styles.note}>{tCommon('offline.editDisabled')}</p>}
      {body}
      <NewDeckModal open={creating === 'new'} onClose={() => setCreating(null)} />
      <ImportDeckModal open={creating === 'import'} onClose={() => setCreating(null)} />
    </div>
  );
}
