import { useId, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router';
import type { DeckCompleteness, DeckDetail, GameMode } from '@/api/types';
import { ApiError } from '@/api/errors';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { ErrorState } from '@/components/ui/ErrorState';
import { PageHeader } from '@/components/ui/PageHeader';
import { Skeleton } from '@/components/ui/Skeleton';
import { translateError, useDocumentTitle } from '@/i18n';
import { up } from '@/lib/breakpoints';
import { formatDate, formatMoney } from '@/lib/format';
import { useMediaQuery } from '@/lib/useMediaQuery';
import { NotFound } from '@/shell/NotFound';
import { CardBrowser } from './CardBrowser';
import { DeckActions } from './DeckActions';
import { DeckSections } from './DeckSections';
import { hardLimitMessage, issueMessage } from './issues';
import { useDeck } from './queries';
import { useDeckEditor, type DeckEditor } from './useDeckEditor';
import styles from './DeckView.module.css';

type Section = keyof DeckCompleteness;
const SECTIONS: Section[] = ['legend', 'champion', 'main', 'runes', 'battlefields', 'sideboard'];

const modesOf = (deck: DeckDetail) => Object.keys(deck.legality) as GameMode[];

/** Main, runes, legality and value, kept in view while the sections scroll (F5-R14). */
function SummaryBar({ editor }: { editor: DeckEditor }) {
  const { t } = useTranslation('decks');
  const id = useId();
  const { deck, done, value } = editor;
  return (
    <section className={styles.summary} aria-labelledby={id}>
      <h2 id={id} className="sr-only">
        {t('summary.label')}
      </h2>
      <span>{t('counts.main', { have: done.main.have, need: done.main.need })}</span>
      <span>{t('counts.runes', { have: done.runes.have, need: done.runes.need })}</span>
      {modesOf(deck).map((mode) => (
        <Badge key={mode} tone={deck.legality[mode].legal ? 'success' : 'danger'}>
          {t(deck.legality[mode].legal ? 'legal.yes' : 'legal.no', { mode })}
        </Badge>
      ))}
      <span className={styles.value}>{formatMoney(value.value)}</span>
    </section>
  );
}

/** Legality of both modes (the server's, as of the last save), every issue explained from its
 *  code and params (F5-R19). */
function LegalityBlock({ editor }: { editor: DeckEditor }) {
  const { t } = useTranslation('decks');
  const id = useId();
  const { deck, dirty } = editor;
  return (
    <section className={styles.block} aria-labelledby={id}>
      <h2 id={id}>{t('legality.title')}</h2>
      {dirty && <p className={styles.muted}>{t('save.staleLegality')}</p>}
      {modesOf(deck).map((mode) => {
        const result = deck.legality[mode];
        const status = t(result.legal ? 'legality.legal' : 'legality.notLegal');
        const label = t(mode === deck.mode ? 'legality.groupDeckMode' : 'legality.group', {
          mode,
          status,
        });
        return (
          <div
            key={mode}
            role="group"
            aria-label={label}
            className={result.legal ? styles.legal : styles.notLegal}
          >
            <h3>{label}</h3>
            {result.legal ? (
              <p>{t('legality.legalIn', { mode })}</p>
            ) : (
              <ul>
                {result.issues.map((issue, index) => (
                  <li key={`${issue.code}-${index}`}>{issueMessage(t, issue)}</li>
                ))}
              </ul>
            )}
          </div>
        );
      })}
    </section>
  );
}

/** "Main deck: 39/39", "Sideboard: 8/10 (2 missing)" per section, live while editing. */
function Completeness({ done }: { done: DeckCompleteness }) {
  const { t } = useTranslation('decks');
  const id = useId();
  return (
    <section className={styles.block} aria-labelledby={id}>
      <h2 id={id}>{t('completeness.title')}</h2>
      <ul className={styles.completeness} aria-label={t('completeness.title')}>
        {SECTIONS.map((key) => {
          const { have, need, missing } = done[key];
          const over = Math.max(0, have - need);
          const kind = missing > 0 ? 'missing' : over > 0 ? 'over' : 'line';
          return (
            <li key={key} data-state={kind}>
              {t(`completeness.${kind}`, {
                section: t(`section.${key}`),
                have,
                need,
                missing,
                over,
              })}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

/** Printings the catalog does not have: kept, out of legality and value; editing and saving
 *  wait until the user removes them. */
function UnknownCards({ editor }: { editor: DeckEditor }) {
  const { t } = useTranslation('decks');
  const id = useId();
  if (editor.unknown.length === 0) return null;
  return (
    <section className={styles.warning} aria-labelledby={id}>
      <h2 id={id}>{t('unknown.title')}</h2>
      <p>{t('unknown.body')}</p>
      <ul>
        {editor.unknown.map((card) => (
          <li key={`${card.zone}-${card.set}-${card.id}`}>
            {t('unknown.item', { key: `${card.set}-${card.id}`, zone: t(`section.${card.zone}`) })}
          </li>
        ))}
      </ul>
      <p>{t('blocked.unknown')}</p>
      <Button
        variant="ghost"
        size="sm"
        disabled={editor.offline || !editor.rules}
        onClick={editor.removeUnknown}
      >
        {t('blocked.removeUnknown')}
      </Button>
    </section>
  );
}

/** Decision A: a content over a hard limit is never sent; say which limits and keep editing. */
function LimitBanner({ editor }: { editor: DeckEditor }) {
  const { t } = useTranslation('decks');
  if (editor.violations.length === 0) return null;
  return (
    <div className={styles.warning} role="alert">
      <p>{t('blocked.limits')}</p>
      <ul>
        {editor.violations.map((violation) => (
          <li key={`${violation.rule}-${violation.name ?? ''}`}>
            {hardLimitMessage(t, violation)}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Saving, saved, not saved (with the reason and a retry) or offline. */
function SaveState({ editor }: { editor: DeckEditor }) {
  const { t, i18n } = useTranslation('decks');
  const { status, error, offline } = editor;
  let text: string;
  if (offline) text = t('save.offline');
  else if (status === 'error') {
    const limit =
      error instanceof ApiError && error.code === 'deck_limit_exceeded' && error.params
        ? hardLimitMessage(t, error.params as { rule: string; max: number; name?: string })
        : translateError(error, i18n);
    text = t('save.error', { reason: limit });
  } else if (status === 'saving') text = t('save.saving');
  else if (status === 'saved') text = t('save.saved');
  else text = t('save.pending');
  return (
    <p
      className={styles.saveState}
      role="status"
      data-slot="save-state"
      data-state={offline ? 'offline' : status}
    >
      <span>{text}</span>
      {status === 'error' && !offline && (
        <Button variant="ghost" size="sm" onClick={editor.retry}>
          {t('save.retry')}
        </Button>
      )}
    </p>
  );
}

/** Two panes from `lg` (960 px): each column keeps about 450 px, the phone width the workspace
 *  already lays out, and the card tiles still fit three or four in a row. */
const TWO_PANE = up('lg');

/** The loaded deck: one editor per deck id. On a wide screen, while editing is possible, the
 *  card browser sits left of the workspace (F5-i step 2); otherwise one column as in F5-h. The
 *  workspace keeps its place in the tree so a layout change never resets it. */
function DeckWorkspace({ deck: loaded, back }: { deck: DeckDetail; back: ReactNode }) {
  const { t } = useTranslation('decks');
  const editor = useDeckEditor(loaded);
  const wide = useMediaQuery(TWO_PANE);
  const twoPane = wide && editor.canEdit;
  const { deck } = editor;
  useDocumentTitle(deck.name);
  return (
    <div
      className={twoPane ? `${styles.page} ${styles.wide}` : styles.page}
      data-layout={twoPane ? 'two-pane' : 'single'}
    >
      {back}
      <div className={styles.panes}>
        {twoPane && (
          <div className={styles.browserPane}>
            <CardBrowser editor={editor} />
          </div>
        )}
        <section className={styles.workspace} aria-label={t('workspace')}>
          <PageHeader
            title={deck.name}
            subtitle={[
              t('version', { seq: deck.current_seq }),
              t('updated', { date: formatDate(deck.updated_at) }),
            ].join(' · ')}
            actions={<Badge tone="accent">{deck.mode}</Badge>}
          />
          <DeckActions editor={editor} />
          <SaveState editor={editor} />
          <SummaryBar editor={editor} />
          <LimitBanner editor={editor} />
          <LegalityBlock editor={editor} />
          <Completeness done={editor.done} />
          <UnknownCards editor={editor} />
          <DeckSections editor={editor} pickers={!twoPane} />
        </section>
      </div>
    </div>
  );
}

/** `/decks/:id` (F5-h): the deck on its own screen, sections collapsible. */
export function DeckView() {
  const { t } = useTranslation('decks');
  const id = Number(useParams().id);
  const query = useDeck(id);
  const deck = query.data;
  useDocumentTitle(deck?.name ?? t('title'));

  const missing =
    !Number.isInteger(id) ||
    id < 1 ||
    (query.error instanceof ApiError && query.error.status === 404);
  if (missing) return <NotFound />;

  const back = (
    <Link to="/decks" className={styles.back}>
      {t('back')}
    </Link>
  );
  if (query.isPending) {
    return (
      <div className={styles.page}>
        {back}
        <Skeleton label={t('loadingDeck')} lines={8} />
      </div>
    );
  }
  if (!deck) {
    return (
      <div className={styles.page}>
        {back}
        <ErrorState message={t('errorDeck')} onRetry={() => void query.refetch()} />
      </div>
    );
  }

  return <DeckWorkspace key={deck.id} deck={deck} back={back} />;
}
