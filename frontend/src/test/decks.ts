import { http } from 'msw';
import type { DeckDetail, DeckListItem } from '@/api/types';
import { deckDetails, deckList } from './fixtures/decks';
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
