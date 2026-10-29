import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';
import { NO_PREFS, API, failure, signedInSession } from '@/test/msw/handlers';
import {
  aylaGroup,
  collectionGroups,
  collectionMeta,
  emberGroup,
} from '@/test/fixtures/collection';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';

const LONG = { timeout: 10000 };

function signedIn(prefs: Record<string, unknown> = NO_PREFS) {
  server.use(http.get(`${API}/auth/session`, () => signedInSession(prefs)));
}

function list(items = collectionGroups, meta: Record<string, unknown> = {}) {
  server.use(
    http.get(`${API}/collection`, () =>
      HttpResponse.json({
        success: true,
        data: { items },
        meta: { ...collectionMeta, total_groups: items.length, ...meta },
      }),
    ),
  );
}

afterEach(() => vi.restoreAllMocks());

describe.each([390, 1000])('CollectionPage at %i px (F3-g S2-S3)', (width) => {
  it('shows the title, the summary, the search and the items', async () => {
    signedIn();
    await renderApp({ path: '/collection', width });
    expect(await screen.findByRole('heading', { name: 'Colección' }, LONG)).toBeVisible();
    expect(
      await screen.findByText('Copias: 16 · Únicas: 3 · Valor: 9,84 €', {}, LONG),
    ).toBeVisible();
    const strip = screen.getByText('Copias', { selector: 'dt' }).closest('dl')!;
    expect(within(strip).getByText('16')).toBeVisible();
    expect(within(strip).getByText('3')).toBeVisible();
    expect(within(strip).getByText('9,84 €')).toBeVisible();
    expect(screen.getByRole('searchbox', { name: 'Buscar en tu colección' })).toBeVisible();
    expect(await screen.findByRole('button', { name: /Ayla/ })).toBeVisible();
    expect(screen.getByRole('button', { name: /Ember Wisp/ })).toBeVisible();
    expect(screen.getByRole('button', { name: 'Añadir carta' })).toBeEnabled();
    expect(screen.getByRole('link', { name: 'Versión clásica' })).toHaveAttribute(
      'href',
      '/riftbound/collection',
    );
  }, 15000);

  it('is axe clean', async () => {
    signedIn();
    const { container } = await renderApp({ path: '/collection', width });
    await screen.findByRole('button', { name: /Ayla/ }, LONG);
    expect(await axe(container)).toHaveNoViolations();
  }, 20000);
});

describe('CollectionPage controls', () => {
  it('the nav entry opens this screen in the app', async () => {
    signedIn();
    await renderApp({ path: '/', width: 1280 });
    const links = await screen.findAllByRole('link', { name: /Colección/ }, LONG);
    expect(links.length).toBeGreaterThan(0);
    for (const link of links) expect(link).toHaveAttribute('href', '/riftbound/app/collection');
  }, 15000);

  it('writes the search to the URL and filters the list', async () => {
    signedIn();
    const { where } = await renderApp({ path: '/collection', width: 390 });
    await screen.findByRole('button', { name: /Ayla/ }, LONG);
    await userEvent.type(screen.getByRole('searchbox'), 'ember');
    await waitFor(() => expect(where()).toBe('/collection?q=ember'), LONG);
    await waitFor(() => expect(screen.queryByRole('button', { name: /Ayla/ })).toBeNull(), LONG);
    expect(screen.getByRole('button', { name: /Ember Wisp/ })).toBeVisible();
  }, 20000);

  it('reads the search from the URL (the link of the card detail)', async () => {
    signedIn();
    await renderApp({ path: '/collection?q=OGN-79', width: 390 });
    expect(await screen.findByRole('searchbox', {}, LONG)).toHaveValue('OGN-79');
  }, 15000);

  it('filters from the sheet, shows a removable chip and clears', async () => {
    signedIn();
    const { where } = await renderApp({ path: '/collection', width: 390 });
    await screen.findByRole('button', { name: /Ayla/ }, LONG);
    await userEvent.click(screen.getByRole('button', { name: 'Filtros' }));
    const sheet = await screen.findByRole('dialog', { name: 'Filtrar colección' });
    await userEvent.click(within(sheet).getByRole('radio', { name: 'Solo foil' }));
    await waitFor(() => expect(where()).toBe('/collection?foil=foil'), LONG);
    // wait for the sheet to render the new URL before the next click
    await waitFor(() =>
      expect(within(sheet).getByRole('radio', { name: 'Solo foil' })).toBeChecked(),
    );
    await userEvent.click(within(sheet).getByRole('button', { name: /^Mint \(MT\)/ }));
    await waitFor(() => expect(where()).toBe('/collection?condition=MT&foil=foil'), LONG);
    await userEvent.click(within(sheet).getByRole('button', { name: /Ver \d+ cartas?/ }));
    const chip = await screen.findByRole('button', { name: 'Quitar filtro Mint (MT)' });
    expect(screen.getByRole('button', { name: /Filtros/ })).toHaveTextContent('2');
    await userEvent.click(chip);
    await waitFor(() => expect(where()).toBe('/collection?foil=foil'), LONG);
  }, 25000);

  it('changes the sort and its direction through the URL', async () => {
    signedIn();
    const { where } = await renderApp({ path: '/collection', width: 390 });
    await screen.findByRole('button', { name: /Ayla/ }, LONG);
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Ordenar por' }), 'Valor');
    await waitFor(() => expect(where()).toBe('/collection?sort=value'), LONG);
    await userEvent.click(screen.getByRole('button', { name: 'Cambiar sentido del orden' }));
    await waitFor(() => expect(where()).toBe('/collection?sort=value&dir=desc'), LONG);
  }, 20000);

  it('starts in the grid, or in the list when the preference is the table', async () => {
    signedIn();
    const { unmount } = await renderApp({ path: '/collection', width: 390 });
    await screen.findByRole('button', { name: /Ayla/ }, LONG);
    expect(screen.getByRole('radio', { name: 'Cuadrícula' })).toBeChecked();
    unmount();
    signedIn({ ...NO_PREFS, collection_view: 'table' });
    await renderApp({ path: '/collection', width: 390 });
    await screen.findByRole('button', { name: /Ayla/ }, LONG);
    expect(screen.getByRole('radio', { name: 'Lista' })).toBeChecked();
    await userEvent.click(screen.getByRole('radio', { name: 'Cuadrícula' }));
    expect(screen.getByRole('radio', { name: 'Cuadrícula' })).toBeChecked();
  }, 25000);

  it('pages through the URL', async () => {
    signedIn();
    list(collectionGroups, { pages: 3, page: 1 });
    const { where } = await renderApp({ path: '/collection', width: 390 });
    await screen.findByRole('button', { name: /Ayla/ }, LONG);
    await userEvent.click(await screen.findByRole('button', { name: 'Siguiente' }));
    await waitFor(() => expect(where()).toBe('/collection?page=2'), LONG);
  }, 20000);

  it('opens the lines of a card and the add sheet', async () => {
    signedIn();
    await renderApp({ path: '/collection', width: 390 });
    await userEvent.click(await screen.findByRole('button', { name: /Ayla/ }, LONG));
    expect(
      await screen.findByRole('dialog', { name: "Copias de Ayla, Fury's Champion" }),
    ).toBeVisible();
    await userEvent.click(screen.getAllByRole('button', { name: 'Cerrar' })[0]);
    await userEvent.click(screen.getByRole('button', { name: 'Añadir carta' }));
    expect(await screen.findByRole('dialog', { name: 'Añadir a la colección' })).toBeVisible();
  }, 20000);

  it('marks the playset shortage in the list', async () => {
    signedIn();
    await renderApp({ path: '/collection', width: 390 });
    expect(await screen.findByText('Playset incompleto (2/3)', {}, LONG)).toBeVisible();
  }, 15000);
});

describe('CollectionPage states (F3-g S9)', () => {
  it('an empty collection invites to add or import', async () => {
    signedIn();
    list([], { totals: { ...collectionMeta.totals, lines: 0, qty: 0, unique: 0, value: 0 } });
    await renderApp({ path: '/collection', width: 390 });
    expect(await screen.findByText('Tu colección está vacía', {}, LONG)).toBeVisible();
    // the empty state and the header both open the import wizard (F3-i S2)
    const imports = screen.getAllByRole('link', { name: 'Importar' });
    expect(imports).toHaveLength(2);
    for (const link of imports) {
      expect(link).toHaveAttribute('href', '/riftbound/app/collection/import');
    }
    await userEvent.click(
      screen.getByRole('button', { name: 'Añadir carta', hidden: false, description: '' }),
    );
  }, 20000);

  it('filters that match nothing offer to clear them', async () => {
    signedIn();
    list([]);
    const { where } = await renderApp({ path: '/collection?q=zzz&foil=foil', width: 390 });
    expect(
      await screen.findByText('Ninguna carta de tu colección coincide con los filtros.', {}, LONG),
    ).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: 'Limpiar filtros' }));
    await waitFor(() => expect(where()).toBe('/collection'), LONG);
  }, 20000);

  it('an error can be retried', async () => {
    signedIn();
    server.use(
      http.get(`${API}/collection`, () => failure(500, { error: 'Internal Server Error' })),
    );
    await renderApp({ path: '/collection', width: 390 });
    expect(await screen.findByText('No se pudo cargar tu colección.', {}, LONG)).toBeVisible();
    expect(screen.getByRole('button', { name: /Reintentar|Intentar/ })).toBeVisible();
  }, 20000);

  it('offline: the add button is disabled', async () => {
    signedIn();
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    await renderApp({ path: '/collection', width: 390 });
    await screen.findByRole('button', { name: /Ayla/ }, LONG);
    expect(screen.getByRole('button', { name: 'Añadir carta' })).toBeDisabled();
  }, 20000);

  it('the group of a deleted line leaves the open sheet closed', async () => {
    signedIn();
    list([aylaGroup]);
    await renderApp({ path: '/collection', width: 390 });
    await userEvent.click(await screen.findByRole('button', { name: /Ayla/ }, LONG));
    expect(await screen.findByRole('dialog', { name: /Copias de Ayla/ })).toBeVisible();
  }, 20000);

  it('deleting the only line of a group still offers the undo toast', async () => {
    signedIn();
    let deleted = false;
    server.use(
      http.get(`${API}/collection`, () =>
        HttpResponse.json({
          success: true,
          data: { items: deleted ? [] : [emberGroup] },
          meta: { ...collectionMeta, total_groups: deleted ? 0 : 1 },
        }),
      ),
      http.delete(`${API}/collection/:id`, ({ params }) => {
        deleted = true;
        return HttpResponse.json({
          success: true,
          data: { deleted: { ...emberGroup.lines[0], id: Number(params.id) } },
        });
      }),
    );
    await renderApp({ path: '/collection', width: 390 });
    await userEvent.click(await screen.findByRole('button', { name: /Ember Wisp/ }, LONG));
    const sheet = await screen.findByRole('dialog', { name: /Copias de Ember Wisp/ }, LONG);
    await userEvent.click(within(sheet).getByRole('button', { name: 'Eliminar' }));
    const confirm = await screen.findByRole('dialog', { name: '¿Eliminar esta línea?' });
    await userEvent.click(within(confirm).getByRole('button', { name: 'Eliminar' }));
    // the group is gone from the list, so the sheet unmounts: the toast must survive
    expect((await screen.findAllByText('Línea eliminada.', {}, LONG))[0]).toBeVisible();
    expect(screen.getByRole('button', { name: 'Deshacer' })).toBeVisible();
  }, 30000);
});
