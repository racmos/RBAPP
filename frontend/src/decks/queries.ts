import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createDeck,
  createDeckVersion,
  deleteDeck,
  getDeck,
  getDeckVersion,
  importDeck,
  listCards,
  listDeckVersions,
  listDecks,
  patchDeck,
  previewDeckImport,
  shareDeck,
  unshareDeck,
} from '@/api/endpoints';
import type { DeckCreateBody, DeckImportBody, DeckPatchBody } from '@/api/types';
import { ApiError } from '@/api/errors';
import { useGameMeta } from '@/catalog';
import { rulesFromMeta, type RulesContext } from './rules';

const STALE_MS = 60 * 1000;
export const DECKS_KEY = ['decks'] as const;
export const DECK_LIST_KEY = ['decks', 'list'] as const;
export const deckKey = (id: number) => ['decks', 'detail', id] as const;
const versionsKey = (id: number) => ['decks', 'versions', id] as const;

const notFound = (error: unknown) => error instanceof ApiError && error.status === 404;
const retry = (count: number, error: unknown) => !notFound(error) && count < 1;
const validId = (id: number) => Number.isInteger(id) && id > 0;

/** The user's decks, newest first (`GET /decks`, F5-d). */
export function useDecks() {
  return useQuery({
    queryKey: DECK_LIST_KEY,
    queryFn: ({ signal }) => listDecks(signal),
    staleTime: STALE_MS,
  });
}

/** One deck with its current content, cards and legality in both modes. */
export function useDeck(id: number) {
  return useQuery({
    queryKey: deckKey(id),
    queryFn: ({ signal }) => getDeck(id, signal),
    staleTime: STALE_MS,
    retry,
    enabled: validId(id),
  });
}

/** The versions of a deck, newest first (the versions screen itself is F5-j). */
export function useDeckVersions(id: number, enabled = true) {
  return useQuery({
    queryKey: versionsKey(id),
    queryFn: ({ signal }) => listDeckVersions(id, signal),
    staleTime: STALE_MS,
    retry,
    enabled: enabled && validId(id),
  });
}

export function useDeckVersion(id: number, seq: number) {
  return useQuery({
    queryKey: [...versionsKey(id), seq] as const,
    queryFn: ({ signal }) => getDeckVersion(id, seq, signal),
    staleTime: STALE_MS,
    retry,
    enabled: validId(id) && Number.isInteger(seq) && seq > 0,
  });
}

/** The rule values of `/meta/game` (never hardcoded); null until it has loaded. */
export function useDeckRules(): { rules: RulesContext | null; pending: boolean } {
  const meta = useGameMeta();
  return {
    rules: meta.data ? rulesFromMeta(meta.data) : null,
    pending: meta.isPending && !meta.isError,
  };
}

/** The base rune of each domain (`autoRunes` needs one for a colour the deck has no rune of). */
export function useRuneCards(domains: readonly string[]) {
  const query = new URLSearchParams([
    ['type', 'Rune'],
    ['base_only', 'true'],
    ['per_page', '48'],
    ...domains.map((domain) => ['domain', domain]),
  ]).toString();
  return useQuery({
    queryKey: ['cards', 'list', query] as const,
    queryFn: ({ signal }) => listCards(query, signal),
    staleTime: 10 * STALE_MS,
    enabled: domains.length > 0,
  });
}

/** Every write refreshes the list (names, counts, legality, dates). */
function useRefreshList() {
  const client = useQueryClient();
  return () => client.invalidateQueries({ queryKey: DECK_LIST_KEY });
}

export function useCreateDeck() {
  const refresh = useRefreshList();
  return useMutation({
    mutationFn: (body: DeckCreateBody) => createDeck(body),
    onSuccess: refresh,
  });
}

export function useImportPreview() {
  return useMutation({ mutationFn: (text: string) => previewDeckImport(text) });
}

export function useImportDeck() {
  const refresh = useRefreshList();
  return useMutation({
    mutationFn: (body: DeckImportBody) => importDeck(body),
    onSuccess: refresh,
  });
}

export function usePatchDeck(id: number) {
  const refresh = useRefreshList();
  return useMutation({
    mutationFn: (body: DeckPatchBody) => patchDeck(id, body),
    onSuccess: refresh,
  });
}

export function useDeleteDeck(id: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => deleteDeck(id),
    onSuccess: async () => {
      client.removeQueries({ queryKey: deckKey(id) });
      await client.invalidateQueries({ queryKey: DECK_LIST_KEY });
    },
  });
}

export function useSaveVersion(id: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (note?: string) => createDeckVersion(id, note),
    onSuccess: () => client.invalidateQueries({ queryKey: versionsKey(id) }),
  });
}

export function useShareDeck(id: number) {
  const refresh = useRefreshList();
  return useMutation({ mutationFn: () => shareDeck(id), onSuccess: refresh });
}

export function useUnshareDeck(id: number) {
  const refresh = useRefreshList();
  return useMutation({ mutationFn: () => unshareDeck(id), onSuccess: refresh });
}
