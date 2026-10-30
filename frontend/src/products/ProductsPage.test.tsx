import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';
import { getToasts } from '@/components/ui/toastStore';
import { API, failure, ok, signedInSession } from '@/test/msw/handlers';
import { noProducts, productListMeta, productSummaries } from '@/test/fixtures/products';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';

const LONG = { timeout: 10000 };
const WIDTH = 390;

type Sent = { method: string; path: string; body: Record<string, unknown> | null };

function signedIn() {
  server.use(http.get(`${API}/auth/session`, () => signedInSession()));
}

function ownsNothing() {
  server.use(http.get(`${API}/me/products`, () => ok(noProducts)));
}

/** The writes to `/me/products` (method, path without the API prefix, JSON body). */
function record() {
  const sent: Sent[] = [];
  server.events.on('request:start', async ({ request }) => {
    if (!request.url.includes('/me/products') || request.method === 'GET') return;
    let body: Record<string, unknown> | null = null;
    try {
      body = (await request.clone().json()) as Record<string, unknown>;
    } catch {
      body = null;
    }
    sent.push({
      method: request.method,
      path: new URL(request.url).pathname.replace(API, ''),
      body,
    });
  });
  return sent;
}

function catalog(meta: Record<string, unknown> = {}, items = productSummaries) {
  server.use(
    http.get(`${API}/products`, () =>
      HttpResponse.json({
        success: true,
        data: { items },
        meta: { ...productListMeta, total: items.length, ...meta },
      }),
    ),
  );
}

const tab = (name: string) => screen.getByRole('tab', { name });

afterEach(() => {
  vi.restoreAllMocks();
  server.events.removeAllListeners();
});

describe('ProductsPage tabs (F14-e S2)', () => {
  it('opens on "Mis productos" when the user owns products', async () => {
    signedIn();
    await renderApp({ path: '/products', width: WIDTH });
    expect(await screen.findByRole('heading', { name: 'Productos' }, LONG)).toBeVisible();
    expect(await screen.findByRole('tablist', { name: 'Productos' }, LONG)).toBeVisible();
    await waitFor(
      () => expect(tab('Mis productos')).toHaveAttribute('aria-selected', 'true'),
      LONG,
    );
    expect(tab('Catálogo')).toHaveAttribute('aria-selected', 'false');
    expect(screen.getByRole('tabpanel', { name: 'Mis productos' })).toBeVisible();
    expect(document.title).toBe('Productos · Rift Manager');
  }, 20000);

  it('opens on "Catálogo" when the user owns nothing', async () => {
    signedIn();
    ownsNothing();
    await renderApp({ path: '/products', width: WIDTH });
    await waitFor(() => expect(tab('Catálogo')).toHaveAttribute('aria-selected', 'true'), LONG);
    expect(await screen.findByRole('link', { name: /Origins Booster Box/ }, LONG)).toBeVisible();
  }, 20000);

  it('follows ?tab= and writes the chosen tab to the URL', async () => {
    signedIn();
    const { where } = await renderApp({ path: '/products?tab=catalog', width: WIDTH });
    await waitFor(() => expect(tab('Catálogo')).toHaveAttribute('aria-selected', 'true'), LONG);
    await userEvent.click(tab('Mis productos'));
    await waitFor(() => expect(where()).toBe('/products?tab=mine'), LONG);
    await waitFor(() => expect(tab('Mis productos')).toHaveAttribute('aria-selected', 'true'));
    // arrow keys move between the tabs
    tab('Mis productos').focus();
    await userEvent.keyboard('{ArrowRight}');
    await waitFor(() => expect(where()).toBe('/products?tab=catalog'), LONG);
    expect(tab('Catálogo')).toHaveFocus();
  }, 20000);

  it('the nav entry opens this screen in the app', async () => {
    signedIn();
    await renderApp({ path: '/', width: 1280 });
    const links = await screen.findAllByRole('link', { name: /Productos/ }, LONG);
    expect(links.length).toBeGreaterThan(0);
    for (const link of links) expect(link).toHaveAttribute('href', '/riftbound/app/products');
  }, 15000);
});

describe('ProductsPage "Mis productos" at 390 px (F14-e S2)', () => {
  it('shows the total band, the separation hint and the lines', async () => {
    signedIn();
    await renderApp({ path: '/products?tab=mine', width: WIDTH });
    const band = (await screen.findByText('Valor de tus productos', {}, LONG)).closest('dl')!;
    expect(within(band).getByText('199,00 €')).toBeVisible();
    expect(within(band).getByText('Líneas')).toBeVisible();
    expect(within(band).getByText('2')).toBeVisible();
    expect(screen.getByText('1 sin precio')).toBeVisible();
    expect(
      screen.getByText('Este total no se suma al valor de tu colección de cartas.'),
    ).toBeVisible();
    const box = screen.getByRole('article', { name: 'Origins Booster Box' });
    expect(within(box).getByText('Caja de sobres')).toBeVisible();
    expect(within(box).getByRole('spinbutton', { name: 'Cantidad' })).toHaveValue(2);
    expect(within(box).getByText('99,50 €')).toBeVisible();
    expect(within(box).getByText('199,00 €')).toBeVisible();
    const sleeves = screen.getByRole('article', { name: 'Riftbound Sleeves' });
    // no image: the kind placeholder (S4); no price: the unpriced text (S5)
    expect(sleeves.querySelector('[data-slot="product-placeholder"]')).toHaveTextContent('Fundas');
    expect(within(sleeves).getAllByText('Sin precio').length).toBeGreaterThan(0);
  }, 20000);

  it('the stepper saves the quantity with a PATCH', async () => {
    signedIn();
    const sent = record();
    await renderApp({ path: '/products?tab=mine', width: WIDTH });
    const box = await screen.findByRole('article', { name: 'Origins Booster Box' }, LONG);
    await userEvent.click(within(box).getByRole('button', { name: 'Más copias: Cantidad' }));
    await waitFor(() => expect(sent).toHaveLength(1), LONG);
    expect(sent[0]).toEqual({ method: 'PATCH', path: '/me/products/801', body: { quantity: 3 } });
  }, 20000);

  it('the line sheet edits the note and the price, and deletes with undo', async () => {
    signedIn();
    const sent = record();
    await renderApp({ path: '/products?tab=mine', width: WIDTH });
    const box = await screen.findByRole('article', { name: 'Origins Booster Box' }, LONG);
    await userEvent.click(within(box).getByRole('button', { name: /Origins Booster Box/ }));
    const sheet = await screen.findByRole('dialog', { name: 'Origins Booster Box' }, LONG);
    expect(within(sheet).getByRole('spinbutton', { name: 'Cantidad' })).toHaveValue(2);
    const note = within(sheet).getByRole('textbox', { name: 'Nota' });
    expect(note).toHaveValue('Sealed');
    await userEvent.clear(note);
    await userEvent.type(note, 'Gift');
    await waitFor(() => expect(sent.some((r) => r.body?.note === 'Gift')).toBe(true), LONG);
    const price = within(sheet).getByRole('spinbutton', { name: 'Precio de compra (unidad)' });
    await userEvent.clear(price);
    await waitFor(
      () => expect(sent.some((r) => r.body && r.body.purchase_price === null)).toBe(true),
      LONG,
    );
    expect(sent.every((r) => r.method === 'PATCH' && r.path === '/me/products/801')).toBe(true);

    await userEvent.click(within(sheet).getByRole('button', { name: 'Eliminar' }));
    const confirm = await screen.findByRole('dialog', { name: '¿Eliminar esta línea?' });
    await userEvent.click(within(confirm).getByRole('button', { name: 'Eliminar' }));
    await waitFor(() => expect(sent.some((r) => r.method === 'DELETE')).toBe(true), LONG);
    expect(sent.find((r) => r.method === 'DELETE')!.path).toBe('/me/products/801');
    // the toast and the live region both say it
    expect((await screen.findAllByText('Línea eliminada.', {}, LONG)).length).toBeGreaterThan(0);
    expect(getToasts().find((toast) => toast.message === 'Línea eliminada.')?.duration).toBe(8000);
    await userEvent.click(screen.getByRole('button', { name: 'Deshacer' }));
    await waitFor(() => expect(sent.some((r) => r.method === 'POST')).toBe(true), LONG);
    expect(sent.find((r) => r.method === 'POST')).toEqual({
      method: 'POST',
      path: '/me/products',
      body: { product_id: 501, quantity: 2, purchase_price: 90, note: 'Sealed' },
    });
  }, 30000);

  it('empty: invites to browse the catalog', async () => {
    signedIn();
    ownsNothing();
    const { where } = await renderApp({ path: '/products?tab=mine', width: WIDTH });
    expect(await screen.findByText('Todavía no has añadido productos.', {}, LONG)).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: 'Ver el catálogo' }));
    await waitFor(() => expect(where()).toBe('/products?tab=catalog'), LONG);
  }, 20000);

  it('offline: the cached lines stay, the edits are disabled', async () => {
    signedIn();
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    await renderApp({ path: '/products?tab=mine', width: WIDTH });
    const box = await screen.findByRole('article', { name: 'Origins Booster Box' }, LONG);
    expect(screen.getByText('Necesitas conexión para hacer cambios.')).toBeVisible();
    expect(within(box).getByRole('button', { name: 'Más copias: Cantidad' })).toBeDisabled();
    expect(within(box).getByRole('spinbutton', { name: 'Cantidad' })).toBeDisabled();
  }, 20000);

  it('an error can be retried', async () => {
    signedIn();
    server.use(
      http.get(`${API}/me/products`, () => failure(500, { error: 'Internal Server Error' })),
    );
    await renderApp({ path: '/products?tab=mine', width: WIDTH });
    expect(await screen.findByText('No se pudieron cargar los productos.', {}, LONG)).toBeVisible();
    expect(screen.getByRole('button', { name: 'Reintentar' })).toBeVisible();
  }, 20000);

  it('is axe clean', async () => {
    signedIn();
    const { container } = await renderApp({ path: '/products?tab=mine', width: WIDTH });
    await screen.findByRole('article', { name: 'Origins Booster Box' }, LONG);
    expect(await axe(container)).toHaveNoViolations();
  }, 30000);
});

describe('ProductsPage "Catálogo" at 390 px (F14-e S2)', () => {
  it('shows tiles with price, 7-day change, owned badge and unpriced text', async () => {
    signedIn();
    await renderApp({ path: '/products?tab=catalog', width: WIDTH });
    const box = await screen.findByRole('link', { name: /Origins Booster Box/ }, LONG);
    expect(box).toHaveAttribute('href', '/riftbound/app/products/501');
    expect(within(box).getByText('99,50 €')).toBeVisible();
    expect(within(box).getByText('+2,5 %')).toBeInTheDocument();
    expect(within(box).getByText('×2')).toBeVisible();
    expect(within(box).getByText('Tienes 2')).toBeInTheDocument();
    expect(within(box).getByText('Caja de sobres')).toBeVisible();
    const sleeves = screen.getByRole('link', { name: /Riftbound Sleeves/ });
    expect(within(sleeves).getByText('Sin precio')).toBeVisible();
    expect(sleeves.querySelector('[data-slot="product-placeholder"]')).toHaveTextContent('Fundas');
    const booster = screen.getByRole('link', { name: /^Origins Booster Sobre/ });
    expect(within(booster).queryByText(/×/)).toBeNull();
  }, 20000);

  it('writes the search to the URL', async () => {
    signedIn();
    const { where } = await renderApp({ path: '/products?tab=catalog', width: WIDTH });
    await screen.findByRole('link', { name: /Origins Booster Box/ }, LONG);
    await userEvent.type(screen.getByRole('searchbox', { name: 'Buscar productos' }), 'sleeve');
    await waitFor(() => expect(where()).toBe('/products?tab=catalog&q=sleeve'), LONG);
    await waitFor(
      () => expect(screen.queryByRole('link', { name: /Origins Booster Box/ })).toBeNull(),
      LONG,
    );
    expect(screen.getByRole('link', { name: /Riftbound Sleeves/ })).toBeVisible();
  }, 20000);

  it('kind chips show the facet counts and toggle the kind', async () => {
    signedIn();
    const { where } = await renderApp({ path: '/products?tab=catalog', width: WIDTH });
    await screen.findByRole('link', { name: /Origins Booster Box/ }, LONG);
    const kinds = screen.getByRole('group', { name: 'Tipo' });
    const chip = within(kinds).getByRole('button', { name: 'Caja de sobres (1)' });
    expect(chip).toHaveAttribute('aria-pressed', 'false');
    await userEvent.click(chip);
    await waitFor(() => expect(where()).toBe('/products?tab=catalog&kind=box'), LONG);
    await waitFor(() =>
      expect(within(kinds).getByRole('button', { name: 'Caja de sobres (1)' })).toHaveAttribute(
        'aria-pressed',
        'true',
      ),
    );
    await userEvent.click(within(kinds).getByRole('button', { name: 'Caja de sobres (1)' }));
    await waitFor(() => expect(where()).toBe('/products?tab=catalog'), LONG);
  }, 20000);

  it('the set and the sort go to the URL', async () => {
    signedIn();
    const { where } = await renderApp({ path: '/products?tab=catalog', width: WIDTH });
    await screen.findByRole('link', { name: /Origins Booster Box/ }, LONG);
    const set = screen.getByRole('combobox', { name: 'Set' });
    expect(within(set).getByRole('option', { name: 'Todos los sets' })).toBeInTheDocument();
    await userEvent.selectOptions(set, 'OGN');
    await waitFor(() => expect(where()).toBe('/products?tab=catalog&set=OGN'), LONG);
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Ordenar por' }), 'Precio');
    await waitFor(() => expect(where()).toBe('/products?tab=catalog&set=OGN&sort=price'), LONG);
    await userEvent.click(screen.getByRole('button', { name: 'Cambiar sentido del orden' }));
    await waitFor(
      () => expect(where()).toBe('/products?tab=catalog&set=OGN&sort=price&dir=desc'),
      LONG,
    );
  }, 20000);

  it('pages through the URL', async () => {
    signedIn();
    catalog({ pages: 3, page: 1 });
    const { where } = await renderApp({ path: '/products?tab=catalog', width: WIDTH });
    await screen.findByRole('link', { name: /Origins Booster Box/ }, LONG);
    await userEvent.click(screen.getByRole('button', { name: 'Siguiente' }));
    await waitFor(() => expect(where()).toBe('/products?tab=catalog&page=2'), LONG);
  }, 20000);

  it('filters that match nothing offer to clear them', async () => {
    signedIn();
    catalog({ pages: 0 }, []);
    const { where } = await renderApp({
      path: '/products?tab=catalog&q=zzz&kind=box',
      width: WIDTH,
    });
    expect(
      await screen.findByText('Ningún producto coincide con los filtros.', {}, LONG),
    ).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: 'Limpiar filtros' }));
    await waitFor(() => expect(where()).toBe('/products?tab=catalog'), LONG);
  }, 20000);

  it('an error can be retried', async () => {
    signedIn();
    server.use(http.get(`${API}/products`, () => failure(500, { error: 'Internal Server Error' })));
    await renderApp({ path: '/products?tab=catalog', width: WIDTH });
    expect(await screen.findByText('No se pudieron cargar los productos.', {}, LONG)).toBeVisible();
    expect(screen.getByRole('button', { name: 'Reintentar' })).toBeVisible();
  }, 20000);

  it('is axe clean', async () => {
    signedIn();
    const { container } = await renderApp({ path: '/products?tab=catalog', width: WIDTH });
    await screen.findByRole('link', { name: /Origins Booster Box/ }, LONG);
    expect(await axe(container)).toHaveNoViolations();
  }, 30000);

  it('renders above the mobile widths too', async () => {
    signedIn();
    await renderApp({ path: '/products?tab=catalog', width: 1440 });
    expect(await screen.findByRole('link', { name: /Origins Booster Box/ }, LONG)).toBeVisible();
  }, 20000);
});

describe('ProductsPage set order (owner feedback S19)', () => {
  it('the set select lists the sets newest first and the undated or unknown ones last', async () => {
    signedIn();
    catalog({ facets: { kind: { box: 1 }, set: { OGN: 2, NOD: 1, VEN: 3 } } });
    server.use(
      http.get(`${API}/meta/game`, () =>
        ok({
          modes: ['1v1', '2v2'],
          domains: ['Fury'],
          types: ['Unit'],
          supertypes: ['Champion'],
          rarities: ['Common'],
          sets: [
            { id: 'OGN', name: 'Origen', released_on: '2024-01-15', card_count: 6 },
            { id: 'VEN', name: 'Vendetta', released_on: '2026-08-01', card_count: 166 },
          ],
          price: { provider: 'cardmarket', currency: 'EUR', updated_on: null },
          rules: {},
          conditions: ['NM'],
          languages: ['English'],
        }),
      ),
    );
    await renderApp({ path: '/products?tab=catalog', width: WIDTH });
    await screen.findByRole('link', { name: /Origins Booster Box/ }, LONG);
    const set = screen.getByRole('combobox', { name: 'Set' });
    await within(set).findByRole('option', { name: /Vendetta/ }, LONG);
    expect(
      within(set)
        .getAllByRole('option')
        .map((option) => option.getAttribute('value')),
    ).toEqual(['', 'VEN', 'OGN', 'NOD']);
  }, 20000);
});
