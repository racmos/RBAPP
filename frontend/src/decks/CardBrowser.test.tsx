import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';
import type { CardSummary, DeckCard, DeckContentV2 } from '@/api/types';
import { cardList, champion as ayla, foilCommon as emberWisp } from '@/test/fixtures/cards';
import { recordDeckRequests, withDecks } from '@/test/decks';
import { deckDetail, deckDetails, listItemOf, mainCards, rivenDeck } from '@/test/fixtures/decks';
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
const ITEMS = [discipline, emberWisp, ayla];

/** `GET /cards` answers `items` (filtered by `q`) in `pages` pages; the browser's queries are kept. */
function cardServer({ items = ITEMS, pages = 1 } = {}) {
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
        meta: { ...cardList.meta, page, per_page: 48, total: found.length, pages },
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

async function openBrowser(options: Parameters<typeof cardServer>[0] = {}) {
  signedIn();
  withDecks(deckDetails.map(listItemOf), deckDetails);
  savingServer();
  const seen = cardServer(options);
  const sent = recordDeckRequests();
  const app = await renderApp({ path: '/decks/41', width: DESKTOP });
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
});
const section = (name: RegExp) =>
  screen.getByText(name, { selector: 'summary *' }).closest('details') as HTMLElement;
const rowOf = (details: HTMLElement, name: string) =>
  within(details)
    .queryAllByRole('listitem')
    .find((row) => row.querySelector('[data-slot="name"]')?.textContent === name);
const puts = (sent: ReturnType<typeof recordDeckRequests>) =>
  writes(sent).filter((r) => r.method === 'PUT' && r.path === '/decks/41/content');

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
      domain: [],
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
    });
    expect(within(browser).getByRole('button', { name: 'Choose Ember Wisp' })).toBeVisible();
    expect(await choose('Runes')).toMatchObject({ type: ['Rune'], domain: ['Calm', 'Chaos'] });
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
    const tile = within(browser).getByRole('button', { name: /Ayla/ });
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
