import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { axe } from 'vitest-axe';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { http } from 'msw';
import { API, ok } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';
import { clearToasts } from '@/components/ui/toastStore';
import {
  AHRI,
  BOX,
  EXPANSIONS,
  EXPANSION_PRODUCTS,
  UNNAMED,
  callsTo,
  expansionProductsAnswer,
  matchingApi,
  unmatchedList,
} from '@/test/fixtures/cardmarketMatching';

const LONG = { timeout: 10000 };
const PATH = '/admin/cardmarket/matching';
const LIST = 'Products of the latest load';

/** An expansion Cardmarket gives no name, mapped to the set UNLX. */
const UNLX_EXPANSION = { id: 6567, name: null, set_id: 'UNLX' };
const RUNE = {
  ...AHRI,
  id_product: 9300,
  name: 'Fury Rune',
  expansion: UNLX_EXPANSION,
  low_price: 0.5,
  first_seen_date: null,
  suggestions: [],
};
const SPIRIT_ITEM = {
  ...AHRI,
  id_product: 9301,
  name: 'Spirit Card',
  expansion: { id: 6399, name: 'Spiritforged', set_id: null },
  suggestions: [],
};
const EXPANSION_LIST = [
  ...EXPANSIONS,
  { ...UNNAMED, mapped_set_id: 'UNLX', mapped_set_name: 'Unleashed' },
];

const api = () =>
  matchingApi({
    unmatched: unmatchedList([AHRI, BOX, RUNE, SPIRIT_ITEM]),
    expansions: EXPANSION_LIST,
  });

const rowOf = (list: HTMLElement, name: string) =>
  within(list)
    .getAllByRole('listitem')
    .find((item) => within(item).queryByRole('heading', { name }) !== null)!;

async function openList(user = userEvent.setup()) {
  const rendered = await renderApp({ path: PATH, width: 1280 });
  const list = await screen.findByRole('list', { name: 'Products to link' }, LONG);
  return { ...rendered, list, user };
}

afterEach(() => {
  vi.restoreAllMocks();
  clearToasts();
});

describe('Expansion context of the products to link (CM-i)', () => {
  it('each row names its expansion with the mapped set, "not mapped" or nothing', async () => {
    api();
    const { list } = await openList();
    expect(
      within(rowOf(list, 'Fury Rune')).getByText(
        '#9300 · Single · Riftbound Single · Expansion #6567 (UNLX) · 0.50 €',
      ),
    ).toBeVisible();
    expect(within(rowOf(list, 'Ahri, Alluring')).getByText(/· Origins \(OGN\) ·/)).toBeVisible();
    expect(
      within(rowOf(list, 'Spirit Card')).getByText(/· Spiritforged \(not mapped\) ·/),
    ).toBeVisible();
    // a product without an expansion has no expansion products to show
    expect(within(rowOf(list, 'Origins Booster Box')).queryByRole('button')).toBeNull();
  });

  it('Expansion products opens the products of that expansion and gives focus back', async () => {
    const calls = api();
    const { list, user } = await openList();
    const button = within(rowOf(list, 'Fury Rune')).getByRole('button', {
      name: 'Expansion products for Fury Rune',
    });
    expect(button).toHaveTextContent('Expansion products');
    await user.click(button);
    const dialog = await screen.findByRole('dialog', { name: 'Products of Expansion #6567' });
    const region = within(dialog).getByRole('region', { name: LIST });
    expect(await within(region).findByText('Ahri, Nine-Tailed Fox', {}, LONG)).toBeVisible();
    expect(within(dialog).getByText('Now mapped to Unleashed (UNLX).')).toBeVisible();
    expect(within(dialog).getByRole('radiogroup', { name: 'Kind' })).toBeVisible();
    // the dialog shows the list only: the mapping is done in the Expansions tab
    expect(
      within(dialog).queryByRole('button', { name: /Map to a set|Change the set|new set/ }),
    ).toBeNull();
    expect(callsTo(calls, 'GET', '/expansions/6567/products').length).toBeGreaterThan(0);
    // the expansion row comes from the (cached) expansions list, never a new endpoint
    expect(callsTo(calls, 'GET', '/expansions').length).toBeGreaterThan(0);

    await user.click(within(dialog).getByRole('button', { name: 'Close' }));
    await vi.waitFor(() =>
      expect(screen.queryByRole('dialog', { name: 'Products of Expansion #6567' })).toBeNull(),
    );
    expect(button).toHaveFocus();
  });

  it('offline: Expansion products is disabled with the writes', async () => {
    api();
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    const { list } = await openList();
    expect(
      within(rowOf(list, 'Fury Rune')).getByRole('button', {
        name: 'Expansion products for Fury Rune',
      }),
    ).toBeDisabled();
  });

  it('the link dialog names the expansion and opens its products on top, keeping the search', async () => {
    api();
    const { list, user } = await openList();
    await user.click(
      within(rowOf(list, 'Fury Rune')).getByRole('button', {
        name: 'Choose a card for Fury Rune',
      }),
    );
    const dialog = await screen.findByRole('dialog', { name: 'Link Fury Rune' });
    expect(
      await within(dialog).findByText(
        '#9300 · Riftbound Single · Expansion #6567 (UNLX)',
        {},
        LONG,
      ),
    ).toBeVisible();
    const search = within(dialog).getByRole('textbox', { name: 'Search cards' });
    await user.clear(search);
    await user.type(search, 'Fury');
    const button = within(dialog).getByRole('button', { name: 'Expansion products' });
    await user.click(button);
    const products = await screen.findByRole('dialog', { name: 'Products of Expansion #6567' });
    await within(products).findByText('Ahri, Nine-Tailed Fox', {}, LONG);
    await user.click(within(products).getByRole('button', { name: 'Close' }));
    await vi.waitFor(() =>
      expect(screen.queryByRole('dialog', { name: 'Products of Expansion #6567' })).toBeNull(),
    );
    expect(screen.getByRole('dialog', { name: 'Link Fury Rune' })).toBeVisible();
    expect(within(dialog).getByRole('textbox', { name: 'Search cards' })).toHaveValue('Fury');
    expect(button).toHaveFocus();
  });

  it('the create form names the expansion and keeps what was typed under the products', async () => {
    api();
    const { list, user } = await openList();
    await user.click(
      within(rowOf(list, 'Fury Rune')).getByRole('button', {
        name: 'Create a card for Fury Rune',
      }),
    );
    const dialog = await screen.findByRole('dialog', { name: 'Create a card for Fury Rune' });
    expect(
      within(dialog).getByText('#9300 · Riftbound Single · Expansion #6567 (UNLX)'),
    ).toBeVisible();
    // an unnamed expansion is named by its id in the set hint too
    expect(
      within(dialog).getByText('From the Cardmarket expansion Expansion #6567.'),
    ).toBeVisible();
    const number = within(dialog).getByRole('textbox', { name: /^Number/ });
    await user.type(number, '099');
    const button = within(dialog).getByRole('button', { name: 'Expansion products' });
    await user.click(button);
    const products = await screen.findByRole('dialog', { name: 'Products of Expansion #6567' });
    await within(products).findByText('Ahri, Nine-Tailed Fox', {}, LONG);
    await user.click(within(products).getByRole('button', { name: 'Close' }));
    await vi.waitFor(() =>
      expect(screen.queryByRole('dialog', { name: 'Products of Expansion #6567' })).toBeNull(),
    );
    expect(screen.getByRole('dialog', { name: 'Create a card for Fury Rune' })).toBeVisible();
    expect(within(dialog).getByRole('textbox', { name: /^Number/ })).toHaveValue('099');
    expect(button).toHaveFocus();
  });

  it('an expansion missing from the expansions list still opens with what the row knows', async () => {
    const calls = matchingApi({ unmatched: unmatchedList([RUNE]), expansions: EXPANSIONS });
    const unlx = { ...UNNAMED, mapped_set_id: 'UNLX', mapped_set_name: null };
    server.use(
      http.get(`${API}/admin/cardmarket/expansions/:id/products`, ({ request }) =>
        ok(expansionProductsAnswer(unlx, EXPANSION_PRODUCTS, new URL(request.url).searchParams)),
      ),
    );
    const { list, user } = await openList();
    await user.click(
      within(rowOf(list, 'Fury Rune')).getByRole('button', {
        name: 'Expansion products for Fury Rune',
      }),
    );
    const dialog = await screen.findByRole('dialog', { name: 'Products of Expansion #6567' });
    expect(await within(dialog).findByText('Ahri, Nine-Tailed Fox', {}, LONG)).toBeVisible();
    // the set the row names, without a set name the list could give
    expect(within(dialog).getByText('Now mapped to UNLX (not a set).')).toBeVisible();
    expect(callsTo(calls, 'GET', '/expansions').length).toBeGreaterThan(0);
  });

  it('has no axe violations (row and dialog header)', async () => {
    api();
    const { list, user } = await openList();
    expect(await axe(rowOf(list, 'Fury Rune'))).toHaveNoViolations();
    await user.click(
      within(rowOf(list, 'Fury Rune')).getByRole('button', {
        name: 'Choose a card for Fury Rune',
      }),
    );
    const dialog = await screen.findByRole('dialog', { name: 'Link Fury Rune' });
    await within(dialog).findByText(/Expansion #6567 \(UNLX\)/, {}, LONG);
    expect(await axe(dialog)).toHaveNoViolations();
  }, 20000);
});
