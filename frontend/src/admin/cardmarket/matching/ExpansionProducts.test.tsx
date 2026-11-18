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
  expansionProduct,
  matchingApi,
} from '@/test/fixtures/cardmarketMatching';
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
    expect(callsTo(calls, 'GET', '/expansions/6567/products')[0]!.search.toString()).toBe('');
    for (const text of [
      '115 singles',
      '5 sealed products',
      'Singles 0.02 € - 34.00 €',
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
    const products = await within(dialog).findByRole('table', { name: LIST });
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
      'Proving Grounds Booster Box#9101 · Riftbound Booster Box',
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
      'box · OGS',
    ]);
    expect(cells('Ahri, Nine-Tailed Fox')).toEqual([
      'Ahri, Nine-Tailed Fox#9001 · Riftbound Single',
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
      'Jinx, Loose Cannon#9003 · Riftbound Single',
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
    const list = await within(dialog).findByRole('list', { name: LIST });
    expect(within(dialog).queryByRole('table', { name: LIST })).toBeNull();
    const items = within(list).getAllByRole('listitem');
    expect(items).toHaveLength(3);
    const ahri = items[1]!;
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
    expect(within(items[0]!).getByText('Catalog: box · OGS')).toBeVisible();
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

  it('search, type and sort ask the server again', async () => {
    const calls = matchingApi({ expansions: [UNNAMED] });
    const user = userEvent.setup();
    const { table } = await openTab();
    const dialog = await openProducts(table, 'Expansion #6567');
    await within(dialog).findByRole('table', { name: LIST });
    await user.type(within(dialog).getByRole('textbox', { name: 'Search products' }), 'ahri');
    await vi.waitFor(() =>
      expect(callsTo(calls, 'GET', '/expansions/6567/products').at(-1)!.search.toString()).toBe(
        'q=ahri',
      ),
    );
    await vi.waitFor(() => expect(within(listOf(dialog)).getAllByRole('row')).toHaveLength(2));
    const type = within(dialog).getByRole('radiogroup', { name: 'Type' });
    await user.click(within(type).getByRole('radio', { name: 'Sealed' }));
    await vi.waitFor(() =>
      expect(callsTo(calls, 'GET', '/expansions/6567/products').at(-1)!.search.toString()).toBe(
        'q=ahri&type=sealed',
      ),
    );
    expect(await within(dialog).findByText('No products match')).toBeVisible();
    await user.clear(within(dialog).getByRole('textbox', { name: 'Search products' }));
    await user.click(within(type).getByRole('radio', { name: 'Singles' }));
    const sort = within(dialog).getByRole('combobox', { name: 'Sort' });
    expect(
      within(sort)
        .getAllByRole('option')
        .map((option) => option.textContent),
    ).toEqual(['Price, dearest first', 'Name', 'Newest first']);
    await user.selectOptions(sort, 'Name');
    await vi.waitFor(() =>
      expect(callsTo(calls, 'GET', '/expansions/6567/products').at(-1)!.search.toString()).toBe(
        'type=single&sort=name',
      ),
    );
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
    expect(callsTo(calls, 'GET', '/expansions/6567/products').at(-1)!.search.toString()).toBe(
      'page=2',
    );
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
