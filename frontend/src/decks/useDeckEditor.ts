import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { putDeckContent } from '@/api/endpoints';
import type { CardSummary, DeckCard, DeckContentV2, DeckDetail, DeckRef } from '@/api/types';
import { useOffline } from '@/auth';
import { pushToast } from '@/components/ui/toastStore';
import {
  addCopy,
  bookOf,
  contentValue,
  knownContent,
  moveCopy,
  removeCopy,
  removeUnknown,
  rulesCardsOf,
  toDeckCard,
  unknownRefs,
  type CardBook,
  type EditZone,
  type LineZone,
} from './editor';
import { issueMessage } from './issues';
import { cardLabel, refKey } from './labels';
import { DECK_LIST_KEY, deckKey, useDeckRules } from './queries';
import {
  applyChampion,
  applyLegend,
  autoRunes,
  canAdd,
  canMove,
  cardKey,
  completeness,
  fitReason,
  hardLimitViolations,
  identity,
  type Cards,
  type CheckResult,
} from './rules';

const AUTOSAVE_MS = 1000;
export type SaveStatus = 'saved' | 'pending' | 'saving' | 'error' | 'blocked';

/**
 * The editing state of one deck (F5-h stage 2): the local content is the truth while editing,
 * every change is checked with the rules library first, and the content autosaves 1 s after the
 * last change (`PUT /decks/:id/content`, D-F5-3). A content over a hard limit or with cards the
 * catalog lacks is never sent (decision A): the screen lists why.
 */
export function useDeckEditor(deck: DeckDetail) {
  const { t } = useTranslation('decks');
  const client = useQueryClient();
  const offline = useOffline();
  const { rules } = useDeckRules();
  const [content, setContent] = useState<DeckContentV2>(deck.content);
  const [book, setBook] = useState<CardBook>(() => bookOf(deck.cards));
  const [server, setServer] = useState<DeckDetail>(deck);
  const [revision, setRevision] = useState(0);
  const [savedRevision, setSavedRevision] = useState(0);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const cards = useMemo(() => rulesCardsOf(book), [book]);
  const unknown = useMemo(() => unknownRefs(content, book), [content, book]);
  const known = useMemo(() => knownContent(content, book), [content, book]);
  const violations = useMemo(
    () => (rules ? hardLimitViolations(known, cards, rules) : []),
    [rules, known, cards],
  );
  const done = useMemo(
    () => (rules ? completeness(known, rules) : server.legality[server.mode].completeness),
    [rules, known, server],
  );
  const value = useMemo(() => contentValue(content, book), [content, book]);
  const dirty = revision !== savedRevision;
  const blocked = violations.length > 0 || unknown.length > 0;
  /** Edits need the rule values, a connection and a content the rules can read. */
  const canEdit = rules !== null && !offline && unknown.length === 0;
  const status: SaveStatus = saving
    ? 'saving'
    : error
      ? 'error'
      : dirty
        ? blocked
          ? 'blocked'
          : 'pending'
        : 'saved';

  const edit = useCallback((next: DeckContentV2) => {
    setContent(next);
    setRevision((value) => value + 1);
    setError(null);
  }, []);

  const save = useCallback(
    async (body: DeckContentV2, sent: number) => {
      setSaving(true);
      setError(null);
      try {
        const result = await putDeckContent(deck.id, body);
        setServer(result);
        setSavedRevision(sent);
        client.setQueryData(deckKey(deck.id), result);
        void client.invalidateQueries({ queryKey: DECK_LIST_KEY });
      } catch (failure) {
        setError(failure);
      } finally {
        setSaving(false);
      }
    },
    [client, deck.id],
  );

  useEffect(() => {
    if (!dirty || blocked || offline || saving || error) return;
    const timer = window.setTimeout(() => void save(content, revision), AUTOSAVE_MS);
    return () => window.clearTimeout(timer);
  }, [dirty, blocked, offline, saving, error, save, content, revision]);

  // Leaving the screen within the debounce still saves the last change.
  const latest = useRef({ dirty, blocked, offline, content });
  useEffect(() => {
    latest.current = { dirty, blocked, offline, content };
  });
  useEffect(
    () => () => {
      const last = latest.current;
      if (last.dirty && !last.blocked && !last.offline) {
        void putDeckContent(deck.id, last.content)
          .then((result) => client.setQueryData(deckKey(deck.id), result))
          .then(() => client.invalidateQueries({ queryKey: DECK_LIST_KEY }))
          .catch(() => undefined);
      }
    },
    [client, deck.id],
  );

  const name = (ref: DeckRef) => {
    const card = book[refKey(ref)];
    return card ? cardLabel(card) : refKey(ref);
  };

  /** A removal can be undone from its toast: the deck goes back to how it was. */
  const removeWithUndo = (next: DeckContentV2, message: string) => {
    const before = content;
    edit(next);
    pushToast({
      kind: 'info',
      message,
      action: { label: t('edit.undo'), onAction: () => edit(before) },
    });
  };

  const refusal = (check: CheckResult) => (check.ok ? null : issueMessage(t, check));

  /** The owner's rule for the editor (F5-i): with a legend, the main deck and the sideboard
   *  only take cards of its domains, and Signature cards that share a tag with it. The rules
   *  library keeps both soft (`validate` reports them) so imports and versions still load. */
  const identityReason = (ref: DeckRef, zone: EditZone, rulesCards: Cards) => {
    if ((zone !== 'main' && zone !== 'sideboard') || !known.legend) return null;
    const card = rulesCards.get(cardKey(ref));
    const legend = rulesCards.get(cardKey(known.legend));
    if (!card || !legend) return null;
    const reason = fitReason(card, zone, legend, identity(known, rulesCards));
    if (reason === 'tag') return t('edit.signatureTag');
    if (reason === 'domain') return t('edit.offDomain');
    return null;
  };

  /** Why a copy cannot be added to `zone` (null when it can). */
  const addReason = (ref: DeckRef, zone: EditZone, withBook: CardBook = book) => {
    if (!rules) return t('edit.needRules');
    const rulesCards = withBook === book ? cards : rulesCardsOf(withBook);
    return (
      refusal(canAdd(known, rulesCards, ref, zone, rules)) ?? identityReason(ref, zone, rulesCards)
    );
  };
  const moveReason = (ref: DeckRef, from: LineZone, to: LineZone) => {
    if (!rules || from === 'runes' || to === 'runes') return t('edit.needRules');
    // a card entering the deck from the workbench meets the same legend rule as an added one
    return (
      refusal(canMove(known, cards, ref, from, to, rules)) ??
      (from === 'workbench' ? identityReason(ref, to, cards) : null)
    );
  };

  const add = (ref: DeckRef, zone: EditZone) => {
    if (canEdit && addReason(ref, zone) === null) edit(addCopy(content, zone, ref));
  };
  const remove = (ref: DeckRef, zone: EditZone) => {
    if (!canEdit) return;
    const line =
      zone === 'battlefields' ? null : content[zone].find((l) => refKey(l) === refKey(ref));
    const next = removeCopy(content, zone, ref);
    if (line && line.qty > 1) edit(next);
    else removeWithUndo(next, t('edit.removed', { name: name(ref) }));
  };
  const move = (ref: DeckRef, from: LineZone, to: LineZone) => {
    if (canEdit && moveReason(ref, from, to) === null) edit(moveCopy(content, from, to, ref));
  };

  /** A card picked in a section's search: checked, then added (or refused with the reason). */
  const pick = (found: CardSummary, zone: EditZone | 'legend' | 'champion') => {
    if (!canEdit || !rules) return;
    const card: DeckCard = toDeckCard(found);
    const ref = { set: card.set_id, id: card.card_id };
    const withBook = { ...book, [card.key]: card };
    const rulesCards = rulesCardsOf(withBook);
    const fail = (message: string) => pushToast({ kind: 'error', message });
    if (zone === 'legend' || zone === 'champion') {
      const result =
        zone === 'legend'
          ? applyLegend(known, rulesCards, ref)
          : applyChampion(known, rulesCards, ref, rules);
      if (!result.ok) return fail(issueMessage(t, result));
      setBook(withBook);
      const next = result.deck as DeckContentV2;
      const purged =
        zone === 'legend' &&
        (next.runes.length !== content.runes.length ||
          (content.champion !== null && next.champion === null));
      if (purged) removeWithUndo(next, t('edit.legendChanged'));
      else edit(next);
      return;
    }
    const reason = addReason(ref, zone, withBook);
    if (reason) return fail(reason);
    setBook(withBook);
    edit(addCopy(content, zone, ref));
  };

  const clearSlot = (slot: 'legend' | 'champion') => {
    if (!canEdit || !content[slot]) return;
    const label = name(content[slot]);
    const result =
      slot === 'legend'
        ? applyLegend(known, cards, null)
        : rules
          ? applyChampion(known, cards, null, rules)
          : null;
    if (result?.ok)
      removeWithUndo(result.deck as DeckContentV2, t('edit.removed', { name: label }));
  };

  const identityDomains = useMemo(
    () => (known.legend ? identity(known, cards) : []),
    [known, cards],
  );

  /** Replaces the runes by the balanced ones (`autoRunes`); `runeCards` are the base runes. */
  const balanceRunes = (runeCards: CardSummary[]) => {
    if (!canEdit || !rules) return;
    const withBook: Record<string, DeckCard> = { ...book };
    for (const card of runeCards) if (!withBook[card.key]) withBook[card.key] = toDeckCard(card);
    setBook(withBook);
    edit(autoRunes(known, rulesCardsOf(withBook), rules) as DeckContentV2);
  };

  return {
    t,
    deck: server,
    setServer,
    content,
    book,
    done,
    value,
    unknown,
    violations,
    status,
    error,
    dirty,
    canEdit,
    offline,
    rules,
    identityDomains,
    retry: () => void save(content, revision),
    addReason,
    moveReason,
    add,
    remove,
    move,
    pick,
    clearSlot,
    balanceRunes,
    removeUnknown: () => edit(removeUnknown(content, book)),
  };
}

export type DeckEditor = ReturnType<typeof useDeckEditor>;
