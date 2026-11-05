import { useId, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';
import type { DeckListItem, GameMode } from '@/api/types';
import { useOffline } from '@/auth';
import { DomainPips } from '@/components/card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { Icon } from '@/components/ui/Icon';
import { PageHeader } from '@/components/ui/PageHeader';
import { Skeleton } from '@/components/ui/Skeleton';
import { useDocumentTitle } from '@/i18n';
import { formatDate, formatMoney } from '@/lib/format';
import { legacyHref } from '@/shell/legacyRoutes';
import { ImportDeckModal, NewDeckModal } from './DeckCreate';
import { issueShort } from './issues';
import { cardLabel } from './labels';
import { useDeckRules, useDecks } from './queries';
import type { RulesContext } from './rules';
import styles from './DecksPage.module.css';

const REASONS_SHOWN = 3;

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

function DeckItem({ deck, rules }: { deck: DeckListItem; rules: RulesContext | null }) {
  const { t } = useTranslation('decks');
  const need = rules?.deck;
  const count = (key: 'main' | 'runes' | 'battlefields' | 'sideboard', max?: number) =>
    t(`counts.${key}`, { have: deck.counts[key], need: max ?? '—' });
  const modes = Object.keys(deck.legal) as GameMode[];
  return (
    <li className={styles.item}>
      <div className={styles.top}>
        <h2 className={styles.name}>
          <Link to={`/decks/${deck.id}`}>{deck.name}</Link>
        </h2>
        <Badge tone="accent">{deck.mode}</Badge>
      </div>
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
    </li>
  );
}

/** `/decks` (F5-h): the user's decks in one readable column on every width (the desktop
 *  layout is F5-i), with New deck and Import. */
export function DecksPage() {
  const { t } = useTranslation('decks');
  const { t: tCommon } = useTranslation('common');
  useDocumentTitle(t('title'));
  const offline = useOffline();
  const query = useDecks();
  const { rules, pending: rulesPending } = useDeckRules();
  const [creating, setCreating] = useState<null | 'new' | 'import'>(null);
  const items = query.data?.items ?? [];

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
      <ul className={styles.list} aria-label={t('list')} aria-busy={query.isFetching || undefined}>
        {items.map((deck) => (
          <DeckItem key={deck.id} deck={deck} rules={rules} />
        ))}
      </ul>
    );
  }

  return (
    <div className={styles.page}>
      <PageHeader title={t('title')} subtitle={t('subtitle')} actions={actions} />
      {offline && <p className={styles.note}>{tCommon('offline.editDisabled')}</p>}
      {body}
      <a className={styles.classic} href={legacyHref('decks')}>
        {t('classic')}
      </a>
      <NewDeckModal open={creating === 'new'} onClose={() => setCreating(null)} />
      <ImportDeckModal open={creating === 'import'} onClose={() => setCreating(null)} />
    </div>
  );
}
