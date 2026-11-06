import { join } from 'node:path';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';
import type { DeckListItem } from '@/api/types';
import { SRC_DIR, declsFor, readCss } from '@/test/css';
import { deckDetail, deckList, emptyContent } from '@/test/fixtures/decks';
import { recordDeckRequests, withDecks } from '@/test/decks';
import { signedIn, writes } from '@/test/locations';
import { API, failure, ok } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';

const LONG = { timeout: 10000 };
const PHONE = 390;
const DESKTOP = 1280;
const URL_41 = 'http://localhost/riftbound/app/d/abcdefghijklmnopqrstuv';
const shared41: DeckListItem = {
  ...deckList[0],
  share: { slug: 'abcdefghijklmnopqrstuv', url: URL_41 },
};

let writeText: ReturnType<typeof vi.fn>;
beforeEach(() => {
  writeText = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
});
afterEach(() => {
  vi.restoreAllMocks();
  server.events.removeAllListeners();
});

const list = () => screen.findByRole('list', { name: 'Your decks' }, LONG);
const item = (name: string) => screen.getByRole('heading', { name }).closest('li') as HTMLElement;
const shownNames = () =>
  within(screen.getByRole('list', { name: 'Your decks' }))
    .getAllByRole('heading')
    .map((h) => h.textContent);
const toast = async (text: string) =>
  expect((await screen.findAllByText(text, {}, LONG)).length).toBeGreaterThan(0);

async function openPage(width = DESKTOP, path = '/decks') {
  signedIn();
  const app = await renderApp({ path, width });
  await list();
  return app;
}

/** Opens the actions of one deck and returns the panel. */
async function actionsOf(name: string) {
  await userEvent.click(
    within(item(name)).getByRole('button', { name: `More actions for ${name}` }),
  );
  return screen.findByRole('dialog', { name: `Actions for ${name}` });
}

describe('DecksPage layout (F5 deck list grid)', () => {
  it('is a grid of cards at 1280 px and one column at 390 px', async () => {
    withDecks();
    const desktop = await openPage(DESKTOP);
    expect(screen.getByRole('list', { name: 'Your decks' })).toHaveAttribute('data-layout', 'grid');
    desktop.unmount();
    await openPage(PHONE);
    expect(screen.getByRole('list', { name: 'Your decks' })).toHaveAttribute(
      'data-layout',
      'column',
    );
  }, 20000);

  it('the grid fills its width with cards of at least 280 px', () => {
    const css = readCss(join(SRC_DIR, 'decks/DecksPage.module.css'));
    expect(declsFor(css, '.grid')).toEqual(
      expect.arrayContaining([
        { prop: 'display', value: 'grid' },
        { prop: 'grid-template-columns', value: 'repeat(auto-fill, minmax(280px, 1fr))' },
      ]),
    );
  });

  it('each card has the legend art (or a placeholder), its sharing state and an Open link', async () => {
    withDecks([shared41, ...deckList.slice(1)]);
    await openPage();
    const riven = item('Riven, The Exile');
    const art = riven.querySelector('[data-slot="art"] img') as HTMLImageElement;
    expect(art).toHaveAttribute('src', deckList[0].legend?.image_src);
    expect(within(riven).getByText('Shared')).toBeVisible();
    expect(within(item('Riven tournament')).getByText('Private')).toBeVisible();
    const draft = item('Draft ideas');
    expect(draft.querySelector('[data-slot="art"] img')).toBeNull();
    expect(draft.querySelector('[data-slot="art"]')).not.toBeNull();
    expect(within(riven).getByRole('link', { name: 'Open Riven, The Exile' })).toHaveAttribute(
      'href',
      '/riftbound/app/decks/41',
    );
  }, 20000);
});

describe('DecksPage toolbar (F5 deck list grid)', () => {
  it('search, mode, legality and sort filter the loaded list and live in the URL', async () => {
    withDecks();
    const { where } = await openPage();
    expect(screen.getByText('3 of 3 decks')).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Clear filters' })).toBeNull();

    await userEvent.type(screen.getByRole('searchbox', { name: 'Search decks' }), 'riven');
    await waitFor(() => expect(where()).toBe('/decks?q=riven'), LONG);
    await waitFor(() => expect(shownNames()).toEqual(['Riven, The Exile', 'Riven tournament']));
    expect(screen.getByText('2 of 3 decks')).toBeVisible();

    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), '2v2');
    await waitFor(() => expect(where()).toBe('/decks?q=riven&mode=2v2'));
    await waitFor(() => expect(shownNames()).toEqual(['Riven tournament']));
    expect(screen.getByText('1 of 3 decks')).toBeVisible();

    await userEvent.click(screen.getByRole('button', { name: 'Clear filters' }));
    await waitFor(() => expect(where()).toBe('/decks'));
    await waitFor(() => expect(shownNames()).toHaveLength(3));
    await waitFor(() =>
      expect(screen.getByRole('searchbox', { name: 'Search decks' })).toHaveValue(''),
    );

    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: 'Legality' }),
      'Not legal in its mode',
    );
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Sort' }), 'Name, A to Z');
    await waitFor(() => expect(where()).toBe('/decks?legal=no&sort=name'));
    await waitFor(() => expect(shownNames()).toEqual(['Draft ideas', 'Riven, The Exile']));
  }, 30000);

  it('back and forward and a reload keep the toolbar', async () => {
    withDecks();
    const { router, where } = await openPage();
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Mode' }), '1v1');
    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: 'Sort' }),
      'Value, highest first',
    );
    await waitFor(() => expect(where()).toBe('/decks?mode=1v1&sort=value'));
    await router.navigate(-1);
    await waitFor(() => expect(where()).toBe('/decks?mode=1v1'));
    await waitFor(() =>
      expect(screen.getByRole('combobox', { name: 'Sort' })).toHaveValue('updated'),
    );
    expect(shownNames()).toEqual(['Riven, The Exile', 'Draft ideas']);
    await router.navigate(1);
    await waitFor(() =>
      expect(screen.getByRole('combobox', { name: 'Sort' })).toHaveValue('value'),
    );
  }, 30000);

  it('opens with the toolbar of the URL', async () => {
    withDecks();
    await openPage(PHONE, '/decks?q=Draft&legal=no&sort=updated_asc');
    expect(screen.getByRole('searchbox', { name: 'Search decks' })).toHaveValue('Draft');
    expect(screen.getByRole('combobox', { name: 'Legality' })).toHaveValue('no');
    expect(screen.getByRole('combobox', { name: 'Sort' })).toHaveValue('updated_asc');
    expect(shownNames()).toEqual(['Draft ideas']);
  }, 20000);

  it('no match says so, unlike an account without decks, and can clear the filters', async () => {
    withDecks();
    signedIn();
    const { where } = await renderApp({ path: '/decks?q=zzz', width: DESKTOP });
    expect(await screen.findByRole('heading', { name: 'No decks match' }, LONG)).toBeVisible();
    expect(screen.queryByRole('list', { name: 'Your decks' })).toBeNull();
    expect(screen.getByText('Try another search or clear the filters.')).toBeVisible();
    expect(screen.queryByRole('heading', { name: 'No decks yet' })).toBeNull();
    expect(screen.getByText('0 of 3 decks')).toBeVisible();
    const clears = screen.getAllByRole('button', { name: 'Clear filters' });
    await userEvent.click(clears[clears.length - 1]);
    await waitFor(() => expect(where()).toBe('/decks'));
    await list();
    expect(shownNames()).toHaveLength(3);
  }, 20000);

  it('an account without decks shows no toolbar', async () => {
    withDecks([]);
    signedIn();
    await renderApp({ path: '/decks', width: DESKTOP });
    expect(await screen.findByRole('heading', { name: 'No decks yet' }, LONG)).toBeVisible();
    expect(screen.queryByRole('searchbox', { name: 'Search decks' })).toBeNull();
    expect(screen.queryByText(/ of \d+ decks?$/)).toBeNull();
  }, 20000);
});

describe('DecksPage card actions (F5 deck list grid)', () => {
  it('Duplicate posts to /duplicate, refreshes the list and offers to open the copy', async () => {
    const copy = deckDetail({ id: 60, name: 'Riven, The Exile (copy)' }, emptyContent);
    let listed = deckList;
    server.use(
      http.get(`${API}/decks`, () => ok({ items: listed })),
      http.post(`${API}/decks/:id/duplicate`, () => {
        listed = [...deckList, { ...deckList[2], id: 60, name: copy.name }];
        return ok(copy, 201);
      }),
      http.get(`${API}/decks/60`, () => ok(copy)),
    );
    const sent = recordDeckRequests();
    const { where } = await openPage();
    const panel = await actionsOf('Riven, The Exile');
    await userEvent.click(within(panel).getByRole('button', { name: 'Duplicate' }));
    await toast('Duplicated as Riven, The Exile (copy).');
    expect(writes(sent)).toEqual([
      { method: 'POST', path: '/decks/41/duplicate', search: '', body: {} },
    ]);
    expect(
      await screen.findByRole('heading', { name: 'Riven, The Exile (copy)' }, LONG),
    ).toBeVisible();
    expect(where()).toBe('/decks');
    expect(screen.queryByRole('dialog', { name: 'Actions for Riven, The Exile' })).toBeNull();
    await userEvent.click(screen.getByRole('button', { name: 'Open' }));
    await waitFor(() => expect(where()).toBe('/decks/60'), LONG);
  }, 30000);

  it('Duplicate: a failure is a translated error toast', async () => {
    withDecks();
    server.use(
      http.post(`${API}/decks/:id/duplicate`, () =>
        failure(409, { error: 'Conflict', code: 'already_exists' }),
      ),
    );
    await openPage();
    const panel = await actionsOf('Riven, The Exile');
    await userEvent.click(within(panel).getByRole('button', { name: 'Duplicate' }));
    await toast('An item with that identifier already exists.');
  }, 20000);

  it('Copy deck text reads the export and copies it; there is no download', async () => {
    withDecks();
    const text = 'Legend:\n1 Riven, The Exile\n';
    server.use(
      http.get(
        `${API}/decks/:id/export`,
        () => new HttpResponse(text, { headers: { 'Content-Type': 'text/plain' } }),
      ),
    );
    const sent = recordDeckRequests();
    await openPage();
    const panel = await actionsOf('Riven, The Exile');
    expect(within(panel).queryByRole('link')).toBeNull();
    expect(within(panel).queryByText('Download text')).toBeNull();
    expect(document.querySelector('a[download]')).toBeNull();
    await userEvent.click(within(panel).getByRole('button', { name: 'Copy deck text' }));
    await toast('Deck text copied.');
    expect(writeText).toHaveBeenCalledWith(text);
    expect(sent.find((r) => r.path === '/decks/41/export')).toMatchObject({
      method: 'GET',
      search: '?format=text',
    });
  }, 20000);

  it('Copy deck text: a failed export or a refused clipboard says so', async () => {
    withDecks();
    server.use(http.get(`${API}/decks/:id/export`, () => failure(404, { error: 'Not Found' })));
    await openPage();
    let panel = await actionsOf('Riven, The Exile');
    await userEvent.click(within(panel).getByRole('button', { name: 'Copy deck text' }));
    await toast('Something went wrong');

    server.use(http.get(`${API}/decks/:id/export`, () => new HttpResponse('x')));
    writeText.mockRejectedValue(new Error('denied'));
    panel = await actionsOf('Riven, The Exile');
    await userEvent.click(within(panel).getByRole('button', { name: 'Copy deck text' }));
    await toast('Could not copy the deck text.');
  }, 20000);

  it('Copy share link creates the link when missing, copies it and shows it', async () => {
    let listed = deckList;
    server.use(
      http.get(`${API}/decks`, () => ok({ items: listed })),
      http.post(`${API}/decks/:id/share`, () => {
        listed = [shared41, ...deckList.slice(1)];
        return ok(shared41.share);
      }),
    );
    const sent = recordDeckRequests();
    await openPage();
    const panel = await actionsOf('Riven, The Exile');
    expect(within(panel).queryByRole('button', { name: 'Stop sharing' })).toBeNull();
    await userEvent.click(within(panel).getByRole('button', { name: 'Copy share link' }));
    await toast('Link copied.');
    expect(writeText).toHaveBeenCalledWith(URL_41);
    expect(await within(panel).findByRole('textbox', { name: 'Link' }, LONG)).toHaveValue(URL_41);
    expect(within(item('Riven, The Exile')).getByText('Shared')).toBeVisible();
    expect(writes(sent).map((r) => `${r.method} ${r.path}`)).toEqual(['POST /decks/41/share']);
  }, 20000);

  it('a shared deck copies its link without a request; Stop sharing revokes it', async () => {
    let listed = [shared41, ...deckList.slice(1)];
    let fail = false;
    server.use(
      http.get(`${API}/decks`, () => ok({ items: listed })),
      http.delete(`${API}/decks/:id/share`, () => {
        if (fail) return failure(500, { error: 'Internal Server Error', code: 'internal_error' });
        listed = deckList;
        return ok({ share: null });
      }),
    );
    const sent = recordDeckRequests();
    await openPage();
    const panel = await actionsOf('Riven, The Exile');
    await userEvent.click(within(panel).getByRole('button', { name: 'Copy share link' }));
    expect(writeText).toHaveBeenCalledWith(URL_41);
    expect(writes(sent)).toEqual([]);

    fail = true;
    await userEvent.click(within(panel).getByRole('button', { name: 'Stop sharing' }));
    await toast('An unexpected error occurred. Please try again later.');
    fail = false;
    await userEvent.click(within(panel).getByRole('button', { name: 'Stop sharing' }));
    await toast('The link no longer works.');
    await waitFor(() =>
      expect(within(item('Riven, The Exile')).getByText('Private')).toBeVisible(),
    );
    expect(writes(sent).map((r) => `${r.method} ${r.path}`)).toEqual([
      'DELETE /decks/41/share',
      'DELETE /decks/41/share',
    ]);
  }, 20000);

  it('Delete asks with the deck name, deletes and stays on the list', async () => {
    let listed = deckList;
    server.use(
      http.get(`${API}/decks`, () => ok({ items: listed })),
      http.delete(`${API}/decks/:id`, () => {
        listed = deckList.slice(1);
        return ok({ deleted: { id: 41 } });
      }),
    );
    const sent = recordDeckRequests();
    const { where } = await openPage();
    const panel = await actionsOf('Riven, The Exile');
    await userEvent.click(within(panel).getByRole('button', { name: 'Delete deck' }));
    const confirm = await screen.findByRole('dialog', { name: 'Delete Riven, The Exile?' });
    await userEvent.click(within(confirm).getByRole('button', { name: 'Cancel' }));
    expect(writes(sent)).toEqual([]);

    await userEvent.click(
      within(await actionsOf('Riven, The Exile')).getByRole('button', { name: 'Delete deck' }),
    );
    await userEvent.click(
      within(await screen.findByRole('dialog', { name: 'Delete Riven, The Exile?' })).getByRole(
        'button',
        { name: 'Delete' },
      ),
    );
    await toast('Deleted Riven, The Exile.');
    await waitFor(() =>
      expect(screen.queryByRole('heading', { name: 'Riven, The Exile' })).toBeNull(),
    );
    expect(where()).toBe('/decks');
    expect(writes(sent).map((r) => `${r.method} ${r.path}`)).toEqual(['DELETE /decks/41']);
  }, 30000);

  it('Delete: a failure is an error toast and the deck stays', async () => {
    withDecks();
    server.use(
      http.delete(`${API}/decks/:id`, () =>
        failure(500, { error: 'Internal Server Error', code: 'internal_error' }),
      ),
    );
    await openPage();
    await userEvent.click(
      within(await actionsOf('Riven, The Exile')).getByRole('button', { name: 'Delete deck' }),
    );
    await userEvent.click(
      within(await screen.findByRole('dialog', { name: 'Delete Riven, The Exile?' })).getByRole(
        'button',
        { name: 'Delete' },
      ),
    );
    await toast('An unexpected error occurred. Please try again later.');
    expect(item('Riven, The Exile')).toBeVisible();
  }, 20000);

  it('offline: the actions are disabled; Open still works', async () => {
    withDecks();
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    await openPage();
    for (const deck of deckList) {
      expect(
        within(item(deck.name)).getByRole('button', { name: `More actions for ${deck.name}` }),
      ).toBeDisabled();
      expect(
        within(item(deck.name)).getByRole('link', { name: `Open ${deck.name}` }),
      ).toBeVisible();
    }
  }, 20000);
});

describe('DecksPage grid accessibility (F5 deck list grid)', () => {
  it('is axe clean at 390 px with the toolbar', async () => {
    withDecks([shared41, ...deckList.slice(1)]);
    const { container } = await openPage(PHONE);
    expect(await axe(container)).toHaveNoViolations();
  }, 30000);

  it('is axe clean at 1280 px with the actions open', async () => {
    withDecks([shared41, ...deckList.slice(1)]);
    const { container } = await openPage(DESKTOP);
    await actionsOf('Riven, The Exile');
    expect(await axe(container)).toHaveNoViolations();
  }, 30000);
});
