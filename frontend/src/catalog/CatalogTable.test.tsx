import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { describe, expect, it } from 'vitest';
import { API, signedInSession } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';

const LONG = { timeout: 10000 };

function signedInApi() {
  server.use(http.get(`${API}/auth/session`, () => signedInSession()));
}

describe('CatalogTable (F2-i S4)', () => {
  it('renders 13 columns at 1024 px inside a horizontal scroll wrapper', async () => {
    window.localStorage.setItem('rb_cards_view', 'table');
    signedInApi();
    await renderApp({ path: '/cards', width: 1024 });
    const table = await screen.findByRole('table', {}, LONG);
    const headers = screen.getAllByRole('columnheader');
    expect(headers).toHaveLength(13);
    expect(table.parentElement!.tagName).toBe('DIV');
  });

  it('renders 16 columns at 1280 px', async () => {
    window.localStorage.setItem('rb_cards_view', 'table');
    signedInApi();
    await renderApp({ path: '/cards', width: 1280 });
    await screen.findByRole('table', {}, LONG);
    expect(screen.getAllByRole('columnheader')).toHaveLength(16);
  });

  it('sets aria-sort on the active column and toggles direction', async () => {
    window.localStorage.setItem('rb_cards_view', 'table');
    signedInApi();
    await renderApp({ path: '/cards?sort=name', width: 1280 });
    const table = await screen.findByRole('table', {}, LONG);
    const nameHeader = await within(table).findByRole('columnheader', { name: /Nombre/ });
    expect(nameHeader).toHaveAttribute('aria-sort', 'ascending');
    await userEvent.click(within(table).getByRole('button', { name: /Nombre/ }));
    await waitFor(() => expect(nameHeader).toHaveAttribute('aria-sort', 'descending'));
  });

  it('starts price sort in descending order', async () => {
    window.localStorage.setItem('rb_cards_view', 'table');
    signedInApi();
    const { where } = await renderApp({ path: '/cards', width: 1280 });
    const table = await screen.findByRole('table', {}, LONG);
    await userEvent.click(within(table).getByRole('button', { name: /Precio/ }));
    await waitFor(() => expect(where()).toBe('/cards?sort=price&dir=desc'), LONG);
  });

  it('starts 7-day trend sort in descending order', async () => {
    window.localStorage.setItem('rb_cards_view', 'table');
    signedInApi();
    const { where } = await renderApp({ path: '/cards', width: 1280 });
    const table = await screen.findByRole('table', {}, LONG);
    await userEvent.click(within(table).getByRole('button', { name: /7 d/ }));
    await waitFor(() => expect(where()).toBe('/cards?sort=trend_7d&dir=desc'), LONG);
  });

  it('name links point to the detail route', async () => {
    window.localStorage.setItem('rb_cards_view', 'table');
    signedInApi();
    await renderApp({ path: '/cards', width: 1280 });
    const table = await screen.findByRole('table', {}, LONG);
    const link = await within(table).findByRole('link', { name: /Ayla/ });
    expect(link).toHaveAttribute('href', '/riftbound/app/cards/OGN/79');
  });

  it('falls back from stored table to list below 860 px', async () => {
    window.localStorage.setItem('rb_cards_view', 'table');
    signedInApi();
    await renderApp({ path: '/cards', width: 390 });
    expect(await screen.findByRole('list', { name: 'Resultados' }, LONG)).toBeVisible();
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });
});
