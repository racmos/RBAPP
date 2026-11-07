import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { API, ok } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';
import { clearToasts } from '@/components/ui/toastStore';
import { PREVIEW, callsTo, linkList, matchingApi } from '@/test/fixtures/cardmarketMatching';

const LONG = { timeout: 10000 };
const PATH = '/admin/cardmarket/matching';

async function openTab(tab: string, search = '') {
  const rendered = await renderApp({ path: `${PATH}?tab=${tab}${search}`, width: 1280 });
  await screen.findByRole('heading', { name: 'Matching workbench', level: 1 }, LONG);
  return rendered;
}

const rowOf = (table: HTMLElement, text: string) =>
  within(table)
    .getAllByRole('row')
    .find((row) => within(row).queryByText(text) !== null)!;

afterEach(() => {
  vi.restoreAllMocks();
  // the toast store outlives a render: an Undo left by one test must not reach the next
  clearToasts();
});

describe('Linked tab (CM-b)', () => {
  it('lists every link with product, card, slot, price and match type', async () => {
    const calls = matchingApi();
    await openTab('linked');
    const table = await screen.findByRole('table', { name: 'Cardmarket links' }, LONG);
    expect(within(table).getAllByRole('row')).toHaveLength(3);
    const first = within(rowOf(table, 'Product 601')).getAllByRole('cell');
    expect(first[0]).toHaveTextContent('#601');
    expect(first[1]).toHaveTextContent('OGN-066');
    expect(first[1]).toHaveTextContent('Card 066');
    expect(first[2]).toHaveTextContent('N');
    expect(first[3]).toHaveTextContent('1.50 €');
    expect(first[4]).toHaveTextContent('Auto');
    const second = within(rowOf(table, 'Product 602')).getAllByRole('cell');
    expect(second[0]).toHaveTextContent('Not in the latest load');
    expect(second[2]).toHaveTextContent('None');
    expect(second[3]).toHaveTextContent('—');
    expect(second[4]).toHaveTextContent('Manual');
    expect(screen.getByText('2 links')).toBeVisible();
    expect(callsTo(calls, 'GET', '/links')[0]!.search.toString()).toBe('per_page=50');
  });

  it('the filters send q, set, foil and match_type', async () => {
    const calls = matchingApi();
    const user = userEvent.setup();
    await openTab('linked');
    await screen.findByRole('table', { name: 'Cardmarket links' }, LONG);
    await user.type(screen.getByRole('textbox', { name: 'Search links' }), 'ahri{Enter}');
    await user.type(screen.getByRole('textbox', { name: 'Set' }), 'OGN{Enter}');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Slot' }), 'None');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Match' }), 'Manual');
    await vi.waitFor(() =>
      expect(callsTo(calls, 'GET', '/links').at(-1)!.search.toString()).toBe(
        'q=ahri&set=OGN&foil=none&match_type=manual&per_page=50',
      ),
    );
  });

  it('Unlink asks, removes the link and Undo posts it back', async () => {
    const calls = matchingApi();
    const user = userEvent.setup();
    await openTab('linked');
    const table = await screen.findByRole('table', { name: 'Cardmarket links' }, LONG);
    await user.click(
      within(rowOf(table, 'Product 601')).getByRole('button', { name: 'Unlink Product 601' }),
    );
    const dialog = await screen.findByRole('dialog', { name: 'Unlink Product 601?' });
    await user.click(within(dialog).getByRole('button', { name: 'Unlink' }));
    expect((await screen.findAllByText('Unlinked Product 601.')).length).toBeGreaterThan(0);
    expect(callsTo(calls, 'DELETE', '/links/601')).toHaveLength(1);
    await user.click(screen.getByRole('button', { name: 'Undo' }));
    await vi.waitFor(() =>
      expect(callsTo(calls, 'POST', '/links').map((call) => call.body)).toEqual([
        { id_product: 601, card: { set_id: 'OGN', card_id: '066' }, foil: 'N' },
      ]),
    );
  });

  it('Unlink cancelled sends nothing', async () => {
    const calls = matchingApi();
    const user = userEvent.setup();
    await openTab('linked');
    const table = await screen.findByRole('table', { name: 'Cardmarket links' }, LONG);
    await user.click(
      within(rowOf(table, 'Product 601')).getByRole('button', { name: 'Unlink Product 601' }),
    );
    const dialog = await screen.findByRole('dialog', { name: 'Unlink Product 601?' });
    await user.click(within(dialog).getByRole('button', { name: 'Cancel' }));
    expect(callsTo(calls, 'DELETE', /^\/links\//)).toHaveLength(0);
  });

  it('Relink opens the candidates and PUTs the new card, showing previous and new', async () => {
    const calls = matchingApi();
    const user = userEvent.setup();
    await openTab('linked');
    const table = await screen.findByRole('table', { name: 'Cardmarket links' }, LONG);
    await user.click(
      within(rowOf(table, 'Product 601')).getByRole('button', { name: 'Relink Product 601' }),
    );
    const dialog = await screen.findByRole('dialog', { name: 'Relink Product 601' });
    expect(within(dialog).getByText('Linked now to OGN-066, slot N.')).toBeVisible();
    const cards = within(
      await within(dialog).findByRole('list', { name: 'Cards' }, LONG),
    ).getAllByRole('listitem');
    await user.click(within(cards[1]!).getByRole('button', { name: 'Relink to OGN-299' }));
    await vi.waitFor(() =>
      expect(callsTo(calls, 'PUT', '/links/601').map((call) => call.body)).toEqual([
        { card: { set_id: 'OGN', card_id: '299' }, foil: null },
      ]),
    );
    expect(
      (await screen.findAllByText('Relinked Product 601: OGN-066, slot N → OGN-299, slot None.'))
        .length,
    ).toBeGreaterThan(0);
    // Undo puts the previous target back
    await user.click(screen.getByRole('button', { name: 'Undo' }));
    await vi.waitFor(() =>
      expect(callsTo(calls, 'PUT', '/links/601').at(-1)!.body).toEqual({
        card: { set_id: 'OGN', card_id: '066' },
        foil: 'N',
      }),
    );
  });

  it('an empty list says so', async () => {
    matchingApi({ links: linkList([]) });
    await openTab('linked');
    expect(await screen.findByRole('heading', { name: 'No links' }, LONG)).toBeVisible();
  });
});

describe('Conflicts tab (CM-b)', () => {
  it('asks for conflicts=true and groups the products of each slot', async () => {
    const calls = matchingApi();
    const user = userEvent.setup();
    await openTab('conflicts');
    const groups = await screen.findByRole('list', { name: 'Conflict slots' }, LONG);
    const slots = within(groups).getAllByRole('listitem');
    expect(slots).toHaveLength(2);
    expect(
      within(slots[0]!).getByRole('heading', { name: 'OGN-010 Card 010, slot N' }),
    ).toBeVisible();
    expect(within(slots[0]!).getByText('Product 701')).toBeVisible();
    expect(within(slots[0]!).getByText('Product 702')).toBeVisible();
    expect(
      within(slots[1]!).getByRole('heading', { name: 'OGN-020 Card 020, slot None' }),
    ).toBeVisible();
    expect(screen.getByText('Conflict slots: 2')).toBeVisible();
    expect(callsTo(calls, 'GET', '/links')[0]!.search.toString()).toBe(
      'conflicts=true&per_page=50',
    );
    await user.click(within(slots[0]!).getByRole('button', { name: 'Unlink Product 702' }));
    const dialog = await screen.findByRole('dialog', { name: 'Unlink Product 702?' });
    await user.click(within(dialog).getByRole('button', { name: 'Unlink' }));
    await vi.waitFor(() => expect(callsTo(calls, 'DELETE', '/links/702')).toHaveLength(1));
  });

  it('no conflicts says so', async () => {
    matchingApi({ conflicts: linkList([]) });
    await openTab('conflicts');
    expect(await screen.findByRole('heading', { name: 'No conflicts' }, LONG)).toBeVisible();
  });
});

describe('Ignored tab (CM-b)', () => {
  it('lists the ignored products; Restore removes that name and Undo ignores it again', async () => {
    const calls = matchingApi();
    const user = userEvent.setup();
    await openTab('ignored');
    const table = await screen.findByRole('table', { name: 'Ignored products' }, LONG);
    const cells = within(rowOf(table, 'Token Pack')).getAllByRole('cell');
    expect(cells[1]).toHaveTextContent('801');
    expect(cells[2]).toHaveTextContent('1.50 €');
    await user.click(within(table).getByRole('button', { name: 'Restore Token Pack' }));
    expect((await screen.findAllByText('Restored Token Pack.')).length).toBeGreaterThan(0);
    const restore = callsTo(calls, 'DELETE', '/ignored/801');
    expect(restore).toHaveLength(1);
    expect(restore[0]!.search.get('name')).toBe('Token Pack');
    await user.click(screen.getByRole('button', { name: 'Undo' }));
    await vi.waitFor(() =>
      expect(callsTo(calls, 'POST', '/ignored').map((call) => call.body)).toEqual([
        { id_product: 801, name: 'Token Pack' },
      ]),
    );
  });

  it('an empty list says so', async () => {
    matchingApi({ ignored: [] });
    await openTab('ignored');
    expect(await screen.findByRole('heading', { name: 'Nothing ignored' }, LONG)).toBeVisible();
  });
});

describe('Auto-match tab (CM-b)', () => {
  it('previews the counts and the proposed links, then applies after confirming', async () => {
    const calls = matchingApi();
    const user = userEvent.setup();
    await openTab('auto');
    const apply = await screen.findByRole('button', { name: 'Apply clear cases' }, LONG);
    expect(apply).toBeDisabled();
    await user.click(screen.getByRole('button', { name: 'Preview' }));
    const result = await screen.findByRole('region', { name: 'Preview' });
    expect(within(result).getByText('Proposed').nextSibling).toHaveTextContent('5');
    expect(within(result).getByText('Clear').nextSibling).toHaveTextContent('3');
    expect(within(result).getByText('Doubtful').nextSibling).toHaveTextContent('2');
    const table = within(result).getByRole('table', { name: 'Proposed links' });
    expect(within(table).getAllByText('Garen, Rugged')).toHaveLength(2);
    expect(within(table).getByText('OGN-100')).toBeVisible();
    expect(callsTo(calls, 'POST', '/auto-match/preview')).toHaveLength(1);

    expect(apply).toBeEnabled();
    await user.click(apply);
    const dialog = await screen.findByRole('dialog', { name: 'Link the 3 clear cases?' });
    await user.click(within(dialog).getByRole('button', { name: 'Apply clear cases' }));
    expect(await screen.findByText('Linked 3. Clear cases left: 0. Doubtful: 2.')).toBeVisible();
    expect(callsTo(calls, 'POST', '/auto-match/apply').map((call) => call.body)).toEqual([{}]);
  });

  it('Apply stays disabled when the preview has no clear case', async () => {
    matchingApi();
    server.use(
      http.post(`${API}/admin/cardmarket/auto-match/preview`, () =>
        ok({ ...PREVIEW, proposed: 2, clear: 0, links: [] }),
      ),
    );
    const user = userEvent.setup();
    await openTab('auto');
    await user.click(await screen.findByRole('button', { name: 'Preview' }, LONG));
    await screen.findByRole('region', { name: 'Preview' });
    expect(screen.getByText('No clear cases to link.')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Apply clear cases' })).toBeDisabled();
  });

  it('lists the review with reason counts, filters by reason and opens the link dialog', async () => {
    const calls = matchingApi();
    const user = userEvent.setup();
    await openTab('auto');
    const review = await screen.findByRole('list', { name: 'Products to review' }, LONG);
    const item = within(review).getAllByRole('listitem')[0]!;
    expect(within(item).getByText('Ahri, Alluring')).toBeVisible();
    expect(within(item).getByText('Several candidates')).toBeVisible();
    expect(within(item).getByText(/OGN-066 Ahri, Alluring/)).toBeVisible();
    const reason = screen.getByRole('combobox', { name: 'Reason' });
    expect(within(reason).getByRole('option', { name: 'Several candidates (1)' })).toBeVisible();
    expect(within(reason).getByRole('option', { name: 'No candidates (3)' })).toBeVisible();
    await user.selectOptions(reason, 'No candidates (3)');
    await vi.waitFor(() =>
      expect(callsTo(calls, 'GET', '/review').at(-1)!.search.toString()).toBe(
        'reason=no_candidates&per_page=50',
      ),
    );
    await user.click(
      within(item).getByRole('button', { name: 'Choose a card for Ahri, Alluring' }),
    );
    const dialog = await screen.findByRole('dialog', { name: 'Link Ahri, Alluring' });
    expect(await within(dialog).findByRole('list', { name: 'Cards' }, LONG)).toBeVisible();
  });
});
