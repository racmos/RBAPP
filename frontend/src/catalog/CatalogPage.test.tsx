import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';
import { axe } from 'vitest-axe';
import { API, failure, signedInSession } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';
import { cardList } from '@/test/fixtures/cards';

const LONG = { timeout: 10000 };

function signedInApi() {
  server.use(http.get(`${API}/auth/session`, () => signedInSession()));
}

describe('CatalogPage (F2-h AC3, AC4, AC7)', () => {
  it('renders the catalog grid at 390 px', async () => {
    signedInApi();
    await renderApp({ path: '/cards', width: 390 });
    expect(await screen.findByRole('heading', { name: 'Cartas' }, LONG)).toBeVisible();
    expect(await screen.findByRole('link', { name: /Ayla/ }, LONG)).toBeVisible();
    expect(screen.getByText('6 cartas')).toBeVisible();
  });

  it('debounces the search input and uses replace', async () => {
    signedInApi();
    const { where } = await renderApp({ path: '/cards', width: 390 });
    await screen.findByRole('link', { name: /Ayla/ }, LONG);
    const input = screen.getByPlaceholderText('Nombre, etiqueta o número');
    await userEvent.type(input, 'aya');
    expect(where()).toBe('/cards');
    await waitFor(() => expect(where()).toBe('/cards?q=aya'), LONG);
    expect(screen.getByRole('link', { name: /Ayla/ })).toBeVisible();
  });

  it('keeps a letter typed while the URL catches up with the previous ones', async () => {
    signedInApi();
    const { where } = await renderApp({ path: '/cards', width: 390 });
    await screen.findByRole('link', { name: /Ayla/ }, LONG);
    const input = screen.getByPlaceholderText('Nombre, etiqueta o número');
    const user = userEvent.setup();
    await user.type(input, 'ay');
    // The previous letters are on their way to the URL: type the next one right then.
    await new Promise((resolve) => setTimeout(resolve, 450));
    await user.type(input, 'l');
    await waitFor(() => expect(where()).toBe('/cards?q=ayl'), LONG);
    await new Promise((resolve) => setTimeout(resolve, 700));
    expect(input).toHaveValue('ayl');
  }, 15000);

  it('still follows the URL when the search is changed from outside', async () => {
    signedInApi();
    const { router, where } = await renderApp({ path: '/cards?q=ayl', width: 390 });
    const input = await screen.findByPlaceholderText('Nombre, etiqueta o número', {}, LONG);
    expect(input).toHaveValue('ayl');
    await router.navigate('/cards');
    await waitFor(() => expect(input).toHaveValue(''), LONG);
    expect(where()).toBe('/cards');
  }, 15000);

  it('opens the filter sheet and shows domain chips with counts', async () => {
    signedInApi();
    await renderApp({ path: '/cards', width: 390 });
    await screen.findByRole('link', { name: /Ayla/ }, LONG);
    await userEvent.click(screen.getByRole('button', { name: 'Filtros' }));
    expect(await screen.findByRole('dialog', { name: 'Filtros' }, LONG)).toBeVisible();
    expect(screen.getByRole('button', { name: 'Furia (3)' })).toBeVisible();
  });

  it('filters by domain and reflects in URL and active chips', async () => {
    signedInApi();
    const { where } = await renderApp({ path: '/cards', width: 390 });
    await screen.findByRole('link', { name: /Ayla/ }, LONG);
    await userEvent.click(screen.getByRole('button', { name: 'Filtros' }));
    await screen.findByRole('dialog', { name: 'Filtros' }, LONG);
    await userEvent.click(screen.getByRole('button', { name: 'Furia (3)' }));
    await waitFor(() => expect(where()).toBe('/cards?domain=Fury'), LONG);
    expect(await screen.findByRole('button', { name: 'Quitar filtro Furia' }, LONG)).toBeVisible();
  });

  it('clears all active filters', async () => {
    signedInApi();
    const { where } = await renderApp({ path: '/cards?domain=Fury', width: 390 });
    await screen.findByRole('button', { name: 'Quitar filtro Furia' }, LONG);
    await userEvent.click(screen.getByRole('button', { name: 'Limpiar filtros' }));
    await waitFor(() => expect(where()).toBe('/cards'), LONG);
  });

  it('changes sort and direction', async () => {
    signedInApi();
    const { where } = await renderApp({ path: '/cards', width: 390 });
    await screen.findByRole('link', { name: /Ayla/ }, LONG);
    await userEvent.selectOptions(screen.getByLabelText('Ordenar por'), 'name');
    await waitFor(() => expect(where()).toBe('/cards?sort=name'), LONG);
    await userEvent.click(screen.getByRole('button', { name: 'Orden descendente' }));
    await waitFor(() => expect(where()).toBe('/cards?sort=name&dir=desc'), LONG);
  });

  it('toggles grid/list view and persists in localStorage', async () => {
    signedInApi();
    await renderApp({ path: '/cards', width: 390 });
    await screen.findByRole('list', { name: 'Resultados' }, LONG);
    await userEvent.click(screen.getByRole('radio', { name: 'Lista' }));
    expect(screen.getByRole('list', { name: 'Resultados' })).toHaveAttribute('data-view', 'list');
    expect(window.localStorage.getItem('rb_cards_view')).toBe('list');
  });

  it('tile links keep the search string', async () => {
    signedInApi();
    await renderApp({ path: '/cards?domain=Fury', width: 390 });
    const link = await screen.findByRole('link', { name: /Ayla/ }, LONG);
    expect(link).toHaveAttribute('href', '/riftbound/app/cards/OGN/79?domain=Fury');
  });

  it('at 390 px the detail replaces the catalog and back restores it', async () => {
    signedInApi();
    const { where, router } = await renderApp({ path: '/cards?domain=Fury', width: 390 });
    await screen.findByRole('link', { name: /Ayla/ }, LONG);
    await userEvent.click(screen.getByRole('link', { name: /Ayla/ }));
    await waitFor(() => expect(where()).toBe('/cards/OGN/79?domain=Fury'), LONG);
    expect(screen.queryByRole('heading', { name: 'Cartas' })).not.toBeInTheDocument();
    router.navigate(-1);
    await waitFor(() => expect(where()).toBe('/cards?domain=Fury'), LONG);
    expect(await screen.findByRole('heading', { name: 'Cartas' }, LONG)).toBeVisible();
  });

  it('at 1024 px the detail is a modal with close returning to /cards?...', async () => {
    signedInApi();
    const { where } = await renderApp({ path: '/cards?domain=Fury', width: 1024 });
    await screen.findByRole('link', { name: /Ayla/ }, LONG);
    await userEvent.click(screen.getByRole('link', { name: /Ayla/ }));
    const dialog = await screen.findByRole('dialog', undefined, LONG);
    expect(dialog).toBeVisible();
    expect(where()).toBe('/cards/OGN/79?domain=Fury');
    await userEvent.click(screen.getByRole('button', { name: 'Cerrar' }));
    await waitFor(() => expect(where()).toBe('/cards?domain=Fury'), LONG);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('shows an empty state when no cards match', async () => {
    signedInApi();
    server.use(
      http.get(`${API}/cards`, () =>
        HttpResponse.json({
          success: true,
          data: { items: [] },
          meta: { ...cardList.meta, total: 0, pages: 0 },
        }),
      ),
    );
    await renderApp({ path: '/cards?q=nothing', width: 390 });
    expect(
      await screen.findByText('Ninguna carta coincide con los filtros', {}, LONG),
    ).toBeVisible();
  });

  it('shows an error state with retry', async () => {
    signedInApi();
    let failing = true;
    server.use(
      http.get(`${API}/cards`, () =>
        failing
          ? failure(500, { message: 'boom' })
          : HttpResponse.json({
              success: true,
              data: { items: cardList.items },
              meta: cardList.meta,
            }),
      ),
    );
    await renderApp({ path: '/cards', width: 390 });
    expect(await screen.findByRole('alert', {}, LONG)).toBeVisible();
    failing = false;
    await userEvent.click(screen.getByRole('button', { name: 'Reintentar' }));
    expect(await screen.findByRole('link', { name: /Ayla/ }, LONG)).toBeVisible();
  });

  it('is axe clean at 390 px', async () => {
    signedInApi();
    const { container } = await renderApp({ path: '/cards', width: 390 });
    await screen.findByRole('link', { name: /Ayla/ }, LONG);
    expect(await axe(container)).toHaveNoViolations();
  });

  it('is axe clean at 1024 px with the modal open', async () => {
    signedInApi();
    const { container } = await renderApp({ path: '/cards/OGN/79', width: 1024 });
    await screen.findByRole('dialog', undefined, LONG);
    expect(await axe(container)).toHaveNoViolations();
  });
});
