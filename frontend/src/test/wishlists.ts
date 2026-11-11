import { screen, within } from '@testing-library/react';
import { HttpResponse, http } from 'msw';
import type { CardSummary, Wishlist, WishlistLine, WishFoil } from '@/api/types';
import { cardList } from './fixtures/cards';
import {
  defaultList,
  line,
  miniOf,
  tradesList,
  wishlist,
  wishlistLines,
} from './fixtures/wishlists';
import { API, failure, ok, signedInSession } from './msw/handlers';
import { server } from './msw/server';

export type Sent = {
  method: string;
  path: string;
  search: string;
  body: Record<string, unknown> | null;
};

const MAX_LISTS = 20;
const MAX_LINES = 100;

export function signedIn() {
  server.use(http.get(`${API}/auth/session`, () => signedInSession()));
}

type State = { lists: Wishlist[]; lines: WishlistLine[] };

const clone = <T>(value: T): T => JSON.parse(JSON.stringify(value)) as T;
const conflict = (code: string, message: string, params?: Record<string, unknown>) =>
  failure(409, { error: 'Conflict', message, code, ...(params ? { params } : {}) });
const invalid = (field: string) =>
  failure(400, {
    error: 'Validation Error',
    message: 'Invalid request data',
    code: 'validation_error',
    details: [{ field, message: 'invalid', type: 'value_error', code: 'invalid_value' }],
  });

/**
 * An in-memory wishlists API (F3-f-2 contract) over the fixture lists and lines: every route of
 * `docs/api.md` "Wishlists" with its merges, limits and conflicts. Tests read `state` and
 * override single routes with `server.use(...)`.
 */
export function installWishlists(
  lists: Wishlist[] = [defaultList, tradesList],
  lines: WishlistLine[] = wishlistLines,
) {
  const state: State = { lists: clone(lists), lines: clone(lines) };
  let nextList = 500;
  let nextLine = 9000;

  const counted = (list: Wishlist): Wishlist => ({
    ...list,
    line_count: state.lines.filter((item) => item.list_id === list.id).length,
  });
  const ordered = () =>
    [...state.lists].sort((a, b) => a.position - b.position).map((list) => counted(list));
  const renumber = (ids: number[]) =>
    ids.forEach((id, index) => {
      const list = state.lists.find((item) => item.id === id);
      if (list) list.position = index + 1;
    });
  const find = (id: unknown) => state.lists.find((list) => String(list.id) === String(id));
  const sameTarget = (
    a: WishlistLine,
    b: Pick<WishlistLine, 'name' | 'set_id' | 'card_id' | 'foil'>,
  ) => a.name === b.name && a.set_id === b.set_id && a.card_id === b.card_id && a.foil === b.foil;
  const meta = (items: WishlistLine[], listId: number) => {
    const priced = items.filter((item) => item.market !== null);
    return {
      total: items.length,
      line_count: state.lines.filter((item) => item.list_id === listId).length,
      max_lines: MAX_LINES,
      market_total:
        Math.round(priced.reduce((sum, item) => sum + item.market!.value * item.qty, 0) * 100) /
        100,
      unpriced: items.length - priced.length,
    };
  };
  const nameTaken = (name: string, except?: number) =>
    state.lists.some(
      (list) => list.id !== except && list.name.toLowerCase() === name.trim().toLowerCase(),
    );

  server.use(
    http.get(`${API}/wishlists`, () => ok({ items: ordered() })),
    http.post(`${API}/wishlists`, async ({ request }) => {
      const { name } = (await request.json()) as { name: string };
      if (nameTaken(name))
        return conflict('already_exists', 'A wishlist with that name already exists.');
      if (state.lists.length >= MAX_LISTS) {
        return conflict('wishlist_limit', 'You can have at most 20 wishlists.', {
          scope: 'lists',
          max: MAX_LISTS,
        });
      }
      const created = wishlist({
        id: nextList++,
        name: name.trim(),
        position: state.lists.length + 1,
        is_default: state.lists.length === 0,
      });
      state.lists.push(created);
      return ok(counted(created), 201);
    }),
    http.put(`${API}/wishlists/order`, async ({ request }) => {
      const { ids } = (await request.json()) as { ids: number[] };
      if (ids.length !== state.lists.length || ids.some((id) => !find(id))) return invalid('ids');
      renumber(ids);
      return ok({ items: ordered() });
    }),
    http.patch(`${API}/wishlists/:id`, async ({ params, request }) => {
      const list = find(params.id);
      if (!list) return failure(404, { error: 'Not Found' });
      const body = (await request.json()) as { name?: string; is_default?: boolean };
      if (body.name !== undefined) {
        if (nameTaken(body.name, list.id)) {
          return conflict('already_exists', 'A wishlist with that name already exists.');
        }
        list.name = body.name.trim();
      }
      if (body.is_default === false && list.is_default) return invalid('is_default');
      if (body.is_default === true) {
        for (const other of state.lists) other.is_default = other.id === list.id;
      }
      return ok(counted(list));
    }),
    http.delete(`${API}/wishlists/:id`, ({ params }) => {
      const list = find(params.id);
      if (!list) return failure(404, { error: 'Not Found' });
      if (list.is_default) {
        return conflict(
          'wishlist_default',
          'The default list cannot be deleted. Star another list first.',
        );
      }
      const gone = state.lines.filter((item) => item.list_id === list.id);
      const deleted = counted(list);
      state.lines = state.lines.filter((item) => item.list_id !== list.id);
      state.lists = state.lists.filter((item) => item.id !== list.id);
      renumber(ordered().map((item) => item.id));
      return ok({ deleted, lines: gone });
    }),
    http.get(`${API}/wishlists/:id/lines`, ({ params, request }) => {
      const list = find(params.id);
      if (!list) return failure(404, { error: 'Not Found' });
      const q = (new URL(request.url).searchParams.get('q') ?? '').toLowerCase();
      const items = state.lines.filter(
        (item) => item.list_id === list.id && item.name.toLowerCase().includes(q),
      );
      return HttpResponse.json({ success: true, data: { items }, meta: meta(items, list.id) });
    }),
    http.post(`${API}/wishlists/:id/lines/move`, async ({ params, request }) => {
      const list = find(params.id);
      const body = (await request.json()) as {
        line_ids: number[];
        to_list_id: number;
        mode: 'move' | 'copy';
      };
      const target = find(body.to_list_id);
      if (!list || !target) return failure(404, { error: 'Not Found' });
      if (target.id === list.id) return invalid('to_list_id');
      const moving = state.lines.filter((item) => body.line_ids.includes(item.id));
      const result = { moved: 0, merged: 0, skipped: 0 };
      const fresh = moving.filter(
        (item) =>
          !state.lines.some((other) => other.list_id === target.id && sameTarget(other, item)),
      );
      if (counted(target).line_count + fresh.length > MAX_LINES) {
        return conflict('wishlist_limit', 'A wishlist can hold at most 100 cards.', {
          scope: 'lines',
          max: MAX_LINES,
        });
      }
      for (const item of moving) {
        const existing = state.lines.find(
          (other) => other.list_id === target.id && sameTarget(other, item),
        );
        if (existing && existing.qty >= 99) result.skipped += 1;
        else if (existing) {
          existing.qty = Math.min(99, existing.qty + item.qty);
          result.merged += 1;
        } else {
          state.lines.push({ ...clone(item), id: nextLine++, list_id: target.id });
          result.moved += 1;
        }
      }
      if (body.mode === 'move') {
        state.lines = state.lines.filter((item) => !body.line_ids.includes(item.id));
      }
      return ok(result);
    }),
    http.post(`${API}/wishlists/:id/lines`, async ({ params, request }) => {
      const list = find(params.id);
      if (!list) return failure(404, { error: 'Not Found' });
      const body = (await request.json()) as {
        set_id?: string | null;
        card_id?: string | null;
        name?: string | null;
        foil?: WishFoil;
        qty?: number;
        max_price?: number | null;
        note?: string | null;
      };
      const printing = Boolean(body.set_id && body.card_id);
      const card: CardSummary | undefined = printing
        ? cardList.items.find(
            (item) => item.set_id === body.set_id && item.card_id === body.card_id,
          )
        : cardList.items.find((item) => item.name === body.name);
      if (!card) return invalid(printing ? 'card_id' : 'name');
      const foil = body.foil ?? 'any';
      if (foil === 'S' && !card.foilable) {
        return failure(400, {
          error: 'Bad Request',
          message: 'This card has no foil version.',
          code: 'foil_not_allowed',
        });
      }
      const target = {
        name: card.name,
        set_id: printing ? card.set_id : null,
        card_id: printing ? card.card_id : null,
        foil,
      };
      const qty = body.qty ?? 1;
      const existing = state.lines.find(
        (item) => item.list_id === list.id && sameTarget(item, target),
      );
      if (existing) {
        existing.qty = Math.min(99, existing.qty + qty);
        if (body.max_price != null) existing.max_price = body.max_price;
        if (body.note) existing.note = body.note;
        return ok({ line: existing, merged: true });
      }
      if (counted(list).line_count >= MAX_LINES) {
        return conflict('wishlist_limit', 'A wishlist can hold at most 100 cards.', {
          scope: 'lines',
          max: MAX_LINES,
        });
      }
      const price = card.price?.market ?? null;
      const created = line({
        id: nextLine++,
        list_id: list.id,
        ...target,
        card: miniOf(card),
        qty,
        max_price: body.max_price ?? null,
        note: body.note || null,
        market:
          price === null
            ? null
            : {
                value: price,
                source: card.price?.market_source ?? null,
                as_of: card.price?.as_of ?? null,
                set_id: card.set_id,
                card_id: card.card_id,
                foil: false,
              },
        reached: body.max_price == null ? null : price !== null && price <= body.max_price,
      });
      state.lines.push(created);
      return ok({ line: created, merged: false }, 201);
    }),
    http.patch(`${API}/wishlists/:id/lines/:lineId`, async ({ params, request }) => {
      const item = state.lines.find(
        (other) => String(other.id) === params.lineId && String(other.list_id) === params.id,
      );
      if (!item) return failure(404, { error: 'Not Found' });
      const body = (await request.json()) as Partial<WishlistLine>;
      Object.assign(item, body);
      if ('max_price' in body) {
        item.reached =
          item.max_price === null
            ? null
            : item.market !== null && item.market.value <= item.max_price;
      }
      return ok(item);
    }),
    http.delete(`${API}/wishlists/:id/lines/:lineId`, ({ params }) => {
      const item = state.lines.find(
        (other) => String(other.id) === params.lineId && String(other.list_id) === params.id,
      );
      if (!item) return failure(404, { error: 'Not Found' });
      state.lines = state.lines.filter((other) => other !== item);
      return ok({ deleted: item });
    }),
  );
  return state;
}

/** Every request to `/wishlists` (method, path without the API prefix, query, JSON body). */
export function recordWishlistRequests() {
  const sent: Sent[] = [];
  server.events.on('request:start', async ({ request }) => {
    const url = new URL(request.url);
    if (!url.pathname.startsWith(`${API}/wishlists`)) return;
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

/** `count` lists named `List 1..count` (the first is the default). */
export const manyLists = (count: number) =>
  Array.from({ length: count }, (_, index) =>
    wishlist({
      id: index + 1,
      name: `List ${index + 1}`,
      position: index + 1,
      is_default: index === 0,
    }),
  );

/**
 * A toast by its text. The live announcer speaks the same words, so a page-wide text query sees
 * two matches until the toast goes; this looks inside the toast stack only.
 */
export async function findToast(text: string) {
  const stack = await screen.findByRole('region', { name: 'Notifications' }, { timeout: 10000 });
  return within(stack).findByText(text, {}, { timeout: 10000 });
}
