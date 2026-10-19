import { QueryClient } from '@tanstack/react-query';
import { screen, waitFor } from '@testing-library/react';
import { http } from 'msw';
import { describe, expect, it } from 'vitest';
import { requireAdmin } from '@/auth/guards';
import { API, NO_PREFS, USER, ok, signedInSession } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';
import { RouteError } from './RouteError';

const signedIn = () => server.use(http.get(`${API}/auth/session`, () => signedInSession()));
const asAdmin = () =>
  server.use(
    http.get(`${API}/auth/session`, () =>
      ok({
        authenticated: true,
        csrf_token: 't',
        user: { ...USER, is_admin: true },
        prefs: NO_PREFS,
      }),
    ),
  );

const adminRoute = (queryClient: QueryClient) => [
  {
    path: '/admin-test',
    loader: requireAdmin(queryClient),
    element: <p>Panel de administración</p>,
    errorElement: <RouteError />,
  },
];

describe('requireAdmin (FAUTH-8, R10)', () => {
  it('renders the 404 view for a signed-in non-admin', async () => {
    signedIn();
    await renderApp({ path: '/admin-test', extraRoutes: adminRoute });
    expect(await screen.findByRole('heading', { name: 'Página no encontrada' })).toBeVisible();
    expect(screen.queryByText('Panel de administración')).not.toBeInTheDocument();
  });

  it('renders the page for an admin', async () => {
    asAdmin();
    await renderApp({ path: '/admin-test', extraRoutes: adminRoute });
    expect(await screen.findByText('Panel de administración')).toBeVisible();
  });

  it('still sends an anonymous visitor to /login', async () => {
    const app = await renderApp({ path: '/admin-test', extraRoutes: adminRoute });
    await waitFor(() => expect(app.where()).toContain('/login?next='));
  });
});
