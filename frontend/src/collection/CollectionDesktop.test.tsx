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

const table = () => screen.findByRole('table', { name: 'Tu colección agrupada por carta' }, LONG);
const row = (name: RegExp) => screen.getByRole('row', { name });

describe('CollectionDesktop at 1280 px (F3-h S1-S3)', () => {
  it('shows the facet sidebar, the toolbar, the summary band and the table by default', async () => {
    signedIn();
    await renderApp({ path: '/collection', width: 1280 });
    expect(await table()).toBeVisible();
    // sidebar with group counts
    const sidebar = screen.getByRole('complementary', { name: 'Filtrar colección' });
    expect(within(sidebar).getByRole('button', { name: /OGN/ })).toHaveTextContent('3');
    expect(within(sidebar).getByRole('button', { name: /Común/ })).toHaveTextContent('2');
    // toolbar
    expect(screen.getByText('3 cartas')).toBeVisible();
    expect(screen.getByRole('combobox', { name: 'Ordenar por' })).toBeVisible();
    expect(screen.getByRole('combobox', { name: 'Por página' })).toBeVisible();
    expect(screen.getByRole('radio', { name: 'Tabla' })).toBeChecked();
    // summary band
    const band = screen.getByText('Coste', { selector: 'dt' }).closest('dl')!;
    expect(within(band).getByText('9,84 €')).toBeVisible();
    expect(within(band).getByText('2,40 €')).toBeVisible();
    expect(within(band).getByText(/^\+1,23 €/)).toBeVisible();
    expect(within(band).getByText('1,30 €')).toBeVisible();
    expect(within(band).getByText('12,5 %')).toBeVisible();
    // the mobile layout is not there
    expect(screen.queryByRole('button', { name: 'Filtros' })).toBeNull();
  }, 20000);

  it('starts in the grid when the preference says so', async () => {
    signedIn({ ...NO_PREFS, collection_view: 'grid' });
    await renderApp({ path: '/collection', width: 1280 });
    await screen.findByRole('button', { name: /Ayla/ }, LONG);
    expect(screen.queryByRole('table')).toBeNull();
    expect(screen.getByRole('radio', { name: 'Cuadrícula' })).toBeChecked();
    await userEvent.click(screen.getByRole('radio', { name: 'Tabla' }));
    expect(await table()).toBeVisible();
  }, 20000);

  it('writes a negative profit with a minus sign', async () => {
    signedIn();
    list(collectionGroups, { totals: { ...collectionMeta.totals, pl: -2, cost: 10 } });
    await renderApp({ path: '/collection', width: 1280 });
    await table();
    const band = screen.getByText('Coste', { selector: 'dt' }).closest('dl')!;
    expect(within(band).getByText(/^−2,00 €/)).toBeVisible();
  }, 20000);

  it('is axe clean', async () => {
    signedIn();
    const { container } = await renderApp({ path: '/collection', width: 1280 });
    await table();
    expect(await axe(container)).toHaveNoViolations();
  }, 30000);
});

describe('the table (F3-h S3)', () => {
  it('has a row per card with the totals and a warning for a short playset', async () => {
    signedIn();
    await renderApp({ path: '/collection', width: 1280 });
    await table();
    const ayla = row(/Ayla/);
    expect(within(ayla).getByText('Playset incompleto (2/3)')).toBeVisible();
    expect(within(ayla).getByText('4')).toBeVisible(); // copies, summed over its two lines
    expect(within(ayla).getByText('OGN')).toBeVisible();
    // the foil card shows its foil mark and no warning
    expect(within(row(/Ember Wisp/)).getByText('Foil')).toBeVisible();
    expect(within(row(/Ember Wisp/)).queryByText(/Playset/)).toBeNull();
  }, 20000);

  it('folds the lines of a card with several lines and unfolds them on request', async () => {
    signedIn();
    await renderApp({ path: '/collection', width: 1280 });
    await table();
    expect(screen.queryByRole('checkbox', { name: /línea 1/ })).toBeNull();
    const expand = screen.getByRole('button', { name: "Ver las líneas de Ayla, Fury's Champion" });
    expect(expand).toHaveAttribute('aria-expanded', 'false');
    await userEvent.click(expand);
    expect(expand).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByRole('checkbox', { name: /Seleccionar .*línea 1/ })).toBeVisible();
    expect(screen.getByRole('checkbox', { name: /Seleccionar .*línea 2/ })).toBeVisible();
    await userEvent.click(expand);
    expect(screen.queryByRole('checkbox', { name: /línea 1/ })).toBeNull();
    // a single-line card has nothing to unfold
    expect(screen.queryByRole('button', { name: /Ver las líneas de Ember Wisp/ })).toBeNull();
  }, 20000);

  it('edits a single-line card in its own row', async () => {
    signedIn();
    await renderApp({ path: '/collection', width: 1280 });
    await table();
    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: 'Estado: Ember Wisp' }),
      'Excelente (EX)',
    );
    await waitFor(() => expect(sent.some((r) => r.method === 'PATCH')).toBe(true), LONG);
    expect(sent.find((r) => r.method === 'PATCH')).toMatchObject({
      path: '/collection/1301',
      body: { condition: 'EX', if_updated_at: '2026-10-25T09:12:00Z' },
    });
  }, 20000);

  it('edits a line of a multi-line card in its sub-line', async () => {
    signedIn();
    await renderApp({ path: '/collection', width: 1280 });
    await table();
    await userEvent.click(
      screen.getByRole('button', { name: "Ver las líneas de Ayla, Fury's Champion" }),
    );
    const switchOn = screen.getByRole('switch', {
      name: /En venta: .*línea 2/,
    });
    await userEvent.click(switchOn);
    await waitFor(() => expect(sent.some((r) => r.method === 'PATCH')).toBe(true), LONG);
    expect(sent.find((r) => r.method === 'PATCH')).toMatchObject({
      path: '/collection/1202',
      body: { selling: true },
    });
  }, 20000);

  it('sorts from the headers, with aria-sort', async () => {
    signedIn();
    const { where } = await renderApp({ path: '/collection', width: 1280 });
    await table();
    const nameHeader = screen.getByRole('columnheader', { name: 'Nombre' });
    expect(nameHeader).toHaveAttribute('aria-sort', 'none');
    expect(screen.getByRole('columnheader', { name: /Nº/ })).toHaveAttribute(
      'aria-sort',
      'ascending',
    );
    await userEvent.click(within(nameHeader).getByRole('button'));
    await waitFor(() => expect(where()).toBe('/collection?sort=name'), LONG);
    await waitFor(() =>
      expect(screen.getByRole('columnheader', { name: /Nombre/ })).toHaveAttribute(
        'aria-sort',
        'ascending',
      ),
    );
    await userEvent.click(
      within(screen.getByRole('columnheader', { name: /Nombre/ })).getByRole('button'),
    );
    await waitFor(() => expect(where()).toBe('/collection?sort=name&dir=desc'), LONG);
    // a column that cannot be sorted has no button
    expect(
      within(screen.getByRole('columnheader', { name: 'Idioma' })).queryByRole('button'),
    ).toBeNull();
  }, 30000);

  it('changes the page size', async () => {
    signedIn();
    const { where } = await renderApp({ path: '/collection', width: 1280 });
    await table();
    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: 'Por página' }),
      'Por página: 100',
    );
    await waitFor(() => expect(where()).toBe('/collection?per_page=100'), LONG);
  }, 20000);
});
