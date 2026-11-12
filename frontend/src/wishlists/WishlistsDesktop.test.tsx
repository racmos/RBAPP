import { createEvent, fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';
import { clearToasts } from '@/components/ui/toastStore';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';
import { installWishlists, recordWishlistRequests, signedIn, writes } from '@/test/wishlists';

const LONG = { timeout: 10000 };
const DESKTOP = 1280;

afterEach(() => {
  vi.restoreAllMocks();
  server.events.removeAllListeners();
  clearToasts();
});

async function openPage(path = '/collection/wishlists') {
  signedIn();
  return renderApp({ path, width: DESKTOP });
}

const table = (name = 'Wishlist') => screen.findByRole('table', { name: `Cards in ${name}` }, LONG);
const rail = () => screen.findByRole('region', { name: 'Your wishlists' }, LONG);
const rowOf = (name: string) =>
  screen.getByRole('button', { name: `Remove ${name}` }).closest('tr') as HTMLElement;
const listRow = (menu: HTMLElement, name: string) =>
  within(within(menu).getByRole('list', { name: 'Your wishlists' }))
    .getAllByRole('listitem')
    .find((item) =>
      within(item).queryByText(name, { selector: '[data-slot="name"]' }),
    ) as HTMLElement;
const railNames = (menu: HTMLElement) =>
  within(within(menu).getByRole('list', { name: 'Your wishlists' }))
    .getAllByRole('listitem')
    .map((item) => item.querySelector('[data-slot="name"]')?.textContent);

describe('Wishlists from 1240 px (F3-j)', () => {
  it('shows the lists in a rail and the lines as a table', async () => {
    installWishlists();
    await openPage();
    const menu = await rail();
    expect(railNames(menu)).toEqual(['Wishlist', 'Trades']);
    expect(
      within(listRow(menu, 'Wishlist')).getByRole('button', { name: /^Wishlist/ }),
    ).toHaveAttribute('aria-current', 'true');
    expect(within(menu).getByRole('button', { name: 'New list' })).toBeEnabled();
    // no switcher button on the desktop
    expect(screen.queryByRole('button', { name: /Change list/ })).toBeNull();

    const grid = await table();
    const headers = within(grid)
      .getAllByRole('columnheader')
      .map((cell) => cell.textContent);
    expect(headers).toEqual([
      'Card',
      'Wanted',
      'Max price',
      'Market',
      'This version',
      'Other versions',
      'Note',
      'Actions',
    ]);
    const ayla = rowOf("Ayla, Fury's Champion");
    expect(
      within(ayla).getByRole('spinbutton', { name: "Wanted: Ayla, Fury's Champion" }),
    ).toHaveValue(2);
    expect(within(ayla).getByText('Reached')).toBeVisible();
    expect(within(ayla).getByText('1.21 €')).toBeVisible();
    expect(within(ayla).getByText('3 (1 foil)')).toBeVisible();
    expect(within(ayla).getByText('2 (1 alt art, 0 foil)')).toBeVisible();
    const ember = rowOf('Ember Wisp');
    expect(within(ember).getByText('Foil')).toBeVisible();
    expect(within(ember).getByText('No alert price')).toBeVisible();
    expect(screen.getByText('3 of 100')).toBeVisible();
  }, 20000);

  it('edits the quantity and the max price in the table', async () => {
    const sent = recordWishlistRequests();
    installWishlists();
    await openPage();
    await table();
    await userEvent.click(
      within(rowOf('Ember Wisp')).getByRole('button', { name: 'More copies: Wanted: Ember Wisp' }),
    );
    await waitFor(() =>
      expect(writes(sent)).toContainEqual(
        expect.objectContaining({ path: '/wishlists/1/lines/102', body: { qty: 5 } }),
      ),
    );
    const price = within(rowOf('Ember Wisp')).getByRole('spinbutton', {
      name: 'Max price: Ember Wisp',
    });
    await userEvent.type(price, '1');
    await waitFor(
      () =>
        expect(writes(sent)).toContainEqual(
          expect.objectContaining({ path: '/wishlists/1/lines/102', body: { max_price: 1 } }),
        ),
      LONG,
    );
  }, 20000);

  it('edits the finish in the table, foil only when the card has one (F3-j follow-ups)', async () => {
    const sent = recordWishlistRequests();
    installWishlists();
    await openPage();
    await table();
    const ayla = within(rowOf("Ayla, Fury's Champion")).getByRole('combobox', {
      name: "Finish: Ayla, Fury's Champion",
    });
    expect(within(ayla).getByRole('option', { name: 'Foil' })).toBeDisabled();
    const ember = within(rowOf('Ember Wisp')).getByRole('combobox', {
      name: 'Finish: Ember Wisp',
    });
    expect(ember).toHaveValue('S');
    await userEvent.selectOptions(ember, 'Any finish');
    await waitFor(() =>
      expect(writes(sent)).toContainEqual(
        expect.objectContaining({
          method: 'PATCH',
          path: '/wishlists/1/lines/102',
          body: { foil: 'any' },
        }),
      ),
    );
    await waitFor(() =>
      expect(
        within(rowOf('Ember Wisp')).getByRole('combobox', { name: 'Finish: Ember Wisp' }),
      ).toHaveValue('any'),
    );
  }, 20000);

  it('offline: the finish cannot change in the table (F3-j follow-ups)', async () => {
    installWishlists();
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    await openPage();
    await table();
    expect(
      within(rowOf('Ember Wisp')).getByRole('combobox', { name: 'Finish: Ember Wisp' }),
    ).toBeDisabled();
  }, 20000);

  it('opens another list from the rail', async () => {
    installWishlists();
    const { where } = await openPage();
    const menu = await rail();
    await userEvent.click(within(listRow(menu, 'Trades')).getByRole('button', { name: /^Trades/ }));
    expect(await table('Trades')).toBeVisible();
    await waitFor(() => expect(where()).toBe('/collection/wishlists?list=2'));
  }, 20000);

  it('reorders the lists by dragging one onto another', async () => {
    const sent = recordWishlistRequests();
    installWishlists();
    await openPage();
    const menu = await rail();
    const store = new Map<string, string>();
    const dataTransfer = {
      setData: (type: string, value: string) => store.set(type, value),
      getData: (type: string) => store.get(type) ?? '',
      effectAllowed: 'move',
      dropEffect: 'move',
    };
    fireEvent.dragStart(listRow(menu, 'Trades'), { dataTransfer });
    fireEvent.dragOver(listRow(menu, 'Wishlist'), { dataTransfer });
    const drop = createEvent.drop(listRow(menu, 'Wishlist'), { dataTransfer });
    fireEvent(listRow(menu, 'Wishlist'), drop);
    expect(drop.defaultPrevented).toBe(true);
    await waitFor(() => expect(railNames(menu)).toEqual(['Trades', 'Wishlist']));
    await waitFor(() => expect(writes(sent)).toHaveLength(1), LONG);
    expect(writes(sent)[0]).toMatchObject({
      method: 'PUT',
      path: '/wishlists/order',
      body: { ids: [2, 1] },
    });
  }, 20000);

  it('is axe clean', async () => {
    installWishlists();
    const { container } = await openPage();
    await table();
    expect(await axe(container)).toHaveNoViolations();
  }, 30000);
});
