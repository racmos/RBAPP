import { act, fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';
import { API, signedInSession } from '@/test/msw/handlers';
import { productListMeta, productSummaries, unlistedSummary } from '@/test/fixtures/products';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';
import { expectCollapsible } from '@/test/sidePanel';

const LONG = { timeout: 10000 };
const DESKTOP = 1280;
const WIDE = 1700;

type Sent = { method: string; path: string; body: Record<string, unknown> | null };

function signedIn() {
  server.use(http.get(`${API}/auth/session`, () => signedInSession()));
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

/** The catalog with the unlisted product as well. */
function withUnlisted() {
  const items = [...productSummaries, unlistedSummary];
  server.use(
    http.get(`${API}/products`, () =>
      HttpResponse.json({
        success: true,
        data: { items },
        meta: { ...productListMeta, total: items.length },
      }),
    ),
  );
}

const catalogTable = () => screen.findByRole('table', { name: 'Productos de Cardmarket' }, LONG);
const mineTable = () => screen.findByRole('table', { name: 'Tus productos' }, LONG);
const rail = () => screen.getByRole('complementary', { name: 'Filtros' });
const header = (name: string) => screen.getByRole('columnheader', { name });

afterEach(() => {
  vi.restoreAllMocks();
  server.events.removeAllListeners();
});

describe('ProductsDesktop rail at 1280 px (F14-f S1)', () => {
  it('keeps the tabs above the content and writes every rail filter to the URL', async () => {
    signedIn();
    const { where } = await renderApp({ path: '/products?tab=catalog', width: DESKTOP });
    await catalogTable();
    expect(screen.getByRole('tab', { name: 'Catálogo' })).toHaveAttribute('aria-selected', 'true');
    // the mobile chips and sort select are not there
    expect(screen.queryByRole('button', { name: 'Caja de sobres (1)' })).toBeNull();
    expect(screen.queryByRole('combobox', { name: 'Ordenar por' })).toBeNull();

    const box = within(rail()).getByRole('checkbox', { name: 'Caja de sobres (1)' });
    expect(box).not.toBeChecked();
    await userEvent.click(box);
    await waitFor(() => expect(where()).toBe('/products?tab=catalog&kind=box'), LONG);
    await waitFor(() =>
      expect(within(rail()).getByRole('checkbox', { name: 'Caja de sobres (1)' })).toBeChecked(),
    );

    await userEvent.selectOptions(within(rail()).getByRole('combobox', { name: 'Set' }), 'OGN');
    await waitFor(() => expect(where()).toBe('/products?tab=catalog&kind=box&set=OGN'), LONG);

    const mine = within(rail()).getByRole('switch', { name: 'Solo los míos' });
    expect(mine).toHaveAttribute('aria-checked', 'false');
    await userEvent.click(mine);
    await waitFor(
      () => expect(where()).toBe('/products?tab=catalog&kind=box&set=OGN&owned=owned'),
      LONG,
    );
    await waitFor(() =>
      expect(within(rail()).getByRole('switch', { name: 'Solo los míos' })).toHaveAttribute(
        'aria-checked',
        'true',
      ),
    );

    await userEvent.type(
      within(rail()).getByRole('searchbox', { name: 'Buscar productos' }),
      'box',
    );
    await waitFor(
      () => expect(where()).toBe('/products?tab=catalog&q=box&kind=box&set=OGN&owned=owned'),
      LONG,
    );

    await userEvent.click(within(rail()).getByRole('switch', { name: 'Solo los míos' }));
    await waitFor(() => expect(where()).toBe('/products?tab=catalog&q=box&kind=box&set=OGN'), LONG);
  }, 30000);

  it('keeps a filter change that the page has not rendered yet (L6)', async () => {
    signedIn();
    const { where } = await renderApp({ path: '/products?tab=catalog', width: DESKTOP });
    await catalogTable();
    const box = within(rail()).getByRole('checkbox', { name: 'Caja de sobres (1)' });
    const mine = within(rail()).getByRole('switch', { name: 'Solo los míos' });
    // the router applies a navigation in a transition: the second change comes before the render
    act(() => {
      fireEvent.click(box);
      fireEvent.click(mine);
    });
    await waitFor(() => expect(where()).toBe('/products?tab=catalog&kind=box&owned=owned'), LONG);
  }, 20000);

  it('"solo los míos" asks the API for the owned products only', async () => {
    signedIn();
    await renderApp({ path: '/products?tab=catalog&owned=owned', width: DESKTOP });
    const table = await catalogTable();
    await waitFor(
      () => expect(within(table).queryByRole('row', { name: /^Origins Booster Sobre/ })).toBeNull(),
      LONG,
    );
    expect(within(table).getByRole('row', { name: /Origins Booster Box/ })).toBeVisible();
    expect(within(table).getByRole('row', { name: /Riftbound Sleeves/ })).toBeVisible();
  }, 20000);
});

describe('ProductsDesktop catalog table at 1280 px (F14-f S2)', () => {
  it('shows image, name, kind, set, price, signed changes, owned and listed', async () => {
    signedIn();
    withUnlisted();
    await renderApp({ path: '/products?tab=catalog', width: DESKTOP });
    const table = await catalogTable();
    for (const name of [
      'Imagen',
      'Nombre',
      'Tipo',
      'Set',
      'Precio',
      '7 d',
      '30 d',
      'Tienes',
      'En Cardmarket',
    ]) {
      expect(within(table).getByRole('columnheader', { name })).toBeInTheDocument();
    }
    const box = within(table).getByRole('row', { name: /Origins Booster Box/ });
    expect(within(box).getByRole('link', { name: 'Origins Booster Box' })).toHaveAttribute(
      'href',
      '/riftbound/app/products/501',
    );
    expect(within(box).getByText('Caja de sobres')).toBeVisible();
    expect(within(box).getByText('OGN')).toBeVisible();
    expect(within(box).getByText('99,50 €')).toBeVisible();
    expect(within(box).getByText('+2,5 %')).toBeVisible();
    expect(within(box).getByText('-4,1 %')).toBeVisible();
    expect(within(box).getByText('×2')).toBeVisible();
    expect(within(box).queryByText('Ya no aparece')).toBeNull();

    const booster = within(table).getByRole('row', { name: /^Origins Booster Sobre/ });
    expect(within(booster).getByText('-1,2 %')).toBeVisible();
    expect(within(booster).getAllByText('—').length).toBeGreaterThanOrEqual(2); // 30 d, owned

    const sleeves = within(table).getByRole('row', { name: /Riftbound Sleeves/ });
    expect(within(sleeves).getByText('Sin precio')).toBeVisible();
    expect(sleeves.querySelector('[data-slot="product-placeholder"]')).toBeInTheDocument();
    expect(within(sleeves).getByText('×1')).toBeVisible();

    const promo = within(table).getByRole('row', { name: /Origins Promo Pack/ });
    expect(within(promo).getByText('Ya no aparece')).toBeVisible();
    expect(within(promo).getByText('+6,3 %')).toBeVisible();
  }, 20000);

  it('sorts from the headers (aria-sort) and changes the page size', async () => {
    signedIn();
    const { where } = await renderApp({ path: '/products?tab=catalog', width: DESKTOP });
    await catalogTable();
    expect(header('Nombre')).toHaveAttribute('aria-sort', 'ascending');
    expect(header('Precio')).toHaveAttribute('aria-sort', 'none');

    await userEvent.click(within(header('Precio')).getByRole('button'));
    await waitFor(() => expect(where()).toBe('/products?tab=catalog&sort=price&dir=desc'), LONG);
    await waitFor(() => expect(header('Precio')).toHaveAttribute('aria-sort', 'descending'));
    expect(header('Nombre')).toHaveAttribute('aria-sort', 'none');
    await userEvent.click(within(header('Precio')).getByRole('button'));
    await waitFor(() => expect(where()).toBe('/products?tab=catalog&sort=price'), LONG);
    await waitFor(() => expect(header('Precio')).toHaveAttribute('aria-sort', 'ascending'));

    await userEvent.click(within(header('7 d')).getByRole('button'));
    await waitFor(
      () => expect(where()).toBe('/products?tab=catalog&sort=change_7d&dir=desc'),
      LONG,
    );
    await userEvent.click(within(header('30 d')).getByRole('button'));
    await waitFor(
      () => expect(where()).toBe('/products?tab=catalog&sort=change_30d&dir=desc'),
      LONG,
    );
    await userEvent.click(within(header('Nombre')).getByRole('button'));
    await waitFor(() => expect(where()).toBe('/products?tab=catalog'), LONG);

    const size = screen.getByRole('combobox', { name: 'Por página' });
    expect(
      within(size)
        .getAllByRole('option')
        .map((option) => option.textContent),
    ).toEqual(['48', '96']);
    await userEvent.selectOptions(size, '96');
    await waitFor(() => expect(where()).toBe('/products?tab=catalog&per_page=96'), LONG);
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Por página' }), '48');
    await waitFor(() => expect(where()).toBe('/products?tab=catalog'), LONG);
  }, 30000);

  it('a row click opens the product page below 1600 px', async () => {
    signedIn();
    const { where } = await renderApp({ path: '/products?tab=catalog', width: DESKTOP });
    const table = await catalogTable();
    const booster = within(table).getByRole('row', { name: /^Origins Booster Sobre/ });
    await userEvent.click(within(booster).getByRole('cell', { name: 'Sobre' }));
    await waitFor(() => expect(where()).toBe('/products/503'), LONG);
  }, 20000);

  it('filters that match nothing offer to clear them, "solo los míos" included', async () => {
    signedIn();
    server.use(
      http.get(`${API}/products`, () =>
        HttpResponse.json({
          success: true,
          data: { items: [] },
          meta: { ...productListMeta, total: 0, pages: 0 },
        }),
      ),
    );
    const { where } = await renderApp({
      path: '/products?tab=catalog&q=zzz&kind=box&owned=owned',
      width: DESKTOP,
    });
    expect(
      await screen.findByText('Ningún producto coincide con los filtros.', {}, LONG),
    ).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: 'Limpiar filtros' }));
    await waitFor(() => expect(where()).toBe('/products?tab=catalog'), LONG);
  }, 20000);

  it('is axe clean', async () => {
    signedIn();
    withUnlisted();
    const { container } = await renderApp({ path: '/products?tab=catalog', width: DESKTOP });
    await catalogTable();
    expect(await axe(container)).toHaveNoViolations();
  }, 30000);
});

describe('ProductsDesktop mine table at 1280 px (F14-f S3)', () => {
  it('shows the total band and one row per line with every column', async () => {
    signedIn();
    await renderApp({ path: '/products?tab=mine', width: DESKTOP });
    const table = await mineTable();
    const band = screen.getByText('Valor de tus productos').closest('dl')!;
    expect(within(band).getByText('199,00 €')).toBeVisible();
    expect(within(band).getByText('2')).toBeVisible();
    expect(screen.getByText('1 sin precio')).toBeVisible();
    expect(
      screen.getByText('Este total no se suma al valor de tu colección de cartas.'),
    ).toBeVisible();
    for (const name of [
      'Imagen',
      'Nombre',
      'Tipo',
      'Cantidad',
      'Compra',
      'Precio',
      'Valor',
      'Ganancia €',
      'Ganancia %',
      'Nota',
    ]) {
      expect(within(table).getByRole('columnheader', { name })).toBeInTheDocument();
    }
    const box = within(table).getByRole('row', { name: /Origins Booster Box/ });
    expect(
      within(box).getByRole('spinbutton', { name: 'Cantidad: Origins Booster Box' }),
    ).toHaveValue(2);
    expect(
      within(box).getByRole('spinbutton', { name: 'Compra: Origins Booster Box' }),
    ).toHaveValue(90);
    expect(within(box).getByRole('textbox', { name: 'Nota: Origins Booster Box' })).toHaveValue(
      'Sealed',
    );
    expect(within(box).getByText('Caja de sobres')).toBeVisible();
    expect(within(box).getByText('99,50 €')).toBeVisible();
    expect(within(box).getByText('199,00 €')).toBeVisible();
    expect(within(box).getByText('+19,00 €')).toBeVisible();
    expect(within(box).getByText('+10,6 %')).toBeVisible();
    const sleeves = within(table).getByRole('row', { name: /Riftbound Sleeves/ });
    expect(within(sleeves).getAllByText('Sin precio').length).toBeGreaterThan(0);
    expect(
      within(sleeves).getByRole('spinbutton', { name: 'Compra: Riftbound Sleeves' }),
    ).toHaveValue(null);
  }, 20000);

  it('saves the inline edits with the right PATCH bodies', async () => {
    signedIn();
    const sent = record();
    await renderApp({ path: '/products?tab=mine', width: DESKTOP });
    const table = await mineTable();
    const box = within(table).getByRole('row', { name: /Origins Booster Box/ });
    await userEvent.click(
      within(box).getByRole('button', { name: 'Más copias: Cantidad: Origins Booster Box' }),
    );
    await waitFor(() => expect(sent).toHaveLength(1), LONG);
    expect(sent[0]).toEqual({ method: 'PATCH', path: '/me/products/801', body: { quantity: 3 } });

    const price = within(box).getByRole('spinbutton', { name: 'Compra: Origins Booster Box' });
    await userEvent.clear(price);
    await userEvent.type(price, '80');
    await waitFor(() => expect(sent.some((r) => r.body?.purchase_price === 80)).toBe(true), LONG);

    const note = within(box).getByRole('textbox', { name: 'Nota: Origins Booster Box' });
    await userEvent.clear(note);
    await userEvent.type(note, ' Gift ');
    await waitFor(() => expect(sent.some((r) => r.body?.note === 'Gift')).toBe(true), LONG);

    const sleeves = within(table).getByRole('row', { name: /Riftbound Sleeves/ });
    await userEvent.type(
      within(sleeves).getByRole('textbox', { name: 'Nota: Riftbound Sleeves' }),
      'x',
    );
    await waitFor(
      () =>
        expect(sent).toContainEqual({
          method: 'PATCH',
          path: '/me/products/802',
          body: { note: 'x' },
        }),
      LONG,
    );
    expect(sent.every((r) => r.method === 'PATCH')).toBe(true);
    expect(sent.filter((r) => r.path === '/me/products/801').map((r) => r.body)).toEqual(
      expect.arrayContaining([{ quantity: 3 }, { purchase_price: 80 }, { note: 'Gift' }]),
    );
  }, 30000);

  it('the name opens the line sheet (delete stays reachable)', async () => {
    signedIn();
    const { where } = await renderApp({ path: '/products?tab=mine', width: DESKTOP });
    const table = await mineTable();
    const box = within(table).getByRole('row', { name: /Origins Booster Box/ });
    await userEvent.click(within(box).getByRole('button', { name: 'Origins Booster Box' }));
    const sheet = await screen.findByRole('dialog', { name: 'Origins Booster Box' }, LONG);
    expect(within(sheet).getByRole('button', { name: 'Eliminar' })).toBeVisible();
    expect(where()).toBe('/products?tab=mine');
  }, 20000);

  it('a row click opens the product page below 1600 px; an inline edit does not', async () => {
    signedIn();
    const { where } = await renderApp({ path: '/products?tab=mine', width: DESKTOP });
    const table = await mineTable();
    const box = within(table).getByRole('row', { name: /Origins Booster Box/ });
    await userEvent.click(within(box).getByRole('textbox', { name: 'Nota: Origins Booster Box' }));
    expect(where()).toBe('/products?tab=mine');
    await userEvent.click(within(box).getByText('Caja de sobres'));
    await waitFor(() => expect(where()).toBe('/products/501'), LONG);
  }, 20000);

  it('offline: the inline edits are disabled', async () => {
    signedIn();
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    await renderApp({ path: '/products?tab=mine', width: DESKTOP });
    const table = await mineTable();
    expect(screen.getByText('Necesitas conexión para hacer cambios.')).toBeVisible();
    const box = within(table).getByRole('row', { name: /Origins Booster Box/ });
    expect(
      within(box).getByRole('spinbutton', { name: 'Cantidad: Origins Booster Box' }),
    ).toBeDisabled();
    expect(
      within(box).getByRole('spinbutton', { name: 'Compra: Origins Booster Box' }),
    ).toBeDisabled();
    expect(within(box).getByRole('textbox', { name: 'Nota: Origins Booster Box' })).toBeDisabled();
  }, 20000);

  it('is axe clean', async () => {
    signedIn();
    const { container } = await renderApp({ path: '/products?tab=mine', width: DESKTOP });
    await mineTable();
    expect(await axe(container)).toHaveNoViolations();
  }, 30000);
});

describe('ProductsDesktop wide panel at 1700 px (F14-f S4)', () => {
  const panel = () => screen.findByRole('complementary', { name: 'Detalle del producto' }, LONG);

  it('says what to do until a row is picked, then shows the product', async () => {
    signedIn();
    const sent = record();
    const { where } = await renderApp({ path: '/products?tab=catalog', width: WIDE });
    const table = await catalogTable();
    const aside = await panel();
    expect(within(aside).getByText('Elige un producto para ver su detalle.')).toBeVisible();

    await userEvent.click(
      within(within(table).getByRole('row', { name: /Origins Booster Box/ })).getByText('OGN'),
    );
    expect(where()).toBe('/products?tab=catalog');
    expect(
      await within(aside).findByRole('heading', { name: 'Origins Booster Box' }, LONG),
    ).toBeVisible();
    expect(within(aside).getByRole('img', { name: 'Origins Booster Box' })).toBeVisible();
    // the price facts (the chart's axis can show the same amounts)
    const facts = within(aside).getByText('Precio', { selector: 'dt' }).closest('dl')!;
    expect(within(facts).getByText('99,50 €')).toBeVisible();
    expect(within(facts).getByText('+2,5 %')).toBeVisible();
    expect(within(facts).getByText('-4,1 %')).toBeVisible();
    const history = within(aside).getByRole('region', { name: 'Evolución del precio' });
    expect(
      await within(history).findByRole('button', { name: 'Ver como tabla' }, LONG),
    ).toBeVisible();
    expect(within(history).getByRole('radio', { name: '90 d' })).toBeChecked();
    const lines = await within(aside).findByRole('region', { name: 'Tus unidades' }, LONG);
    expect(within(lines).getAllByRole('listitem')).toHaveLength(1);
    expect(within(lines).getByRole('listitem')).toHaveTextContent('Sealed');

    const form = within(aside).getByRole('form', { name: 'Añadir a mis productos' });
    await userEvent.click(within(form).getByRole('button', { name: 'Añadir' }));
    await waitFor(() => expect(sent.some((r) => r.method === 'POST')).toBe(true), LONG);
    expect(sent.find((r) => r.method === 'POST')!.body).toEqual({
      product_id: 501,
      quantity: 1,
      purchase_price: null,
      note: null,
    });
  }, 30000);

  it('the name button selects the product too; the mine table rows select as well', async () => {
    signedIn();
    const { where } = await renderApp({ path: '/products?tab=catalog', width: WIDE });
    const table = await catalogTable();
    const booster = within(table).getByRole('row', { name: /^Origins Booster Sobre/ });
    const name = within(booster).getByRole('button', { name: 'Origins Booster' });
    expect(name).toHaveAttribute('aria-pressed', 'false');
    await userEvent.click(name);
    const aside = await panel();
    expect(
      await within(aside).findByRole('heading', { name: 'Origins Booster' }, LONG),
    ).toBeVisible();
    expect(within(booster).getByRole('button', { name: 'Origins Booster' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );

    await userEvent.click(screen.getByRole('tab', { name: 'Mis productos' }));
    const mine = await mineTable();
    await userEvent.click(
      within(within(mine).getByRole('row', { name: /Riftbound Sleeves/ })).getByRole('cell', {
        name: 'Fundas',
      }),
    );
    expect(
      await within(aside).findByRole('heading', { name: 'Riftbound Sleeves' }, LONG),
    ).toBeVisible();
    expect(where()).toBe('/products?tab=mine');
  }, 30000);

  it('is not there below 1600 px', async () => {
    signedIn();
    await renderApp({ path: '/products?tab=catalog', width: DESKTOP });
    await catalogTable();
    expect(screen.queryByRole('complementary', { name: 'Detalle del producto' })).toBeNull();
  }, 20000);

  it('is axe clean with a product open', async () => {
    signedIn();
    const { container } = await renderApp({ path: '/products?tab=catalog', width: WIDE });
    const table = await catalogTable();
    await userEvent.click(
      within(within(table).getByRole('row', { name: /Origins Booster Box/ })).getByText('OGN'),
    );
    const aside = await panel();
    await within(aside).findByRole('region', { name: 'Tus unidades' }, LONG);
    await within(aside).findByRole('button', { name: 'Ver como tabla' }, LONG);
    expect(await axe(container)).toHaveNoViolations();
  }, 30000);
});

describe('ProductsDesktop side panels (owner feedback S23)', () => {
  it('folds the filter rail and the detail panel away', async () => {
    signedIn();
    await renderApp({ path: '/products?tab=catalog', width: WIDE });
    await catalogTable();
    await expectCollapsible(
      rail(),
      { hide: 'Ocultar filtros', show: 'Mostrar filtros' },
      'rb_panel_products-filters_v1',
    );
    await expectCollapsible(
      await screen.findByRole('complementary', { name: 'Detalle del producto' }, LONG),
      { hide: 'Ocultar detalle', show: 'Mostrar detalle' },
      'rb_panel_products-detail_v1',
    );
  }, 30000);
});
