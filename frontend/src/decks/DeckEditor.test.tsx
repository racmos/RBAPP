import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';
import type { CardSummary, DeckContentV2 } from '@/api/types';
import { champion as aylaChampion } from '@/test/fixtures/cards';
import { recordDeckRequests, withDecks } from '@/test/decks';
import {
  deckDetail,
  deckDetails,
  draftDeck,
  listItemOf,
  mainCards,
  rivenContent,
  rivenDeck,
} from '@/test/fixtures/decks';
import { signedIn, writes } from '@/test/locations';
import { API, failure, ok } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';

const LONG = { timeout: 10000 };
const SAVE = { timeout: 5000 };
const PHONE = 390;

afterEach(() => {
  vi.restoreAllMocks();
  server.events.removeAllListeners();
});

/** The server saves what it gets and answers the detail of that content. */
function savingServer(details = deckDetails) {
  server.use(
    http.put(`${API}/decks/:id/content`, async ({ params, request }) => {
      const { content } = (await request.json()) as { content: DeckContentV2 };
      const head = details.find((deck) => String(deck.id) === params.id) ?? rivenDeck;
      return ok({ ...deckDetail(head, content), current_seq: head.current_seq });
    }),
  );
}

async function openDeck(id = 41, details = deckDetails) {
  signedIn();
  withDecks(details.map(listItemOf), details);
  savingServer(details);
  const sent = recordDeckRequests();
  const app = await renderApp({ path: `/decks/${id}`, width: PHONE });
  await screen.findByRole('heading', { level: 1 }, LONG);
  // the rule values come from /meta/game
  await waitFor(() => expect(screen.getAllByRole('combobox').length).toBeGreaterThan(0), LONG);
  return { ...app, sent };
}

const section = (name: RegExp) =>
  screen.getByText(name, { selector: 'summary *' }).closest('details') as HTMLElement;
const qtyOf = (row: HTMLElement) =>
  row.querySelector('[data-slot="qty"]')?.textContent?.replace('×', '');
const saveState = () => document.querySelector('[data-slot="save-state"]') as HTMLElement;
const toast = async (text: string) =>
  expect((await screen.findAllByText(text, {}, LONG)).length).toBeGreaterThan(0);
const rowOf = (details: HTMLElement, name: string) =>
  within(details)
    .getAllByRole('listitem')
    .find((row) => row.querySelector('[data-slot="name"]')?.textContent === name) as HTMLElement;
/** The autosaves of one deck (a previous test may still flush its own on unmount). */
const puts = (sent: ReturnType<typeof recordDeckRequests>, id = 41) =>
  writes(sent).filter(
    (request) => request.method === 'PUT' && request.path === `/decks/${id}/content`,
  );

describe('Deck editing at 390 px (F5-h stage 2)', () => {
  it('a 4th copy is refused before it can happen, with the reason as description', async () => {
    await openDeck();
    const add = screen.getByRole('button', { name: 'Add a copy of Discipline' });
    expect(add).toBeDisabled();
    expect(add).toHaveAttribute('title', 'Discipline has 4 copies (max 3).');
    expect(add).toHaveAccessibleDescription('Discipline has 4 copies (max 3).');
    // a 13th rune too
    const rune = screen.getByRole('button', { name: 'Add a copy of Chaos Rune' });
    expect(rune).toBeDisabled();
    expect(rune).toHaveAccessibleDescription('The deck has 13 of 12 runes (1 too many).');
  }, 20000);

  it('removes a copy at once and autosaves the content after a second', async () => {
    const { sent } = await openDeck();
    const main = section(/^Main deck$/);
    await userEvent.click(screen.getByRole('button', { name: 'Remove a copy of Discipline' }));
    expect(qtyOf(rowOf(main, 'Discipline'))).toBe('2');
    expect(within(main).getByText('38/39')).toBeVisible();
    expect(saveState()).toHaveTextContent('Not saved yet.');
    expect(screen.getByText('Legality as of the last save.')).toBeVisible();
    await waitFor(() => expect(puts(sent)).toHaveLength(1), SAVE);
    const body = puts(sent)[0].body as { content: DeckContentV2 };
    expect(body.content.main[0]).toEqual({ set: 'OGN', id: mainCards[0].card_id, qty: 2 });
    await waitFor(() => expect(saveState()).toHaveTextContent('All changes saved.'));
    // the server legality now says the main deck is short
    const legality = screen.getByRole('region', { name: 'Legality' });
    expect(
      within(legality).getAllByText('The main deck has 38 of 39 cards (1 missing).').length,
    ).toBe(2);
    // and now a copy can be added again
    expect(screen.getByRole('button', { name: 'Add a copy of Discipline' })).toBeEnabled();
  }, 20000);

  it('moves a copy to the sideboard; a full sideboard refuses it with the reason', async () => {
    const { sent } = await openDeck();
    await userEvent.click(
      screen.getByRole('button', { name: 'Move a copy of Discipline to the sideboard' }),
    );
    const side = section(/^Sideboard$/);
    expect(qtyOf(rowOf(side, 'Discipline'))).toBe('1');
    expect(within(side).getByText('9/10')).toBeVisible();
    await waitFor(() => expect(puts(sent)).toHaveLength(1), SAVE);

    await userEvent.click(
      screen.getByRole('button', { name: 'Move a copy of Defy to the sideboard' }),
    );
    const blocked = screen.getByRole('button', {
      name: 'Move a copy of Gust to the sideboard',
    });
    expect(blocked).toBeDisabled();
    expect(blocked).toHaveAccessibleDescription('The sideboard has 11 of 10 cards (1 too many).');
  }, 20000);

  it('removing the last copy offers an undo', async () => {
    const { sent } = await openDeck();
    await userEvent.click(screen.getByRole('button', { name: 'Remove Star Spring' }));
    const fields = section(/^Battlefields$/);
    expect(within(fields).getAllByRole('listitem')).toHaveLength(2);
    await toast('Star Spring removed.');
    await userEvent.click(screen.getByRole('button', { name: 'Undo' }));
    expect(within(fields).getAllByRole('listitem')).toHaveLength(3);
    await waitFor(() => expect(puts(sent).length).toBeGreaterThan(0), SAVE);
    const last = puts(sent).at(-1)?.body as { content: DeckContentV2 };
    expect(last.content.battlefields).toEqual(rivenContent.battlefields);
  }, 20000);

  it('a deck over a hard limit is not saved until fixed, and says why (decision A)', async () => {
    const over = deckDetail(
      { id: 44, name: 'Imported over' },
      {
        ...rivenContent,
        main: rivenContent.main.map((line, index) => (index === 0 ? { ...line, qty: 4 } : line)),
      },
    );
    const { sent } = await openDeck(44, [over]);
    const banner = screen.getByRole('alert');
    expect(banner).toHaveTextContent(
      'This deck goes over a limit, so it is not saved until you fix it:',
    );
    expect(within(banner).getByText('Discipline: more than 3 copies.')).toBeVisible();
    // another edit is kept locally but not sent
    await userEvent.click(screen.getByRole('button', { name: 'Remove a copy of Defy' }));
    await new Promise((resolve) => setTimeout(resolve, 1300));
    expect(puts(sent, 44)).toEqual([]);
    expect(saveState()).toHaveTextContent('Not saved yet.');
    // fixing the limit saves
    await userEvent.click(screen.getByRole('button', { name: 'Remove a copy of Discipline' }));
    expect(screen.queryByRole('alert')).toBeNull();
    await waitFor(() => expect(puts(sent, 44)).toHaveLength(1), SAVE);
  }, 20000);

  it('a refused save (deck_limit_exceeded) keeps the local deck and shows the reason', async () => {
    const { sent } = await openDeck();
    server.use(
      http.put(`${API}/decks/:id/content`, () =>
        failure(400, {
          error: 'Validation Error',
          code: 'deck_limit_exceeded',
          params: { rule: 'runes', max: 12 },
        }),
      ),
    );
    await userEvent.click(screen.getByRole('button', { name: 'Remove a copy of Calm Rune' }));
    await waitFor(
      () => expect(saveState()).toHaveTextContent('Changes not saved: More than 12 runes.'),
      SAVE,
    );
    expect(qtyOf(rowOf(section(/^Runes$/), 'Calm Rune'))).toBe('4');
    expect(puts(sent)).toHaveLength(1);
    savingServer();
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await waitFor(() => expect(saveState()).toHaveTextContent('All changes saved.'));
  }, 20000);

  it('adds a searched card to the sideboard after the rules allow it', async () => {
    const { sent } = await openDeck();
    const pick = screen.getByRole('combobox', { name: 'Add to the sideboard' });
    await userEvent.type(pick, 'Ember');
    await userEvent.click(await screen.findByRole('option', { name: /Ember Wisp/ }, LONG));
    const side = section(/^Sideboard$/);
    expect(rowOf(side, 'Ember Wisp')).toBeDefined();
    expect(within(side).getByText('9/10')).toBeVisible();
    await waitFor(() => expect(puts(sent).length).toBeGreaterThan(0), SAVE);
    const body = puts(sent).at(-1)?.body as { content: DeckContentV2 };
    expect(body.content.sideboard.at(-1)).toEqual({ set: 'OGN', id: '12', qty: 1 });
  }, 20000);

  it('a new legend purges the runes and champion outside it, with an undo', async () => {
    const furyLegend: CardSummary = {
      ...aylaChampion,
      card_id: '200',
      key: 'OGN-200',
      name: 'Fury Queen',
      type: 'Legend',
      supertype: null,
      type_raw: 'Legend',
      domains: ['Fury'],
      tags: ['Ayla'],
    };
    const seen: string[] = [];
    server.use(
      http.get(`${API}/cards`, ({ request }) => {
        seen.push(new URL(request.url).search);
        return ok({ items: [furyLegend] });
      }),
    );
    const noLegend = deckDetail(
      { id: 45, name: 'No legend yet' },
      { ...rivenContent, legend: null },
    );
    await openDeck(45, [noLegend]);
    const pick = screen.getByRole('combobox', { name: 'Choose a legend' });
    await userEvent.type(pick, 'Fury');
    await userEvent.click(await screen.findByRole('option', { name: /Fury Queen/ }, LONG));
    expect(seen.some((search) => search.includes('type=Legend'))).toBe(true);
    expect(within(section(/^Legend$/)).getByText('Ayla, Fury Queen')).toBeVisible();
    await toast('Legend changed: runes and champion outside it were removed.');
    expect(within(section(/^Runes$/)).getByText('No cards.')).toBeVisible();
    expect(within(section(/^Champion$/)).getByText('No cards.')).toBeVisible();
    // the main deck is never purged
    expect(within(section(/^Main deck$/)).getAllByRole('listitem')).toHaveLength(13);
    await userEvent.click(screen.getByRole('button', { name: 'Undo' }));
    expect(within(section(/^Runes$/)).getAllByRole('listitem')).toHaveLength(2);
    expect(within(section(/^Legend$/)).getByText('No cards.')).toBeVisible();
  }, 30000);

  it('renames the deck and saves a version once everything is saved', async () => {
    const { sent } = await openDeck();
    server.use(
      http.patch(`${API}/decks/:id`, async ({ request }) =>
        ok({ ...rivenDeck, ...((await request.json()) as object) }),
      ),
      http.post(`${API}/decks/:id/versions`, () =>
        ok(
          { seq: 2, note: 'Before the cup', created_at: '2026-11-05T10:00:00Z', is_current: true },
          201,
        ),
      ),
    );
    await userEvent.click(screen.getByRole('button', { name: 'Rename or change mode' }));
    const dialog = await screen.findByRole('dialog', { name: 'Deck settings' });
    const name = within(dialog).getByRole('textbox', { name: 'Name' });
    await userEvent.clear(name);
    await userEvent.type(name, 'Riven cup');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save' }));
    expect(await screen.findByRole('heading', { level: 1, name: 'Riven cup' }, LONG)).toBeVisible();
    expect(writes(sent).find((r) => r.method === 'PATCH')).toMatchObject({
      path: '/decks/41',
      body: { name: 'Riven cup' },
    });

    await userEvent.click(screen.getByRole('button', { name: 'Save as version' }));
    const form = await screen.findByRole('dialog', { name: 'Save as version' });
    await userEvent.type(within(form).getByRole('textbox', { name: /Note/ }), 'Before the cup');
    await userEvent.click(within(form).getByRole('button', { name: 'Save version' }));
    await toast('Saved as version 2.');
    expect(writes(sent).find((r) => r.path === '/decks/41/versions')?.body).toEqual({
      note: 'Before the cup',
    });
    expect(screen.getByText(/^Version 2 ·/)).toBeVisible();
  }, 30000);

  it('a taken name stays in the dialog with its message', async () => {
    await openDeck();
    server.use(
      http.patch(`${API}/decks/:id`, () =>
        failure(409, { error: 'Conflict', code: 'already_exists' }),
      ),
    );
    await userEvent.click(screen.getByRole('button', { name: 'Rename or change mode' }));
    const dialog = await screen.findByRole('dialog', { name: 'Deck settings' });
    await userEvent.type(within(dialog).getByRole('textbox', { name: 'Name' }), ' 2');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save' }));
    expect(
      await within(dialog).findByText('You already have a deck with this name.', {}, LONG),
    ).toBeVisible();
  }, 20000);

  it('creates, copies and revokes the share link; exports the text', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
    const url = 'http://localhost/riftbound/app/d/abcdefghijklmnopqrstuv';
    server.use(
      http.post(`${API}/decks/:id/share`, () => ok({ slug: 'abcdefghijklmnopqrstuv', url })),
      http.delete(`${API}/decks/:id/share`, () => ok({ share: null })),
    );
    const { sent } = await openDeck();
    expect(screen.getByRole('link', { name: 'Export text' })).toHaveAttribute(
      'href',
      '/riftbound/api/v1/decks/41/export?format=text',
    );
    await userEvent.click(screen.getByRole('button', { name: 'Share link' }));
    const dialog = await screen.findByRole('dialog', { name: 'Share link' });
    expect(within(dialog).getByText('This deck has no link yet.')).toBeVisible();
    await userEvent.click(within(dialog).getByRole('button', { name: 'Create link' }));
    expect(await within(dialog).findByRole('textbox', { name: 'Link' }, LONG)).toHaveValue(url);
    await userEvent.click(within(dialog).getByRole('button', { name: 'Copy link' }));
    expect(writeText).toHaveBeenCalledWith(url);
    await toast('Link copied.');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Stop sharing' }));
    expect(await within(dialog).findByText('This deck has no link yet.', {}, LONG)).toBeVisible();
    expect(writes(sent).map((r) => `${r.method} ${r.path}`)).toEqual([
      'POST /decks/41/share',
      'DELETE /decks/41/share',
    ]);
  }, 20000);

  it('deletes after a confirmation and goes back to the list', async () => {
    server.use(http.delete(`${API}/decks/:id`, () => ok({ deleted: { id: 41 } })));
    const { sent, where } = await openDeck();
    await userEvent.click(screen.getByRole('button', { name: 'Delete deck' }));
    const confirm = await screen.findByRole('dialog', { name: 'Delete Riven, The Exile?' });
    expect(
      within(confirm).getByText(
        'The deck and all its versions are deleted. This cannot be undone.',
      ),
    ).toBeVisible();
    await userEvent.click(within(confirm).getByRole('button', { name: 'Delete' }));
    await toast('Deck deleted.');
    await waitFor(() => expect(where()).toBe('/decks'));
    expect(writes(sent)).toMatchObject([{ method: 'DELETE', path: '/decks/41' }]);
  }, 20000);

  it('cards missing from the catalog block editing until the user removes them', async () => {
    signedIn();
    withDecks();
    savingServer();
    const sent = recordDeckRequests();
    await renderApp({ path: '/decks/43', width: PHONE });
    const warning = await screen.findByRole('region', { name: 'Cards not in the catalog' }, LONG);
    expect(
      within(warning).getByText(
        'Remove the cards that are not in the catalog to edit and save this deck.',
      ),
    ).toBeVisible();
    expect(screen.queryAllByRole('combobox')).toEqual([]);
    expect(screen.getByRole('button', { name: 'Remove a copy of Discipline' })).toBeDisabled();
    await userEvent.click(
      within(warning).getByRole('button', { name: 'Remove cards not in the catalog' }),
    );
    expect(screen.queryByRole('region', { name: 'Cards not in the catalog' })).toBeNull();
    await waitFor(() => expect(puts(sent, 43)).toHaveLength(1), SAVE);
    const body = puts(sent, 43)[0].body as { content: DeckContentV2 };
    expect(body.content.main).toEqual([draftDeck.content.main[0]]);
  }, 20000);

  it('offline: every edit is disabled', async () => {
    signedIn();
    withDecks();
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    await renderApp({ path: '/decks/41', width: PHONE });
    await screen.findByRole('heading', { level: 1 }, LONG);
    expect(saveState()).toHaveTextContent('Offline: editing is disabled.');
    expect(screen.queryAllByRole('combobox')).toEqual([]);
    expect(screen.getByRole('button', { name: 'Remove a copy of Discipline' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Remove Star Spring' })).toBeDisabled();
    for (const name of ['Rename or change mode', 'Save as version', 'Share link', 'Delete deck']) {
      expect(screen.getByRole('button', { name })).toBeDisabled();
    }
  }, 20000);

  it('is axe clean while editing', async () => {
    const { container } = await openDeck();
    expect(await axe(container)).toHaveNoViolations();
  }, 30000);
});

describe('Deck editing at 1280 px (F5-i step 2)', () => {
  it('the card browser replaces the per-section search; Auto runes stays', async () => {
    signedIn();
    withDecks();
    await renderApp({ path: '/decks/41', width: 1280 });
    await screen.findByRole('region', { name: 'Card browser' }, LONG);
    // the topbar keeps its own card search; the sections have none
    const workspace = screen.getByRole('region', { name: 'Deck workspace' });
    expect(within(workspace).queryAllByRole('combobox')).toEqual([]);
    await waitFor(
      () => expect(screen.getByRole('button', { name: 'Auto runes' })).toBeEnabled(),
      LONG,
    );
    expect(screen.getByRole('button', { name: 'Remove a copy of Discipline' })).toBeEnabled();
  }, 20000);

  it('offline the browser is not shown and every edit stays disabled', async () => {
    signedIn();
    withDecks();
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    await renderApp({ path: '/decks/41', width: 1280 });
    await screen.findByRole('heading', { level: 1 }, LONG);
    expect(screen.queryByRole('region', { name: 'Card browser' })).toBeNull();
    const workspace = screen.getByRole('region', { name: 'Deck workspace' });
    expect(within(workspace).queryAllByRole('combobox')).toEqual([]);
    expect(screen.getByRole('button', { name: 'Remove a copy of Discipline' })).toBeDisabled();
  }, 20000);
});
