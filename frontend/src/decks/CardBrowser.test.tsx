import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import type { QueryClient } from '@tanstack/react-query';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';
import type { CardFacets, CardSummary, DeckCard, DeckContentV2 } from '@/api/types';
import { cardList, champion as ayla, foilCommon as emberWisp } from '@/test/fixtures/cards';
import { recordDeckRequests, withDecks } from '@/test/decks';
import {
  deckDetail,
  deckDetails,
  emptyContent,
  line,
  listItemOf,
  mainCards,
  rivenDeck,
} from '@/test/fixtures/decks';
import { signedIn, writes } from '@/test/locations';
import { API, failure, ok } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';

const LONG = { timeout: 10000 };
const SAVE = { timeout: 5000 };
const DESKTOP = 1280;

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
const discipline = summaryOf(mainCards[0]);
/** Ember Wisp of the deck's domains (the fixture is Fury, outside The Exile's Calm and Chaos). */
const wisp: CardSummary = { ...emberWisp, domains: ['Chaos'] };
const ITEMS = [discipline, wisp, ayla];

/** A card of the list fixture under another printing. */
const extra = (id: string, overrides: Partial<CardSummary>): CardSummary => ({
  ...emberWisp,
  card_id: id,
  key: `OGN-${id}`,
  ...overrides,
});
const furyBolt = extra('70', { name: 'Fury Bolt', domains: ['Fury'] });
const relic = extra('71', { name: 'Plain Relic', type: 'Gear', domains: ['Colorless'] });
const yasuoSignature = extra('72', {
  name: 'Wind Wall',
  supertype: 'Signature',
  domains: ['Chaos'],
  tags: ['Yasuo'],
});
const rivenSignature = extra('73', {
  name: 'Exile Blade',
  supertype: 'Signature',
  domains: ['Chaos'],
  tags: ['Riven'],
});

/** `GET /cards` answers `items` (filtered by `q`) in `pages` pages; the browser's queries are kept. */
function cardServer({
  items = ITEMS,
  pages = 1,
  facets = cardList.meta.facets,
}: { items?: CardSummary[]; pages?: number; facets?: CardFacets } = {}) {
  const seen: URLSearchParams[] = [];
  server.use(
    http.get(`${API}/cards`, ({ request }) => {
      const search = new URL(request.url).searchParams;
      // Auto runes asks for the base runes on its own (`base_only`): not the browser
      if (search.get('base_only') === null) seen.push(search);
      const q = (search.get('q') ?? '').toLowerCase();
      const found = items.filter((card) => card.name.toLowerCase().includes(q));
      const page = Number(search.get('page') ?? 1);
      return HttpResponse.json({
        success: true,
        data: { items: found },
        meta: { ...cardList.meta, page, per_page: 48, total: found.length, pages, facets },
      });
    }),
  );
  return seen;
}

/** The deck save answers the detail of what it got. */
function savingServer() {
  server.use(
    http.put(`${API}/decks/:id/content`, async ({ request }) => {
      const { content } = (await request.json()) as { content: DeckContentV2 };
      return ok({ ...deckDetail(rivenDeck, content), current_seq: rivenDeck.current_seq });
    }),
  );
}

async function openBrowser({
  deck = rivenDeck,
  ...options
}: Parameters<typeof cardServer>[0] & { deck?: typeof rivenDeck } = {}) {
  signedIn();
  const details = [...deckDetails.filter((d) => d.id !== deck.id), deck];
  withDecks(details.map(listItemOf), details);
  savingServer();
  const seen = cardServer(options);
  const sent = recordDeckRequests();
  const app = await renderApp({ path: `/decks/${deck.id}`, width: DESKTOP });
  const browser = await screen.findByRole('region', { name: 'Card browser' }, LONG);
  await within(browser).findByRole('button', { name: 'Add Ember Wisp' }, LONG);
  return { ...app, browser, seen, sent };
}

const last = (seen: URLSearchParams[]) => seen.at(-1) as URLSearchParams;
const filtersOf = (search: URLSearchParams) => ({
  type: search.getAll('type'),
  supertype: search.getAll('supertype'),
  exclude_supertype: search.getAll('exclude_supertype'),
  tag: search.getAll('tag'),
  domain: search.getAll('domain').sort(),
  domain_match: search.get('domain_match'),
});
const section = (name: RegExp) =>
  screen.getByText(name, { selector: 'summary *' }).closest('details') as HTMLElement;
const rowOf = (details: HTMLElement, name: string) =>
  within(details)
    .queryAllByRole('listitem')
    .find((row) => row.querySelector('[data-slot="name"]')?.textContent === name);
const puts = (sent: ReturnType<typeof recordDeckRequests>) =>
  writes(sent).filter((r) => r.method === 'PUT' && r.path === '/decks/41/content');
/** Every card id the autosaves sent in `zone`. */
const sentIds = (sent: ReturnType<typeof recordDeckRequests>, zone: 'main' | 'sideboard') =>
  puts(sent).flatMap((r) => (r.body as { content: DeckContentV2 }).content[zone].map((l) => l.id));

describe('Card browser of the two-pane editor (F5-i step 2)', () => {
  it('opens on the main deck; each tab asks for the cards of its zone', async () => {
    const { browser, seen } = await openBrowser();
    const tabs = within(browser).getAllByRole('tab');
    expect(tabs.map((tab) => tab.textContent)).toEqual([
      'Legend',
      'Champion',
      'Main deck',
      'Battlefields',
      'Sideboard',
      'Runes',
    ]);
    expect(within(browser).getByRole('tab', { name: 'Main deck' })).toHaveAttribute(
      'aria-selected',
      'true',
    );
    expect(within(browser).getByText('3 cards for Main deck')).toBeVisible();
    expect(filtersOf(last(seen))).toEqual({
      type: ['Unit', 'Spell', 'Gear'],
      supertype: [],
      exclude_supertype: ['Token'],
      tag: [],
      // the deck has a legend: only cards of its domains (or colourless) are listed
      domain: ['Calm', 'Chaos', 'Colorless'],
      domain_match: 'subset',
    });
    expect(last(seen).get('sort')).toBe('name');
    expect(last(seen).get('q')).toBeNull();

    const choose = async (name: string) => {
      await userEvent.click(within(browser).getByRole('tab', { name }));
      expect(within(browser).getByRole('tab', { name })).toHaveAttribute('aria-selected', 'true');
      await within(browser).findByText(`3 cards for ${name}`, {}, LONG);
      return filtersOf(last(seen));
    };
    expect(await choose('Champion')).toMatchObject({
      type: ['Unit'],
      supertype: ['Champion'],
      tag: ['Riven'],
      domain: ['Calm', 'Chaos', 'Colorless'],
      domain_match: 'subset',
    });
    expect(within(browser).getByRole('button', { name: 'Choose Ember Wisp' })).toBeVisible();
    expect(await choose('Runes')).toMatchObject({
      type: ['Rune'],
      domain: ['Calm', 'Chaos'],
      domain_match: null,
    });
    expect(await choose('Battlefields')).toMatchObject({ type: ['Battlefield'], tag: [] });
    // the sideboard takes what the main deck takes: the same query, served from the cache
    const asked = seen.length;
    await choose('Sideboard');
    expect(seen).toHaveLength(asked);
    expect(within(browser).getByRole('button', { name: 'Add Ember Wisp' })).toBeVisible();
    expect(await choose('Legend')).toMatchObject({ type: ['Legend'] });
    expect(within(browser).getByRole('button', { name: 'Choose Discipline' })).toBeVisible();

    // arrows move between the tabs
    within(browser).getByRole('tab', { name: 'Legend' }).focus();
    await userEvent.keyboard('{ArrowRight}');
    const champion = within(browser).getByRole('tab', { name: 'Champion' });
    expect(champion).toHaveAttribute('aria-selected', 'true');
    expect(champion).toHaveFocus();
    await userEvent.keyboard('{End}');
    expect(within(browser).getByRole('tab', { name: 'Runes' })).toHaveFocus();
  }, 30000);

  it('sends the search as q once the typing stops', async () => {
    const { browser, seen } = await openBrowser();
    const search = within(browser).getByRole('searchbox', { name: 'Search Main deck cards' });
    await userEvent.type(search, 'Emb');
    await waitFor(() => expect(last(seen).get('q')).toBe('Emb'), LONG);
    expect(seen.map((s) => s.get('q')).filter(Boolean)).toEqual(['Emb']);
    await within(browser).findByText('1 card for Main deck', {}, LONG);
    expect(within(browser).queryByRole('button', { name: 'Add Discipline' })).toBeNull();

    await userEvent.clear(search);
    await userEvent.type(search, 'zzz');
    expect(await within(browser).findByText('No cards match.', {}, LONG)).toBeVisible();
  }, 30000);

  it('a tile adds a copy to the zone of its tab and the deck autosaves', async () => {
    const { browser, sent } = await openBrowser();
    await userEvent.click(within(browser).getByRole('tab', { name: 'Sideboard' }));
    await within(browser).findByText('3 cards for Sideboard', {}, LONG);
    const tile = within(browser).getByRole('button', { name: 'Add Ember Wisp' });
    expect(tile.querySelector('[data-slot="copies"]')).toBeNull();
    await userEvent.click(tile);
    const side = section(/^Sideboard$/);
    expect(rowOf(side, 'Ember Wisp')).toBeDefined();
    expect(within(side).getByText('9/10')).toBeVisible();
    expect(tile.querySelector('[data-slot="copies"]')).toHaveTextContent('×1');
    await waitFor(() => expect(puts(sent).length).toBeGreaterThan(0), SAVE);
    const body = puts(sent).at(-1)?.body as { content: DeckContentV2 };
    expect(body.content.sideboard.at(-1)).toEqual({ set: 'OGN', id: '12', qty: 1 });
    expect(body.content.main).toEqual(rivenDeck.content.main);
  }, 30000);

  it('shows energy and might, and the copies already in the deck', async () => {
    const { browser } = await openBrowser();
    const tile = within(browser).getByRole('button', { name: /^Add Ayla/ });
    expect(tile.querySelector('[data-slot="energy"]')).toHaveTextContent('3');
    expect(tile.querySelector('[data-slot="might"]')).toHaveTextContent('1');
    const wisp = within(browser).getByRole('button', { name: 'Add Ember Wisp' });
    expect(wisp.querySelector('[data-slot="energy"]')).toBeNull();
    expect(wisp.querySelector('[data-slot="might"]')).toBeNull();
    const copies = within(browser)
      .getByRole('button', { name: 'Add Discipline' })
      .querySelector('[data-slot="copies"]');
    expect(copies).toHaveTextContent('×3');
  }, 30000);

  it('a tile the rules refuse says why and adds nothing', async () => {
    const { browser, sent } = await openBrowser();
    const tile = within(browser).getByRole('button', { name: 'Add Discipline' });
    expect(tile).toHaveAttribute('aria-disabled', 'true');
    expect(tile).toHaveAttribute('title', 'Discipline has 4 copies (max 3).');
    expect(tile).toHaveAccessibleDescription('Discipline has 4 copies (max 3).');
    await userEvent.click(tile);
    const main = section(/^Main deck$/);
    expect(within(main).getByText('39/39')).toBeVisible();
    await new Promise((resolve) => setTimeout(resolve, 1300));
    expect(puts(sent)).toEqual([]);
    // a card the rules allow is not marked
    expect(within(browser).getByRole('button', { name: 'Add Ember Wisp' })).not.toHaveAttribute(
      'aria-disabled',
    );
  }, 30000);

  it('a card outside the legend domains is refused; a colourless one is added', async () => {
    const { browser, sent } = await openBrowser({ items: [...ITEMS, furyBolt, relic] });
    const reason = "This card is outside the legend's domains.";
    const bolt = within(browser).getByRole('button', { name: 'Add Fury Bolt' });
    expect(bolt).toHaveAttribute('aria-disabled', 'true');
    expect(bolt).toHaveAttribute('title', reason);
    expect(bolt).toHaveAccessibleDescription(reason);
    await userEvent.click(bolt);
    expect(rowOf(section(/^Main deck$/), 'Fury Bolt')).toBeUndefined();

    const plain = within(browser).getByRole('button', { name: 'Add Plain Relic' });
    expect(plain).not.toHaveAttribute('aria-disabled');
    await userEvent.click(plain);
    expect(rowOf(section(/^Main deck$/), 'Plain Relic')).toBeDefined();
    await waitFor(() => expect(puts(sent).length).toBeGreaterThan(0), SAVE);
    const body = puts(sent).at(-1)?.body as { content: DeckContentV2 };
    expect(sentIds(sent, 'main')).not.toContain('70');
    expect(body.content.main.at(-1)).toEqual({ set: 'OGN', id: '71', qty: 1 });
  }, 30000);

  it('a signature card needs a tag shared with the legend', async () => {
    const { browser, sent } = await openBrowser({
      items: [...ITEMS, yasuoSignature, rivenSignature],
    });
    const reason = 'Signature cards need a tag shared with the legend.';
    const foreign = within(browser).getByRole('button', { name: 'Add Wind Wall' });
    expect(foreign).toHaveAttribute('aria-disabled', 'true');
    expect(foreign).toHaveAttribute('title', reason);
    expect(foreign).toHaveAccessibleDescription(reason);
    await userEvent.click(foreign);
    expect(rowOf(section(/^Main deck$/), 'Wind Wall')).toBeUndefined();
    await new Promise((resolve) => setTimeout(resolve, 1300));
    // (the previous test may still flush its own save on unmount)
    expect(sentIds(sent, 'main')).not.toContain('72');

    // the sideboard refuses it the same way
    await userEvent.click(within(browser).getByRole('tab', { name: 'Sideboard' }));
    await within(browser).findByText('5 cards for Sideboard', {}, LONG);
    expect(within(browser).getByRole('button', { name: 'Add Wind Wall' })).toHaveAttribute(
      'title',
      reason,
    );

    await userEvent.click(within(browser).getByRole('tab', { name: 'Main deck' }));
    const own = await within(browser).findByRole('button', { name: 'Add Exile Blade' }, LONG);
    expect(own).not.toHaveAttribute('aria-disabled');
    await userEvent.click(own);
    expect(rowOf(section(/^Main deck$/), 'Exile Blade')).toBeDefined();
    await waitFor(() => expect(sentIds(sent, 'main')).toContain('73'), SAVE);
  }, 30000);

  it('pages the results; a new tab or search goes back to page 1', async () => {
    const { browser, seen } = await openBrowser({ pages: 2 });
    const pages = within(browser).getByRole('navigation', { name: 'Pagination' });
    expect(within(pages).getByText('Page 1 of 2')).toBeVisible();
    expect(within(pages).getByRole('button', { name: 'Previous' })).toBeDisabled();
    await userEvent.click(within(pages).getByRole('button', { name: 'Next' }));
    await within(browser).findByText('Page 2 of 2', {}, LONG);
    expect(last(seen).get('page')).toBe('2');
    expect(within(pages).getByRole('button', { name: 'Next' })).toBeDisabled();

    await userEvent.click(within(browser).getByRole('tab', { name: 'Battlefields' }));
    await waitFor(() => expect(last(seen).getAll('type')).toEqual(['Battlefield']), LONG);
    expect(last(seen).get('page')).toBeNull();
    expect(await within(browser).findByText('Page 1 of 2', {}, LONG)).toBeVisible();

    await userEvent.click(within(browser).getByRole('button', { name: 'Next' }));
    await waitFor(() => expect(last(seen).get('page')).toBe('2'), LONG);
    await userEvent.type(
      within(browser).getByRole('searchbox', { name: 'Search Battlefields cards' }),
      'Emb',
    );
    await waitFor(() => expect(last(seen).get('q')).toBe('Emb'), LONG);
    expect(last(seen).get('page')).toBeNull();
  }, 30000);

  it('a failed search offers a retry', async () => {
    signedIn();
    withDecks(deckDetails.map(listItemOf), deckDetails);
    let fail = true;
    server.use(
      http.get(`${API}/cards`, () =>
        fail
          ? failure(500, { error: 'Internal Server Error' })
          : HttpResponse.json({
              success: true,
              data: { items: ITEMS },
              meta: { ...cardList.meta, total: ITEMS.length, pages: 1 },
            }),
      ),
    );
    await renderApp({ path: '/decks/41', width: DESKTOP });
    const browser = await screen.findByRole('region', { name: 'Card browser' }, LONG);
    const alert = await within(browser).findByRole('alert', {}, LONG);
    expect(alert).toHaveTextContent('The cards could not be loaded.');
    fail = false;
    await userEvent.click(within(alert).getByRole('button', { name: 'Retry' }));
    expect(
      await within(browser).findByRole('button', { name: 'Add Ember Wisp' }, LONG),
    ).toBeVisible();
  }, 30000);

  it('is axe clean', async () => {
    const { browser } = await openBrowser();
    expect(await axe(browser)).toHaveNoViolations();
  }, 30000);
});

/** Facets of the browser's answer (disjunctive, like the catalog). */
const FACETS: CardFacets = {
  set: { OGN: 8 },
  domain: { Fury: 6, Calm: 4, Chaos: 2, Colorless: 1 },
  type: { Unit: 5, Spell: 2, Gear: 1 },
  rarity: { Common: 3, Rare: 2 },
  tag: [
    { tag: 'Riven', count: 2 },
    { tag: 'Yasuo', count: 1 },
  ],
};
/** A deck without a legend (and nothing outside the catalog, so it can be edited). */
const noLegendDeck = deckDetail(
  { id: 44, name: 'No legend yet', updated_at: '2026-11-05T10:00:00Z' },
  { ...emptyContent, main: [line(mainCards[0], 2)] },
);

const filterButton = (browser: HTMLElement) =>
  within(browser).getByRole('button', { name: /^Filter/ });
async function openFilters(browser: HTMLElement) {
  await userEvent.click(filterButton(browser));
  return within(browser).getByRole('dialog', { name: 'Filter cards' });
}
const group = (panel: HTMLElement, name: string) => within(panel).getByRole('group', { name });
const names = (scope: HTMLElement) =>
  within(scope)
    .getAllByRole('button')
    .map((button) => button.getAttribute('aria-label') ?? button.textContent);
/** The filters of the browser's query on screen (an answer from the cache sends no request). */
const shown = (queryClient: QueryClient) => {
  const active = queryClient
    .getQueryCache()
    .findAll({ queryKey: ['cards', 'list'], type: 'active' })
    .map((query) => new URLSearchParams(String(query.queryKey[2])))
    // Auto runes keeps its own query (`base_only`): not the browser
    .filter((search) => search.get('base_only') === null);
  expect(active).toHaveLength(1);
  return active[0];
};
const press = (panel: HTMLElement, groupName: string, value: string) =>
  userEvent.click(within(group(panel, groupName)).getByRole('button', { name: value }));

describe('Filter popover of the card browser (F5-i step 3)', () => {
  it('opens the groups of the zone; Escape closes it and focus goes back', async () => {
    const { browser } = await openBrowser({ facets: FACETS });
    const button = filterButton(browser);
    expect(button).toHaveAccessibleName('Filter');
    expect(button).toHaveAttribute('aria-expanded', 'false');
    const panel = await openFilters(browser);
    expect(panel).toContainElement(document.activeElement as HTMLElement);
    expect(
      within(panel)
        .getAllByRole('heading')
        .map((h) => h.textContent),
    ).toEqual(['Filter cards', 'Card', 'Cost & Might', 'Advanced', 'Status']);
    // the legend's domains (and colourless): the API counts do not match a subset, so none shown
    expect(names(group(panel, 'Domain'))).toEqual(['Calm', 'Chaos', 'Colorless']);
    // only the types the main deck takes, with their counts
    expect(names(group(panel, 'Type'))).toEqual(['Unit (5)', 'Spell (2)', 'Gear (1)']);
    expect(names(group(panel, 'Rarity'))).toEqual([
      'Common (3)',
      'Uncommon (0)',
      'Rare (2)',
      'Epic (0)',
      'Showcase (0)',
    ]);
    expect(names(group(panel, 'Energy'))).toEqual(['0', '1', '2', '3', '4', '5', '6', '7+']);
    expect(names(group(panel, 'Power'))).toEqual(['0', '1', '2', '3+']);
    expect(names(group(panel, 'Might'))).toEqual(['0', '1', '2', '3', '4', '5', '6', '7+']);
    expect(names(group(panel, 'Set'))).toEqual(['Origins (8)']);
    expect(names(group(panel, 'Tags'))).toEqual(['Riven (2)', 'Yasuo (1)']);
    expect(within(panel).getByRole('switch', { name: 'Owned only' })).not.toBeChecked();
    // no control the API cannot serve yet
    expect(within(panel).queryByText(/keyword|abilit|legal only|available/i)).toBeNull();

    await userEvent.keyboard('{Escape}');
    expect(within(browser).queryByRole('dialog')).toBeNull();
    expect(button).toHaveFocus();
    expect(button).toHaveAttribute('aria-expanded', 'false');
  }, 30000);

  it('each group sends its parameters over the zone filters', async () => {
    const { browser, seen } = await openBrowser({ facets: FACETS });
    const panel = await openFilters(browser);
    const sent = async (key: string, values: string[]) =>
      waitFor(() => expect(last(seen).getAll(key)).toEqual(values), LONG);

    await press(panel, 'Domain', 'Calm');
    await sent('domain', ['Calm']);
    expect(last(seen).get('domain_match')).toBe('subset');
    await press(panel, 'Type', 'Unit (5)');
    await sent('type', ['Unit']);
    expect(last(seen).getAll('exclude_supertype')).toEqual(['Token']);
    await press(panel, 'Rarity', 'Rare (2)');
    await sent('rarity', ['Rare']);
    await press(panel, 'Energy', '3');
    await sent('energy_min', ['3']);
    expect(last(seen).get('energy_max')).toBe('3');
    await press(panel, 'Energy', '7+');
    await sent('energy_min', ['7']);
    expect(last(seen).get('energy_max')).toBeNull();
    await press(panel, 'Power', '3+');
    await sent('power_min', ['3']);
    expect(last(seen).get('power_max')).toBeNull();
    await press(panel, 'Might', '2');
    await sent('might_max', ['2']);
    await press(panel, 'Set', 'Origins (8)');
    await sent('set', ['OGN']);
    await press(panel, 'Tags', 'Yasuo (1)');
    await sent('tag', ['Yasuo']);
    await userEvent.click(within(panel).getByRole('switch', { name: 'Owned only' }));
    await sent('owned', ['owned']);
    expect(filterButton(browser)).toHaveAccessibleName('Filter, 9 active');
    expect(within(group(panel, 'Energy')).getByRole('button', { name: '7+' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );

    // a pressed value lets go
    await press(panel, 'Energy', '7+');
    await waitFor(() => expect(last(seen).get('energy_min')).toBeNull(), LONG);
    expect(filterButton(browser)).toHaveAccessibleName('Filter, 8 active');
  }, 30000);

  it('a deck without a legend offers every domain, with its count', async () => {
    const { browser, seen } = await openBrowser({ facets: FACETS, deck: noLegendDeck });
    const panel = await openFilters(browser);
    expect(names(group(panel, 'Domain'))).toEqual([
      'Fury (6)',
      'Calm (4)',
      'Mind (0)',
      'Body (0)',
      'Chaos (2)',
      'Order (0)',
      'Colorless (1)',
    ]);
    await press(panel, 'Domain', 'Fury (6)');
    await waitFor(() => expect(last(seen).getAll('domain')).toEqual(['Fury']), LONG);
    expect(last(seen).get('domain_match')).toBeNull();
  }, 30000);

  it('shows the filters as chips; a chip or Clear filters removes them', async () => {
    const { browser, seen, queryClient } = await openBrowser({ facets: FACETS });
    const panel = await openFilters(browser);
    await press(panel, 'Domain', 'Calm');
    await press(panel, 'Rarity', 'Rare (2)');
    await press(panel, 'Energy', '3');
    await press(panel, 'Power', '3+');
    await userEvent.click(within(panel).getByRole('switch', { name: 'Owned only' }));
    await userEvent.keyboard('{Escape}');

    const chips = within(browser).getByRole('list', { name: 'Active filters' });
    expect(
      within(chips)
        .getAllByRole('listitem')
        .map((chip) => chip.textContent),
    ).toEqual(['Calm', 'Rare', 'Energy 3', 'Power 3+', 'Owned only']);
    expect(await within(browser).findByText('3 cards for Main deck', {}, LONG)).toBeVisible();

    await userEvent.click(within(chips).getByRole('button', { name: 'Remove filter Rare' }));
    await waitFor(() => expect(last(seen).getAll('rarity')).toEqual([]), LONG);
    expect(last(seen).get('energy_min')).toBe('3');
    expect(filterButton(browser)).toHaveAccessibleName('Filter, 4 active');

    await userEvent.click(within(browser).getByRole('button', { name: 'Clear filters' }));
    // back to the zone filters alone (the first answer, from the cache)
    await waitFor(() => expect(shown(queryClient).get('owned')).toBeNull(), LONG);
    expect(filtersOf(shown(queryClient))).toEqual(filtersOf(seen[0]));
    expect(shown(queryClient).get('energy_min')).toBeNull();
    expect(shown(queryClient).get('power_min')).toBeNull();
    expect(within(browser).queryByRole('list', { name: 'Active filters' })).toBeNull();
    expect(filterButton(browser)).toHaveAccessibleName('Filter');

    // the panel has its own Clear filters
    const again = await openFilters(browser);
    await press(again, 'Set', 'Origins (8)');
    await waitFor(() => expect(last(seen).getAll('set')).toEqual(['OGN']), LONG);
    await userEvent.click(within(again).getByRole('button', { name: 'Clear filters' }));
    await waitFor(() => expect(shown(queryClient).getAll('set')).toEqual([]), LONG);
  }, 30000);

  it('never widens the zone or the legend; a tab keeps only the filters that apply', async () => {
    const { browser, seen } = await openBrowser({ facets: FACETS });
    let panel = await openFilters(browser);
    await press(panel, 'Domain', 'Colorless');
    await press(panel, 'Domain', 'Calm');
    await press(panel, 'Type', 'Unit (5)');
    await press(panel, 'Energy', '2');
    await press(panel, 'Rarity', 'Rare (2)');
    await press(panel, 'Tags', 'Yasuo (1)');
    await userEvent.keyboard('{Escape}');

    // runes: only the legend's domains, no type, cost or free tag choice
    await userEvent.click(within(browser).getByRole('tab', { name: 'Runes' }));
    await waitFor(() => expect(last(seen).getAll('type')).toEqual(['Rune']), LONG);
    expect(filtersOf(last(seen))).toMatchObject({ domain: ['Calm'], tag: [], domain_match: null });
    expect(last(seen).getAll('rarity')).toEqual(['Rare']);
    expect(last(seen).get('energy_min')).toBeNull();
    panel = await openFilters(browser);
    expect(names(group(panel, 'Domain'))).toEqual(['Calm (4)', 'Chaos (2)']);
    expect(within(panel).queryByRole('group', { name: 'Type' })).toBeNull();
    expect(within(panel).queryByRole('group', { name: 'Energy' })).toBeNull();
    await userEvent.keyboard('{Escape}');

    // back on the main deck the dropped filters stay dropped
    await userEvent.click(within(browser).getByRole('tab', { name: 'Main deck' }));
    await waitFor(() => expect(last(seen).getAll('type')).toEqual(['Unit', 'Spell', 'Gear']), LONG);
    expect(filtersOf(last(seen))).toMatchObject({ domain: ['Calm'], domain_match: 'subset' });

    // the champion takes the legend's tags only
    await userEvent.click(within(browser).getByRole('tab', { name: 'Champion' }));
    await waitFor(() => expect(last(seen).getAll('supertype')).toEqual(['Champion']), LONG);
    panel = await openFilters(browser);
    expect(names(group(panel, 'Tags'))).toEqual(['Riven (2)']);
    expect(within(panel).queryByRole('group', { name: 'Type' })).toBeNull();
    await press(panel, 'Domain', 'Chaos');
    await waitFor(() => expect(filtersOf(last(seen)).domain).toEqual(['Calm', 'Chaos']), LONG);
    expect(filtersOf(last(seen))).toMatchObject({ type: ['Unit'], tag: ['Riven'] });
  }, 40000);

  it('a filter change goes back to page 1', async () => {
    const { browser, seen } = await openBrowser({ facets: FACETS, pages: 2 });
    await userEvent.click(within(browser).getByRole('button', { name: 'Next' }));
    await waitFor(() => expect(last(seen).get('page')).toBe('2'), LONG);
    const panel = await openFilters(browser);
    await press(panel, 'Rarity', 'Common (3)');
    await waitFor(() => expect(last(seen).getAll('rarity')).toEqual(['Common']), LONG);
    expect(last(seen).get('page')).toBeNull();
  }, 30000);

  it('is axe clean with the panel open and with chips', async () => {
    const { browser } = await openBrowser({ facets: FACETS });
    const panel = await openFilters(browser);
    await press(panel, 'Domain', 'Calm');
    await press(panel, 'Energy', '3');
    expect(await axe(browser)).toHaveNoViolations();
    await userEvent.keyboard('{Escape}');
    expect(await axe(browser)).toHaveNoViolations();
  }, 30000);
});
