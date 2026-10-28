import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { API, NO_PREFS, ok, signedInSession } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';

const LONG = { timeout: 10000 };
const patches: Array<Record<string, unknown>> = [];

beforeEach(() => {
  patches.length = 0;
  server.events.on('request:start', async ({ request }) => {
    if (request.method === 'PATCH' && request.url.endsWith('/me/prefs')) {
      patches.push((await request.clone().json()) as Record<string, unknown>);
    }
  });
});
afterEach(() => server.events.removeAllListeners());

function signedIn(prefs: Record<string, unknown> = NO_PREFS) {
  server.use(
    http.get(`${API}/auth/session`, () => signedInSession(prefs)),
    http.patch(`${API}/me/prefs`, async ({ request }) =>
      ok({ prefs: { ...prefs, ...((await request.json()) as object) } }),
    ),
  );
}

describe('Interface page: playset size (F3-g S8)', () => {
  it('shows the setting with its hint and an empty value for the default', async () => {
    signedIn();
    await renderApp({ path: '/account/interface', width: 390 });
    const input = await screen.findByRole('spinbutton', { name: 'Tamaño del playset' }, LONG);
    expect(input).toHaveValue(null);
    expect(
      screen.getByText('Copias que quieres conservar de cada carta marcada. Por defecto, 3.'),
    ).toBeVisible();
  }, 15000);

  it('shows the stored size', async () => {
    signedIn({ ...NO_PREFS, playset_size: 4 });
    await renderApp({ path: '/account/interface', width: 390 });
    expect(await screen.findByRole('spinbutton', { name: 'Tamaño del playset' }, LONG)).toHaveValue(
      4,
    );
  }, 15000);

  it('saves a size through PATCH /me/prefs and clears it to null', async () => {
    signedIn({ ...NO_PREFS, playset_size: 4 });
    await renderApp({ path: '/account/interface', width: 390 });
    const input = await screen.findByRole('spinbutton', { name: 'Tamaño del playset' }, LONG);
    await userEvent.clear(input);
    await userEvent.type(input, '6');
    await waitFor(() => expect(patches).toContainEqual({ playset_size: 6 }), LONG);
    await userEvent.clear(input);
    await waitFor(() => expect(patches).toContainEqual({ playset_size: null }), LONG);
  }, 20000);

  it('ignores values outside 1-9', async () => {
    signedIn();
    await renderApp({ path: '/account/interface', width: 390 });
    const input = await screen.findByRole('spinbutton', { name: 'Tamaño del playset' }, LONG);
    await userEvent.type(input, '12');
    await new Promise((resolve) => setTimeout(resolve, 700));
    expect(patches.filter((p) => 'playset_size' in p)).toEqual([]);
  }, 20000);
});
