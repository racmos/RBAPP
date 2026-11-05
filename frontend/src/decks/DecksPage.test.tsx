import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';
import { deckDetail, deckList, emptyContent, rivenDeck } from '@/test/fixtures/decks';
import { recordDeckRequests, withDecks } from '@/test/decks';
import { writes } from '@/test/locations';
import { signedIn } from '@/test/locations';
import { API, failure, ok } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';

const LONG = { timeout: 10000 };
const PHONE = 390;

afterEach(() => {
  vi.restoreAllMocks();
  server.events.removeAllListeners();
});

const list = () => screen.findByRole('list', { name: 'Your decks' }, LONG);
const item = (name: string) => screen.getByRole('heading', { name }).closest('li') as HTMLElement;

async function openPage(width = PHONE) {
  signedIn();
  return renderApp({ path: '/decks', width });
}

const clean = {
  deck_preview: rivenDeck,
  warnings: [],
  counts: { lines: 33, copies: 66, unresolved: 0 },
};
const withProblems = {
  deck_preview: rivenDeck,
  warnings: [
    { line: 4, text: '2 Mystery Card', reason_code: 'unknown_card', params: {} },
    { line: 5, text: '1 Nope [OGN-998]', reason_code: 'unknown_card', params: { id: 'OGN-998' } },
    {
      line: 6,
      text: '2 Defy [OGN-999]',
      reason_code: 'printing_unknown',
      params: { id: 'OGN-999', name: 'Defy' },
    },
    {
      line: 7,
      text: '1 Gust [OGN-008]',
      reason_code: 'name_mismatch',
      params: { written: 'Gust', found: 'Astral Heron' },
    },
    {
      line: 9,
      text: '1 Star Spring',
      reason_code: 'wrong_zone',
      params: { name: 'Star Spring', zone: 'main' },
    },
    {
      line: null,
      text: '',
      reason_code: 'hard_limit',
      params: { rule: 'copies', max: 3, name: 'Discipline' },
    },
  ],
  counts: { lines: 31, copies: 63, unresolved: 2 },
};

async function openImport() {
  await list();
  await userEvent.click(screen.getByRole('button', { name: 'Import' }));
  return screen.findByRole('dialog', { name: 'Import a deck' });
}
const textbox = (dialog: HTMLElement) => within(dialog).getByRole('textbox', { name: 'Deck text' });

describe('DecksPage at 390 px (F5-h stage 1)', () => {
  it('lists the decks newest first with mode, legend, champion, counts, value and date', async () => {
    withDecks();
    await openPage();
    const decks = await list();
    expect(screen.getByRole('heading', { level: 1, name: 'Decks' })).toBeVisible();
    expect(document.title).toBe('Decks · Rift Manager');
    expect(
      within(decks)
        .getAllByRole('heading')
        .map((h) => h.textContent),
    ).toEqual(['Riven, The Exile', 'Riven tournament', 'Draft ideas']);

    const riven = item('Riven, The Exile');
    expect(within(riven).getByRole('link', { name: 'Riven, The Exile' })).toHaveAttribute(
      'href',
      '/riftbound/app/decks/41',
    );
    expect(within(riven).getByText('1v1')).toBeVisible();
    // the legend is shown with its champion tag, the way decks are written
    expect(within(riven).getByText('Riven, The Exile', { selector: 'span' })).toBeVisible();
    expect(within(riven).getByText('Riven, Broken Blade')).toBeVisible();
    expect(within(riven).getByRole('img', { name: 'Calm and Chaos' })).toBeVisible();
    expect(within(riven).getByText('Main 39/39')).toBeVisible();
    expect(within(riven).getByText('Runes 12/12')).toBeVisible();
    expect(within(riven).getByText('Battlefields 3/3')).toBeVisible();
    expect(within(riven).getByText('Sideboard 8/10')).toBeVisible();
    expect(within(riven).getByText(`${deckList[0].value.toFixed(2)} €`)).toBeVisible();
    expect(within(riven).getByText('3 cards without price')).toBeVisible();
    expect(within(riven).getByText('Updated 4 Nov 2026')).toBeVisible();

    const draft = item('Draft ideas');
    expect(within(draft).getByText('No legend')).toBeVisible();
    expect(within(draft).getByText('No champion')).toBeVisible();
  }, 20000);

  it('shows legality per mode; a tap on a not legal badge shows the first reasons', async () => {
    withDecks();
    await openPage();
    await list();
    const legal = item('Riven tournament');
    expect(within(legal).getByText('1v1: Legal')).toBeVisible();
    expect(within(legal).getByText('2v2: Legal')).toBeVisible();
    expect(within(legal).queryByRole('button', { name: /Legal/ })).toBeNull();

    const riven = item('Riven, The Exile');
    const twoVsTwo = within(riven).getByRole('button', { name: '2v2: Not legal' });
    expect(twoVsTwo).toHaveAttribute('aria-expanded', 'false');
    await userEvent.click(twoVsTwo);
    expect(twoVsTwo).toHaveAttribute('aria-expanded', 'true');
    const reasons = within(riven).getByRole('list', { name: 'Why it is not legal in 2v2' });
    expect(
      within(reasons)
        .getAllByRole('listitem')
        .map((li) => li.textContent),
    ).toEqual(['Sideboard size', 'A banned card']);
    await userEvent.click(twoVsTwo);
    expect(within(riven).queryByRole('list', { name: 'Why it is not legal in 2v2' })).toBeNull();

    // more than three reasons: the first three and how many more
    const draft = item('Draft ideas');
    await userEvent.click(within(draft).getByRole('button', { name: '1v1: Not legal' }));
    const draftReasons = within(draft).getByRole('list', { name: 'Why it is not legal in 1v1' });
    expect(
      within(draftReasons)
        .getAllByRole('listitem')
        .map((li) => li.textContent),
    ).toEqual(['No legend', 'No champion', 'Main deck size', 'And 3 more']);
  }, 20000);

  it('the nav entry opens the decks in the app and the classic page stays linked', async () => {
    withDecks();
    signedIn();
    await renderApp({ path: '/', width: 1280 });
    const links = await screen.findAllByRole('link', { name: /Decks/ }, LONG);
    expect(links.length).toBeGreaterThan(0);
    for (const link of links) expect(link).toHaveAttribute('href', '/riftbound/app/decks');
    await userEvent.click(links[0]);
    await list();
    expect(screen.getByRole('link', { name: 'Classic version' })).toHaveAttribute(
      'href',
      '/riftbound/deck',
    );
  }, 20000);

  it('empty: says so, with New deck and Import', async () => {
    withDecks([]);
    await openPage();
    expect(await screen.findByRole('heading', { name: 'No decks yet' }, LONG)).toBeVisible();
    expect(screen.getByRole('button', { name: 'New deck' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Import' })).toBeEnabled();
  }, 20000);

  it('New deck: creates it and opens it; a taken name stays in the dialog', async () => {
    const created = deckDetail({ id: 50, name: 'Fresh' }, emptyContent);
    withDecks(deckList, [created]);
    let calls = 0;
    server.use(
      http.post(`${API}/decks`, () => {
        calls += 1;
        return calls === 1
          ? failure(409, { error: 'Conflict', code: 'already_exists' })
          : ok(created, 201);
      }),
    );
    const sent = recordDeckRequests();
    const { where } = await openPage();
    await list();
    await userEvent.click(screen.getByRole('button', { name: 'New deck' }));
    const dialog = await screen.findByRole('dialog', { name: 'New deck' });
    await userEvent.click(within(dialog).getByRole('button', { name: 'Create' }));
    expect(within(dialog).getByText('Enter a name.')).toBeVisible();
    await userEvent.type(within(dialog).getByRole('textbox', { name: 'Name' }), 'Fresh');
    await userEvent.selectOptions(within(dialog).getByRole('combobox', { name: 'Mode' }), '2v2');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Create' }));
    expect(
      await within(dialog).findByText('You already have a deck with this name.', {}, LONG),
    ).toBeVisible();
    await userEvent.click(within(dialog).getByRole('button', { name: 'Create' }));
    await waitFor(() => expect(where()).toBe('/decks/50'), LONG);
    expect(writes(sent).at(-1)).toMatchObject({
      method: 'POST',
      path: '/decks',
      body: { name: 'Fresh', mode: '2v2' },
    });
    expect(await screen.findByRole('heading', { level: 1, name: 'Fresh' }, LONG)).toBeVisible();
  }, 30000);

  it('Import: one button and no Preview; a clean text imports in one press', async () => {
    withDecks(deckList, [rivenDeck]);
    server.use(
      http.post(`${API}/decks/import/preview`, () => ok(clean)),
      http.post(`${API}/decks/import`, () => ok({ ...rivenDeck, warnings: [] }, 201)),
    );
    const sent = recordDeckRequests();
    const { where } = await openPage();
    const dialog = await openImport();
    expect(within(dialog).queryByRole('button', { name: 'Preview' })).toBeNull();
    const submit = within(dialog).getByRole('button', { name: 'Import deck' });
    await userEvent.click(submit);
    expect(within(dialog).getByText('Paste the deck text.')).toBeVisible();
    expect(writes(sent)).toEqual([]);

    await userEvent.type(textbox(dialog), 'Legend:{Enter}1 Riven, The Exile [[RAD-149]');
    await userEvent.type(within(dialog).getByRole('textbox', { name: 'Name (optional)' }), 'Cup');
    await userEvent.click(submit);
    await waitFor(() => expect(where()).toBe('/decks/41'), LONG);
    const text = 'Legend:\n1 Riven, The Exile [RAD-149]';
    expect(writes(sent).map((r) => [r.path, r.body])).toEqual([
      ['/decks/import/preview', { text }],
      ['/decks/import', { text, mode: '1v1', name: 'Cup' }],
    ]);
    expect((await screen.findAllByText('Deck imported.', {}, LONG)).length).toBeGreaterThan(0);
  }, 30000);

  it('Import: a text with problems stops at the first press and shows them; a second press imports', async () => {
    withDecks(deckList, [rivenDeck]);
    server.use(
      http.post(`${API}/decks/import/preview`, () => ok(withProblems)),
      http.post(`${API}/decks/import`, () => ok({ ...rivenDeck, warnings: [{}] }, 201)),
    );
    const sent = recordDeckRequests();
    const { where } = await openPage();
    const dialog = await openImport();
    const panel = within(dialog).getByRole('region', { name: 'Validation' });
    expect(within(panel).getByText('Press Import deck to check the text.')).toBeVisible();
    await userEvent.type(textbox(dialog), 'Legend:{Enter}1 Riven, The Exile');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Import deck' }));

    const anyway = await within(dialog).findByRole('button', { name: 'Import anyway' }, LONG);
    expect(within(dialog).queryByRole('button', { name: 'Import deck' })).toBeNull();
    expect(writes(sent).map((r) => r.path)).toEqual(['/decks/import/preview']);
    expect(where()).toBe('/decks');
    expect(within(panel).getByText('31 lines, 63 copies placed, 2 left out.')).toBeVisible();
    expect(
      within(within(panel).getByRole('list', { name: 'Sections' }))
        .getAllByRole('listitem')
        .map((li) => li.textContent),
    ).toEqual([
      '1/1 legend',
      '1/1 champion',
      '39/39 main deck',
      '3/3 battlefields',
      '12/12 runes',
      '8/10 sideboard cards',
    ]);
    expect(
      within(within(panel).getByRole('list', { name: 'Warnings' }))
        .getAllByRole('listitem')
        .map((li) => li.textContent),
    ).toEqual([
      'Line 4: 2 Mystery Card (card not found: left out)',
      'Line 5: 1 Nope [OGN-998] (OGN-998 not found: left out)',
      'Line 6: 2 Defy [OGN-999] (printing OGN-999 not found: loaded Defy)',
      'Line 7: 1 Gust [OGN-008] (that printing is Astral Heron, not Gust: loaded Astral Heron)',
      'Line 9: 1 Star Spring (Star Spring does not belong in the main deck: kept there)',
      'Discipline: more than 3 copies.',
    ]);
    expect(
      within(panel).getByText('Fix the text, or press Import anyway to load the deck as it is.'),
    ).toBeVisible();

    await userEvent.click(anyway);
    await waitFor(() => expect(where()).toBe('/decks/41'), LONG);
    expect(writes(sent).map((r) => r.path)).toEqual(['/decks/import/preview', '/decks/import']);
    expect(
      (await screen.findAllByText('Deck imported with 1 warning.', {}, LONG)).length,
    ).toBeGreaterThan(0);
  }, 30000);

  it('Import: editing the text resets the button and the next press checks again', async () => {
    withDecks(deckList, [rivenDeck]);
    server.use(http.post(`${API}/decks/import/preview`, () => ok(withProblems)));
    const sent = recordDeckRequests();
    await openPage();
    const dialog = await openImport();
    await userEvent.type(textbox(dialog), '1 Gust');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Import deck' }));
    await within(dialog).findByRole('button', { name: 'Import anyway' }, LONG);

    await userEvent.type(textbox(dialog), 'x');
    const again = within(dialog).getByRole('button', { name: 'Import deck' });
    expect(within(dialog).queryByRole('button', { name: 'Import anyway' })).toBeNull();
    expect(
      within(dialog).getByText('The text changed: press Import deck to check it again.'),
    ).toBeVisible();
    await userEvent.click(again);
    await within(dialog).findByRole('button', { name: 'Import anyway' }, LONG);
    expect(writes(sent).map((r) => [r.path, r.body])).toEqual([
      ['/decks/import/preview', { text: '1 Gust' }],
      ['/decks/import/preview', { text: '1 Gustx' }],
    ]);
  }, 30000);

  it('Import: offline the button is disabled', async () => {
    withDecks();
    await openPage();
    const dialog = await openImport();
    await userEvent.type(textbox(dialog), '1 Gust');
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    window.dispatchEvent(new Event('offline'));
    await waitFor(() =>
      expect(within(dialog).getByRole('button', { name: 'Import deck' })).toBeDisabled(),
    );
    // back online, so the query client of the next tests is not paused
    vi.restoreAllMocks();
    window.dispatchEvent(new Event('online'));
  }, 20000);

  it('Import: the dialog with its validation panel is axe clean', async () => {
    withDecks();
    server.use(http.post(`${API}/decks/import/preview`, () => ok(withProblems)));
    const { container } = await openPage(1280);
    const dialog = await openImport();
    await userEvent.type(textbox(dialog), '1 Gust');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Import deck' }));
    await within(dialog).findByRole('button', { name: 'Import anyway' }, LONG);
    expect(await axe(container)).toHaveNoViolations();
  }, 30000);

  it('loading shows a skeleton', async () => {
    signedIn();
    let answer = () => undefined as void;
    const answered = new Promise<void>((resolve) => (answer = resolve));
    server.use(
      http.get(`${API}/decks`, async () => {
        await answered;
        return ok({ items: deckList });
      }),
    );
    await renderApp({ path: '/decks', width: PHONE });
    expect(await screen.findByText('Loading decks', {}, LONG)).toBeInTheDocument();
    answer();
    await list();
  }, 20000);

  it('error: can be retried', async () => {
    signedIn();
    let calls = 0;
    server.use(
      http.get(`${API}/decks`, () => {
        calls += 1;
        return calls === 1
          ? failure(500, { error: 'Internal Server Error' })
          : ok({ items: deckList });
      }),
    );
    await renderApp({ path: '/decks', width: PHONE });
    expect(await screen.findByText('Your decks could not be loaded.', {}, LONG)).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await list()).toBeVisible();
  }, 20000);

  it('offline: the list still reads and creating is disabled', async () => {
    withDecks();
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    await openPage();
    await list();
    expect(screen.getByText('You need a connection to make changes.')).toBeVisible();
    for (const button of screen.getAllByRole('button', { name: 'New deck' })) {
      expect(button).toBeDisabled();
    }
  }, 20000);

  it('at 1280 px the list keeps one readable column', async () => {
    withDecks();
    await openPage(1280);
    expect(await list()).toBeVisible();
    await waitFor(() => expect(screen.getAllByRole('link', { name: /Riven/ }).length).toBe(2));
  }, 20000);

  it('is axe clean', async () => {
    withDecks();
    const { container } = await openPage();
    await list();
    await userEvent.click(
      within(item('Riven, The Exile')).getByRole('button', { name: '2v2: Not legal' }),
    );
    expect(await axe(container)).toHaveNoViolations();
  }, 30000);
});
