import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { ApiError } from '@/api/errors';
import { getCard, getCardPrices, type PriceRange } from '@/api/endpoints';

const STALE_MS = 5 * 60 * 1000;

function retryOnCardError(failureCount: number, error: unknown): boolean {
  if (error instanceof ApiError && error.kind === 'http' && error.status === 404) return false;
  return failureCount < 1;
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
