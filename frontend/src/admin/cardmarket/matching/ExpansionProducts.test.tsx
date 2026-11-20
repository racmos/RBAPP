import { join } from 'node:path';
import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { axe } from 'vitest-axe';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { clearToasts } from '@/components/ui/toastStore';
import modalStyles from '@/components/ui/Modal.module.css';
import tableStyles from '@/components/ui/TableScroll.module.css';
import { SRC_DIR, declsFor, readCss } from '@/test/css';
import { API, failure } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';
import {
  EXPANSIONS,
  UNNAMED,
  callsTo,
  expansion,
  expansionProduct,
  matchingApi,
} from '@/test/fixtures/cardmarketMatching';
import badgeStyles from '@/components/ui/Badge.module.css';
import segmentedStyles from '@/components/ui/SegmentedControl.module.css';
import styles from './MatchingPage.module.css';

const LONG = { timeout: 10000 };
const PATH = '/admin/cardmarket/matching';
const BASE = `${API}/admin/cardmarket`;
const LIST = 'Products of the latest load';

async function openTab(search = '', width = 1280) {
  const rendered = await renderApp({ path: `${PATH}?tab=expansions${search}`, width });
  const table = await screen.findByRole('table', { name: 'Cardmarket expansions' }, LONG);
  return { ...rendered, table };
}

const rowOf = (table: HTMLElement, text: string) =>
  within(table)
    .getAllByRole('row')
    .find((row) => within(row).queryByText(text) !== null)!;

async function openProducts(table: HTMLElement, name: string) {
  await userEvent.click(
    within(rowOf(table, name)).getByRole('button', { name: `View the products of ${name}` }),
  );
  return screen.findByRole('dialog', { name: `Products of ${name}` });
}

const listOf = (dialog: HTMLElement) => within(dialog).getByRole('region', { name: LIST });

const kindGroup = (dialog: HTMLElement) => within(dialog).getByRole('radiogroup', { name: 'Kind' });

/** Choose a kind by the start of its label ("All", "Booster boxes"...): the label ends in its count. */
const chooseKind = (dialog: HTMLElement, label: string) =>
  userEvent.click(
    within(kindGroup(dialog)).getByRole('radio', { name: new RegExp(`^${label} \\(`) }),
  );

const lastSearch = (calls: ReturnType<typeof matchingApi>) =>
  callsTo(calls, 'GET', '/expansions/6567/products').at(-1)!.search.toString();

/** An expansion of sealed products only. */
const SEALED_ONLY = expansion(6600, 'Sealed Only', null, {
  products_count: 2,
  sealed_count: 2,
});
const SEALED = [
  expansionProduct(9201, 'Origins Booster', {
    type: 'sealed',
    kind: 'booster',
    category: 'Riftbound Booster',
  }),
  expansionProduct(9202, 'Legacy Vault', {
    type: 'sealed',
    kind: 'sealed_box_set',
    category: 'Riftbound Riftbound Box Sets',
  }),
];

/** The counters of an expansion like Origins on the real database. */
const ORIGINS_KINDS = [
  { kind: 'card', count: 355 },
  { kind: 'booster', count: 4 },
  { kind: 'booster_box', count: 2 },
  { kind: 'champion_deck', count: 6 },
  { kind: 'sealed_box_set', count: 3 },
  { kind: 'unused', count: 5 },
];

/** An expansion with a product of a Cardmarket category we do not use (taxonomy 2026-11-20). */
const WITH_UNUSED = expansion(6610, 'With Unused', null, {
  products_count: 2,
  sealed_count: 2,
});
const UNUSED_PRODUCTS = [
  expansionProduct(9301, 'Origins Booster', {
    type: 'sealed',
    kind: 'booster',
    category: 'Riftbound Booster',
  }),
  expansionProduct(9302, 'Origins: Full Set', {
    type: 'sealed',
    kind: 'unused',
    category: 'RB Set',
  }),
];

const many = (count: number) =>
  Array.from({ length: count }, (_, index) =>
    expansionProduct(20000 + index, `Card ${String(index).padStart(3, '0')}`, {
      price: count - index,
      price_source: 'low',
    }),
  );

afterEach(() => {
  vi.restoreAllMocks();
  clearToasts();
});

describe('Expansion products (CM-f)', () => {
  it('every row has View products; the dialog shows the figures of the expansion', async () => {
    const calls = matchingApi({ expansions: [UNNAMED, ...EXPANSIONS] });
    const { table } = await openTab();
    const dialog = await openProducts(table, 'Expansion #6567');
    // the expansion has cards: the list starts on them
    expect(callsTo(calls, 'GET', '/expansions/6567/products')[0]!.search.toString()).toBe(
      'kind=card',
    );
    for (const text of [
      '120 products',
      '115 cards',
      'Cards 0.02 € - 34.00 €',
      'First seen 14 Jul 2025',
      'Not mapped yet.',
    ]) {
      expect(within(dialog).getByText(text)).toBeVisible();
    }
    expect(await within(dialog).findByText('Latest load 6 Nov 2026')).toBeVisible();
    expect(
      within(dialog).getByText(
        'Read-only list. To create a card for a single, use Create card in the To link tab; the daily load adds the sealed products to the catalog.',
      ),
    ).toBeVisible();
    // the other rows have it too, mapped or not
    expect(
      within(rowOf(table, 'Spiritforged')).getByRole('button', {
        name: 'View the products of Spiritforged',
      }),
    ).toHaveTextContent('View products');
  });

  it('from 860 px the products are a table with every field', async () => {
    matchingApi({ expansions: [UNNAMED] });
    const { table } = await openTab();
    const dialog = await openProducts(table, 'Expansion #6567');
    await within(dialog).findByRole('table', { name: LIST });
    await chooseKind(dialog, 'All');
    const products = await within(dialog).findByRole('table', { name: LIST });
    await vi.waitFor(() => expect(within(products).getAllByRole('row')).toHaveLength(4));
    expect(
      within(products)
        .getAllByRole('columnheader')
        .map((cell) => cell.textContent),
    ).toEqual([
      'Product',
      'Type',
      'Added',
      'Price',
      'Low',
      'Trend',
      '7-day avg',
      '30-day avg',
      'Average',
      'Foil low',
      'Foil trend',
      'Linked card',
      'Catalog',
    ]);
    const cells = (name: string) =>
      within(rowOf(products, name))
        .getAllByRole('cell')
        .map((cell) => cell.textContent);
    expect(cells('Proving Grounds Booster Box')).toEqual([
      'Proving Grounds Booster BoxBooster boxes#9101 · Riftbound Booster Box',
      'Sealed',
      '14 Jul 2025',
      '95.00 € (7-day avg)',
      '90.00 €',
      '97.50 €',
      '95.00 €',
      '96.00 €',
      '94.00 €',
      '—',
      '—',
      '—',
      'Booster boxes · OGS',
    ]);
    expect(cells('Ahri, Nine-Tailed Fox')).toEqual([
      'Ahri, Nine-Tailed FoxCard#9001 · Riftbound Single',
      'Single',
      '15 Jul 2025',
      '34.00 € (low)',
      '34.00 €',
      '36.10 €',
      '35.00 €',
      '33.00 €',
      '34.50 €',
      '60.00 €',
      '64.00 €',
      'OGS-001, slot N',
      '—',
    ]);
    expect(cells('Jinx, Loose Cannon')).toEqual([
      'Jinx, Loose CannonCard#9003 · Riftbound Single',
      'Single',
      '—',
      'no price',
      '—',
      '—',
      '—',
      '—',
      '—',
      '—',
      '—',
      '—',
      '—',
    ]);
    expect(within(dialog).getByText('Showing 3 of 3 products')).toBeVisible();
  });

  it('below 860 px the dialog is full screen and the products are cards', async () => {
    matchingApi({ expansions: [UNNAMED] });
    const { table } = await openTab('', 390);
    const dialog = await openProducts(table, 'Expansion #6567');
    expect(dialog).toHaveClass(modalStyles.fullMd);
    await within(dialog).findByRole('list', { name: LIST });
    await chooseKind(dialog, 'All');
    const list = within(dialog).getByRole('list', { name: LIST });
    await vi.waitFor(() => expect(within(list).getAllByRole('listitem')).toHaveLength(3));
    expect(within(dialog).queryByRole('table', { name: LIST })).toBeNull();
    const items = within(list).getAllByRole('listitem');
    const ahri = items[1]!;
    // the kind badge sits next to the Cardmarket category
    expect(within(ahri).getByText('Card')).toBeVisible();
    expect(within(items[0]!).getByText('Booster boxes')).toBeVisible();
    for (const text of [
      'Ahri, Nine-Tailed Fox',
      'Single · Riftbound Single · #9001',
      'Added 15 Jul 2025',
      'Price 34.00 € (low)',
      'Linked to OGS-001, slot N',
    ]) {
      expect(within(ahri).getByText(text)).toBeVisible();
    }
    expect(within(ahri).getByText('Foil trend').nextSibling).toHaveTextContent('64.00 €');
    // the catalog kind is its label, not its id
    expect(within(items[0]!).getByText('Catalog: Booster boxes · OGS')).toBeVisible();
    expect(within(items[2]!).getByText('Price no price')).toBeVisible();
  });

  it('the list scrolls inside the dialog, not the page', async () => {
    matchingApi({ expansions: [UNNAMED] });
    const { table } = await openTab();
    const dialog = await openProducts(table, 'Expansion #6567');
    const region = listOf(dialog);
    expect(region).toHaveAttribute('tabindex', '0');
    expect(region).toHaveClass(styles.productsScroll!);
    // a TableScroll box (`overflow: auto`, its header sticks to its top) with a lower cap
    expect(region).toHaveAttribute('data-slot', 'table-scroll');
    expect(region).toHaveClass(tableStyles.scroll!);
    const css = readCss(join(SRC_DIR, 'admin/cardmarket/matching/MatchingPage.module.css'));
    // the list takes all the room the summary, the filters and the map buttons leave in a column
    // as tall as the dialog (a fixed 55 % cap left room for about five rows on a laptop)
    const decls = declsFor(css, ".productsScroll[data-slot='table-scroll']");
    expect(decls.findLast((decl) => decl.prop === 'max-height')?.value).toBe('none');
    expect(decls.find((decl) => decl.prop === 'flex')?.value).toBe('1 1 auto');
    const column = declsFor(css, '.products');
    expect(column.find((decl) => decl.prop === 'display')?.value).toBe('flex');
    expect(column.findLast((decl) => decl.prop === 'height')?.value).toBe(
      'min(calc(100dvh - 170px), 860px)',
    );
    // below 860 px the products are cards and the dialog scrolls as a whole
    expect(declsFor(css, '.productsStacked').find((decl) => decl.prop === 'height')?.value).toBe(
      'auto',
    );
    // full screen below 860 px (the md breakpoint)
    const modalCss = readCss(join(SRC_DIR, 'components/ui/Modal.module.css'));
    expect(declsFor(modalCss, '.fullMd').find((decl) => decl.prop === 'height')?.value).toBe(
      '100%',
    );
  });

  it('search, kind and sort ask the server again', async () => {
    const calls = matchingApi({ expansions: [UNNAMED] });
    const user = userEvent.setup();
    const { table } = await openTab();
    const dialog = await openProducts(table, 'Expansion #6567');
    await within(dialog).findByRole('table', { name: LIST });
    // the Type control is gone: the kind says it
    expect(within(dialog).queryByRole('radiogroup', { name: 'Type' })).toBeNull();
    await user.type(within(dialog).getByRole('textbox', { name: 'Search products' }), 'ahri');
    await vi.waitFor(() => expect(lastSearch(calls)).toBe('q=ahri&kind=card'));
    await vi.waitFor(() => expect(within(listOf(dialog)).getAllByRole('row')).toHaveLength(2));
    await chooseKind(dialog, 'Booster boxes');
    await vi.waitFor(() => expect(lastSearch(calls)).toBe('q=ahri&kind=booster_box'));
    expect(await within(dialog).findByText('No products match')).toBeVisible();
    expect(within(dialog).getByText('Try another search or kind.')).toBeVisible();
    await user.clear(within(dialog).getByRole('textbox', { name: 'Search products' }));
    await chooseKind(dialog, 'All');
    await vi.waitFor(() => expect(lastSearch(calls)).toBe(''));
    const sort = within(dialog).getByRole('combobox', { name: 'Sort' });
    expect(
      within(sort)
        .getAllByRole('option')
        .map((option) => option.textContent),
    ).toEqual(['Price, dearest first', 'Name', 'Newest first']);
    await user.selectOptions(sort, 'Name');
    await vi.waitFor(() => expect(lastSearch(calls)).toBe('sort=name'));
  });

  it('the Kind filter lists every kind of the expansion with its count; Cards is the default', async () => {
    const calls = matchingApi({ expansions: [UNNAMED], kinds: ORIGINS_KINDS });
    const { table } = await openTab();
    const dialog = await openProducts(table, 'Expansion #6567');
    await within(dialog).findByRole('table', { name: LIST });
    const group = kindGroup(dialog);
    await vi.waitFor(() =>
      expect(
        within(group)
          .getAllByRole('radio')
          .map((radio) => radio.closest('label')!.textContent),
      ).toEqual([
        'All (375)',
        'Cards (355)',
        'Booster (4)',
        'Booster boxes (2)',
        'Champion decks (6)',
        'Sealed box sets (3)',
        'Not used (5)',
      ]),
    );
    // only the kinds the expansion has: no Accessories or Other
    expect(within(group).queryByRole('radio', { name: /^Accessories/ })).toBeNull();
    expect(within(group).queryByRole('radio', { name: /^Other/ })).toBeNull();
    expect(within(group).getByRole('radio', { name: 'Cards (355)' })).toBeChecked();
    expect(callsTo(calls, 'GET', '/expansions/6567/products')).toHaveLength(1);
    expect(lastSearch(calls)).toBe('kind=card');
    // the counters are of the whole expansion: a search does not change them
    await userEvent.type(within(dialog).getByRole('textbox', { name: 'Search products' }), 'zzz');
    await vi.waitFor(() => expect(lastSearch(calls)).toBe('q=zzz&kind=card'));
    expect(within(group).getByRole('radio', { name: 'Booster boxes (2)' })).toBeVisible();
  });

  it('the Kind filter is a radio group the arrow keys move through', async () => {
    const calls = matchingApi({ expansions: [UNNAMED], kinds: ORIGINS_KINDS });
    const user = userEvent.setup();
    const { table } = await openTab();
    const dialog = await openProducts(table, 'Expansion #6567');
    await within(dialog).findByRole('table', { name: LIST });
    const cards = within(kindGroup(dialog)).getByRole('radio', { name: 'Cards (355)' });
    cards.focus();
    await user.keyboard('{ArrowRight}');
    expect(within(kindGroup(dialog)).getByRole('radio', { name: 'Booster (4)' })).toBeChecked();
    await vi.waitFor(() => expect(lastSearch(calls)).toBe('kind=booster'));
  });

  it('an expansion without cards starts on All', async () => {
    const calls = matchingApi({ expansions: [SEALED_ONLY], products: SEALED });
    const { table } = await openTab();
    const dialog = await openProducts(table, 'Sealed Only');
    const products = await within(dialog).findByRole('table', { name: LIST });
    expect(callsTo(calls, 'GET', '/expansions/6600/products')[0]!.search.toString()).toBe('');
    expect(within(products).getAllByRole('row')).toHaveLength(3);
    const group = kindGroup(dialog);
    expect(within(group).getByRole('radio', { name: 'All (2)' })).toBeChecked();
    expect(within(group).queryByRole('radio', { name: /^Cards/ })).toBeNull();
    expect(within(group).getByRole('radio', { name: 'Sealed box sets (1)' })).toBeVisible();
    expect(within(rowOf(products, 'Legacy Vault')).getByText('Sealed box sets')).toBeVisible();
    expect(within(dialog).getByText('0 cards')).toBeVisible();
  });

  it('a product of a category we do not use is a muted "Not used", counted last and explained', async () => {
    const calls = matchingApi({ expansions: [WITH_UNUSED], products: UNUSED_PRODUCTS });
    const { table } = await openTab();
    const dialog = await openProducts(table, 'With Unused');
    const products = await within(dialog).findByRole('table', { name: LIST });
    const group = kindGroup(dialog);
    expect(
      within(group)
        .getAllByRole('radio')
        .map((radio) => radio.closest('label')!.textContent),
    ).toEqual(['All (2)', 'Booster (1)', 'Not used (1)']);
    // the option and the badge are muted; a real kind is not
    const option = within(group).getByRole('radio', { name: 'Not used (1)' }).closest('label')!;
    expect(option.querySelector(`.${styles.notUsed}`)).not.toBeNull();
    const badge = within(rowOf(products, 'Origins: Full Set')).getByText('Not used');
    expect(badge).toHaveClass(badgeStyles.muted!);
    expect(within(rowOf(products, 'Origins Booster')).getByText('Booster')).not.toHaveClass(
      badgeStyles.muted!,
    );
    const hint = 'Not used: Cardmarket Sets and Sealed Products never enter the product catalog.';
    expect(within(dialog).queryByText(hint)).toBeNull();
    await chooseKind(dialog, 'Not used');
    await vi.waitFor(() =>
      expect(callsTo(calls, 'GET', '/expansions/6610/products').at(-1)!.search.toString()).toBe(
        'kind=unused',
      ),
    );
    expect(within(dialog).getByText(hint)).toBeVisible();
    await vi.waitFor(() => expect(within(listOf(dialog)).getAllByRole('row')).toHaveLength(2));
    expect(await axe(dialog)).toHaveNoViolations();
  });

  it('on narrow screens the kinds wrap onto more lines', async () => {
    matchingApi({ expansions: [UNNAMED], kinds: ORIGINS_KINDS });
    const { table } = await openTab('', 390);
    const dialog = await openProducts(table, 'Expansion #6567');
    await within(dialog).findByRole('list', { name: LIST });
    const group = kindGroup(dialog);
    expect(group).toHaveClass(segmentedStyles.group!);
    const css = readCss(join(SRC_DIR, 'components/ui/SegmentedControl.module.css'));
    const decls = declsFor(css, '.group');
    expect(decls.find((decl) => decl.prop === 'flex-wrap')?.value).toBe('wrap');
    expect(decls.find((decl) => decl.prop === 'max-width')?.value).toBe('100%');
    expect(within(group).getAllByRole('radio')).toHaveLength(7);
  });

  it('Show more loads the next page under the first one', async () => {
    const calls = matchingApi({ expansions: [UNNAMED], products: many(120) });
    const user = userEvent.setup();
    const { table } = await openTab();
    const dialog = await openProducts(table, 'Expansion #6567');
    const products = await within(dialog).findByRole('table', { name: LIST });
    expect(within(products).getAllByRole('row')).toHaveLength(51);
    expect(within(dialog).getByText('Showing 50 of 120 products')).toBeVisible();
    await user.click(within(dialog).getByRole('button', { name: 'Show more' }));
    await vi.waitFor(() => expect(within(products).getAllByRole('row')).toHaveLength(101));
    expect(lastSearch(calls)).toBe('kind=card&page=2');
    await user.click(within(dialog).getByRole('button', { name: 'Show more' }));
    await vi.waitFor(() => expect(within(products).getAllByRole('row')).toHaveLength(121));
    expect(within(dialog).getByText('Showing 120 of 120 products')).toBeVisible();
    expect(within(dialog).queryByRole('button', { name: 'Show more' })).toBeNull();
    // the first page stays where it was
    expect(within(products).getAllByRole('row')[1]).toHaveTextContent('Card 000');
  });

  it('an expansion without products on the latest load says so', async () => {
    matchingApi({ products: [] });
    const { table } = await openTab();
    const dialog = await openProducts(table, 'Spiritforged');
    expect(await within(dialog).findByText('No products on the latest load')).toBeVisible();
  });

  it('a failed list shows the error with a retry that asks again', async () => {
    const calls = matchingApi({ expansions: [UNNAMED] });
    server.use(
      http.get(
        `${BASE}/expansions/:id/products`,
        () => failure(500, { error: 'Internal Server Error', message: 'boom' }),
        { once: true },
      ),
    );
    const user = userEvent.setup();
    const { table } = await openTab();
    const dialog = await openProducts(table, 'Expansion #6567');
    await user.click(await within(dialog).findByRole('button', { name: /retry/i }, LONG));
    expect(await within(dialog).findByRole('table', { name: LIST }, LONG)).toBeVisible();
    expect(callsTo(calls, 'GET', '/expansions/6567/products')).toHaveLength(1);
  });

  it('Map to a set… opens the map form under the list; mapping closes the dialog', async () => {
    const calls = matchingApi({ expansions: [UNNAMED, ...EXPANSIONS] });
    const user = userEvent.setup();
    const { table } = await openTab();
    const dialog = await openProducts(table, 'Expansion #6567');
    await within(dialog).findByRole('table', { name: LIST });
    await user.click(within(dialog).getByRole('button', { name: 'Map to a set…' }));
    const form = within(dialog).getByRole('region', { name: 'Map this expansion' });
    // the list stays on screen while the owner decides
    expect(listOf(dialog)).toBeVisible();
    const select = within(form).getByRole('combobox', { name: 'Set' });
    expect(select).toHaveValue('');
    // the samples are not repeated: the list above has every product
    expect(within(form).queryByRole('list')).toBeNull();
    await user.selectOptions(select, 'OGS');
    await user.click(within(form).getByRole('button', { name: 'Map' }));
    expect((await screen.findAllByText('Mapped Expansion #6567 to OGS.')).length).toBeGreaterThan(
      0,
    );
    expect(callsTo(calls, 'PUT', '/expansions/6567').map((call) => call.body)).toEqual([
      { set_id: 'OGS' },
    ]);
    await vi.waitFor(() =>
      expect(screen.queryByRole('dialog', { name: 'Products of Expansion #6567' })).toBeNull(),
    );
  });

  it('Cancel folds the map form back into the two buttons', async () => {
    matchingApi({ expansions: [UNNAMED] });
    const user = userEvent.setup();
    const { table } = await openTab();
    const dialog = await openProducts(table, 'Expansion #6567');
    await user.click(within(dialog).getByRole('button', { name: 'Map to a set…' }));
    await user.click(within(dialog).getByRole('button', { name: 'Cancel' }));
    expect(within(dialog).queryByRole('region', { name: 'Map this expansion' })).toBeNull();
    expect(within(dialog).getByRole('button', { name: 'Create a new set…' })).toBeEnabled();
  });

  it('Create a new set… opens the set fields of the sets admin and maps to the new set', async () => {
    const calls = matchingApi({ expansions: [UNNAMED] });
    const user = userEvent.setup();
    const { table } = await openTab();
    const dialog = await openProducts(table, 'Expansion #6567');
    await user.click(within(dialog).getByRole('button', { name: 'Create a new set…' }));
    const form = within(dialog).getByRole('region', { name: 'Map this expansion' });
    expect(within(form).getByRole('combobox', { name: 'Set' })).toHaveValue('__new__');
    await user.type(within(form).getByRole('textbox', { name: /Code/ }), 'ogs2');
    await user.type(within(form).getByRole('textbox', { name: /Name/ }), 'Proving Grounds 2');
    await user.type(within(form).getByLabelText(/Release date/), '2026-02-13');
    await user.click(within(form).getByRole('button', { name: 'Save' }));
    expect(
      (await screen.findAllByText('Created set OGS2 and mapped Expansion #6567 to it.')).length,
    ).toBeGreaterThan(0);
    expect(callsTo(calls, 'PUT', '/expansions/6567').map((call) => call.body)).toEqual([
      {
        set_id: 'ogs2',
        create_set: { name: 'Proving Grounds 2', release_date: '2026-02-13', declared_count: null },
      },
    ]);
  });

  it('a mapped expansion offers Change the set… starting on its set', async () => {
    matchingApi();
    const user = userEvent.setup();
    const { table } = await openTab('&show=all');
    const dialog = await openProducts(table, 'Origins');
    expect(within(dialog).getByText('Now mapped to Origins (OGN).')).toBeVisible();
    await user.click(within(dialog).getByRole('button', { name: 'Change the set…' }));
    expect(within(dialog).getByRole('combobox', { name: 'Set' })).toHaveValue('OGN');
  });

  it('the map dialog links to every product of the expansion', async () => {
    matchingApi({ expansions: [UNNAMED, ...EXPANSIONS] });
    const user = userEvent.setup();
    const { table } = await openTab();
    await user.click(
      within(rowOf(table, 'Expansion #6567')).getByRole('button', {
        name: 'Map Expansion #6567 to a set',
      }),
    );
    const map = await screen.findByRole('dialog', { name: 'Map Expansion #6567' });
    await user.click(within(map).getByRole('button', { name: 'View all 120 products' }));
    const dialog = await screen.findByRole('dialog', { name: 'Products of Expansion #6567' });
    expect(await within(dialog).findByRole('table', { name: LIST })).toBeVisible();
    await vi.waitFor(() =>
      expect(screen.queryByRole('dialog', { name: 'Map Expansion #6567' })).toBeNull(),
    );
  });

  it('offline: the list still shows, the map buttons are disabled', async () => {
    matchingApi({ expansions: [UNNAMED] });
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    const { table } = await openTab();
    const dialog = await openProducts(table, 'Expansion #6567');
    expect(within(dialog).getByRole('button', { name: 'Map to a set…' })).toBeDisabled();
    expect(within(dialog).getByRole('button', { name: 'Create a new set…' })).toBeDisabled();
  });

  it('has no axe violations as a table', async () => {
    matchingApi({ expansions: [UNNAMED] });
    const { table } = await openTab();
    const dialog = await openProducts(table, 'Expansion #6567');
    await within(dialog).findByRole('table', { name: LIST });
    expect(await axe(dialog)).toHaveNoViolations();
  }, 20000);

  it('has no axe violations as cards with the map form open', async () => {
    matchingApi({ expansions: [UNNAMED] });
    const { table } = await openTab('', 390);
    const dialog = await openProducts(table, 'Expansion #6567');
    await within(dialog).findByRole('list', { name: LIST });
    await userEvent.click(within(dialog).getByRole('button', { name: 'Create a new set…' }));
    expect(await axe(dialog)).toHaveNoViolations();
  }, 20000);
});
