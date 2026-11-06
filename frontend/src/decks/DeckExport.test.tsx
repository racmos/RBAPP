import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';
import { recordDeckRequests, withDecks } from '@/test/decks';
import { signedIn, writes } from '@/test/locations';
import { API, failure, ok } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';

const LONG = { timeout: 10000 };
const TEXT = 'Legend:\n1 Riven, The Exile\n\nMainDeck:\n3 Discipline\n';
const URL_41 = 'http://localhost/riftbound/app/d/abcdefghijklmnopqrstuv';

let writeText: ReturnType<typeof vi.fn>;
beforeEach(() => {
  writeText = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
});
afterEach(() => {
  vi.restoreAllMocks();
  server.events.removeAllListeners();
});

const toast = async (text: string) =>
  expect((await screen.findAllByText(text, {}, LONG)).length).toBeGreaterThan(0);

function exportAnswers(text = TEXT) {
  server.use(
    http.get(
      `${API}/decks/:id/export`,
      () => new HttpResponse(text, { headers: { 'Content-Type': 'text/plain' } }),
    ),
  );
}

async function openDeck(width = 390) {
  signedIn();
  withDecks();
  const sent = recordDeckRequests();
  const app = await renderApp({ path: '/decks/41', width });
  await screen.findByRole('heading', { level: 1 }, LONG);
  return { ...app, sent };
}

/** Opens the editor's Export menu and returns its panel. */
async function exportMenu() {
  await userEvent.click(screen.getByRole('button', { name: 'Export' }));
  return screen.findByRole('dialog', { name: 'Export deck' });
}

describe('Deck export goes to the clipboard (F5-i step 6)', () => {
  it('Copy decklist copies the exact export text, with a toast', async () => {
    exportAnswers();
    const { sent } = await openDeck();
    const menu = await exportMenu();
    await userEvent.click(within(menu).getByRole('button', { name: 'Copy decklist' }));
    await toast('Decklist copied.');
    expect(writeText).toHaveBeenCalledWith(TEXT);
    expect(sent.find((r) => r.path === '/decks/41/export')).toMatchObject({
      method: 'GET',
      search: '?format=text',
    });
    // the menu closed and nothing was written
    expect(screen.queryByRole('dialog', { name: 'Export deck' })).toBeNull();
    expect(writes(sent)).toEqual([]);
  }, 20000);

  it('the editor has no download link any more', async () => {
    await openDeck();
    expect(screen.queryByRole('link', { name: /export|download/i })).toBeNull();
    expect(document.querySelector('a[download]')).toBeNull();
    const menu = await exportMenu();
    expect(within(menu).queryAllByRole('link')).toEqual([]);
    expect(document.querySelector('a[download]')).toBeNull();
  }, 20000);

  it('a refused clipboard shows the text read-only to copy by hand', async () => {
    exportAnswers();
    writeText.mockRejectedValue(new Error('denied'));
    await openDeck();
    const menu = await exportMenu();
    await userEvent.click(within(menu).getByRole('button', { name: 'Copy decklist' }));
    const dialog = await screen.findByRole('dialog', { name: 'Copy decklist' }, LONG);
    expect(within(dialog).getByText('Could not copy: select the text and copy it.')).toBeVisible();
    const box = within(dialog).getByRole('textbox', { name: 'Decklist' });
    expect(box).toHaveValue(TEXT);
    expect(box).toHaveAttribute('readonly');
    expect(await axe(dialog)).toHaveNoViolations();
    await userEvent.keyboard('{Escape}');
    expect(screen.queryByRole('dialog', { name: 'Copy decklist' })).toBeNull();
  }, 20000);

  it('a failed export is an error toast and copies nothing', async () => {
    server.use(http.get(`${API}/decks/:id/export`, () => failure(404, { error: 'Not Found' })));
    await openDeck();
    const menu = await exportMenu();
    await userEvent.click(within(menu).getByRole('button', { name: 'Copy decklist' }));
    await toast('Something went wrong');
    expect(writeText).not.toHaveBeenCalled();
  }, 20000);

  it('Share deck opens the share link dialog: create, copy and stop sharing', async () => {
    server.use(
      http.post(`${API}/decks/:id/share`, () =>
        ok({ slug: 'abcdefghijklmnopqrstuv', url: URL_41 }),
      ),
      http.delete(`${API}/decks/:id/share`, () => ok({ share: null })),
    );
    const { sent } = await openDeck();
    const menu = await exportMenu();
    await userEvent.click(within(menu).getByRole('button', { name: 'Share deck' }));
    const dialog = await screen.findByRole('dialog', { name: 'Share link' });
    expect(within(dialog).getByText('This deck has no link yet.')).toBeVisible();
    await userEvent.click(within(dialog).getByRole('button', { name: 'Create link' }));
    expect(await within(dialog).findByRole('textbox', { name: 'Link' }, LONG)).toHaveValue(URL_41);
    await userEvent.click(within(dialog).getByRole('button', { name: 'Copy link' }));
    expect(writeText).toHaveBeenCalledWith(URL_41);
    await toast('Link copied.');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Stop sharing' }));
    expect(await within(dialog).findByText('This deck has no link yet.', {}, LONG)).toBeVisible();
    expect(writes(sent).map((r) => `${r.method} ${r.path}`)).toEqual([
      'POST /decks/41/share',
      'DELETE /decks/41/share',
    ]);
  }, 20000);

  it('offline the Export menu is disabled', async () => {
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    await openDeck();
    expect(screen.getByRole('button', { name: 'Export' })).toBeDisabled();
  }, 20000);

  it('is axe clean with the menu open at 390 and 1280 px', async () => {
    for (const width of [390, 1280]) {
      const { container, unmount } = await openDeck(width);
      await exportMenu();
      await waitFor(() =>
        expect(screen.getByRole('dialog', { name: 'Export deck' })).toBeVisible(),
      );
      expect(await axe(container)).toHaveNoViolations();
      unmount();
    }
  }, 40000);
});
