import { act, fireEvent, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';
import { axe } from 'vitest-axe';
import { API, signedInSession } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { cardList } from '@/test/fixtures/cards';
import { renderApp } from '@/test/renderApp';

const LONG = { timeout: 10000 };

function signedInApi() {
  server.use(http.get(`${API}/auth/session`, () => signedInSession()));
}

describe('CatalogPage desktop (F2-i S2, S3)', () => {
  it('shows the two-column layout at 1280 px and hides the sheet filter button', async () => {
    signedInApi();
    const { container } = await renderApp({ path: '/cards', width: 1280 });
    await screen.findByRole('link', { name: /Ayla/ }, LONG);
    expect(container.querySelector('[data-testid="catalog-sidebar"]')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Filtros' })).not.toBeInTheDocument();
    expect(screen.getByTestId('catalog-sidebar')).toHaveTextContent('Set');
  });

  it('shows the count in the toolbar and the page-size selector', async () => {
    signedInApi();
    await renderApp({ path: '/cards', width: 1280 });
    await screen.findByRole('link', { name: /Ayla/ }, LONG);
    expect(
      screen.getAllByText('6 cartas').some((el) => el.closest('form, [class*="toolbar"]')),
    ).toBe(true);
    expect(screen.getByLabelText('Por página')).toHaveValue('48');
  });

  it('changes per_page to 96 and resets the page to 1', async () => {
    signedInApi();
    const { where } = await renderApp({ path: '/cards?page=2', width: 1280 });
    await screen.findByRole('link', { name: /Ayla/ }, LONG);
    await userEvent.selectOptions(await screen.findByLabelText('Por página'), '96');
    await waitFor(() => expect(where()).toBe('/cards?per_page=96'), LONG);
  });

  it('keeps a change that the page has not rendered yet (L6)', async () => {
    signedInApi();
    const { where } = await renderApp({ path: '/cards', width: 1280 });
    await screen.findByRole('link', { name: /Ayla/ }, LONG);
    const perPage = screen.getByLabelText('Por página');
    const dir = screen.getByRole('button', { name: 'Orden descendente' });
    // the router applies a navigation in a transition: the second change comes before the render
    act(() => {
      fireEvent.change(perPage, { target: { value: '96' } });
      fireEvent.click(dir);
    });
    await waitFor(() => expect(where()).toBe('/cards?dir=desc&per_page=96'), LONG);
  }, 20000);

  it('switches to table view and persists it in localStorage', async () => {
    signedInApi();
    await renderApp({ path: '/cards', width: 1280 });
    await screen.findByRole('link', { name: /Ayla/ }, LONG);
    await userEvent.click(screen.getByRole('radio', { name: 'Tabla' }));
    expect(await screen.findByRole('table', {}, LONG)).toBeVisible();
    expect(window.localStorage.getItem('rb_cards_view')).toBe('table');
  });

  it('is axe clean at 1280 px in grid view', async () => {
    signedInApi();
    const { container } = await renderApp({ path: '/cards', width: 1280 });
    await screen.findByRole('link', { name: /Ayla/ }, LONG);
    expect(await axe(container)).toHaveNoViolations();
  });

  it('shows the preview empty state when there are no results at 1680 px', async () => {
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
    await renderApp({ path: '/cards', width: 1680 });
    expect(
      await screen.findByText('Selecciona una carta para verla aquí.', {}, LONG),
    ).toBeVisible();
  });

  it('dims the sidebar counts only after 300 ms in flight', async () => {
    signedInApi();
    server.use(
      http.get(`${API}/cards`, async () => {
        await new Promise((resolve) => setTimeout(resolve, 800));
        return HttpResponse.json({
          success: true,
          data: { items: cardList.items },
          meta: cardList.meta,
        });
      }),
    );
    await renderApp({ path: '/cards', width: 1280 });
    await screen.findByRole('link', { name: /Ayla/ }, LONG);
    const sidebar = screen.getByTestId('catalog-sidebar');
    await userEvent.selectOptions(screen.getByLabelText('Ordenar por'), 'price');
    expect(sidebar).not.toHaveAttribute('aria-busy');
    await waitFor(() => expect(sidebar).toHaveAttribute('aria-busy', 'true'), LONG);
  });

  it('is axe clean at 1280 px in table view', async () => {
    window.localStorage.setItem('rb_cards_view', 'table');
    signedInApi();
    const { container } = await renderApp({ path: '/cards', width: 1280 });
    await screen.findByRole('table', {}, LONG);
    expect(await axe(container)).toHaveNoViolations();
  });
});
