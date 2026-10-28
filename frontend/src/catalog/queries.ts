import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { ApiError } from '@/api/errors';
import { getCard, getCardPrices, getGameMeta, listCards, type PriceRange } from '@/api/endpoints';
import type { CardListParams } from '@/api/types';
import { serializeCatalogParams } from './params';

const STALE_MS = 5 * 60 * 1000;
const META_STALE_MS = 60 * 60 * 1000;

function retryOnCardError(failureCount: number, error: unknown): boolean {
  if (error instanceof ApiError && error.kind === 'http' && error.status === 404) return false;
  return failureCount < 1;
}

/** TanStack Query hook for `GET /meta/game` (F2-h S4). */
export function useGameMeta() {
  return useQuery({
    queryKey: ['meta', 'game'] as const,
    queryFn: ({ signal }) => getGameMeta(signal),
    staleTime: META_STALE_MS,
  });
}

/** TanStack Query hook for the card list endpoint (F2-h S4). */
export function useCardList(params: CardListParams) {
  const query = serializeCatalogParams(params);
  return useQuery({
    queryKey: ['cards', 'list', query] as const,
    queryFn: ({ signal }) => listCards(query, signal),
    placeholderData: keepPreviousData,
    staleTime: STALE_MS,
  });
}

/** TanStack Query hook for the card detail endpoint (F2-f S2). */
export function useCardDetail(setId: string | undefined, cardId: string | undefined) {
  return useQuery({
    queryKey: ['cards', 'detail', setId, cardId] as const,
    queryFn: ({ signal }) => {
      if (!setId || !cardId) throw new Error('Missing card identifiers');
      return getCard(setId, cardId, signal);
    },
    staleTime: STALE_MS,
    retry: retryOnCardError,
    enabled: Boolean(setId && cardId),
  });
}

/** Options a `CardCombobox` lists at most (F2-k S2). */
export const COMBOBOX_LIMIT = 20;

/**
 * TanStack Query hook behind `CardCombobox` (F2-k S2): name search sorted by name, at most
 * `COMBOBOX_LIMIT` cards. `enabled` false keeps whatever is cached and makes no request.
 */
export function useCardSearch(filters: Partial<CardListParams>, q: string, enabled: boolean) {
  const params = new URLSearchParams(serializeCatalogParams({ ...filters, q, sort: 'name' }));
  params.set('per_page', String(COMBOBOX_LIMIT));
  const query = params.toString();
  return useQuery({
    queryKey: ['cards', 'search', query] as const,
    queryFn: ({ signal }) => listCards(query, signal),
    staleTime: STALE_MS,
    retry: false,
    enabled,
  });
}

const PRICE_STALE_MS = 10 * 60 * 1000;

/** TanStack Query hook for the card price history endpoint (F2-g S1). */
export function useCardPrices(
  setId: string | undefined,
  cardId: string | undefined,
  range: PriceRange,
) {
  return useQuery({
    queryKey: ['cards', 'prices', setId, cardId, range] as const,
    queryFn: ({ signal }) => {
      if (!setId || !cardId) throw new Error('Missing card identifiers');
      return getCardPrices(setId, cardId, range, signal);
    },
    placeholderData: keepPreviousData,
    staleTime: PRICE_STALE_MS,
    retry: false,
    enabled: Boolean(setId && cardId),
  });
}
