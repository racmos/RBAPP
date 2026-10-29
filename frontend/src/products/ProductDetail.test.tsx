import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';
import { API, ok, signedInSession } from '@/test/msw/handlers';
import { boxLine } from '@/test/fixtures/products';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';

const LONG = { timeout: 10000 };
const WIDTH = 390;

function signedIn() {
  server.use(http.get(`${API}/auth/session`, () => signedInSession()));
}

/** Every request whose path contains `part`: method, path + search, JSON body. */
function record(part: string) {
  const sent: { method: string; url: string; body: Record<string, unknown> | null }[] = [];
  server.events.on('request:start', async ({ request }) => {
    if (!request.url.includes(part)) return;
    let body: Record<string, unknown> | null = null;
    try {
      body = (await request.clone().json()) as Record<string, unknown>;
    } catch {
      body = null;
    }
    const url = new URL(request.url);
    sent.push({ method: request.method, url: url.pathname.replace(API, '') + url.search, body });
  });
  return sent;
}

afterEach(() => {
  vi.restoreAllMocks();
  server.events.removeAllListeners();
});

describe('ProductDetail at 390 px (F14-e S3-S5)', () => {
  it('shows the image, name, kind, set, price and changes', async () => {
    signedIn();
    await renderApp({ path: '/products/501', width: WIDTH });
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Origins Booster Box' }, LONG),
    ).toBeVisible();
    expect(screen.getByRole('img', { name: 'Origins Booster Box' })).toHaveAttribute(
      'src',
      '/riftbound/media/products/501.png',
    );
    const facts = screen.getByText('Tipo', { selector: 'dt' }).closest('dl')!;
    expect(within(facts).getByText('Caja de sobres')).toBeVisible();
    expect(within(facts).getByText('OGN')).toBeVisible();
    expect(within(facts).getByText('99,50 €')).toBeVisible();
    expect(within(facts).getByText('7 días')).toBeVisible();
    expect(within(facts).getByText('+2,5 %')).toBeVisible();
    expect(within(facts).getByText('30 días')).toBeVisible();
    expect(within(facts).getByText('-4,1 %')).toBeVisible();
    expect(screen.getByRole('link', { name: 'Volver' })).toHaveAttribute(
      'href',
      '/riftbound/app/products',
    );
    expect(document.title).toBe('Origins Booster Box · Rift Manager');
  }, 20000);

  it('the kind placeholder replaces a missing image; no price shows the unpriced text', async () => {
    signedIn();
    const { container } = await renderApp({ path: '/products/502', width: WIDTH });
    await screen.findByRole('heading', { level: 1, name: 'Riftbound Sleeves' }, LONG);
    expect(container.querySelector('[data-slot="product-placeholder"]')).toHaveTextContent(
      'Fundas',
    );
    expect(screen.queryByRole('img', { name: 'Riftbound Sleeves' })).toBeNull();
    expect(screen.getByText('Sin precio')).toBeVisible();
  }, 20000);

  it('the chart ranges request the right range', async () => {
    signedIn();
    const sent = record('/prices');
    await renderApp({ path: '/products/501', width: WIDTH });
    const history = await screen.findByRole('region', { name: 'Evolución del precio' }, LONG);
    await waitFor(() => expect(sent.map((r) => r.url)).toContain('/products/501/prices?range=90d'));
    expect(await within(history).findByRole('button', { name: 'Ver como tabla' })).toBeVisible();
    for (const [label, range] of [
      ['30 d', '30d'],
      ['1 año', '1y'],
      ['Todo', 'all'],
    ] as const) {
      await userEvent.click(within(history).getByRole('radio', { name: label }));
      await waitFor(() =>
        expect(sent.map((r) => r.url)).toContain(`/products/501/prices?range=${range}`),
      );
    }
  }, 20000);

  it('lists the owned lines', async () => {
    signedIn();
    await renderApp({ path: '/products/501', width: WIDTH });
    const lines = await screen.findByRole('region', { name: 'Tus unidades' }, LONG);
    const items = within(lines).getAllByRole('listitem');
    expect(items).toHaveLength(1);
    expect(items[0]).toHaveTextContent('2');
    expect(items[0]).toHaveTextContent('90,00 €');
    expect(items[0]).toHaveTextContent('199,00 €');
    expect(items[0]).toHaveTextContent('Sealed');
  }, 20000);

  it('adds a line and says whether it was merged', async () => {
    signedIn();
    const sent = record('/me/products');
    await renderApp({ path: '/products/501', width: WIDTH });
    const form = await screen.findByRole('form', { name: 'Añadir a mis productos' }, LONG);
    const qty = within(form).getByRole('spinbutton', { name: 'Cantidad' });
    expect(qty).toHaveValue(1);
    await userEvent.clear(qty);
    await userEvent.type(qty, '2');
    await userEvent.type(
      within(form).getByRole('spinbutton', { name: 'Precio de compra (unidad)' }),
      '95.5',
    );
    await userEvent.type(within(form).getByRole('textbox', { name: 'Nota' }), ' Gift ');
    await userEvent.click(within(form).getByRole('button', { name: 'Añadir' }));
    await waitFor(() => expect(sent.some((r) => r.method === 'POST')).toBe(true), LONG);
    expect(sent.find((r) => r.method === 'POST')!.body).toEqual({
      product_id: 501,
      quantity: 2,
      purchase_price: 95.5,
      note: 'Gift',
    });
    expect(
      (await screen.findAllByText('Añadido a tus productos.', {}, LONG)).length,
    ).toBeGreaterThan(0);

    server.use(http.post(`${API}/me/products`, () => ok({ line: boxLine, merged: true }, 201)));
    await userEvent.click(within(form).getByRole('button', { name: 'Añadir' }));
    expect(
      (await screen.findAllByText('Sumado a una línea que ya tenías.', {}, LONG)).length,
    ).toBeGreaterThan(0);
    expect(sent.filter((r) => r.method === 'POST')[1].body).toEqual({
      product_id: 501,
      quantity: 1,
      purchase_price: null,
      note: null,
    });
  }, 30000);

  it('an unknown product is a not found page', async () => {
    signedIn();
    await renderApp({ path: '/products/999', width: WIDTH });
    expect(await screen.findByText('Página no encontrada', {}, LONG)).toBeVisible();
  }, 20000);

  it('offline: the add form is disabled', async () => {
    signedIn();
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    await renderApp({ path: '/products/501', width: WIDTH });
    const form = await screen.findByRole('form', { name: 'Añadir a mis productos' }, LONG);
    expect(within(form).getByText('Necesitas conexión para hacer cambios.')).toBeVisible();
    expect(within(form).getByRole('button', { name: 'Añadir' })).toBeDisabled();
  }, 20000);

  it('is axe clean', async () => {
    signedIn();
    const { container } = await renderApp({ path: '/products/501', width: WIDTH });
    await screen.findByRole('region', { name: 'Tus unidades' }, LONG);
    await screen.findByRole('button', { name: 'Ver como tabla' }, LONG);
    expect(await axe(container)).toHaveNoViolations();
  }, 30000);
});
