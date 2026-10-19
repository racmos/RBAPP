import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter } from 'react-router';
import { RouterProvider } from 'react-router/dom';
import { I18nextProvider } from 'react-i18next';
import { render } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { createI18n } from '@/i18n';
import { RouteError } from './RouteError';

async function renderBroken(thrown: unknown, reload = vi.fn()) {
  const i18n = await createI18n('es');
  const router = createMemoryRouter([
    {
      path: '/',
      errorElement: <RouteError reload={reload} />,
      loader: () => {
        throw thrown;
      },
      element: null,
    },
  ]);
  render(
    <I18nextProvider i18n={i18n}>
      <RouterProvider router={router} />
    </I18nextProvider>,
  );
  return reload;
}

describe('RouteError (D24)', () => {
  it('offers "Recargar" for a dynamic import failure', async () => {
    const reload = await renderBroken(
      new TypeError('Failed to fetch dynamically imported module: /a.js'),
    );
    expect(await screen.findByText(/versión nueva de la aplicación/)).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: 'Recargar' }));
    expect(reload).toHaveBeenCalledTimes(1);
  });

  it('shows a generic message with a reload for any other error', async () => {
    await renderBroken(new Error('boom'));
    expect(await screen.findByRole('heading', { name: 'Algo ha salido mal' })).toBeVisible();
    expect(screen.getByRole('button', { name: 'Recargar' })).toBeVisible();
    expect(screen.queryByText(/boom/)).not.toBeInTheDocument();
  });

  it('shows the not-found view for a 404 response', async () => {
    await renderBroken(new Response(null, { status: 404, statusText: 'Not Found' }));
    expect(await screen.findByRole('heading', { name: 'Página no encontrada' })).toBeVisible();
  });
});
