import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';
import { clearToasts } from '@/components/ui/toastStore';
import { API, failure } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';
import {
  findToast,
  installWishlists,
  recordWishlistRequests,
  signedIn,
  writes,
} from '@/test/wishlists';

const LONG = { timeout: 10000 };

afterEach(() => {
  vi.restoreAllMocks();
  server.events.removeAllListeners();
  clearToasts();
});

async function openCard() {
  signedIn();
  const app = await renderApp({ path: '/cards/OGN/79', width: 390 });
  const section = await screen.findByRole('region', { name: 'Wishlists' }, LONG);
  return { ...app, section };
}

describe('Card detail: Add to wishlist (F3-j)', () => {
  it('adds one copy to the default list, named on the button, and links to it', async () => {
    const state = installWishlists();
    const sent = recordWishlistRequests();
    const { section, where } = await openCard();
    const add = await within(section).findByRole('button', { name: 'Add to Wishlist' }, LONG);
    await userEvent.click(add);
    // Ayla is already in the list: the copy merged into its line (the toast says so)
    expect(await findToast('Added one more to Wishlist.')).toBeVisible();
    expect(writes(sent)).toEqual([
      expect.objectContaining({
        method: 'POST',
        path: '/wishlists/1/lines',
        body: { set_id: 'OGN', card_id: '79', foil: 'any', qty: 1 },
      }),
    ]);
    expect(state.lines.find((item) => item.id === 101)?.qty).toBe(3);
    await userEvent.click(screen.getByRole('button', { name: 'Open list' }));
    await waitFor(() => expect(where()).toBe('/collection/wishlists?list=1'), LONG);
  }, 30000);

  it('adds to another list chosen in a sheet', async () => {
    const state = installWishlists();
    const { section } = await openCard();
    await userEvent.click(
      await within(section).findByRole('button', { name: 'Choose list…' }, LONG),
    );
    const sheet = await screen.findByRole('dialog', {
      name: "Add Ayla, Fury's Champion to a list",
    });
    expect(await axe(sheet)).toHaveNoViolations();
    await userEvent.click(within(sheet).getByRole('button', { name: /^Trades/ }));
    expect(await findToast('Added to Trades.')).toBeVisible();
    expect(state.lines.filter((item) => item.list_id === 2).map((item) => item.name)).toContain(
      "Ayla, Fury's Champion",
    );
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
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
    const { section } = await openCard();
    await userEvent.click(
      await within(section).findByRole('button', { name: 'Add to Wishlist' }, LONG),
    );
    expect(await findToast('That list is full: at most 100 cards.')).toBeVisible();
  }, 30000);

  it('offline: the buttons are disabled', async () => {
    installWishlists();
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    const { section } = await openCard();
    expect(
      await within(section).findByRole('button', { name: 'Add to Wishlist' }, LONG),
    ).toBeDisabled();
    expect(within(section).getByRole('button', { name: 'Choose list…' })).toBeDisabled();
  }, 30000);
});
