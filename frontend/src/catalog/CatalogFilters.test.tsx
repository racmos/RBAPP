import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';
import { API, ok, signedInSession } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';

const LONG = { timeout: 10000 };

function signedInApi() {
  server.use(http.get(`${API}/auth/session`, () => signedInSession()));
}

describe('CatalogFilters (F2-i S1)', () => {
  it('opens the filter sheet below 1240 px; groups are not collapsible there', async () => {
    signedInApi();
    await renderApp({ path: '/cards', width: 390 });
    await screen.findByRole('link', { name: /Ayla/ }, LONG);
    await userEvent.click(screen.getByRole('button', { name: 'Filtros' }));
    expect(await screen.findByRole('dialog', { name: 'Filtros' }, LONG)).toBeVisible();
    expect(screen.getByRole('button', { name: 'Ver 6 cartas' })).toBeVisible();
    const setLegend = screen.getByText('Set');
    expect(setLegend.closest('button')).toBeNull();
    expect(screen.queryAllByRole('button', { expanded: true })).toHaveLength(0);
  });

  it('renders in the sidebar at 1280 px and the sheet button is gone', async () => {
    signedInApi();
    const { container } = await renderApp({ path: '/cards', width: 1280 });
    await screen.findByRole('link', { name: /Ayla/ }, LONG);
    expect(screen.queryByRole('button', { name: 'Filtros' })).not.toBeInTheDocument();
    const sidebar = container.querySelector('[data-testid="catalog-sidebar"]');
    expect(sidebar).toBeInTheDocument();
    expect(sidebar).toHaveTextContent('Set');
  });

  it('collapses sidebar groups with aria-expanded and remembers the state', async () => {
    signedInApi();
    await renderApp({ path: '/cards', width: 1280 });
    await screen.findByRole('link', { name: /Ayla/ }, LONG);
    const setButton = screen.getByRole('button', { name: 'Set' });
    expect(setButton).toHaveAttribute('aria-expanded', 'true');
    await userEvent.click(setButton);
    await waitFor(() => expect(setButton).toHaveAttribute('aria-expanded', 'false'));
    expect(JSON.parse(window.localStorage.getItem('rb_cards_facets')!)).not.toContain('set');
  });

  it('treats invalid rb_cards_facets as all open', async () => {
    window.localStorage.setItem('rb_cards_facets', 'not-json');
    signedInApi();
    await renderApp({ path: '/cards', width: 1280 });
    await screen.findByRole('link', { name: /Ayla/ }, LONG);
    expect(screen.getByRole('button', { name: 'Set' })).toHaveAttribute('aria-expanded', 'true');
  });

  it('shows "Limpiar filtros" at the top of the sidebar when filters are active', async () => {
    signedInApi();
    const { where, container } = await renderApp({ path: '/cards?domain=Fury', width: 1280 });
    await screen.findByRole('link', { name: /Ayla/ }, LONG);
    const sidebar = container.querySelector('[data-testid="catalog-sidebar"]')!;
    const clear = screen
      .getAllByRole('button', { name: 'Limpiar filtros' })
      .find((b) => sidebar.contains(b));
    expect(clear).toBeDefined();
    await userEvent.click(clear!);
    await waitFor(() => expect(where()).toBe('/cards'), LONG);
  });

  it('keeps facet counts readable while a request is in flight (aria-busy)', async () => {
    signedInApi();
    let release!: () => void;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.use(
      http.get(`${API}/cards`, async () => {
        await gate;
        return HttpResponse.json(
          {
            success: true,
            data: { items: [] },
            meta: { page: 1, per_page: 48, total: 0, pages: 0, facets: {}, price_as_of: null },
          },
          { status: 200 },
        );
      }),
    );
    await renderApp({ path: '/cards?q=delay', width: 1280 });
    const sidebar = await screen.findByTestId('catalog-sidebar');
    await waitFor(() => expect(sidebar).toHaveAttribute('aria-busy', 'true'), LONG);
    release();
    await waitFor(() => expect(sidebar).not.toHaveAttribute('aria-busy'), LONG);
  });
});

/** The elements that show `text` on screen (an `sr-only` copy only names a control). */
function shown(container: HTMLElement, text: string): HTMLElement[] {
  return within(container)
    .queryAllByText(text, { exact: true })
    .filter((element) => !element.closest('.sr-only'));
}

const GROUP_TITLES = [
  'Set',
  'Dominio',
  'Tipo',
  'Supertipo',
  'Rareza',
  'Coste de energía',
  'Poder',
  'Fuerza',
  'Precio (€)',
  'Colección',
  'Baneos',
  'Solo versión base',
  'Texto de la carta',
  'Etiquetas',
];

describe('CatalogFilters headings (owner feedback S18 g)', () => {
  it('shows one heading per sidebar group and keeps every control named', async () => {
    signedInApi();
    await renderApp({ path: '/cards', width: 1280 });
    await screen.findByRole('link', { name: /Ayla/ }, LONG);
    const sidebar = screen.getByTestId('catalog-sidebar');
    for (const title of GROUP_TITLES) {
      expect(shown(sidebar, title), title).toHaveLength(1);
    }
    for (const name of ['Dominio', 'Tipo', 'Supertipo', 'Rareza', 'Coste de energía']) {
      expect(within(sidebar).getByRole('group', { name })).toBeInTheDocument();
    }
    expect(within(sidebar).getByRole('combobox', { name: 'Baneos' })).toBeInTheDocument();
    expect(within(sidebar).getByRole('searchbox', { name: 'Texto de la carta' })).toBeVisible();
    expect(within(sidebar).getByRole('switch', { name: 'Solo versión base' })).toBeVisible();
  });

  it('names each sheet group once and translates the base types', async () => {
    signedInApi();
    await renderApp({ path: '/cards', width: 390 });
    await screen.findByRole('link', { name: /Ayla/ }, LONG);
    await userEvent.click(screen.getByRole('button', { name: 'Filtros' }));
    const dialog = await screen.findByRole('dialog', { name: 'Filtros' }, LONG);
    for (const title of ['Dominio', 'Tipo', 'Supertipo', 'Rareza']) {
      expect(shown(dialog, title), title).toHaveLength(1);
    }
    const types = within(dialog).getByRole('group', { name: 'Tipo' });
    expect(within(types).getByRole('button', { name: /^Unidad/ })).toBeInTheDocument();
    expect(within(types).queryByText(/Champion|Unit$/)).not.toBeInTheDocument();
  });
});

describe('CatalogFilters numeric ranges', () => {
  it('keeps the digits typed while the URL waits for the debounce', async () => {
    signedInApi();
    const { where } = await renderApp({ path: '/cards', width: 390 });
    await screen.findByRole('link', { name: /Ayla/ }, LONG);
    await userEvent.click(screen.getByRole('button', { name: 'Filtros' }));
    const dialog = await screen.findByRole('dialog', { name: 'Filtros' }, LONG);
    const energy = within(dialog).getByRole('group', { name: 'Coste de energía' });
    const min = within(energy).getByLabelText('Mín.');
    await userEvent.type(min, '12');
    expect(min).toHaveValue(12);
    await waitFor(() => expect(where()).toBe('/cards?energy_min=12'), LONG);
    expect(min).toHaveValue(12);
  }, 15000);
});

describe('CatalogFilters set order (owner feedback S19)', () => {
  it('lists the sets newest first and the sets without a date last', async () => {
    signedInApi();
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
            { id: 'NOD', name: 'Sin fecha', released_on: null, card_count: 0 },
            { id: 'VEN', name: 'Vendetta', released_on: '2026-08-01', card_count: 166 },
            { id: 'OGS', name: 'Proving Grounds', released_on: '2024-03-01', card_count: 24 },
          ],
          price: { provider: 'cardmarket', currency: 'EUR', updated_on: null },
          rules: {},
          conditions: ['NM'],
          languages: ['English'],
        }),
      ),
    );
    const { container } = await renderApp({ path: '/cards', width: 1280 });
    await screen.findByRole('link', { name: /Ayla/ }, LONG);
    const sidebar = container.querySelector<HTMLElement>('[data-testid="catalog-sidebar"]')!;
    await within(sidebar).findByRole('checkbox', { name: /Vendetta/ }, LONG);
    const names = within(sidebar)
      .getAllByRole('checkbox')
      .map((box) => box.getAttribute('aria-label') ?? box.closest('label')?.textContent ?? '')
      .filter((name) => /Origen|Sin fecha|Vendetta|Proving/.test(name))
      .map((name) => name.replace(/ \(.*\)$/, ''));
    expect(names).toEqual(['Vendetta', 'Proving Grounds', 'Origen', 'Sin fecha']);
  });
});
