import { http } from 'msw';
import type {
  CardMini,
  DeckCard,
  DeckDetail,
  DeckListItem,
  DeckVsCollection,
  MissingToWishlistResult,
} from '@/api/types';
import { deckDetails, deckList, printingDetail } from './fixtures/decks';
import { API, failure, ok } from './msw/handlers';
import { server } from './msw/server';
import type { Sent } from './locations';

/** `GET /decks` answers with these items and `GET /decks/:id` with these details. */
export function withDecks(items: DeckListItem[] = deckList, details: DeckDetail[] = deckDetails) {
  server.use(
    http.get(`${API}/decks`, () => ok({ items })),
    http.get(`${API}/decks/:id`, ({ params }) => {
      const detail = details.find((deck) => String(deck.id) === params.id);
      return detail ? ok(detail) : failure(404, { error: 'Not Found' });
    }),
  );
}

/** Every request to `/decks` (method, path without the API prefix, query, JSON body). */
export function recordDeckRequests() {
  const sent: Sent[] = [];
  server.events.on('request:start', async ({ request }) => {
    const url = new URL(request.url);
    if (!url.pathname.startsWith(`${API}/decks`)) return;
    let body: Record<string, unknown> | null = null;
    if (request.method !== 'GET' && request.method !== 'DELETE') {
      try {
        body = (await request.clone().json()) as Record<string, unknown>;
      } catch {
        body = null;
      }
    }
    sent.push({
      method: request.method,
      path: url.pathname.replace(API, ''),
      search: url.search,
      body,
    });
  });
  return sent;
}

/** `GET /cards/:set/:id` of any of `printings` lists them all as its printings (one name). */
export function withPrintings(printings: DeckCard[]) {
  server.use(
    http.get(`${API}/cards/:setId/:cardId`, ({ params }) => {
      const of = printings.find((c) => c.set_id === params.setId && c.card_id === params.cardId);
      return of ? ok(printingDetail(of, printings)) : failure(404, { error: 'Not Found' });
    }),
  );
}

/** The `CardMini` of a deck card (what the deck-vs-collection answers carry). */
export const miniOfDeckCard = (card: DeckCard): CardMini => ({
  set_id: card.set_id,
  card_id: card.card_id,
  key: card.key,
  name: card.name,
  domains: card.domains,
  type: card.type,
  supertype: card.supertype,
  rarity: card.rarity,
  image_src: card.image_src,
  image_thumb_src: card.image_thumb_src,
  is_base: card.is_base,
  market: card.market,
  owned_total: card.owned_total ?? 0,
});

/**
 * `GET /decks/:id/vs-collection` answers `answer()` (a function, so a test can change it between
 * calls) and `POST /decks/:id/missing-to-wishlist` answers `result` with the list sent (or the
 * default list, id 1, when none). Returns the count of reads and the bodies posted.
 */
export function withVsCollection(
  answer: () => DeckVsCollection,
  result?: (wishlistId: number) => MissingToWishlistResult,
) {
  const calls = { reads: 0, posts: [] as Record<string, unknown>[] };
  server.use(
    http.get(`${API}/decks/:id/vs-collection`, () => {
      calls.reads += 1;
      return ok(answer());
    }),
    http.post(`${API}/decks/:id/missing-to-wishlist`, async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      calls.posts.push(body);
      const id = typeof body.wishlist_id === 'number' ? body.wishlist_id : 1;
      return result ? ok(result(id)) : failure(500, { error: 'Internal Server Error' });
    }),
  );
  return calls;
}
