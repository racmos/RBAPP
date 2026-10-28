import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';
import { axe } from 'vitest-axe';
import { clearToasts } from '@/components/ui/toastStore';
import { collectionMeta } from '@/test/fixtures/collection';
import { API, NO_PREFS, signedInSession } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';

const LONG = { timeout: 10000 };

beforeEach(() => {
  clearToasts();
  server.use(http.get(`${API}/auth/session`, () => signedInSession(NO_PREFS)));
});

const panel = () => screen.findByRole('complementary', { name: 'Detalle de la carta' }, LONG);

describe('wide panel at 1700 px (F3-h S6)', () => {
  it('shows the first card with its chart, lines and decks', async () => {
    await renderApp({ path: '/collection', width: 1700 });
    const aside = await panel();
    expect(
      await within(aside).findByRole('heading', { name: "Ayla, Fury's Champion" }, LONG),
    ).toBeVisible();
    expect(within(aside).getByText('OGN · #79')).toBeVisible();
    expect(within(aside).getByRole('heading', { name: 'Precio, últimos 30 días' })).toBeVisible();
    const lines = within(aside).getByRole('region', { name: 'Líneas' });
    expect(within(lines).getByText(/Línea 1: ×3 · NM · English · En venta: 2/)).toBeVisible();
    expect(within(lines).getByText(/Línea 2: ×1 · EX · Spanish/)).toBeVisible();
    expect(await within(aside).findByText('Fury Chaos: 2', {}, LONG)).toBeVisible();
    expect(within(aside).getByRole('link', { name: 'Ver ficha de la carta' })).toHaveAttribute(
      'href',
      '/riftbound/app/cards/OGN/79',
    );
  }, 25000);

  it('follows the row that is clicked', async () => {
    await renderApp({ path: '/collection', width: 1700 });
    const aside = await panel();
    await within(aside).findByRole('heading', { name: "Ayla, Fury's Champion" }, LONG);
    await userEvent.click(await screen.findByRole('row', { name: /Ember Wisp/ }));
    expect(await within(aside).findByRole('heading', { name: 'Ember Wisp' }, LONG)).toBeVisible();
    expect(within(aside).getByText('OGN · #12 · Foil')).toBeVisible();
  }, 25000);

  it('says what to do when there is no card to show', async () => {
    server.use(
      http.get(`${API}/collection`, () =>
        HttpResponse.json({
          success: true,
          data: { items: [] },
          meta: { ...collectionMeta, total_groups: 0, pages: 0 },
        }),
      ),
    );
    await renderApp({ path: '/collection', width: 1700 });
    expect(
      await within(await panel()).findByText('Elige una carta para ver su detalle.'),
    ).toBeVisible();
  }, 20000);

  it('is not there below 1600 px', async () => {
    await renderApp({ path: '/collection', width: 1280 });
    await screen.findByRole('table', { name: 'Tu colección agrupada por carta' }, LONG);
    expect(screen.queryByRole('complementary', { name: 'Detalle de la carta' })).toBeNull();
  }, 20000);

  it('is axe clean', async () => {
    const { container } = await renderApp({ path: '/collection', width: 1700 });
    const aside = await panel();
    await within(aside).findByText('Fury Chaos: 2', {}, LONG);
    expect(await axe(container)).toHaveNoViolations();
  }, 30000);
});

describe('grid view on the desktop (F3-h S7)', () => {
  it('shows the F3-g tiles and opens the lines of a card', async () => {
    server.use(
      http.get(`${API}/auth/session`, () =>
        signedInSession({ ...NO_PREFS, collection_view: 'grid' }),
      ),
    );
    await renderApp({ path: '/collection', width: 1280 });
    await userEvent.click(await screen.findByRole('button', { name: /Ayla/ }, LONG));
    expect(
      await screen.findByRole('dialog', { name: "Copias de Ayla, Fury's Champion" }),
    ).toBeVisible();
  }, 20000);
});
