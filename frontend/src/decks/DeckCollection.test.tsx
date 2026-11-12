import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';
import type { DeckContentV2, DeckVsCollection, MissingToWishlistResult } from '@/api/types';
import { clearToasts } from '@/components/ui/toastStore';
import { miniOfDeckCard, recordDeckRequests, withDecks, withVsCollection } from '@/test/decks';
import {
  deckDetail,
  deckDetails,
  listItemOf,
  mainCards,
  rivenChampion,
  rivenDeck,
  sideCards,
} from '@/test/fixtures/decks';
import { writes } from '@/test/locations';
import { API, failure, ok } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';
import { findToast, installWishlists, signedIn } from '@/test/wishlists';

const LONG = { timeout: 10000 };
const PHONE = 390;

afterEach(() => {
  vi.restoreAllMocks();
  server.events.removeAllListeners();
  clearToasts();
});

const discipline = mainCards[0]; // 0.25 €
const herder = mainCards[4]; // no price
const decree = sideCards[0]; // 0.20 €

/** Deck 41 against the collection: four names miss 8 copies, one of them unpriced. */
const VS: DeckVsCollection = {
  missing: [
    { card: miniOfDeckCard(rivenChampion), zone: 'champion', need: 1, have: 0, missing: 1 },
    { card: miniOfDeckCard(discipline), zone: 'main', need: 3, have: 1, missing: 2 },
    { card: miniOfDeckCard(herder), zone: 'main', need: 3, have: 0, missing: 3 },
    { card: miniOfDeckCard(decree), zone: 'sideboard', need: 2, have: 0, missing: 2 },
  ],
  complete: 20,
  names: 24,
  cost_eur: 13.4,
  owned_value: 25.75,
  unpriced: 1,
};
const COMPLETE: DeckVsCollection = {
  missing: [],
  complete: 24,
  names: 24,
  cost_eur: 0,
  owned_value: 39.15,
  unpriced: 0,
};

const result = (
  id: number,
  name: string,
  overrides: Partial<MissingToWishlistResult> = {},
): MissingToWishlistResult => ({
  wishlist: { id, name },
  added: 4,
  merged: 0,
  unchanged: 0,
  skipped: [],
  total_missing_names: 4,
  ...overrides,
});

/** The server saves what it gets and answers the detail of that content. */
function savingServer() {
  server.use(
    http.put(`${API}/decks/:id/content`, async ({ params, request }) => {
      const { content } = (await request.json()) as { content: DeckContentV2 };
      const head = deckDetails.find((deck) => String(deck.id) === params.id) ?? rivenDeck;
      return ok({ ...deckDetail(head, content), current_seq: head.current_seq });
    }),
  );
}

async function openCollection(width = PHONE) {
  signedIn();
  withDecks(deckDetails.map(listItemOf), deckDetails);
  installWishlists();
  const app = await renderApp({ path: '/decks/41', width });
  await screen.findByRole('heading', { level: 1 }, LONG);
  await userEvent.click(screen.getByRole('tab', { name: 'Collection' }));
  const panel = screen.getByRole('tabpanel', { name: 'Collection' });
  return { ...app, panel };
}

const tile = (panel: HTMLElement, name: string) =>
  within(panel).getByText(name, { selector: 'dt' }).parentElement as HTMLElement;
const rowOf = (panel: HTMLElement, name: string) =>
  within(panel)
    .getAllByRole('listitem')
    .find((row) => row.querySelector('[data-slot="name"]')?.textContent === name) as HTMLElement;
const addButton = (panel: HTMLElement) =>
  within(panel).getByRole('button', { name: 'Add missing to wishlist' });

describe('Deck view: Collection tab (F5-f)', () => {
  it('shows the tiles and the missing cards grouped by section, as the API orders them', async () => {
    const calls = withVsCollection(() => VS);
    const { panel } = await openCollection();
    expect(
      within(screen.getByRole('tablist', { name: 'Workspace view' }))
        .getAllByRole('tab')
        .map((t) => t.textContent),
    ).toEqual(['List', 'Stats', 'Collection']);
    await within(panel).findByText('Cards missing', {}, LONG);
    expect(within(panel).getByRole('heading', { name: 'Deck vs collection' })).toBeVisible();
    expect(tile(panel, 'Cards missing')).toHaveTextContent('8');
    expect(tile(panel, 'Cost to complete')).toHaveTextContent('13.40 €');
    expect(tile(panel, 'Cost to complete')).toHaveTextContent('1 card without price');
    expect(tile(panel, 'Value you own')).toHaveTextContent('25.75 €');

    expect(
      within(panel)
        .getAllByRole('heading', { level: 3 })
        .map((h) => h.textContent),
    ).toEqual(['Champion', 'Main deck', 'Sideboard']);
    const main = within(panel).getByRole('list', { name: 'Missing cards: Main deck' });
    expect(
      within(main)
        .getAllByRole('listitem')
        .map((row) => row.querySelector('[data-slot="name"]')?.textContent),
    ).toEqual(['Discipline', 'Stellacorn Herder']);
    const row = rowOf(panel, 'Discipline');
    expect(within(row).getByText('Need 3 · Have 1 · Missing 2')).toBeVisible();
    expect(within(row).getByText('0.50 €')).toBeVisible();
    expect(within(rowOf(panel, 'Stellacorn Herder')).getByText('No price')).toBeVisible();
    expect(within(rowOf(panel, 'Riven, Broken Blade')).getByText('12.50 €')).toBeVisible();
    expect(addButton(panel)).toBeEnabled();
    expect(calls.reads).toBe(1);
  }, 30000);

  it('a fully owned deck says so and has nothing to add', async () => {
    withVsCollection(() => COMPLETE);
    const { panel } = await openCollection();
    expect(
      await within(panel).findByText('You own every card of this deck.', {}, LONG),
    ).toBeVisible();
    expect(tile(panel, 'Cards missing')).toHaveTextContent('0');
    expect(tile(panel, 'Cost to complete')).not.toHaveTextContent('without price');
    const button = addButton(panel);
    expect(button).toBeDisabled();
    expect(button).toHaveAccessibleDescription(
      'Nothing is missing: you own every copy this deck needs.',
    );
  }, 30000);

  it('a failed read offers a retry', async () => {
    let fail = true;
    server.use(
      http.get(`${API}/decks/:id/vs-collection`, () =>
        fail ? failure(500, { error: 'Internal Server Error' }) : ok(VS),
      ),
    );
    const { panel } = await openCollection();
    const alert = await within(panel).findByRole('alert', {}, LONG);
    expect(alert).toHaveTextContent('The comparison with your collection could not be loaded.');
    expect(addButton(panel)).toBeDisabled();
    expect(addButton(panel)).toHaveAccessibleDescription(
      'The comparison with your collection could not be loaded.',
    );
    fail = false;
    await userEvent.click(within(panel).getByRole('button', { name: /retry/i }));
    expect(await within(panel).findByText('Cards missing', {}, LONG)).toBeVisible();
  }, 30000);

  it('offline it stays read-only', async () => {
    withVsCollection(() => VS);
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    const { panel } = await openCollection();
    await within(panel).findByText('Cards missing', {}, LONG);
    const button = addButton(panel);
    expect(button).toBeDisabled();
    expect(button).toHaveAccessibleDescription('You are offline.');
  }, 30000);

  it('reads again once an edit is saved, not at every change', async () => {
    const calls = withVsCollection(() => VS);
    savingServer();
    const sent = recordDeckRequests();
    const { panel } = await openCollection();
    await within(panel).findByText('Cards missing', {}, LONG);
    expect(calls.reads).toBe(1);
    await userEvent.click(screen.getByRole('tab', { name: 'List' }));
    await screen.findByRole('button', { name: 'Add cards to the main deck' }, LONG);
    const remove = screen.getByRole('button', { name: 'Remove a copy of Discipline' });
    await userEvent.click(remove);
    await userEvent.click(remove);
    await userEvent.click(screen.getByRole('tab', { name: 'Collection' }));
    const shown = screen.getByRole('tabpanel', { name: 'Collection' });
    expect(
      within(shown).getByText('Shows the deck as last saved; it updates after the next save.'),
    ).toBeVisible();
    await waitFor(
      () => expect(writes(sent).filter((r) => r.method === 'PUT')).toHaveLength(1),
      LONG,
    );
    await waitFor(() => expect(calls.reads).toBe(2), LONG);
    await waitFor(
      () =>
        expect(
          within(shown).queryByText(
            'Shows the deck as last saved; it updates after the next save.',
          ),
        ).toBeNull(),
      LONG,
    );
    expect(writes(sent).filter((r) => r.method === 'PUT')).toHaveLength(1);
    expect(calls.reads).toBe(2);
  }, 30000);

  it('is axe clean, also at 1280 px', async () => {
    withVsCollection(() => VS);
    const { container, panel } = await openCollection();
    await within(panel).findByText('Cards missing', {}, LONG);
    expect(await axe(container)).toHaveNoViolations();
  }, 30000);

  it('at 1280 px the Collection tab sits in the workspace next to the card browser', async () => {
    withVsCollection(() => VS);
    const { container } = await openCollection(1280);
    await screen.findByRole('region', { name: 'Card browser' }, LONG);
    const workspace = screen.getByRole('region', { name: 'Deck workspace' });
    const panel = within(workspace).getByRole('tabpanel', { name: 'Collection' });
    expect(await within(panel).findByText('Need 3 · Have 1 · Missing 2', {}, LONG)).toBeVisible();
    expect(await axe(container)).toHaveNoViolations();
  }, 30000);
});

describe('Add missing to wishlist (F5-f)', () => {
  async function openPicker() {
    const { panel, ...app } = await openCollection();
    await within(panel).findByText('Cards missing', {}, LONG);
    await userEvent.click(addButton(panel));
    const dialog = await screen.findByRole('dialog', { name: 'Add missing cards to a wishlist' });
    await within(dialog).findByRole('radio', { name: /Wishlist/ }, LONG);
    return { ...app, panel, dialog };
  }

  it('lists the wishlists with the default starred and chosen, and says how many cards go', async () => {
    withVsCollection(() => VS);
    const { dialog } = await openPicker();
    expect(
      within(dialog).getByText(
        '4 cards will be added, each with only the copies this deck misses.',
      ),
    ).toBeVisible();
    expect(within(dialog).getByText(/at most 100 cards/)).toBeVisible();
    const radios = within(dialog).getAllByRole('radio');
    expect(radios).toHaveLength(2);
    const wishlist = within(dialog).getByRole('radio', { name: /Wishlist/ });
    expect(wishlist).toBeChecked();
    expect(within(dialog).getByRole('radio', { name: /Trades/ })).not.toBeChecked();
    const label = wishlist.closest('label') as HTMLElement;
    expect(within(label).getByTitle('Default list')).toBeInTheDocument();
    expect(label).toHaveTextContent('3 cards');
    expect(await axe(dialog)).toHaveNoViolations();
  }, 30000);

  it('adds to the chosen list and the toast opens it', async () => {
    const calls = withVsCollection(
      () => VS,
      (id) => result(id, 'Trades', { added: 2, merged: 1, unchanged: 1 }),
    );
    const { dialog, where } = await openPicker();
    await userEvent.click(within(dialog).getByRole('radio', { name: /Trades/ }));
    await userEvent.click(within(dialog).getByRole('button', { name: 'Add' }));
    expect(await findToast('Added 2 cards to Trades. 1 already there was updated.')).toBeVisible();
    expect(calls.posts).toEqual([{ wishlist_id: 2 }]);
    expect(screen.queryByRole('dialog', { name: 'Add missing cards to a wishlist' })).toBeNull();
    await userEvent.click(screen.getByRole('button', { name: 'Open list' }));
    await waitFor(() => expect(where()).toBe('/collection/wishlists?list=2'), LONG);
  }, 30000);

  it('sends the default list when it is left chosen', async () => {
    const calls = withVsCollection(
      () => VS,
      (id) => result(id, 'Wishlist'),
    );
    const { dialog } = await openPicker();
    await userEvent.click(within(dialog).getByRole('button', { name: 'Add' }));
    expect(await findToast('Added 4 cards to Wishlist.')).toBeVisible();
    expect(calls.posts).toEqual([{ wishlist_id: 1 }]);
  }, 30000);

  it('says when only existing lines changed, or nothing did', async () => {
    let answer = result(1, 'Wishlist', { added: 0, merged: 2, unchanged: 2 });
    withVsCollection(
      () => VS,
      () => answer,
    );
    const { dialog, panel } = await openPicker();
    await userEvent.click(within(dialog).getByRole('button', { name: 'Add' }));
    expect(await findToast('Updated 2 cards already in Wishlist.')).toBeVisible();
    answer = result(1, 'Wishlist', { added: 0, merged: 0, unchanged: 4 });
    await userEvent.click(addButton(panel));
    const again = await screen.findByRole('dialog', { name: 'Add missing cards to a wishlist' });
    await userEvent.click(within(again).getByRole('button', { name: 'Add' }));
    expect(await findToast('Wishlist already has every missing card.')).toBeVisible();
  }, 30000);

  it('reports the cards a full list left out, and the capped ones', async () => {
    withVsCollection(
      () => VS,
      (id) =>
        result(id, 'Wishlist', {
          added: 1,
          skipped: [
            { card: miniOfDeckCard(herder), missing: 3, reason: 'list_full' },
            { card: miniOfDeckCard(decree), missing: 2, reason: 'list_full' },
            { card: miniOfDeckCard(discipline), missing: 5, reason: 'qty_cap' },
          ],
        }),
    );
    const { dialog } = await openPicker();
    await userEvent.click(within(dialog).getByRole('button', { name: 'Add' }));
    expect(
      await findToast(
        'Added 1 card to Wishlist. 2 could not be added because the list is full. 1 card was capped at 99 copies.',
      ),
    ).toBeVisible();
    expect(screen.getByRole('button', { name: 'Open list' })).toBeVisible();
  }, 30000);

  it('a list deleted meanwhile is said in the dialog, which stays open', async () => {
    withVsCollection(() => VS);
    server.use(
      http.post(`${API}/decks/:id/missing-to-wishlist`, () =>
        failure(404, { error: 'Not Found', message: 'The requested resource was not found' }),
      ),
    );
    const { dialog } = await openPicker();
    await userEvent.click(within(dialog).getByRole('button', { name: 'Add' }));
    expect(
      await within(dialog).findByText(
        'That wishlist no longer exists. Choose another one.',
        {},
        LONG,
      ),
    ).toBeVisible();
    expect(screen.getByRole('dialog', { name: 'Add missing cards to a wishlist' })).toBeVisible();
  }, 30000);

  it('a network failure is said in the dialog', async () => {
    withVsCollection(() => VS);
    server.use(http.post(`${API}/decks/:id/missing-to-wishlist`, () => Response.error()));
    const { dialog } = await openPicker();
    await userEvent.click(within(dialog).getByRole('button', { name: 'Add' }));
    const alert = await within(dialog).findByRole('alert', {}, LONG);
    expect(alert.textContent?.length).toBeGreaterThan(0);
    expect(screen.getByRole('dialog', { name: 'Add missing cards to a wishlist' })).toBeVisible();
  }, 30000);
});
