import { HttpResponse, http } from 'msw';
import type { StorageLocation } from '@/api/types';
import { UNASSIGNED_COPIES, storageLocations } from './fixtures/locations';
import { API, signedInSession } from './msw/handlers';
import { server } from './msw/server';

export type Sent = {
  method: string;
  path: string;
  search: string;
  body: Record<string, unknown> | null;
};

export function signedIn() {
  server.use(http.get(`${API}/auth/session`, () => signedInSession()));
}

/** `GET /locations` answers with these locations (the fixture list by default). */
export function withLocations(
  items: StorageLocation[] = storageLocations,
  unassigned = UNASSIGNED_COPIES,
) {
  server.use(
    http.get(`${API}/locations`, () =>
      HttpResponse.json({
        success: true,
        data: { items },
        meta: { unassigned_copies: unassigned },
      }),
    ),
  );
}

/**
 * Every request to `/locations` and `/collection` (method, path without the API prefix, query
 * and JSON body), in the order they started.
 */
export function recordRequests() {
  const sent: Sent[] = [];
  server.events.on('request:start', async ({ request }) => {
    const url = new URL(request.url);
    if (
      !url.pathname.startsWith(`${API}/locations`) &&
      !url.pathname.startsWith(`${API}/collection`)
    )
      return;
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

/** The writes only (no GET). */
export const writes = (sent: Sent[]) => sent.filter((request) => request.method !== 'GET');
