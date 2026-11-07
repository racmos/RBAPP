import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { API, failure, ok } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';
import { clearToasts } from '@/components/ui/toastStore';
import {
  AHRI,
  CANDIDATES,
  callsTo,
  matchingApi,
  unmatchedList,
} from '@/test/fixtures/cardmarketMatching';

const LONG = { timeout: 10000 };
const PATH = '/admin/cardmarket/matching';

async function openList(path = PATH) {
  const rendered = await renderApp({ path, width: 1280 });
  const list = await screen.findByRole('list', { name: 'Products to link' }, LONG);
  return { ...rendered, list };
}

const rowOf = (list: HTMLElement, name: string) =>
  within(list)
    .getAllByRole('listitem')
    .find((item) => within(item).queryByRole('heading', { name }) !== null)!;

async function openDialog(user = userEvent.setup()) {
  const { list, ...rest } = await openList();
  await user.click(
    within(rowOf(list, 'Ahri, Alluring')).getByRole('button', {
      name: 'Choose a card for Ahri, Alluring',
    }),
  );
  const dialog = await screen.findByRole('dialog', { name: 'Link Ahri, Alluring' });
  await within(dialog).findByRole('list', { name: 'Cards' }, LONG);
  return { ...rest, list, dialog, user };
}

afterEach(() => {
  vi.restoreAllMocks();
  // the toast store outlives a render: an Undo left by one test must not reach the next
  clearToasts();
});

describe('To link list (CM-b)', () => {
  it('shows each product with its facts, suggestions and actions', async () => {
    const calls = matchingApi();
    const { list } = await openList();
    expect(within(list).getAllByRole('listitem')).toHaveLength(3);
    const ahri = rowOf(list, 'Ahri, Alluring');
    expect(within(ahri).getByText(/#501/)).toBeVisible();
    expect(within(ahri).getByText(/Riftbound Single/)).toBeVisible();
    expect(within(ahri).getByText(/Origins/)).toBeVisible();
    expect(within(ahri).getByText(/0\.12 €/)).toBeVisible();
    expect(within(ahri).getByText(/First seen 1 Nov 2026/)).toBeVisible();
    expect(
      within(ahri).getByRole('button', { name: 'Link to OGN-066 Ahri, Alluring, slot N (1.00)' }),
    ).toBeEnabled();
    expect(
      within(ahri).getByRole('button', { name: 'Link to OGS-005 Ahri, Alluring (0.90)' }),
    ).toBeEnabled();
    // every slot of OGN-299 is linked already
    expect(
      within(ahri).getByRole('button', { name: 'Link to OGN-299 Ahri, Alluring (0.90)' }),
    ).toBeDisabled();
    expect(within(ahri).getByRole('button', { name: 'Ignore Ahri, Alluring' })).toBeEnabled();

    const box = rowOf(list, 'Origins Booster Box');
    expect(within(box).getByText('Linked by identity')).toBeVisible();
    expect(within(box).queryByRole('button')).toBeNull();

    const mystery = rowOf(list, 'Mystery Card');
    expect(within(mystery).getByText(/—/)).toBeVisible();
    expect(within(mystery).getByText('No suggestions.')).toBeVisible();
    expect(screen.getByText('3 products')).toBeVisible();
    expect(callsTo(calls, 'GET', '/unmatched')[0]!.search.toString()).toBe('per_page=50');
  });

  it('search and type filters send q and type', async () => {
    const calls = matchingApi();
    const user = userEvent.setup();
    const { where } = await openList();
    await user.type(screen.getByRole('textbox', { name: 'Search products' }), 'ahri{Enter}');
    await vi.waitFor(() =>
      expect(callsTo(calls, 'GET', '/unmatched').at(-1)!.search.get('q')).toBe('ahri'),
    );
    await user.selectOptions(screen.getByRole('combobox', { name: 'Type' }), 'Sealed products');
    await vi.waitFor(() =>
      expect(callsTo(calls, 'GET', '/unmatched').at(-1)!.search.toString()).toBe(
        'q=ahri&type=nonsingle&per_page=50',
      ),
    );
    expect(where()).toBe(`${PATH}?q=ahri&type=nonsingle`);
  });

  it('pages with the allowed page size', async () => {
    const calls = matchingApi({ unmatched: unmatchedList([AHRI], 120) });
    const user = userEvent.setup();
    await openList();
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await vi.waitFor(() =>
      expect(callsTo(calls, 'GET', '/unmatched').at(-1)!.search.toString()).toBe(
        'page=2&per_page=50',
      ),
    );
  });

  it('an empty list says so', async () => {
    matchingApi({ unmatched: unmatchedList([]) });
    await renderApp({ path: PATH, width: 1280 });
    expect(await screen.findByRole('heading', { name: 'Nothing to link' }, LONG)).toBeVisible();
  });

  it('a suggestion links with the exact body and offers an undo that unlinks', async () => {
    const calls = matchingApi();
    const user = userEvent.setup();
    const { list } = await openList();
    await user.click(
      within(rowOf(list, 'Ahri, Alluring')).getByRole('button', {
        name: 'Link to OGN-066 Ahri, Alluring, slot N (1.00)',
      }),
    );
    expect(
      (await screen.findAllByText('Linked Ahri, Alluring to OGN-066.')).length,
    ).toBeGreaterThan(0);
    expect(callsTo(calls, 'POST', '/links').map((call) => call.body)).toEqual([
      { id_product: 501, card: { set_id: 'OGN', card_id: '066' }, foil: 'N' },
    ]);
    // the list and the counters reload
    await vi.waitFor(() => expect(callsTo(calls, 'GET', '/unmatched').length).toBeGreaterThan(1));
    await user.click(screen.getByRole('button', { name: 'Undo' }));
    await vi.waitFor(() => expect(callsTo(calls, 'DELETE', '/links/501')).toHaveLength(1));
  });

  it('a one-slot suggestion sends foil null', async () => {
    const calls = matchingApi();
    const user = userEvent.setup();
    const { list } = await openList();
    await user.click(
      within(rowOf(list, 'Ahri, Alluring')).getByRole('button', {
        name: 'Link to OGS-005 Ahri, Alluring (0.90)',
      }),
    );
    await vi.waitFor(() =>
      expect(callsTo(calls, 'POST', '/links').map((call) => call.body)).toEqual([
        { id_product: 501, card: { set_id: 'OGS', card_id: '005' }, foil: null },
      ]),
    );
  });

  it('Ignore adds the product with its name; Undo restores it', async () => {
    const calls = matchingApi();
    const user = userEvent.setup();
    const { list } = await openList();
    await user.click(
      within(rowOf(list, 'Ahri, Alluring')).getByRole('button', { name: 'Ignore Ahri, Alluring' }),
    );
    expect((await screen.findAllByText('Ignored Ahri, Alluring.')).length).toBeGreaterThan(0);
    expect(callsTo(calls, 'POST', '/ignored').map((call) => call.body)).toEqual([
      { id_product: 501, name: 'Ahri, Alluring' },
    ]);
    await user.click(screen.getByRole('button', { name: 'Undo' }));
    await vi.waitFor(() => {
      const undo = callsTo(calls, 'DELETE', '/ignored/501');
      expect(undo).toHaveLength(1);
      expect(undo[0]!.search.get('name')).toBe('Ahri, Alluring');
    });
  });

  it('offline: every write is disabled', async () => {
    matchingApi();
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    const { list } = await openList();
    const ahri = rowOf(list, 'Ahri, Alluring');
    for (const button of within(ahri).getAllByRole('button')) expect(button).toBeDisabled();
  });

  it('a failed link shows the translated error', async () => {
    matchingApi();
    server.use(
      http.post(`${API}/admin/cardmarket/links`, () =>
        failure(409, {
          message: 'Unlink it first',
          code: 'already_exists',
          params: { field: 'id_product', set_id: 'OGN', card_id: '001', foil: 'N' },
        }),
      ),
    );
    const user = userEvent.setup();
    const { list } = await openList();
    await user.click(
      within(rowOf(list, 'Ahri, Alluring')).getByRole('button', {
        name: 'Link to OGN-066 Ahri, Alluring, slot N (1.00)',
      }),
    );
    expect(
      (await screen.findAllByText('This product is already linked to OGN-001, slot N.')).length,
    ).toBeGreaterThan(0);
  });
});

describe('Link dialog (CM-b)', () => {
  it('searches with the product name and shows image, set, number, rarity and links', async () => {
    const calls = matchingApi();
    const { dialog } = await openDialog();
    const search = within(dialog).getByRole('textbox', { name: 'Search cards' });
    expect(search).toHaveValue('Ahri, Alluring');
    expect(callsTo(calls, 'GET', '/unmatched/501/candidates')[0]!.search.get('q')).toBe(
      'Ahri, Alluring',
    );
    const cards = within(within(dialog).getByRole('list', { name: 'Cards' })).getAllByRole(
      'listitem',
    );
    expect(cards).toHaveLength(2);
    expect(within(cards[0]!).getByRole('img', { name: 'Ahri, Alluring' })).toHaveAttribute(
      'src',
      '/riftbound/media/cards/ogn/066.webp',
    );
    expect(within(cards[0]!).getByText('OGN-066')).toBeVisible();
    expect(within(cards[0]!).getByText(/Common/)).toBeVisible();
    expect(within(cards[1]!).getByText(/Showcase/)).toBeVisible();
    expect(within(cards[1]!).getByText('Linked to #900, slot None')).toBeVisible();
    expect(within(dialog).getByText(/normal \(N\) and a foil \(S\)/)).toBeVisible();
    // the slot follows the rarity: a common has N and S, a showcase one slot
    expect(within(cards[0]!).getByRole('combobox', { name: 'Slot for OGN-066' })).toHaveValue('N');
    expect(within(cards[1]!).getByRole('combobox', { name: 'Slot for OGN-299' })).toHaveValue('');
  });

  it('asks for two characters before searching; empty shows the suggested cards', async () => {
    const calls = matchingApi();
    const { dialog, user } = await openDialog();
    const search = within(dialog).getByRole('textbox', { name: 'Search cards' });
    const before = callsTo(calls, 'GET', '/unmatched/501/candidates').length;
    await user.clear(search);
    await user.type(search, 'a');
    expect(await within(dialog).findByText('Type at least 2 characters.')).toBeVisible();
    await new Promise((resolve) => setTimeout(resolve, 500));
    const afterOne = callsTo(calls, 'GET', '/unmatched/501/candidates');
    expect(afterOne.every((call) => call.search.get('q') !== 'a')).toBe(true);
    await user.type(search, 'h');
    await vi.waitFor(() =>
      expect(callsTo(calls, 'GET', '/unmatched/501/candidates').at(-1)!.search.get('q')).toBe('ah'),
    );
    await user.clear(search);
    await vi.waitFor(() =>
      expect(callsTo(calls, 'GET', '/unmatched/501/candidates').at(-1)!.search.has('q')).toBe(
        false,
      ),
    );
    expect(callsTo(calls, 'GET', '/unmatched/501/candidates').length).toBeGreaterThan(before);
  });

  it('links the chosen card with the chosen slot', async () => {
    const calls = matchingApi();
    const { dialog, user } = await openDialog();
    const cards = within(within(dialog).getByRole('list', { name: 'Cards' })).getAllByRole(
      'listitem',
    );
    await user.selectOptions(
      within(cards[0]!).getByRole('combobox', { name: 'Slot for OGN-066' }),
      'S (foil)',
    );
    await user.click(within(cards[0]!).getByRole('button', { name: 'Link to OGN-066' }));
    await vi.waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(callsTo(calls, 'POST', '/links').map((call) => call.body)).toEqual([
      { id_product: 501, card: { set_id: 'OGN', card_id: '066' }, foil: 'S' },
    ]);
    expect(
      (await screen.findAllByText('Linked Ahri, Alluring to OGN-066.')).length,
    ).toBeGreaterThan(0);
  });

  it('a taken slot shows who holds it and opens that link, never relinking it', async () => {
    const calls = matchingApi();
    server.use(
      http.post(`${API}/admin/cardmarket/links`, () =>
        failure(409, {
          message: 'That card slot is linked to another product.',
          code: 'already_exists',
          params: { field: 'card', linked_id_product: 900 },
        }),
      ),
    );
    const { dialog, user, where } = await openDialog();
    const cards = within(within(dialog).getByRole('list', { name: 'Cards' })).getAllByRole(
      'listitem',
    );
    await user.click(within(cards[1]!).getByRole('button', { name: 'Link to OGN-299' }));
    const alert = await within(dialog).findByRole('alert');
    expect(alert).toHaveTextContent(
      'That card slot is linked to another product. Cardmarket product #900 holds OGN-299, slot None.',
    );
    await user.click(within(alert).getByRole('button', { name: 'Open the link of #900' }));
    await vi.waitFor(() => expect(where()).toBe(`${PATH}?tab=linked&q=900`));
    expect(callsTo(calls, 'PUT', /^\/links\//)).toHaveLength(0);
  });

  it('a product linked already can be relinked here instead', async () => {
    const calls = matchingApi();
    server.use(
      http.post(`${API}/admin/cardmarket/links`, () =>
        failure(409, {
          message: 'Cardmarket product 501 is already linked. Unlink it first.',
          code: 'already_exists',
          params: { field: 'id_product', set_id: 'OGN', card_id: '001', foil: 'N' },
        }),
      ),
    );
    const { dialog, user } = await openDialog();
    const cards = within(within(dialog).getByRole('list', { name: 'Cards' })).getAllByRole(
      'listitem',
    );
    await user.click(within(cards[0]!).getByRole('button', { name: 'Link to OGN-066' }));
    const alert = await within(dialog).findByRole('alert');
    expect(alert).toHaveTextContent('This product is already linked to OGN-001, slot N.');
    await user.click(within(alert).getByRole('button', { name: 'Relink here instead' }));
    await vi.waitFor(() =>
      expect(callsTo(calls, 'PUT', '/links/501').map((call) => call.body)).toEqual([
        { card: { set_id: 'OGN', card_id: '066' }, foil: 'N' },
      ]),
    );
  });

  it('a candidates failure offers a retry', async () => {
    matchingApi();
    let calls = 0;
    server.use(
      http.get(`${API}/admin/cardmarket/unmatched/:id/candidates`, () => {
        calls += 1;
        return calls === 1 ? failure(500) : ok(CANDIDATES);
      }),
    );
    const user = userEvent.setup();
    const { list } = await openList();
    await user.click(
      within(rowOf(list, 'Ahri, Alluring')).getByRole('button', {
        name: 'Choose a card for Ahri, Alluring',
      }),
    );
    const dialog = await screen.findByRole('dialog', { name: 'Link Ahri, Alluring' });
    await user.click(await within(dialog).findByRole('button', { name: 'Retry' }, LONG));
    expect(await within(dialog).findByRole('list', { name: 'Cards' })).toBeVisible();
  });
});
