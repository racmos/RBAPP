import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';
import { clearToasts } from '@/components/ui/toastStore';
import { foilCommon } from '@/test/fixtures/cards';
import { defaultList, line, miniOf, tradesList, wishlistLines } from '@/test/fixtures/wishlists';
import { API, failure } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';
import {
  installWishlists,
  manyLists,
  recordWishlistRequests,
  signedIn,
  findToast,
  writes,
} from '@/test/wishlists';

const LONG = { timeout: 10000 };
const PHONE = 390;

afterEach(() => {
  vi.restoreAllMocks();
  server.events.removeAllListeners();
  clearToasts();
});

async function openPage(path = '/collection/wishlists') {
  signedIn();
  return renderApp({ path, width: PHONE });
}

const cards = (name = 'Wishlist') => screen.findByRole('list', { name: `Cards in ${name}` }, LONG);
const cardOf = (name: RegExp | string) =>
  screen
    .getAllByRole('listitem')
    .find((item) => within(item).queryByRole('heading', { name })) as HTMLElement;
const switcher = () => screen.findByRole('button', { name: /Change list/ }, LONG);

async function openMenu() {
  await userEvent.click(await switcher());
  return screen.findByRole('dialog', { name: 'Your wishlists' });
}
const rowOf = (menu: HTMLElement, name: string) =>
  within(within(menu).getByRole('list', { name: 'Your wishlists' }))
    .getAllByRole('listitem')
    .find((item) =>
      within(item).queryByText(name, { selector: '[data-slot="name"]' }),
    ) as HTMLElement;

async function rowAction(menu: HTMLElement, name: string, action: string) {
  const row = rowOf(menu, name);
  await userEvent.click(within(row).getByRole('button', { name: `Actions for ${name}` }));
  return within(row).getByRole('button', { name: action });
}

describe('Wishlists at 390 px (F3-j): routes and tabs', () => {
  it('lives in the collection area: tabs, the starred list open by default', async () => {
    installWishlists();
    const { where } = await openPage();
    expect(await screen.findByRole('heading', { level: 1, name: 'Wishlists' }, LONG)).toBeVisible();
    expect(document.title).toBe('Wishlists · Rift Manager');
    const tabs = screen.getByRole('navigation', { name: 'Collection sections' });
    expect(within(tabs).getByRole('link', { name: 'Collection' })).toHaveAttribute(
      'href',
      '/riftbound/app/collection',
    );
    expect(within(tabs).getByRole('link', { name: 'Wishlists' })).toHaveAttribute(
      'aria-current',
      'page',
    );
    const sections = screen.getByRole('navigation', { name: 'Wishlist sections' });
    expect(within(sections).getByRole('link', { name: 'Lists' })).toHaveAttribute(
      'aria-current',
      'page',
    );
    expect(within(sections).getByRole('link', { name: 'Price alerts' })).toHaveAttribute(
      'href',
      '/riftbound/app/collection/wishlists/alerts',
    );
    // the default (starred) list, its name and count on the switcher
    expect(await switcher()).toHaveTextContent('Wishlist');
    expect(await switcher()).toHaveTextContent('3 cards');
    await cards();
    expect(where()).toBe('/collection/wishlists');
  }, 20000);

  it('opens the list of ?list=<id> and falls back to the default for an unknown id', async () => {
    installWishlists();
    await openPage('/collection/wishlists?list=2');
    expect(await cards('Trades')).toBeVisible();
    expect(screen.getByRole('heading', { name: 'Spark Token' })).toBeVisible();
  }, 20000);

  it('an unknown list id shows the default list', async () => {
    installWishlists();
    await openPage('/collection/wishlists?list=999');
    expect(await cards('Wishlist')).toBeVisible();
  }, 20000);

  it('anonymous visitors go to the login page', async () => {
    const { where } = await renderApp({ path: '/collection/wishlists', width: PHONE });
    await waitFor(() => expect(where()).toMatch(/^\/login\?next=/), LONG);
    expect(decodeURIComponent(where())).toContain('/riftbound/app/collection/wishlists');
  }, 20000);

  it('the alerts screen explains itself and reads no wishlist (F4-g-2: no alerts yet)', async () => {
    const sent = recordWishlistRequests();
    await openPage('/collection/wishlists/alerts');
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Price alerts' }, LONG),
    ).toBeVisible();
    expect(
      screen.getByText(
        'You will see here the cards of your wishlists whose market price reaches your price, once per day after Cardmarket prices update.',
      ),
    ).toBeVisible();
    // F4-g-2: the empty state comes once the (empty) alerts have loaded
    expect(await screen.findByRole('heading', { name: 'No price alerts yet' }, LONG)).toBeVisible();
    const sections = screen.getByRole('navigation', { name: 'Wishlist sections' });
    expect(within(sections).getByRole('link', { name: 'Price alerts' })).toHaveAttribute(
      'aria-current',
      'page',
    );
    expect(sent).toEqual([]);
  }, 20000);

  it('the alerts screen without alerts is axe clean', async () => {
    const { container } = await openPage('/collection/wishlists/alerts');
    await screen.findByRole('heading', { level: 1, name: 'Price alerts' }, LONG);
    expect(await axe(container)).toHaveNoViolations();
  }, 30000);
});

describe('Wishlists at 390 px (F3-j): the lists menu', () => {
  it('lists every list in order with its count, the star on the default and the open one', async () => {
    installWishlists();
    await openPage();
    await cards();
    const menu = await openMenu();
    const list = within(menu).getByRole('list', { name: 'Your wishlists' });
    const names = within(list)
      .getAllByRole('listitem')
      .map((item) => item.querySelector('[data-slot="name"]')?.textContent);
    expect(names).toEqual(['Wishlist', 'Trades']);
    const first = rowOf(menu, 'Wishlist');
    expect(within(first).getByRole('button', { name: /^Wishlist/ })).toHaveAttribute(
      'aria-current',
      'true',
    );
    expect(within(first).getByText('3 cards')).toBeVisible();
    const star = within(first).getByRole('button', { name: 'Default list' });
    expect(star).toBeDisabled();
    expect(star).toHaveAccessibleDescription(
      'This is the default list. Star another list to change it.',
    );
    const second = rowOf(menu, 'Trades');
    expect(within(second).getByText('1 card')).toBeVisible();
    expect(within(second).getByRole('button', { name: 'Make default' })).toBeEnabled();
    expect(await axe(menu)).toHaveNoViolations();
  }, 30000);

  it('opening another list writes it to the URL and closes the sheet', async () => {
    installWishlists();
    const { where } = await openPage();
    await cards();
    const menu = await openMenu();
    await userEvent.click(within(rowOf(menu, 'Trades')).getByRole('button', { name: /^Trades/ }));
    expect(await cards('Trades')).toBeVisible();
    await waitFor(() => expect(where()).toBe('/collection/wishlists?list=2'));
    expect(screen.queryByRole('dialog', { name: 'Your wishlists' })).toBeNull();
  }, 20000);

  it('creates a list, opens it, and refuses a taken name and the 21st list', async () => {
    const state = installWishlists();
    const sent = recordWishlistRequests();
    const { where } = await openPage();
    await cards();
    let menu = await openMenu();
    await userEvent.click(within(menu).getByRole('button', { name: 'New list' }));
    let form = await screen.findByRole('dialog', { name: 'New list' });
    const name = within(form).getByRole('textbox', { name: 'Name' });
    // empty name: checked before sending
    await userEvent.click(within(form).getByRole('button', { name: 'Create' }));
    expect(within(form).getByText('Enter a name.')).toBeVisible();
    // taken (ignoring case): the server's 409 already_exists on the field
    await userEvent.type(name, 'trades');
    await userEvent.click(within(form).getByRole('button', { name: 'Create' }));
    expect(
      await within(form).findByText('You already have a list with this name.', {}, LONG),
    ).toBeVisible();
    expect(name).toHaveAttribute('aria-invalid', 'true');
    await userEvent.clear(name);
    await userEvent.type(name, 'Modern');
    await userEvent.click(within(form).getByRole('button', { name: 'Create' }));
    expect(await findToast('List “Modern” created.')).toBeVisible();
    // the new list is open (and empty)
    await waitFor(
      () => expect(screen.getByRole('button', { name: /Change list/ })).toHaveTextContent('Modern'),
      LONG,
    );
    expect(
      await screen.findByRole('heading', { name: 'No cards in this list yet' }, LONG),
    ).toBeVisible();
    await waitFor(() => expect(where()).toMatch(/^\/collection\/wishlists\?list=\d+$/));
    expect(writes(sent).filter((r) => r.method === 'POST')).toEqual([
      expect.objectContaining({ path: '/wishlists', body: { name: 'trades' } }),
      expect.objectContaining({ path: '/wishlists', body: { name: 'Modern' } }),
    ]);
    expect(state.lists.map((list) => list.name)).toContain('Modern');

    // 20 lists: the server's 409 wishlist_limit
    state.lists = manyLists(20);
    menu = await openMenu();
    await userEvent.click(within(menu).getByRole('button', { name: 'New list' }));
    form = await screen.findByRole('dialog', { name: 'New list' });
    await userEvent.type(within(form).getByRole('textbox', { name: 'Name' }), 'One more');
    await userEvent.click(within(form).getByRole('button', { name: 'Create' }));
    expect(
      await within(form).findByText(
        'You already have 20 lists, the most you can have. Delete one first.',
        {},
        LONG,
      ),
    ).toBeVisible();
  }, 40000);

  it('renames a list', async () => {
    const state = installWishlists();
    await openPage();
    await cards();
    const menu = await openMenu();
    await userEvent.click(await rowAction(menu, 'Trades', 'Rename'));
    const form = await screen.findByRole('dialog', { name: 'Rename Trades' });
    const name = within(form).getByRole('textbox', { name: 'Name' });
    expect(name).toHaveValue('Trades');
    await userEvent.clear(name);
    await userEvent.type(name, 'For trade');
    await userEvent.click(within(form).getByRole('button', { name: 'Save' }));
    expect(await findToast('List renamed.')).toBeVisible();
    expect(state.lists.find((list) => list.id === 2)?.name).toBe('For trade');
  }, 30000);

  it('makes another list the default with its star', async () => {
    const state = installWishlists();
    const sent = recordWishlistRequests();
    await openPage();
    await cards();
    const menu = await openMenu();
    await userEvent.click(
      within(rowOf(menu, 'Trades')).getByRole('button', { name: 'Make default' }),
    );
    expect(await findToast('“Trades” is now your default list.')).toBeVisible();
    expect(writes(sent)).toEqual([
      expect.objectContaining({
        method: 'PATCH',
        path: '/wishlists/2',
        body: { is_default: true },
      }),
    ]);
    await waitFor(() =>
      expect(
        within(rowOf(menu, 'Trades')).getByRole('button', { name: 'Default list' }),
      ).toBeDisabled(),
    );
    expect(
      within(rowOf(menu, 'Wishlist')).getByRole('button', { name: 'Make default' }),
    ).toBeEnabled();
    expect(state.lists.find((list) => list.is_default)?.id).toBe(2);
  }, 30000);

  it('the default list cannot be deleted: the action is disabled with its reason', async () => {
    installWishlists();
    await openPage();
    await cards();
    const menu = await openMenu();
    const remove = await rowAction(menu, 'Wishlist', 'Delete');
    expect(remove).toBeDisabled();
    expect(remove).toHaveAccessibleDescription('Star another list first');
  }, 20000);

  it('a 409 wishlist_default from the server is shown', async () => {
    installWishlists();
    server.use(
      http.delete(`${API}/wishlists/:id`, () =>
        failure(409, {
          error: 'Conflict',
          message: 'The default list cannot be deleted. Star another list first.',
          code: 'wishlist_default',
        }),
      ),
    );
    await openPage();
    await cards();
    const menu = await openMenu();
    await userEvent.click(await rowAction(menu, 'Trades', 'Delete'));
    const confirm = await screen.findByRole('dialog', { name: 'Delete “Trades”?' });
    await userEvent.click(within(confirm).getByRole('button', { name: 'Delete' }));
    expect(
      await findToast('The default list cannot be deleted. Star another list first.'),
    ).toBeVisible();
  }, 30000);

  it('deletes a list after confirming how many cards go, and Undo rebuilds it', async () => {
    const state = installWishlists();
    const sent = recordWishlistRequests();
    await openPage('/collection/wishlists?list=2');
    await cards('Trades');
    const menu = await openMenu();
    await userEvent.click(await rowAction(menu, 'Trades', 'Delete'));
    const confirm = await screen.findByRole('dialog', { name: 'Delete “Trades”?' });
    expect(within(confirm).getByText('Its 1 card goes with it.')).toBeVisible();
    await userEvent.click(within(confirm).getByRole('button', { name: 'Delete' }));
    expect(await findToast('List “Trades” deleted.')).toBeVisible();
    expect(state.lists.map((list) => list.name)).toEqual(['Wishlist']);
    // the deleted list was open: the default list takes its place
    expect(await cards('Wishlist')).toBeVisible();

    await userEvent.click(screen.getByRole('button', { name: 'Undo' }));
    expect(await findToast('List “Trades” restored.')).toBeVisible();
    const restored = state.lists.find((list) => list.name === 'Trades');
    expect(restored?.position).toBe(2);
    expect(
      state.lines.filter((item) => item.list_id === restored?.id).map((item) => item.name),
    ).toEqual(['Spark Token']);
    const after = writes(sent).slice(1);
    expect(after[0]).toMatchObject({
      method: 'POST',
      path: '/wishlists',
      body: { name: 'Trades' },
    });
    expect(after[1]).toMatchObject({
      method: 'POST',
      path: `/wishlists/${restored?.id}/lines`,
      body: { set_id: 'OGN', card_id: 't01', name: 'Spark Token', foil: 'any', qty: 1 },
    });
  }, 40000);

  it('moves a list down from its menu (PUT /wishlists/order)', async () => {
    const state = installWishlists();
    const sent = recordWishlistRequests();
    await openPage();
    await cards();
    const menu = await openMenu();
    await userEvent.click(await rowAction(menu, 'Wishlist', 'Move down'));
    await waitFor(() =>
      expect(writes(sent)).toEqual([
        expect.objectContaining({ method: 'PUT', path: '/wishlists/order', body: { ids: [2, 1] } }),
      ]),
    );
    await waitFor(() =>
      expect(
        within(within(menu).getByRole('list', { name: 'Your wishlists' }))
          .getAllByRole('listitem')
          .map((item) => item.querySelector('[data-slot="name"]')?.textContent),
      ).toEqual(['Trades', 'Wishlist']),
    );
    expect(state.lists.find((list) => list.id === 1)?.position).toBe(2);
  }, 30000);
});

describe('Wishlists at 390 px (F3-j): the lines', () => {
  it('shows each line with its quantity, finish, prices and owned indicators', async () => {
    installWishlists();
    await openPage();
    await cards();
    expect(screen.getByText('3 of 100')).toBeVisible();
    // 1.21 x 2 + 0.45 x 4 = 4.22; the rune has no price
    expect(screen.getByText('4.22 €')).toBeVisible();
    const strip = screen.getByText('Unpriced', { selector: 'dt' }).closest('div')!;
    expect(within(strip).getByText('1')).toBeVisible();

    const ayla = cardOf("Ayla, Fury's Champion");
    expect(within(ayla).getByText('OGN · #79')).toBeVisible();
    expect(within(ayla).getByText('Any finish')).toBeVisible();
    expect(within(ayla).getByRole('spinbutton', { name: 'Wanted' })).toHaveValue(2);
    expect(within(ayla).getByRole('spinbutton', { name: 'Max price' })).toHaveValue(3);
    expect(within(ayla).getByText('Reached')).toBeVisible();
    expect(within(ayla).getByText('1.21 €')).toBeVisible();
    expect(within(ayla).getByText('Owned: 3 of this version (1 foil)')).toBeVisible();
    expect(within(ayla).getByText('Other versions: 2 (1 alt art, 0 foil)')).toBeVisible();
    expect(within(ayla).getByRole('textbox', { name: 'Note' })).toHaveValue('For the fury deck');

    const ember = cardOf('Ember Wisp');
    expect(within(ember).getByText('Foil')).toBeVisible();
    expect(within(ember).getByText('No alert price')).toBeVisible();
    expect(within(ember).queryByText('Reached')).toBeNull();
    expect(within(ember).getByText('Owned: 0 of this version')).toHaveAttribute('data-zero');
    expect(within(ember).getByText('Other versions: 0')).toHaveAttribute('data-zero');

    const rune = cardOf('Fury Rune');
    expect(within(rune).getByText('Any printing')).toBeVisible();
    expect(within(rune).getByText('Owned: 1 of any printing')).toBeVisible();
    expect(within(rune).getByText('—')).toBeVisible();
    expect(within(rune).getByText('Not reached')).toBeVisible();
  }, 20000);

  it('changes the quantity with the stepper (PATCH qty)', async () => {
    const state = installWishlists();
    const sent = recordWishlistRequests();
    await openPage();
    await cards();
    const ayla = cardOf("Ayla, Fury's Champion");
    await userEvent.click(within(ayla).getByRole('button', { name: 'More copies: Wanted' }));
    await waitFor(() =>
      expect(writes(sent)).toEqual([
        expect.objectContaining({
          method: 'PATCH',
          path: '/wishlists/1/lines/101',
          body: { qty: 3 },
        }),
      ]),
    );
    await waitFor(() =>
      expect(
        within(cardOf("Ayla, Fury's Champion")).getByRole('spinbutton', { name: 'Wanted' }),
      ).toHaveValue(3),
    );
    expect(state.lines.find((item) => item.id === 101)?.qty).toBe(3);
  }, 20000);

  it('changes the finish of a line (PATCH foil) (F3-j follow-ups)', async () => {
    const state = installWishlists();
    const sent = recordWishlistRequests();
    await openPage();
    await cards();
    const finish = within(cardOf("Ayla, Fury's Champion")).getByRole('combobox', {
      name: 'Finish',
    });
    expect(finish).toHaveValue('any');
    await userEvent.selectOptions(finish, 'Non-foil');
    await waitFor(() =>
      expect(writes(sent)).toEqual([
        expect.objectContaining({
          method: 'PATCH',
          path: '/wishlists/1/lines/101',
          body: { foil: 'N' },
        }),
      ]),
    );
    expect(await findToast('Saved.')).toBeVisible();
    expect(
      within(cardOf("Ayla, Fury's Champion")).getByRole('combobox', { name: 'Finish' }),
    ).toHaveValue('N');
    expect(state.lines.find((item) => item.id === 101)?.foil).toBe('N');
  }, 20000);

  it('a finish another line of the list has: the 409 is explained and the finish goes back (F3-j follow-ups)', async () => {
    const emberPlain = line({
      id: 104,
      list_id: 1,
      name: foilCommon.name,
      set_id: 'OGN',
      card_id: '12',
      card: miniOf(foilCommon),
      foil: 'N',
    });
    const state = installWishlists(undefined, [...wishlistLines, emberPlain]);
    await openPage();
    await cards();
    const ember = screen
      .getAllByRole('combobox', { name: 'Finish' })
      .find((select) => (select as HTMLSelectElement).value === 'S')!;
    await userEvent.selectOptions(ember, 'Non-foil');
    expect(await findToast('Another line of this list already has that finish.')).toBeVisible();
    await waitFor(() => expect(ember).toHaveValue('S'));
    expect(state.lines.find((item) => item.id === 102)?.foil).toBe('S');
  }, 20000);

  it('foil_not_allowed from the server: the finish goes back with its message (F3-j follow-ups)', async () => {
    const state = installWishlists();
    await openPage('/collection/wishlists?list=2');
    await cards('Trades');
    const finish = within(cardOf('Spark Token')).getByRole('combobox', { name: 'Finish' });
    await userEvent.selectOptions(finish, 'Foil');
    expect(await findToast('This card has no foil version.')).toBeVisible();
    await waitFor(() => expect(finish).toHaveValue('any'));
    expect(state.lines.find((item) => item.id === 201)?.foil).toBe('any');
  }, 20000);

  it('offers no foil finish for a card without a foil version (F3-j follow-ups)', async () => {
    installWishlists();
    await openPage();
    await cards();
    const foilOf = (name: string) =>
      within(within(cardOf(name)).getByRole('combobox', { name: 'Finish' })).getByRole('option', {
        name: 'Foil',
      });
    // a rare and a rune have no foil version; a common has one
    expect(foilOf("Ayla, Fury's Champion")).toBeDisabled();
    expect(foilOf('Fury Rune')).toBeDisabled();
    expect(foilOf('Ember Wisp')).toBeEnabled();
  }, 20000);

  it('sets and clears the max price (PATCH max_price) and saves the note', async () => {
    const sent = recordWishlistRequests();
    installWishlists();
    await openPage();
    await cards();
    const ember = cardOf('Ember Wisp');
    await userEvent.type(within(ember).getByRole('spinbutton', { name: 'Max price' }), '0.5');
    await waitFor(
      () =>
        expect(writes(sent)).toContainEqual(
          expect.objectContaining({ path: '/wishlists/1/lines/102', body: { max_price: 0.5 } }),
        ),
      LONG,
    );
    expect(await within(cardOf('Ember Wisp')).findByText('Reached', {}, LONG)).toBeVisible();

    const ayla = cardOf("Ayla, Fury's Champion");
    await userEvent.clear(within(ayla).getByRole('spinbutton', { name: 'Max price' }));
    await waitFor(
      () =>
        expect(writes(sent)).toContainEqual(
          expect.objectContaining({ path: '/wishlists/1/lines/101', body: { max_price: null } }),
        ),
      LONG,
    );
    expect(
      await within(cardOf("Ayla, Fury's Champion")).findByText('No alert price', {}, LONG),
    ).toBeVisible();

    const note = within(cardOf("Ayla, Fury's Champion")).getByRole('textbox', { name: 'Note' });
    await userEvent.clear(note);
    await userEvent.type(note, 'Trade bait');
    await waitFor(
      () =>
        expect(writes(sent)).toContainEqual(
          expect.objectContaining({ path: '/wishlists/1/lines/101', body: { note: 'Trade bait' } }),
        ),
      LONG,
    );
    expect(note).toHaveAttribute('maxlength', '200');
  }, 30000);

  it('removes a line, and Undo posts it back', async () => {
    const state = installWishlists();
    const sent = recordWishlistRequests();
    await openPage();
    await cards();
    await userEvent.click(within(cardOf('Ember Wisp')).getByRole('button', { name: 'Remove' }));
    expect(await findToast('Ember Wisp removed.')).toBeVisible();
    await waitFor(() => expect(screen.queryByRole('heading', { name: 'Ember Wisp' })).toBeNull());
    await userEvent.click(screen.getByRole('button', { name: 'Undo' }));
    expect(await screen.findByRole('heading', { name: 'Ember Wisp' }, LONG)).toBeVisible();
    expect(writes(sent)).toEqual([
      expect.objectContaining({ method: 'DELETE', path: '/wishlists/1/lines/102' }),
      expect.objectContaining({
        method: 'POST',
        path: '/wishlists/1/lines',
        body: {
          set_id: 'OGN',
          card_id: '12',
          name: 'Ember Wisp',
          foil: 'S',
          qty: 4,
          max_price: null,
          note: null,
        },
      }),
    ]);
    expect(state.lines.filter((item) => item.name === 'Ember Wisp')).toHaveLength(1);
  }, 30000);

  it('moves a line to another list and reports the counts', async () => {
    const state = installWishlists();
    await openPage();
    await cards();
    await userEvent.click(
      within(cardOf('Ember Wisp')).getByRole('button', { name: 'Move or copy' }),
    );
    const sheet = await screen.findByRole('dialog', { name: 'Move or copy Ember Wisp' });
    expect(within(sheet).getByRole('combobox', { name: 'To list' })).toHaveValue('2');
    await userEvent.click(within(sheet).getByRole('button', { name: 'Move' }));
    expect(await findToast('Moved: 1 · Merged: 0 · Skipped: 0')).toBeVisible();
    expect(
      state.lines.filter((item) => item.name === 'Ember Wisp').map((item) => item.list_id),
    ).toEqual([2]);
    await waitFor(() => expect(screen.queryByRole('heading', { name: 'Ember Wisp' })).toBeNull());
  }, 30000);

  it('copies a line, and a full list answers with the limit', async () => {
    const state = installWishlists();
    const sent = recordWishlistRequests();
    await openPage();
    await cards();
    await userEvent.click(
      within(cardOf('Fury Rune')).getByRole('button', { name: 'Move or copy' }),
    );
    let sheet = await screen.findByRole('dialog', { name: 'Move or copy Fury Rune' });
    await userEvent.click(within(sheet).getByRole('radio', { name: 'Copy' }));
    await userEvent.click(within(sheet).getByRole('button', { name: 'Copy' }));
    expect(await findToast('Moved: 1 · Merged: 0 · Skipped: 0')).toBeVisible();
    expect(writes(sent)[0]).toMatchObject({
      path: '/wishlists/1/lines/move',
      body: { line_ids: [103], to_list_id: 2, mode: 'copy' },
    });
    expect(state.lines.filter((item) => item.name === 'Fury Rune')).toHaveLength(2);

    server.use(
      http.post(`${API}/wishlists/:id/lines/move`, () =>
        failure(409, {
          error: 'Conflict',
          message: 'A wishlist can hold at most 100 cards.',
          code: 'wishlist_limit',
          params: { scope: 'lines', max: 100 },
        }),
      ),
    );
    await userEvent.click(
      within(cardOf('Ember Wisp')).getByRole('button', { name: 'Move or copy' }),
    );
    sheet = await screen.findByRole('dialog', { name: 'Move or copy Ember Wisp' });
    await userEvent.click(within(sheet).getByRole('button', { name: 'Move' }));
    expect(
      await within(sheet).findByText('That list is full: at most 100 cards.', {}, LONG),
    ).toBeVisible();
  }, 40000);

  it('writes the search to the URL and filters the lines', async () => {
    installWishlists();
    const sent = recordWishlistRequests();
    const { where } = await openPage();
    await cards();
    await userEvent.type(screen.getByRole('searchbox', { name: 'Search this list' }), 'ember');
    await waitFor(() => expect(where()).toBe('/collection/wishlists?q=ember'), LONG);
    await waitFor(
      () => expect(screen.queryByRole('heading', { name: "Ayla, Fury's Champion" })).toBeNull(),
      LONG,
    );
    expect(screen.getByRole('heading', { name: 'Ember Wisp' })).toBeVisible();
    expect(sent.some((r) => r.path === '/wishlists/1/lines' && r.search === '?q=ember')).toBe(true);
  }, 20000);

  it('an empty list offers to add a card', async () => {
    installWishlists([defaultList, tradesList], []);
    await openPage();
    expect(
      await screen.findByRole('heading', { name: 'No cards in this list yet' }, LONG),
    ).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: 'Add card' }));
    expect(await screen.findByRole('dialog', { name: 'Add to Wishlist' })).toBeVisible();
  }, 20000);

  it('a failed load offers a retry', async () => {
    installWishlists();
    let fail = true;
    server.use(
      http.get(`${API}/wishlists/:id/lines`, () => {
        if (fail) {
          fail = false;
          return failure(500, { error: 'Internal Server Error' });
        }
        return undefined;
      }),
    );
    await openPage();
    expect(
      await screen.findByText('The cards of this list could not be loaded.', {}, LONG),
    ).toBeVisible();
    server.resetHandlers();
    signedIn();
    installWishlists();
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await cards()).toBeVisible();
  }, 20000);

  it('offline: shows the lines read-only', async () => {
    installWishlists();
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    await openPage();
    await cards();
    expect(screen.getByText('You need a connection to make changes.')).toBeVisible();
    const ayla = cardOf("Ayla, Fury's Champion");
    expect(within(ayla).getByRole('spinbutton', { name: 'Wanted' })).toBeDisabled();
    expect(within(ayla).getByRole('spinbutton', { name: 'Max price' })).toBeDisabled();
    expect(within(ayla).getByRole('textbox', { name: 'Note' })).toBeDisabled();
    expect(within(ayla).getByRole('combobox', { name: 'Finish' })).toBeDisabled();
    expect(within(ayla).getByRole('button', { name: 'Remove' })).toBeDisabled();
    expect(within(ayla).getByRole('button', { name: 'Move or copy' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Add card' })).toBeDisabled();
    const menu = await openMenu();
    expect(within(menu).getByRole('button', { name: 'New list' })).toBeDisabled();
    expect(
      within(rowOf(menu, 'Trades')).getByRole('button', { name: 'Make default' }),
    ).toBeDisabled();
  }, 20000);

  it('is axe clean', async () => {
    installWishlists();
    const { container } = await openPage();
    await cards();
    expect(await axe(container)).toHaveNoViolations();
  }, 30000);
});

describe('Wishlists at 390 px (F3-j): adding a card', () => {
  const addSheet = async () => {
    await userEvent.click(screen.getByRole('button', { name: 'Add card' }));
    return screen.findByRole('dialog', { name: 'Add to Wishlist' });
  };
  const pick = async (sheet: HTMLElement, query: string, option: RegExp) => {
    await userEvent.type(within(sheet).getByRole('combobox', { name: 'Card' }), query);
    await userEvent.click(await within(sheet).findByRole('option', { name: option }, LONG));
  };

  it('adds a printing with finish, quantity, max price and note', async () => {
    const state = installWishlists([defaultList, tradesList], []);
    const sent = recordWishlistRequests();
    await openPage();
    await screen.findByRole('heading', { name: 'No cards in this list yet' }, LONG);
    const sheet = await addSheet();
    expect(await axe(sheet)).toHaveNoViolations();
    await pick(sheet, 'Ayla', /Ayla/);
    expect(within(sheet).getByText("Chosen: Ayla, Fury's Champion (OGN #79)")).toBeVisible();
    await userEvent.click(within(sheet).getByRole('radio', { name: 'Foil' }));
    await userEvent.click(within(sheet).getByRole('button', { name: 'More copies: Wanted' }));
    await userEvent.type(
      within(sheet).getByRole('spinbutton', { name: 'Max price (optional)' }),
      '2.5',
    );
    await userEvent.type(
      within(sheet).getByRole('textbox', { name: 'Note (optional)' }),
      'Playset',
    );
    await waitFor(() =>
      expect(within(sheet).getByRole('spinbutton', { name: 'Max price (optional)' })).toHaveValue(
        2.5,
      ),
    );
    await new Promise((resolve) => setTimeout(resolve, 600));
    await userEvent.click(within(sheet).getByRole('button', { name: 'Add' }));
    expect(await findToast("Ayla, Fury's Champion added.")).toBeVisible();
    expect(writes(sent)).toEqual([
      expect.objectContaining({
        method: 'POST',
        path: '/wishlists/1/lines',
        body: { set_id: 'OGN', card_id: '79', foil: 'S', qty: 2, max_price: 2.5, note: 'Playset' },
      }),
    ]);
    expect(state.lines).toHaveLength(1);
    // the sheet stays open for the next card
    expect(within(sheet).getByText('Choose a card first.')).toBeVisible();
  }, 40000);

  it('adds by name (any printing) and says when it merged', async () => {
    installWishlists();
    const sent = recordWishlistRequests();
    await openPage();
    await cards();
    const sheet = await addSheet();
    await userEvent.click(within(sheet).getByRole('switch', { name: 'Any printing' }));
    await pick(sheet, 'Fury', /Fury Rune/);
    await userEvent.click(within(sheet).getByRole('button', { name: 'Add' }));
    expect(await findToast('Merged into an existing line.')).toBeVisible();
    expect(writes(sent)[0].body).toEqual({
      name: 'Fury Rune',
      foil: 'any',
      qty: 1,
      max_price: null,
      note: null,
    });
  }, 30000);

  it('disables foil for a card without a foil version', async () => {
    installWishlists();
    await openPage();
    await cards();
    const sheet = await addSheet();
    await pick(sheet, 'Spark', /Spark Token/);
    expect(within(sheet).getByRole('radio', { name: 'Foil' })).toBeDisabled();
    expect(within(sheet).getByText('This card has no foil version.')).toBeVisible();
  }, 30000);

  it('a full list answers with the limit', async () => {
    installWishlists();
    server.use(
      http.post(`${API}/wishlists/:id/lines`, () =>
        failure(409, {
          error: 'Conflict',
          message: 'A wishlist can hold at most 100 cards.',
          code: 'wishlist_limit',
          params: { scope: 'lines', max: 100 },
        }),
      ),
    );
    await openPage();
    await cards();
    const sheet = await addSheet();
    await pick(sheet, 'Spark', /Spark Token/);
    await userEvent.click(within(sheet).getByRole('button', { name: 'Add' }));
    expect(
      await within(sheet).findByText('That list is full: at most 100 cards.', {}, LONG),
    ).toBeVisible();
  }, 30000);
});
