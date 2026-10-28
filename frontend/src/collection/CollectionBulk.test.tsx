import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { axe } from 'vitest-axe';
import { clearToasts } from '@/components/ui/toastStore';
import { collectionGroups, collectionMeta } from '@/test/fixtures/collection';
import { API, NO_PREFS, signedInSession } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';

const LONG = { timeout: 10000 };
type Sent = { method: string; path: string; body: Record<string, unknown> | null };
const sent: Sent[] = [];

beforeEach(() => {
  clearToasts();
  sent.length = 0;
  server.use(http.get(`${API}/auth/session`, () => signedInSession(NO_PREFS)));
  server.events.on('request:start', async ({ request }) => {
    const path = new URL(request.url).pathname.replace(API, '');
    if (!path.startsWith('/collection') || request.method === 'GET') return;
    let body: Record<string, unknown> | null = null;
    try {
      body = (await request.clone().json()) as Record<string, unknown>;
    } catch {
      body = null;
    }
    sent.push({ method: request.method, path, body });
  });
});
afterEach(() => server.events.removeAllListeners());

async function open(width = 1280) {
  const app = await renderApp({ path: '/collection', width });
  await screen.findByRole('table', { name: 'Tu colección agrupada por carta' }, LONG);
  return app;
}

const box = (name: RegExp | string) => screen.getByRole('checkbox', { name });
const bar = () => screen.getByRole('region', { name: /seleccionadas?$/ });

describe('selection (F3-h S4)', () => {
  it('nothing is selected and there is no bulk bar at first', async () => {
    await open();
    expect(screen.queryByRole('region', { name: /seleccionadas?$/ })).toBeNull();
  }, 20000);

  it('selecting one line of a card marks the card as partly selected', async () => {
    await open();
    await userEvent.click(
      screen.getByRole('button', { name: "Ver las líneas de Ayla, Fury's Champion" }),
    );
    await userEvent.click(box(/Seleccionar .*línea 1/));
    expect(await screen.findByText('1 línea seleccionada')).toBeVisible();
    const group = box("Seleccionar Ayla, Fury's Champion") as HTMLInputElement;
    expect(group.indeterminate).toBe(true);
    expect(group.checked).toBe(false);
    await userEvent.click(box(/Seleccionar .*línea 2/));
    expect(await screen.findByText('2 líneas seleccionadas')).toBeVisible();
    expect((box("Seleccionar Ayla, Fury's Champion") as HTMLInputElement).checked).toBe(true);
  }, 20000);

  it('the group box selects all its lines, the header box every line on the page', async () => {
    await open();
    await userEvent.click(box("Seleccionar Ayla, Fury's Champion"));
    expect(await screen.findByText('2 líneas seleccionadas')).toBeVisible();
    await userEvent.click(box('Seleccionar todo en esta página'));
    expect(await screen.findByText('4 líneas seleccionadas')).toBeVisible();
    await userEvent.click(box('Seleccionar todo en esta página'));
    await waitFor(() => expect(screen.queryByText(/seleccionadas?$/)).toBeNull());
  }, 20000);

  it('offers every filtered line when the page is only a part of the result', async () => {
    list(collectionGroups.slice(0, 2), { total_groups: 3, per_page: 2, pages: 2 });
    await open();
    await userEvent.click(box('Seleccionar todo en esta página'));
    const link = await screen.findByRole('button', { name: 'Seleccionar las 4 líneas filtradas' });
    await userEvent.click(link);
    expect(await screen.findByText('4 líneas seleccionadas')).toBeVisible();
  }, 20000);

  it('refuses to select more than 1000 lines', async () => {
    list(collectionGroups.slice(0, 2), {
      total_groups: 3,
      per_page: 2,
      pages: 2,
      totals: { ...collectionMeta.totals, lines: 1500 },
    });
    await open();
    await userEvent.click(box('Seleccionar todo en esta página'));
    expect(await screen.findByText('Más de 1000 líneas: filtra un poco más.')).toBeVisible();
    expect(screen.queryByRole('button', { name: /líneas filtradas/ })).toBeNull();
  }, 20000);

  it('forgets the selection when the filters change', async () => {
    const { where } = await open();
    await userEvent.click(box('Seleccionar todo en esta página'));
    expect(await screen.findByText('4 líneas seleccionadas')).toBeVisible();
    await userEvent.click(screen.getByRole('radio', { name: 'Solo foil' }));
    await waitFor(() => expect(where()).toBe('/collection?foil=foil'), LONG);
    await waitFor(() => expect(screen.queryByText(/seleccionadas?$/)).toBeNull(), LONG);
  }, 25000);
});

function list(items = collectionGroups, meta: Record<string, unknown> = {}) {
  server.use(
    http.get(`${API}/collection`, ({ request }) => {
      const page = Number(new URL(request.url).searchParams.get('page') ?? '1');
      return HttpResponse.json({
        success: true,
        data: { items: page > 1 ? collectionGroups.slice(2) : items },
        meta: { ...collectionMeta, total_groups: items.length, ...meta, page },
      });
    }),
  );
}

describe('bulk bar (F3-h S5)', () => {
  async function selectAll() {
    await userEvent.click(box('Seleccionar todo en esta página'));
    await screen.findByText('4 líneas seleccionadas');
  }

  it('applies one change to the selected lines after a confirmation', async () => {
    await open();
    await selectAll();
    const controls = within(bar());
    await userEvent.selectOptions(controls.getByLabelText('Estado'), 'Excelente (EX)');
    await userEvent.selectOptions(controls.getByLabelText('Copias a vender'), 'Conservar');
    await userEvent.clear(controls.getByLabelText('Copias a conservar'));
    await userEvent.type(controls.getByLabelText('Copias a conservar'), '2');
    await userEvent.click(controls.getByRole('button', { name: 'Aplicar' }));
    const dialog = await screen.findByRole('dialog', { name: 'Aplicar' });
    expect(within(dialog).getByText('¿Aplicar los cambios a 4 líneas?')).toBeVisible();
    await userEvent.click(within(dialog).getByRole('button', { name: 'Aplicar' }));
    await waitFor(() => expect(sent.some((r) => r.path === '/collection/bulk')).toBe(true), LONG);
    expect(sent.find((r) => r.path === '/collection/bulk')!.body).toEqual({
      ids: [1201, 1202, 1301, 1401],
      set: { condition: 'EX', sell_qty_rule: 'keep_n', keep: 2 },
    });
    expect((await screen.findAllByText('Cambios aplicados.')).length).toBeGreaterThan(0);
  }, 30000);

  it('sends the selling flag and the prices when they are filled in', async () => {
    await open();
    await selectAll();
    const controls = within(bar());
    await userEvent.selectOptions(controls.getByLabelText('En venta'), 'Sí');
    await userEvent.type(controls.getByLabelText('Precio de venta'), '2.5');
    await userEvent.type(controls.getByLabelText('Precio de compra'), '1');
    await userEvent.click(controls.getByRole('button', { name: 'Aplicar' }));
    await userEvent.click(
      within(await screen.findByRole('dialog', { name: 'Aplicar' })).getByRole('button', {
        name: 'Aplicar',
      }),
    );
    await waitFor(() => expect(sent.some((r) => r.path === '/collection/bulk')).toBe(true), LONG);
    expect(sent.find((r) => r.path === '/collection/bulk')!.body?.set).toEqual({
      selling: true,
      sell_price: 2.5,
      purchase_price: 1,
    });
  }, 30000);

  it('asks to choose a change when nothing is chosen', async () => {
    await open();
    await selectAll();
    await userEvent.click(within(bar()).getByRole('button', { name: 'Aplicar' }));
    expect(await screen.findByText('Elige al menos un cambio.')).toBeVisible();
    expect(screen.queryByRole('dialog', { name: 'Aplicar' })).toBeNull();
    expect(sent).toHaveLength(0);
  }, 20000);

  it('cancelling the confirmation changes nothing', async () => {
    await open();
    await selectAll();
    await userEvent.selectOptions(within(bar()).getByLabelText('Estado'), 'Buena (GD)');
    await userEvent.click(within(bar()).getByRole('button', { name: 'Aplicar' }));
    await userEvent.click(
      within(await screen.findByRole('dialog', { name: 'Aplicar' })).getByRole('button', {
        name: 'Cancelar',
      }),
    );
    expect(sent).toHaveLength(0);
  }, 20000);

  it('deletes after a confirmation and offers to undo for 8 seconds', async () => {
    await open();
    await selectAll();
    await userEvent.click(within(bar()).getByRole('button', { name: 'Eliminar' }));
    const dialog = await screen.findByRole('dialog', { name: 'Eliminar' });
    expect(within(dialog).getByText('¿Eliminar 4 líneas?')).toBeVisible();
    await userEvent.click(within(dialog).getByRole('button', { name: 'Eliminar' }));
    expect((await screen.findAllByText('4 líneas eliminadas.')).length).toBeGreaterThan(0);
    expect(sent.find((r) => r.path === '/collection/bulk')!.body).toEqual({
      ids: [1201, 1202, 1301, 1401],
      delete: true,
    });
    const { getToasts } = await import('@/components/ui/toastStore');
    expect(getToasts().find((toast) => toast.message === '4 líneas eliminadas.')?.duration).toBe(
      8000,
    );
    // the bar is gone with the selection
    expect(screen.queryByRole('region', { name: /seleccionadas?$/ })).toBeNull();

    await userEvent.click(screen.getByRole('button', { name: 'Deshacer' }));
    await waitFor(
      () =>
        expect(sent.filter((r) => r.method === 'POST' && r.path === '/collection')).toHaveLength(4),
      LONG,
    );
    expect((await screen.findAllByText('Línea restaurada.')).length).toBeGreaterThan(0);
  }, 30000);

  it('clears the selection on request', async () => {
    await open();
    await selectAll();
    await userEvent.click(within(bar()).getByRole('button', { name: 'Quitar selección' }));
    await waitFor(() => expect(screen.queryByText(/seleccionadas?$/)).toBeNull());
  }, 20000);

  it('is axe clean with the bar open', async () => {
    const { container } = await open();
    await selectAll();
    expect(await axe(container)).toHaveNoViolations();
  }, 30000);
});
