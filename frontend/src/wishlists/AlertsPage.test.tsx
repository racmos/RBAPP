import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';
import { clearToasts } from '@/components/ui/toastStore';
import { aylaAlert, emberAlert, tokenAlert } from '@/test/fixtures/wishlists';
import { API, failure } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';
import { installAlerts, installWishlists, manyAlerts, signedIn } from '@/test/wishlists';

const LONG = { timeout: 10000 };
const PHONE = 390;
const PATH = '/collection/wishlists/alerts';

afterEach(() => {
  vi.restoreAllMocks();
  server.events.removeAllListeners();
  clearToasts();
});

async function openPage(path = PATH, width = PHONE) {
  signedIn();
  return renderApp({ path, width });
}

const alertList = () => screen.findByRole('list', { name: 'Your price alerts' }, LONG);
const itemOf = (name: string) =>
  screen
    .getAllByRole('listitem')
    .find((item) => within(item).queryByRole('heading', { name })) as HTMLElement;
const sectionsNav = () => screen.getByRole('navigation', { name: 'Wishlist sections' });
const collectionNav = () => screen.getByRole('navigation', { name: 'Collection sections' });

describe('Price alerts (F4-g-2): the list', () => {
  it('shows each alert newest first with the card, the price reached, the date and unread', async () => {
    const state = installAlerts();
    await openPage();
    const list = await alertList();
    const headings = within(list)
      .getAllByRole('heading', { level: 2 })
      .map((heading) => heading.textContent);
    expect(headings).toEqual(["Ayla, Fury's Champion", 'Ember Wisp', 'Spark Token']);
    const ayla = itemOf("Ayla, Fury's Champion");
    expect(within(ayla).getByText('Reached 2.50 € (your price 3.00 €)')).toBeVisible();
    expect(within(ayla).getByText('Price of 21 Oct 2026')).toBeVisible();
    expect(within(ayla).getByText('OGN · #79')).toBeVisible();
    expect(within(ayla).getByText('Unread')).toBeInTheDocument();
    expect(within(itemOf('Ember Wisp')).getByText('Any printing')).toBeVisible();
    expect(within(itemOf('Spark Token')).queryByText('Unread')).toBeNull();
    expect(state.sent[0]).toMatchObject({
      method: 'GET',
      path: '/wishlist-alerts',
      search: '?page=1&per_page=25',
    });
    // opening the screen marks nothing read
    expect(state.sent.filter((request) => request.method === 'POST')).toEqual([]);
  }, 20000);

  it('pages with Show more', async () => {
    installAlerts(manyAlerts(30));
    await openPage();
    const list = await alertList();
    expect(within(list).getAllByRole('heading', { level: 2 })).toHaveLength(25);
    await userEvent.click(screen.getByRole('button', { name: 'Show more' }));
    await waitFor(
      () => expect(within(list).getAllByRole('heading', { level: 2 })).toHaveLength(30),
      LONG,
    );
    expect(screen.queryByRole('button', { name: 'Show more' })).toBeNull();
  }, 20000);

  it('"Unread only" filters through the URL', async () => {
    const state = installAlerts();
    const { where } = await openPage();
    await alertList();
    await userEvent.click(screen.getByRole('switch', { name: 'Unread only' }));
    await waitFor(() => expect(where()).toBe(`${PATH}?unread=true`), LONG);
    expect(await screen.findByRole('heading', { name: 'Ember Wisp' }, LONG)).toBeVisible();
    expect(screen.queryByRole('heading', { name: 'Spark Token' })).toBeNull();
    expect(state.sent.some((request) => request.search.includes('unread=true'))).toBe(true);
  }, 20000);

  it('opens with the filter of the URL', async () => {
    installAlerts();
    await openPage(`${PATH}?unread=true`);
    await alertList();
    expect(screen.getByRole('switch', { name: 'Unread only' })).toHaveAttribute(
      'aria-checked',
      'true',
    );
    expect(screen.queryByRole('heading', { name: 'Spark Token' })).toBeNull();
  }, 20000);

  it('empty: explains how alerts appear', async () => {
    installAlerts([]);
    await openPage();
    expect(await screen.findByRole('heading', { name: 'No price alerts yet' }, LONG)).toBeVisible();
    expect(
      screen.getByText(
        'Give a card a max price in one of your wishlists to be told when the market price gets there.',
      ),
    ).toBeVisible();
    expect(screen.getByRole('button', { name: 'Mark all as read' })).toBeDisabled();
  }, 20000);

  it('empty with "Unread only": offers every alert', async () => {
    installAlerts([tokenAlert]);
    const { where } = await openPage(`${PATH}?unread=true`);
    expect(await screen.findByRole('heading', { name: 'No unread alerts' }, LONG)).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: 'Show all alerts' }));
    await waitFor(() => expect(where()).toBe(PATH), LONG);
    expect(await screen.findByRole('heading', { name: 'Spark Token' }, LONG)).toBeVisible();
  }, 20000);

  it('a failure offers Retry', async () => {
    server.use(http.get(`${API}/wishlist-alerts`, () => failure(500)));
    await openPage();
    expect(
      await screen.findByText('Your price alerts could not be loaded.', {}, LONG),
    ).toBeVisible();
    installAlerts();
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await alertList()).toBeVisible();
  }, 20000);
});

describe('Price alerts (F4-g-2): lists with the card', () => {
  it('expanding shows the lists that hold the card now, each a link, and marks it read', async () => {
    const state = installAlerts();
    await openPage();
    await alertList();
    const ayla = itemOf("Ayla, Fury's Champion");
    const toggle = within(ayla).getByRole('button', { name: 'Lists with this card' });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    const lists = await within(ayla).findByRole('list', { name: 'Lists with this card' }, LONG);
    const links = within(lists).getAllByRole('link');
    expect(links.map((link) => link.textContent)).toEqual(['Wishlist', 'Trades']);
    expect(links[0]).toHaveAttribute('href', '/riftbound/app/collection/wishlists?list=1');
    expect(links[1]).toHaveAttribute('href', '/riftbound/app/collection/wishlists?list=2');
    expect(within(lists).getByText('Wanted: 2 · max 3.00 €')).toBeVisible();
    expect(within(lists).getByText('Wanted: 1')).toBeVisible();
    await waitFor(() =>
      expect(state.sent.filter((request) => request.method === 'POST')).toEqual([
        { method: 'POST', path: '/wishlist-alerts/read', search: '', body: { ids: [31] } },
      ]),
    );
    await waitFor(() => expect(within(ayla).queryByText('Unread')).toBeNull(), LONG);
    // collapsing hides the lists again
    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(within(ayla).queryByRole('list', { name: 'Lists with this card' })).toBeNull();
  }, 20000);

  it('a list link opens that wishlist', async () => {
    installAlerts();
    installWishlists();
    const { where } = await openPage();
    await alertList();
    const ayla = itemOf("Ayla, Fury's Champion");
    await userEvent.click(within(ayla).getByRole('button', { name: 'Lists with this card' }));
    const lists = await within(ayla).findByRole('list', { name: 'Lists with this card' }, LONG);
    await userEvent.click(within(lists).getByRole('link', { name: 'Trades' }));
    await waitFor(() => expect(where()).toBe('/collection/wishlists?list=2'), LONG);
  }, 20000);

  it('no list holds the card any more (a deleted list is not listed)', async () => {
    installAlerts([emberAlert], {});
    await openPage();
    await alertList();
    const ember = itemOf('Ember Wisp');
    await userEvent.click(within(ember).getByRole('button', { name: 'Lists with this card' }));
    expect(await within(ember).findByText('No list holds this card now.', {}, LONG)).toBeVisible();
  }, 20000);

  it('expanding a read alert marks nothing', async () => {
    const state = installAlerts([tokenAlert], { 29: [] });
    await openPage();
    await alertList();
    const tokenItem = itemOf('Spark Token');
    await userEvent.click(within(tokenItem).getByRole('button', { name: 'Lists with this card' }));
    await within(tokenItem).findByText('No list holds this card now.', {}, LONG);
    expect(state.sent.filter((request) => request.method === 'POST')).toEqual([]);
  }, 20000);

  it('the lists failing to load offer Retry', async () => {
    installAlerts([aylaAlert]);
    server.use(http.get(`${API}/wishlist-alerts/:id/lists`, () => failure(500)));
    await openPage();
    await alertList();
    const ayla = itemOf("Ayla, Fury's Champion");
    await userEvent.click(within(ayla).getByRole('button', { name: 'Lists with this card' }));
    expect(await within(ayla).findByText('The lists could not be loaded.', {}, LONG)).toBeVisible();
    expect(within(ayla).getByRole('button', { name: 'Retry' })).toBeVisible();
  }, 20000);
});

describe('Price alerts (F4-g-2): marking read and the badge', () => {
  it('"Mark all as read" marks every alert and the badges go', async () => {
    const state = installAlerts();
    await openPage();
    await alertList();
    expect(within(sectionsNav()).getByRole('img', { name: '2 unread alerts' })).toBeInTheDocument();
    expect(
      within(collectionNav()).getByRole('img', { name: '2 unread alerts' }),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Mark all as read' }));
    await waitFor(() =>
      expect(state.sent.filter((request) => request.method === 'POST')).toEqual([
        { method: 'POST', path: '/wishlist-alerts/read', search: '', body: {} },
      ]),
    );
    await waitFor(() => expect(screen.queryAllByText('Unread')).toEqual([]), LONG);
    await waitFor(
      () => expect(within(sectionsNav()).queryByRole('img', { name: /unread/ })).toBeNull(),
      LONG,
    );
    expect(within(collectionNav()).queryByRole('img', { name: /unread/ })).toBeNull();
    expect(screen.getByRole('button', { name: 'Mark all as read' })).toBeDisabled();
  }, 20000);

  it('the Wishlists tab of the collection shows the badge', async () => {
    installAlerts([aylaAlert]);
    await openPage('/collection');
    const nav = await screen.findByRole('navigation', { name: 'Collection sections' }, LONG);
    expect(await within(nav).findByRole('img', { name: '1 unread alert' }, LONG)).toBeVisible();
    expect(within(nav).getByRole('link', { name: /Wishlists/ })).toHaveTextContent('1');
  }, 20000);

  it('no badge when nothing is unread', async () => {
    installAlerts([tokenAlert]);
    await openPage();
    await alertList();
    expect(screen.queryByRole('img', { name: /unread/ })).toBeNull();
  }, 20000);

  it('no badge when the alerts cannot be read', async () => {
    installWishlists();
    server.use(http.get(`${API}/wishlist-alerts`, () => failure(500)));
    await openPage('/collection/wishlists');
    await screen.findByRole('navigation', { name: 'Wishlist sections' }, LONG);
    expect(screen.queryByRole('img', { name: /unread/ })).toBeNull();
  }, 20000);

  it('offline: read-only, nothing is marked read', async () => {
    const state = installAlerts();
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    await openPage();
    await alertList();
    expect(screen.getByText('You need a connection to make changes.')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Mark all as read' })).toBeDisabled();
    const ayla = itemOf("Ayla, Fury's Champion");
    await userEvent.click(within(ayla).getByRole('button', { name: 'Lists with this card' }));
    await within(ayla).findByRole('list', { name: 'Lists with this card' }, LONG);
    expect(state.sent.filter((request) => request.method === 'POST')).toEqual([]);
  }, 20000);
});

describe('Price alerts (F4-g-2): accessibility', () => {
  it.each([PHONE, 1280])(
    'is axe clean at %i px with an alert open',
    async (width) => {
      installAlerts();
      const { container } = await openPage(PATH, width);
      await alertList();
      const ayla = itemOf("Ayla, Fury's Champion");
      await userEvent.click(within(ayla).getByRole('button', { name: 'Lists with this card' }));
      await within(ayla).findByRole('list', { name: 'Lists with this card' }, LONG);
      expect(await axe(container)).toHaveNoViolations();
    },
    30000,
  );
});
