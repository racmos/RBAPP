import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { axe } from 'vitest-axe';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { API, failure } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';
import { clearToasts } from '@/components/ui/toastStore';
import {
  PROMO_ITEMS,
  callsTo,
  matchingApi,
  promoItem,
  promoPlan,
} from '@/test/fixtures/cardmarketMatching';

const LONG = { timeout: 10000 };
const PATH = '/admin/cardmarket/matching';
const BASE = `${API}/admin/cardmarket`;

async function openTab(search = '&set=OGNX', width = 1280) {
  const rendered = await renderApp({ path: `${PATH}?tab=missing${search}`, width });
  await screen.findByRole('combobox', { name: 'Promo set' }, LONG);
  return rendered;
}

async function openTable() {
  const rendered = await openTab();
  const table = await screen.findByRole('table', { name: 'Missing promo cards' }, LONG);
  return { ...rendered, table };
}

const rowOf = (table: HTMLElement, text: string) =>
  within(table)
    .getAllByRole('row')
    .find((row) => within(row).queryByText(text) !== null)!;

const box = (name: string, id: number) =>
  screen.getByRole('checkbox', { name: `Create the promo card of ${name} (#${id})` });

afterEach(() => {
  vi.restoreAllMocks();
  clearToasts();
});

describe('Missing cards tab (CM-h)', () => {
  it('is the seventh tab and asks for a promo set before listing anything', async () => {
    const calls = matchingApi();
    const user = userEvent.setup();
    const { where } = await openTab('');
    expect(screen.getByRole('tab', { name: 'Missing cards' })).toHaveAttribute(
      'aria-selected',
      'true',
    );
    const select = screen.getByRole('combobox', { name: 'Promo set' });
    expect(
      within(select)
        .getAllByRole('option')
        .map((option) => option.textContent),
    ).toEqual([
      'Choose a promo set',
      'Origins Promos (OGNX), 2 cards to create',
      'Plated Legends (PLAT), 1 card to create',
      'Spiritforged Promos (SFDX), nothing to create',
    ]);
    expect(screen.getByText(/OGN-035 becomes OGNX-035/)).toBeVisible();
    expect(callsTo(calls, 'GET', '/promo-cards').map((call) => call.search.toString())).toEqual([
      '',
    ]);
    await user.selectOptions(select, 'OGNX');
    await vi.waitFor(() => expect(where()).toBe(`${PATH}?tab=missing&set=OGNX`));
    await screen.findByRole('table', { name: 'Missing promo cards' }, LONG);
    expect(callsTo(calls, 'GET', '/promo-cards').at(-1)!.search.toString()).toBe('set=OGNX');
  });

  it('lists every product with its base card, proposed card and status', async () => {
    matchingApi();
    const { table } = await openTable();
    const header = within(table).getAllByRole('columnheader');
    expect(header.map((cell) => cell.textContent)).toEqual([
      'Create',
      'Cardmarket product',
      'Price',
      'Base card',
      'Promo card',
      'Status',
    ]);
    const spark = within(rowOf(table, 'Little Spark (Foil)')).getAllByRole('cell');
    expect(spark.map((cell) => cell.textContent)).toEqual([
      'Create the promo card of Little Spark (#1002)',
      'Little Spark#1002 · 0.50 € · slot NLittle Spark (Foil)#1003 · 2.00 € · slot S',
      '0.50 €',
      'OGN-010Little Spark · Common',
      'OGNX-010',
      'To createCopy of OGN-010.',
    ]);
    const vayne = within(rowOf(table, 'Vayne, Hunter')).getAllByRole('cell');
    expect(vayne.slice(1).map((cell) => cell.textContent)).toEqual([
      'Vayne, Hunter#1001',
      '12.00 €',
      'OGN-035Vayne, Hunter · Rare',
      'OGNX-035',
      'To createCopy of OGN-035.',
    ]);
    expect(within(rowOf(table, 'Already There')).getAllByRole('cell').at(-1)!.textContent).toBe(
      'In the catalogAuto-match links it.',
    );
    expect(within(rowOf(table, 'Nobody Known')).getAllByRole('cell').at(-1)!.textContent).toBe(
      'By handNo card of this name in OGN.',
    );
    expect(within(rowOf(table, '#1004')).getAllByRole('cell').at(-1)!.textContent).toBe(
      'By handNo card slot left: link it by hand.',
    );
  });

  it('create rows start checked; exists and manual rows are disabled', async () => {
    matchingApi();
    await openTable();
    expect(box('Little Spark', 1002)).toBeChecked();
    expect(box('Vayne, Hunter', 1001)).toBeChecked();
    for (const [name, id] of [
      ['Already There', 1011],
      ['Little Spark', 1004],
      ['Nobody Known', 1010],
    ] as const) {
      expect(box(name, id)).toBeDisabled();
      expect(box(name, id)).not.toBeChecked();
    }
    expect(screen.getByText('2 cards to create')).toBeVisible();
    expect(
      screen.getByText('1 product already has its card. 2 products to link by hand.'),
    ).toBeVisible();
    expect(screen.getByRole('button', { name: 'Create 2 cards' })).toBeEnabled();
  });

  it('creates the checked cards after confirming, then refreshes the workbench', async () => {
    const calls = matchingApi();
    const user = userEvent.setup();
    await openTable();
    await user.click(box('Little Spark', 1002));
    expect(screen.getByText('1 card to create')).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Create 1 card' }));
    const dialog = await screen.findByRole('dialog', { name: 'Create 1 promo card in OGNX?' });
    expect(
      within(dialog).getByText(
        'Each card copies its base card, without the image. Nothing is linked yet: run Auto-match afterwards.',
      ),
    ).toBeVisible();
    const before = callsTo(calls, 'GET', '/status').length;
    await user.click(within(dialog).getByRole('button', { name: 'Create 1 card' }));
    expect(
      (await screen.findAllByText('1 card created. Run Auto-match to link its products.')).length,
    ).toBeGreaterThan(0);
    expect(callsTo(calls, 'POST', '/promo-cards').map((call) => call.body)).toEqual([
      { set_id: 'OGNX', product_ids: [1001] },
    ]);
    await vi.waitFor(() => {
      expect(callsTo(calls, 'GET', '/status').length).toBeGreaterThan(before);
      expect(
        callsTo(calls, 'GET', '/promo-cards').filter((call) => call.search.get('set')).length,
      ).toBeGreaterThan(1);
    });
  });

  it('every product of a checked card goes in the request', async () => {
    const calls = matchingApi();
    const user = userEvent.setup();
    await openTable();
    await user.click(screen.getByRole('button', { name: 'Create 2 cards' }));
    const dialog = await screen.findByRole('dialog', { name: 'Create 2 promo cards in OGNX?' });
    await user.click(within(dialog).getByRole('button', { name: 'Create 2 cards' }));
    expect(
      (await screen.findAllByText('2 cards created. Run Auto-match to link their products.'))
        .length,
    ).toBeGreaterThan(0);
    expect(callsTo(calls, 'POST', '/promo-cards')[0]!.body).toEqual({
      set_id: 'OGNX',
      product_ids: [1002, 1003, 1001],
    });
  });

  it('cancel writes nothing', async () => {
    const calls = matchingApi();
    const user = userEvent.setup();
    await openTable();
    await user.click(screen.getByRole('button', { name: 'Create 2 cards' }));
    const dialog = await screen.findByRole('dialog', { name: 'Create 2 promo cards in OGNX?' });
    await user.click(within(dialog).getByRole('button', { name: 'Cancel' }));
    expect(callsTo(calls, 'POST', '/promo-cards')).toEqual([]);
  });

  it('a refused create shows what the server says', async () => {
    matchingApi();
    const user = userEvent.setup();
    server.use(
      http.post(`${BASE}/promo-cards`, () =>
        failure(400, {
          error: 'Validation Error',
          message: 'These products get no promo card: 1004 (no card slot left: link it by hand).',
          code: 'validation_error',
        }),
      ),
    );
    await openTable();
    await user.click(screen.getByRole('button', { name: 'Create 2 cards' }));
    const dialog = await screen.findByRole('dialog', { name: 'Create 2 promo cards in OGNX?' });
    await user.click(within(dialog).getByRole('button', { name: 'Create 2 cards' }));
    expect(
      (
        await screen.findAllByText(
          'These products get no promo card: 1004 (no card slot left: link it by hand).',
        )
      ).length,
    ).toBeGreaterThan(0);
  });

  it('nothing to create: the button is disabled', async () => {
    matchingApi({ promo: promoPlan(PROMO_ITEMS.filter((one) => one.status !== 'create')) });
    await openTable();
    expect(screen.getByText('0 cards to create')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Create 0 cards' })).toBeDisabled();
  });

  it('an empty plan says nothing is missing', async () => {
    matchingApi({ promo: promoPlan([]) });
    await openTab();
    expect(await screen.findByText('Nothing is missing in OGNX', undefined, LONG)).toBeVisible();
  });

  it('no promo set with a mapped expansion says how to get one', async () => {
    matchingApi({ promoSets: [] });
    await renderApp({ path: `${PATH}?tab=missing`, width: 1280 });
    expect(await screen.findByText('No promo set to fill', undefined, LONG)).toBeVisible();
    expect(screen.getByText(/in the Expansions tab/)).toBeVisible();
  });

  it('a set that is not a promo set shows the reason', async () => {
    matchingApi();
    await openTab('&set=OGN');
    expect(
      await screen.findByText(
        'OGN is not a promo set: a promo set id is its base set id followed by X (OGN -> OGNX).',
        undefined,
        LONG,
      ),
    ).toBeVisible();
  });

  it('a failed plan can be retried', async () => {
    matchingApi();
    server.use(http.get(`${BASE}/promo-cards`, () => failure(500, { error: 'Internal' })));
    await renderApp({ path: `${PATH}?tab=missing&set=OGNX`, width: 1280 });
    expect((await screen.findAllByRole('button', { name: 'Retry' }, LONG)).length).toBeGreaterThan(
      0,
    );
  });

  it('offline: Create is disabled', async () => {
    matchingApi();
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    await openTable();
    expect(screen.getByRole('button', { name: 'Create 2 cards' })).toBeDisabled();
  });

  it('on a phone each product is a card with its checkbox', async () => {
    matchingApi();
    const { container } = await openTab('&set=OGNX', 390);
    const list = await screen.findByRole('list', { name: 'Missing promo cards' }, LONG);
    expect(screen.queryByRole('table', { name: 'Missing promo cards' })).toBeNull();
    const items = within(list).getAllByRole('listitem');
    expect(items).toHaveLength(5);
    expect(box('Vayne, Hunter', 1001)).toBeChecked();
    expect(within(items[4]!).getByText('OGN-035 → OGNX-035')).toBeVisible();
    expect(await axe(container)).toHaveNoViolations();
  }, 20000);

  it('has no axe violations, with the confirm dialog open too', async () => {
    matchingApi({
      promo: promoPlan([
        ...PROMO_ITEMS,
        promoItem(1016, 'Little Spark', 0.7, { reason: 'no_metacard' }),
      ]),
    });
    const { container } = await openTable();
    expect(
      within(rowOf(screen.getByRole('table'), '#1016'))
        .getAllByRole('cell')
        .at(-1)!.textContent,
    ).toBe('By handCardmarket gives it no card group: link it by hand.');
    expect(await axe(container)).toHaveNoViolations();
    await userEvent.click(screen.getByRole('button', { name: 'Create 2 cards' }));
    const dialog = await screen.findByRole('dialog', { name: 'Create 2 promo cards in OGNX?' });
    expect(await axe(dialog)).toHaveNoViolations();
  }, 20000);
});

describe('Missing cards of PLAT, the plated cards (CM-k)', () => {
  async function openPlated(width = 1280) {
    const rendered = await openTab('&set=PLAT', width);
    return rendered;
  }

  it('the help says how a plated card is coded', async () => {
    matchingApi();
    await openTab('');
    expect(screen.getByText(/SFD-189 becomes PLAT-SFD-189/)).toBeVisible();
  });

  it('lists each PLAT product with its origin card, its plated card and why', async () => {
    matchingApi();
    await openPlated();
    const table = await screen.findByRole('table', { name: 'Missing promo cards' }, LONG);
    expect(
      within(table)
        .getAllByRole('columnheader')
        .map((cell) => cell.textContent),
    ).toEqual(['Create', 'Cardmarket product', 'Price', 'Origin card', 'Plated card', 'Status']);
    const ornn = within(rowOf(table, 'Ornn, Fire Below the Mountain')).getAllByRole('cell');
    expect(ornn.slice(2).map((cell) => cell.textContent)).toEqual([
      '8.00 €',
      'SFD-189Ornn, Fire Below the Mountain · Epic',
      'PLAT-sfd189',
      'To createCopy of SFD-189.',
    ]);
    const last = (text: string) =>
      within(rowOf(table, text)).getAllByRole('cell').at(-1)!.textContent;
    expect(last('Jinx, Loose Cannon')).toBe('By handSeveral origin cards: OGN-058, SFD-020.');
    expect(last('Nobody Known')).toBe('By handNo card of this name in any set.');
    expect(last('Long Name')).toBe(
      'By handIts origin card cannot be copied: create the card by hand.',
    );
    expect(last('Already There')).toBe('In the catalogAuto-match links it.');
  });

  it('creates the checked plated cards after confirming', async () => {
    const calls = matchingApi();
    const user = userEvent.setup();
    await openPlated();
    await screen.findByRole('table', { name: 'Missing promo cards' }, LONG);
    await user.click(screen.getByRole('button', { name: 'Create 1 card' }));
    const dialog = await screen.findByRole('dialog', { name: 'Create 1 promo card in PLAT?' });
    expect(
      within(dialog).getByText(
        'Each card copies its origin card, without the image. Nothing is linked yet: run Auto-match afterwards.',
      ),
    ).toBeVisible();
    await user.click(within(dialog).getByRole('button', { name: 'Create 1 card' }));
    expect(
      (await screen.findAllByText('1 card created. Run Auto-match to link its products.')).length,
    ).toBeGreaterThan(0);
    expect(callsTo(calls, 'POST', '/promo-cards').map((call) => call.body)).toEqual([
      { set_id: 'PLAT', product_ids: [4001] },
    ]);
  });

  it('on a phone the ambiguous product names its origin candidates', async () => {
    matchingApi();
    const { container } = await openPlated(390);
    const list = await screen.findByRole('list', { name: 'Missing promo cards' }, LONG);
    const jinx = within(list)
      .getAllByRole('listitem')
      .find((item) => within(item).queryByText('Jinx, Loose Cannon') !== null)!;
    expect(within(jinx).getByText('Several origin cards: OGN-058, SFD-020.')).toBeVisible();
    const ornn = within(list)
      .getAllByRole('listitem')
      .find((item) => within(item).queryByText('Ornn, Fire Below the Mountain') !== null)!;
    expect(within(ornn).getByText('SFD-189 → PLAT-sfd189')).toBeVisible();
    expect(await axe(container)).toHaveNoViolations();
  }, 20000);
});
