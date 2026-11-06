import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';
import type { CardSummary, DeckCard, DeckContentV2, DeckDetail } from '@/api/types';
import { cardList, foilCommon as emberWisp } from '@/test/fixtures/cards';
import { recordDeckRequests, withDecks } from '@/test/decks';
import {
  calmRune,
  deckDetail,
  deckDetails,
  emptyContent,
  line,
  listItemOf,
  mainCards,
  rivenChampion,
  rivenContent,
  rivenDeck,
  rivenLegend,
} from '@/test/fixtures/decks';
import { signedIn, writes } from '@/test/locations';
import { API, ok } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';

const LONG = { timeout: 10000 };
const SAVE = { timeout: 5000 };
const PHONE = 390;

afterEach(() => {
  vi.restoreAllMocks();
  server.events.removeAllListeners();
});

/** A deck card as `GET /cards` lists it. */
const summaryOf = (card: DeckCard): CardSummary => ({
  ...emberWisp,
  set_id: card.set_id,
  card_id: card.card_id,
  key: card.key,
  name: card.name,
  domains: card.domains,
  type: card.type,
  supertype: card.supertype,
  type_raw: card.type,
  tags: card.tags,
  energy: card.energy,
  power: card.power,
  might: card.might,
  image_src: card.image_src,
  image_thumb_src: card.image_thumb_src,
});
/** Ember Wisp of the deck's domains (the fixture is Fury, outside The Exile's Calm and Chaos). */
const wisp: CardSummary = { ...emberWisp, domains: ['Chaos'] };
const furyBolt: CardSummary = {
  ...emberWisp,
  card_id: '70',
  key: 'OGN-70',
  name: 'Fury Bolt',
  domains: ['Fury'],
};
const CATALOG = [
  summaryOf(rivenLegend),
  summaryOf(rivenChampion),
  summaryOf(calmRune),
  summaryOf(mainCards[0]),
  wisp,
  furyBolt,
];

/** `GET /cards` answers the catalog cards of the asked types (and `q`); the queries are kept. */
function cardServer() {
  const seen: URLSearchParams[] = [];
  server.use(
    http.get(`${API}/cards`, ({ request }) => {
      const search = new URL(request.url).searchParams;
      // Auto runes asks for the base runes on its own (`base_only`): not the browser
      if (search.get('base_only') === null) seen.push(search);
      const types = search.getAll('type');
      const supertypes = search.getAll('supertype');
      const q = (search.get('q') ?? '').toLowerCase();
      const found = CATALOG.filter(
        (card) =>
          (types.length === 0 || types.includes(card.type)) &&
          (supertypes.length === 0 || supertypes.includes(card.supertype ?? '')) &&
          card.name.toLowerCase().includes(q),
      );
      return HttpResponse.json({
        success: true,
        data: { items: found },
        meta: { ...cardList.meta, page: 1, per_page: 48, total: found.length, pages: 1 },
      });
    }),
  );
  return seen;
}

function savingServer(details: DeckDetail[]) {
  server.use(
    http.put(`${API}/decks/:id/content`, async ({ params, request }) => {
      const { content } = (await request.json()) as { content: DeckContentV2 };
      const head = details.find((deck) => String(deck.id) === params.id) ?? rivenDeck;
      return ok({ ...deckDetail(head, content), current_seq: head.current_seq });
    }),
  );
}

async function openDeck(deck: DeckDetail = rivenDeck, width = PHONE) {
  signedIn();
  const details = [...deckDetails.filter((d) => d.id !== deck.id), deck];
  withDecks(details.map(listItemOf), details);
  savingServer(details);
  const seen = cardServer();
  const sent = recordDeckRequests();
  const app = await renderApp({ path: `/decks/${deck.id}`, width });
  await screen.findByRole('heading', { level: 1 }, LONG);
  // the rule values come from /meta/game: editing waits for them
  await waitFor(
    () => expect(screen.getByRole('button', { name: 'Remove a copy of Discipline' })).toBeEnabled(),
    LONG,
  );
  return { ...app, seen, sent };
}

const section = (name: RegExp) =>
  screen.getByText(name, { selector: 'summary *' }).closest('details') as HTMLElement;
const rowOf = (details: HTMLElement, name: string) =>
  within(details)
    .queryAllByRole('listitem')
    .find((row) => row.querySelector('[data-slot="name"]')?.textContent === name);
const qtyOf = (row: HTMLElement | undefined) =>
  row?.querySelector('[data-slot="qty"]')?.textContent?.replace('×', '');
const last = (seen: URLSearchParams[]) => seen.at(-1) as URLSearchParams;
const filtersOf = (search: URLSearchParams) => ({
  type: search.getAll('type'),
  supertype: search.getAll('supertype'),
  exclude_supertype: search.getAll('exclude_supertype'),
  tag: search.getAll('tag'),
  domain: search.getAll('domain').sort(),
  domain_match: search.get('domain_match'),
});
const puts = (sent: ReturnType<typeof recordDeckRequests>, id = 41) =>
  writes(sent).filter((r) => r.method === 'PUT' && r.path === `/decks/${id}/content`);

/** Opens the sheet of a section and waits for its first tiles. */
async function openSheet(label: string, title: string) {
  await userEvent.click(screen.getByRole('button', { name: label }));
  const sheet = await screen.findByRole('dialog', { name: title });
  await within(sheet).findByText(/cards? for /, {}, LONG);
  return sheet;
}

/** A deck with a legend and an empty champion slot. */
const noChampion = deckDetail(
  { id: 46, name: 'No champion yet', updated_at: '2026-11-05T10:00:00Z' },
  { ...rivenContent, champion: null },
);
/** A deck with nothing but two copies of Discipline. */
const almostEmpty = deckDetail(
  { id: 47, name: 'Almost empty', updated_at: '2026-11-05T10:00:00Z' },
  { ...emptyContent, main: [line(mainCards[0], 2)] },
);

describe('Card browser sheet at 390 px (F5-i decision 4)', () => {
  it('each editable section has an Add cards button; a full slot has none', async () => {
    await openDeck();
    // the sections no longer have their own search
    expect(screen.queryAllByRole('combobox')).toEqual([]);
    const button = (name: RegExp) =>
      within(section(name)).queryByRole('button', { name: /^Add cards/ });
    expect(button(/^Main deck$/)).toHaveAccessibleName('Add cards to the main deck');
    expect(button(/^Main deck$/)).toHaveTextContent('Add cards');
    expect(button(/^Battlefields$/)).toHaveAccessibleName('Add cards to the battlefields');
    expect(button(/^Runes$/)).toHaveAccessibleName('Add cards to the runes');
    expect(button(/^Sideboard$/)).toHaveAccessibleName('Add cards to the sideboard');
    // the legend and the champion are chosen: the slot is full, as before
    expect(button(/^Legend$/)).toBeNull();
    expect(button(/^Champion$/)).toBeNull();
    // Auto runes stays
    expect(within(section(/^Runes$/)).getByRole('button', { name: 'Auto runes' })).toBeVisible();
    // the browser is not on the page until a sheet opens
    expect(screen.queryByRole('region', { name: 'Card browser' })).toBeNull();
    expect(screen.queryByRole('dialog')).toBeNull();
  }, 20000);

  it('empty slots offer the button too', async () => {
    await openDeck(almostEmpty);
    expect(
      within(section(/^Legend$/)).getByRole('button', { name: 'Add cards to the legend slot' }),
    ).toBeVisible();
    expect(
      within(section(/^Champion$/)).getByRole('button', {
        name: 'Add cards to the champion slot',
      }),
    ).toBeVisible();
  }, 20000);

  it('opens the browser for that zone only, with its filters and no zone tabs', async () => {
    const { seen } = await openDeck();
    const sheet = await openSheet('Add cards to the main deck', 'Add to Main deck');
    expect(within(sheet).queryByRole('tablist')).toBeNull();
    expect(within(sheet).queryByRole('tab')).toBeNull();
    expect(within(sheet).getByText('4 cards for Main deck')).toBeVisible();
    expect(within(sheet).getByRole('searchbox', { name: 'Search Main deck cards' })).toBeVisible();
    expect(within(sheet).getByRole('button', { name: /^Filter/ })).toBeVisible();
    expect(within(sheet).getByRole('list', { name: 'Cards for Main deck' })).toBeVisible();
    // the legend identity still applies
    expect(filtersOf(last(seen))).toEqual({
      type: ['Unit', 'Spell', 'Gear'],
      supertype: [],
      exclude_supertype: ['Token'],
      tag: [],
      domain: ['Calm', 'Chaos', 'Colorless'],
      domain_match: 'subset',
    });
    await userEvent.click(within(sheet).getByRole('button', { name: 'Done' }));
    expect(screen.queryByRole('dialog')).toBeNull();

    const runes = await openSheet('Add cards to the runes', 'Add to Runes');
    expect(within(runes).getByRole('button', { name: 'Add Calm Rune' })).toBeVisible();
    expect(filtersOf(last(seen))).toMatchObject({
      type: ['Rune'],
      domain: ['Calm', 'Chaos'],
      domain_match: null,
    });
  }, 30000);

  it('a search inside the sheet is sent as q with the zone filters', async () => {
    const { seen } = await openDeck();
    const sheet = await openSheet('Add cards to the sideboard', 'Add to Sideboard');
    await userEvent.type(
      within(sheet).getByRole('searchbox', { name: 'Search Sideboard cards' }),
      'Ember',
    );
    await waitFor(() => expect(last(seen).get('q')).toBe('Ember'), LONG);
    expect(filtersOf(last(seen))).toMatchObject({
      domain: ['Calm', 'Chaos', 'Colorless'],
      domain_match: 'subset',
    });
    await within(sheet).findByText('1 card for Sideboard', {}, LONG);
  }, 30000);

  it('adding keeps the sheet open, counts the copies and fills the section behind', async () => {
    const { sent } = await openDeck();
    const sheet = await openSheet('Add cards to the sideboard', 'Add to Sideboard');
    const tile = within(sheet).getByRole('button', { name: 'Add Ember Wisp' });
    expect(tile.querySelector('[data-slot="copies"]')).toBeNull();
    await userEvent.click(tile);
    await userEvent.click(tile);
    expect(screen.getByRole('dialog', { name: 'Add to Sideboard' })).toBeVisible();
    expect(tile.querySelector('[data-slot="copies"]')).toHaveTextContent('×2');
    const side = section(/^Sideboard$/);
    expect(qtyOf(rowOf(side, 'Ember Wisp'))).toBe('2');
    expect(within(side).getByText('10/10')).toBeInTheDocument();
    await waitFor(() => expect(puts(sent).length).toBeGreaterThan(0), SAVE);
    const body = puts(sent).at(-1)?.body as { content: DeckContentV2 };
    expect(body.content.sideboard.at(-1)).toEqual({ set: 'OGN', id: '12', qty: 2 });
  }, 30000);

  it('a tile the legend does not allow is disabled with the reason and adds nothing', async () => {
    await openDeck();
    const sheet = await openSheet('Add cards to the main deck', 'Add to Main deck');
    const tile = within(sheet).getByRole('button', { name: 'Add Fury Bolt' });
    expect(tile).toHaveAttribute('aria-disabled', 'true');
    expect(tile).toHaveAccessibleDescription("This card is outside the legend's domains.");
    await userEvent.click(tile);
    expect(rowOf(section(/^Main deck$/), 'Fury Bolt')).toBeUndefined();
    expect(screen.getByRole('dialog', { name: 'Add to Main deck' })).toBeVisible();
  }, 30000);

  it('choosing a legend fills the slot and closes the sheet', async () => {
    await openDeck(almostEmpty);
    const sheet = await openSheet('Add cards to the legend slot', 'Add to Legend');
    await userEvent.click(within(sheet).getByRole('button', { name: 'Choose The Exile' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    const legend = section(/^Legend$/);
    expect(rowOf(legend, 'Riven, The Exile')).toBeDefined();
    // the slot is full: no button, and focus stays in the section
    expect(within(legend).queryByRole('button', { name: /^Add cards/ })).toBeNull();
    expect(legend).toContainElement(document.activeElement as HTMLElement);
  }, 30000);

  it('choosing a champion fills the slot and closes the sheet', async () => {
    await openDeck(noChampion);
    const sheet = await openSheet('Add cards to the champion slot', 'Add to Champion');
    expect(within(sheet).getByText('1 card for Champion')).toBeVisible();
    await userEvent.click(
      within(sheet).getByRole('button', { name: 'Choose Riven, Broken Blade' }),
    );
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(rowOf(section(/^Champion$/), 'Riven, Broken Blade')).toBeDefined();
  }, 30000);

  it('Done and Escape close the sheet and focus goes back to Add cards', async () => {
    await openDeck();
    const opener = screen.getByRole('button', { name: 'Add cards to the battlefields' });
    let sheet = await openSheet('Add cards to the battlefields', 'Add to Battlefields');
    await userEvent.click(within(sheet).getByRole('button', { name: 'Done' }));
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(opener).toHaveFocus();

    sheet = await openSheet('Add cards to the battlefields', 'Add to Battlefields');
    within(sheet).getByRole('searchbox').focus();
    await userEvent.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(opener).toHaveFocus();
  }, 30000);

  it('the filters open inline in the sheet and narrow the query', async () => {
    const { seen } = await openDeck();
    const sheet = await openSheet('Add cards to the main deck', 'Add to Main deck');
    const toggle = within(sheet).getByRole('button', { name: 'Filter' });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(within(sheet).queryByRole('group', { name: 'Filter cards' })).toBeNull();
    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    const panel = within(sheet).getByRole('group', { name: 'Filter cards' });
    // not a popover: no dialog inside the sheet
    expect(within(sheet).queryByRole('dialog')).toBeNull();
    await userEvent.click(
      within(within(panel).getByRole('group', { name: 'Rarity' })).getByRole('button', {
        name: /^Rare/,
      }),
    );
    await waitFor(() => expect(last(seen).getAll('rarity')).toEqual(['Rare']));
    expect(filtersOf(last(seen)).domain).toEqual(['Calm', 'Chaos', 'Colorless']);
    expect(within(sheet).getByRole('button', { name: 'Filter, 1 active' })).toBeVisible();
    expect(
      within(within(sheet).getByRole('list', { name: 'Active filters' })).getByText('Rare'),
    ).toBeVisible();
    // the sheet is still open
    expect(screen.getByRole('dialog', { name: 'Add to Main deck' })).toBeVisible();
  }, 30000);

  it('offline there is no Add cards button', async () => {
    signedIn();
    withDecks();
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    await renderApp({ path: '/decks/41', width: PHONE });
    await screen.findByRole('heading', { level: 1 }, LONG);
    expect(screen.getByText('Offline: editing is disabled.')).toBeVisible();
    expect(screen.queryAllByRole('button', { name: /^Add cards/ })).toEqual([]);
  }, 20000);

  it('a deck with cards missing from the catalog has no Add cards button', async () => {
    signedIn();
    withDecks();
    await renderApp({ path: '/decks/43', width: PHONE });
    await screen.findByRole('region', { name: 'Cards not in the catalog' }, LONG);
    expect(screen.queryAllByRole('button', { name: /^Add cards/ })).toEqual([]);
  }, 20000);

  it('is axe clean with the sheet open and the filters shown', async () => {
    await openDeck();
    const sheet = await openSheet('Add cards to the main deck', 'Add to Main deck');
    await userEvent.click(within(sheet).getByRole('button', { name: 'Filter' }));
    expect(await axe(sheet)).toHaveNoViolations();
  }, 30000);
});

describe('Card browser at 1280 px (unchanged)', () => {
  it('has no Add cards buttons: the browser pane fills the deck', async () => {
    await openDeck(rivenDeck, 1280);
    expect(await screen.findByRole('region', { name: 'Card browser' }, LONG)).toBeVisible();
    expect(screen.queryAllByRole('button', { name: /^Add cards/ })).toEqual([]);
    expect(screen.queryByRole('dialog')).toBeNull();
  }, 20000);
});
