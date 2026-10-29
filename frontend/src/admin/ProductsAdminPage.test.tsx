import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { axe } from 'vitest-axe';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { adminProductList, sleeves } from '@/test/fixtures/products';
import { API, adminSession, failure, ok } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';

const TABLE = 'Productos del catálogo';

/** Admin session; records every PATCH body and the query string of every list request. */
function productsApi(list = adminProductList) {
  const patches: unknown[] = [];
  const queries: string[] = [];
  server.use(
    http.get(`${API}/auth/session`, () => adminSession()),
    http.get(`${API}/admin/products`, ({ request }) => {
      queries.push(new URL(request.url).search);
      return ok(list);
    }),
    http.patch(`${API}/admin/products/:id`, async ({ params, request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      patches.push(body);
      const product = list.items.find((item) => String(item.id) === params.id);
      return ok({ ...product, ...body });
    }),
  );
  return { patches, queries };
}

async function openEditor(name: string) {
  await userEvent.click(await screen.findByRole('button', { name }, { timeout: 10000 }));
  return screen.findByRole('dialog', { name });
}

describe('ProductsAdminPage (F14-d S5)', () => {
  afterEach(() => vi.restoreAllMocks());

  it('table at 1280 px: image or placeholder, kind, set, price, listed, hidden, updated', async () => {
    productsApi();
    const { container } = await renderApp({ path: '/admin/products', width: 1280 });
    const table = await screen.findByRole('table', { name: TABLE }, { timeout: 10000 });
    expect(screen.getByRole('heading', { name: 'Productos' })).toBeVisible();
    const headers = within(table)
      .getAllByRole('columnheader')
      .map((cell) => cell.textContent);
    expect(headers).toEqual([
      'Imagen',
      'Nombre',
      'Tipo',
      'Set',
      'Precio',
      'En Cardmarket',
      'Oculto',
      'Actualizado',
    ]);
    const rows = within(table).getAllByRole('row').slice(1);
    expect(rows).toHaveLength(2);
    expect(rows[0].querySelector('img[src="/riftbound/media/products/501.png"]')).not.toBeNull();
    expect(within(rows[0]).getByText('Caja de sobres')).toBeVisible();
    expect(within(rows[0]).getByText('OGN')).toBeVisible();
    expect(within(rows[0]).getByText(/99,50/)).toBeVisible();
    expect(rows[1].querySelector('img')).toBeNull();
    expect(rows[1].querySelector('svg')).not.toBeNull();
    expect(within(rows[1]).getByText('Fundas')).toBeVisible();
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(await axe(container)).toHaveNoViolations();
  }, 30000);

  it('cards at 390 px open the editor in a bottom sheet', async () => {
    productsApi();
    const { container } = await renderApp({ path: '/admin/products', width: 390 });
    const card = await screen.findByRole(
      'button',
      { name: /Riftbound Sleeves/ },
      { timeout: 10000 },
    );
    expect(screen.queryByRole('table')).toBeNull();
    expect(await axe(container)).toHaveNoViolations();
    await userEvent.click(card);
    const sheet = await screen.findByRole('dialog', { name: 'Riftbound Sleeves' });
    expect(within(sheet).getByRole('combobox', { name: /Tipo/ })).toBeVisible();
  }, 30000);

  it('≥ 1600 px: a persistent panel edits the picked product and saves the kind', async () => {
    const { patches } = productsApi();
    await renderApp({ path: '/admin/products', width: 1700 });
    expect(
      await screen.findByText('Elige un producto para editarlo.', undefined, { timeout: 10000 }),
    ).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: 'Origins Booster Box' }));
    expect(screen.queryByRole('dialog')).toBeNull();
    const kind = await screen.findByRole('combobox', { name: /Tipo/ });
    expect(kind).toHaveValue('');
    await userEvent.selectOptions(kind, 'sleeves');
    await userEvent.click(screen.getByRole('button', { name: 'Guardar' }));
    expect((await screen.findAllByText('Producto guardado.')).length).toBeGreaterThan(0);
    expect(patches).toEqual([{ kind: 'sleeves' }]);
  }, 30000);

  it('locked fields show the badge; auto unlocks (kind null, set_id "auto") and hidden toggles', async () => {
    const { patches } = productsApi();
    await renderApp({ path: '/admin/products', width: 1280 });
    const editor = await openEditor('Riftbound Sleeves');
    expect(within(editor).getAllByText('Fijado a mano')).toHaveLength(2);
    const kind = within(editor).getByRole('combobox', { name: /Tipo/ });
    const set = within(editor).getByRole('combobox', { name: /Set/ });
    const hidden = within(editor).getByRole('switch', { name: 'Ocultar a los usuarios' });
    expect(kind).toHaveValue('sleeves');
    expect(hidden).toHaveAttribute('aria-checked', 'true');
    await userEvent.selectOptions(kind, 'Automático (según la categoría)');
    await userEvent.selectOptions(set, 'Automático (según la expansión)');
    await userEvent.click(hidden);
    await userEvent.click(within(editor).getByRole('button', { name: 'Guardar' }));
    await waitFor(() => expect(patches).toHaveLength(1));
    expect(patches[0]).toEqual({ kind: null, set_id: 'auto', hidden: false });
  }, 30000);

  it('an unlocked product shows no badge; a set or "no set" is sent as set_id', async () => {
    const { patches } = productsApi();
    await renderApp({ path: '/admin/products', width: 1280 });
    let editor = await openEditor('Origins Booster Box');
    expect(within(editor).queryByText('Fijado a mano')).toBeNull();
    await userEvent.selectOptions(within(editor).getByRole('combobox', { name: /Set/ }), 'Sin set');
    await userEvent.click(within(editor).getByRole('switch', { name: 'Ocultar a los usuarios' }));
    await userEvent.click(within(editor).getByRole('button', { name: 'Guardar' }));
    await waitFor(() => expect(patches).toHaveLength(1));
    expect(patches[0]).toEqual({ set_id: null, hidden: true });

    editor = await openEditor('Origins Booster Box');
    await userEvent.selectOptions(within(editor).getByRole('combobox', { name: /Set/ }), 'OGN');
    await userEvent.click(within(editor).getByRole('button', { name: 'Guardar' }));
    await waitFor(() => expect(patches).toHaveLength(2));
    expect(patches[1]).toEqual({ set_id: 'OGN' });
  }, 30000);

  it('a field error from the server is shown next to the field', async () => {
    productsApi();
    server.use(
      http.patch(`${API}/admin/products/:id`, () =>
        failure(400, {
          error: 'Validation Error',
          code: 'validation_error',
          details: [
            { field: 'set_id', message: 'Unknown set', type: 'value_error', code: 'invalid_value' },
          ],
        }),
      ),
    );
    await renderApp({ path: '/admin/products', width: 1280 });
    const editor = await openEditor('Origins Booster Box');
    await userEvent.selectOptions(within(editor).getByRole('combobox', { name: /Set/ }), 'OGN');
    await userEvent.click(within(editor).getByRole('button', { name: 'Guardar' }));
    expect(await within(editor).findByText('El valor no es válido.')).toBeVisible();
    expect(within(editor).getByRole('combobox', { name: /Set/ })).toHaveAttribute(
      'aria-invalid',
      'true',
    );
  }, 30000);

  it('uploads the image as multipart field `file`', async () => {
    productsApi();
    const uploads: unknown[] = [];
    server.use(
      http.post(`${API}/admin/products/:id/image`, ({ params, request }) => {
        uploads.push({ id: params.id, type: request.headers.get('content-type') });
        return ok({ ...sleeves, image_src: '/riftbound/media/products/502.png' });
      }),
    );
    await renderApp({ path: '/admin/products', width: 1280 });
    const editor = await openEditor('Riftbound Sleeves');
    const file = new File(['png'], 'sleeves.png', { type: 'image/png' });
    const append = vi.spyOn(FormData.prototype, 'append');
    await userEvent.upload(within(editor).getByLabelText('Subir imagen'), file);
    expect((await screen.findAllByText('Imagen actualizada.')).length).toBeGreaterThan(0);
    expect(uploads).toHaveLength(1);
    expect(uploads[0]).toMatchObject({ id: '502' });
    expect((uploads[0] as { type: string | null }).type ?? '').not.toContain('json');
    // jsdom's FormData cannot be read back on the MSW side: check what went into it.
    expect(append).toHaveBeenCalledWith('file', file);
    expect(editor.querySelector('img[src="/riftbound/media/products/502.png"]')).not.toBeNull();
  }, 30000);

  it('filters live in the URL and reach the API', async () => {
    const { queries } = productsApi();
    const app = await renderApp({ path: '/admin/products?kind=box&hidden=yes', width: 1280 });
    await screen.findByRole('table', { name: TABLE }, { timeout: 10000 });
    expect(queries[0]).toContain('kind=box');
    expect(queries[0]).toContain('hidden=yes');
    expect(screen.getByRole('button', { name: 'Caja de sobres' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    expect(screen.getByRole('combobox', { name: 'Ocultos' })).toHaveValue('yes');

    await userEvent.click(screen.getByRole('button', { name: 'Fundas' }));
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'En Cardmarket' }), 'no');
    await userEvent.click(screen.getByRole('switch', { name: 'Sin set' }));
    await userEvent.click(screen.getByRole('switch', { name: 'Sin imagen' }));
    await userEvent.type(screen.getByRole('textbox', { name: /Buscar/ }), 'box');
    await waitFor(() => expect(app.where()).toContain('q=box'));
    const url = new URLSearchParams(app.where().split('?')[1]);
    expect(url.getAll('kind')).toEqual(['box', 'sleeves']);
    expect(url.get('hidden')).toBe('yes');
    expect(url.get('listed')).toBe('no');
    expect(url.get('no_set')).toBe('true');
    expect(url.get('no_image')).toBe('true');
    await waitFor(() => expect(queries.at(-1)).toContain('q=box'));
    expect(queries.at(-1)).toContain('no_image=true');

    await userEvent.click(screen.getByRole('button', { name: 'Caja de sobres' }));
    await waitFor(() =>
      expect(new URLSearchParams(app.where().split('?')[1]).getAll('kind')).toEqual(['sleeves']),
    );
  }, 30000);

  it('empty result: the empty state', async () => {
    productsApi({ items: [], meta: { page: 1, per_page: 50, total: 0, pages: 1 } });
    await renderApp({ path: '/admin/products', width: 1280 });
    expect(
      await screen.findByText('Ningún producto coincide con los filtros.', undefined, {
        timeout: 10000,
      }),
    ).toBeVisible();
    expect(screen.queryByRole('table')).toBeNull();
  }, 30000);

  it('a failed load shows the error state with a retry', async () => {
    server.use(
      http.get(`${API}/auth/session`, () => adminSession()),
      http.get(`${API}/admin/products`, () => failure(500, { error: 'Internal Server Error' })),
    );
    await renderApp({ path: '/admin/products', width: 1280 });
    expect(
      await screen.findByText('No se pudo cargar', undefined, { timeout: 10000 }),
    ).toBeVisible();
    expect(screen.getByRole('button', { name: /Reintentar/ })).toBeVisible();
  }, 30000);
});
