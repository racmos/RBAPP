import { useQuery } from '@tanstack/react-query';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { describe, expect, it, vi } from 'vitest';
import { request } from '@/api/client';
import { hasSignedInHint } from '@/auth/hint';
import { API, failure, signedInSession } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';

function PrefsProbe() {
  // Three independent calls fail together: the burst must navigate once.
  const keys = ['a', 'b', 'c'];
  keys.forEach((key) =>
    // eslint-disable-next-line react-hooks/rules-of-hooks -- fixed-length list
    useQuery({ queryKey: ['probe', key], queryFn: () => request('/me/prefs'), retry: false }),
  );
  return <p>Interfaz</p>;
}

// A page that fires three failing calls at once; the real Interface page fires one on a click.
const probeRoute = () => [{ path: '/probe', element: <PrefsProbe /> }];

describe('401 from an API call (FAUTH-7, R2)', () => {
  const expired = () => {
    server.use(
      http.get(`${API}/auth/session`, () => signedInSession()),
      http.get(`${API}/me/prefs`, () =>
        failure(401, {
          error: 'Unauthorized',
          message: 'Authentication is required',
          code: 'unauthenticated',
        }),
      ),
    );
  };

  it('clears the cache, goes anonymous, clears the hint and lands on /login?next=<absolute>', async () => {
    expired();
    server.use(
      http.patch(`${API}/me/prefs`, () =>
        failure(401, { error: 'Unauthorized', code: 'unauthenticated' }),
      ),
    );
    const app = await renderApp({ path: '/account/interface' });
    app.queryClient.setQueryData(['cached-per-user'], { secret: 'ada' });
    await userEvent.click(await screen.findByRole('radio', { name: 'Cian' }));
    expect(await screen.findByLabelText('Usuario')).toBeVisible();
    expect(app.where()).toBe('/login?next=%2Friftbound%2Fapp%2Faccount%2Finterface');
    expect(app.queryClient.getQueryData(['session'])).toEqual({
      authenticated: false,
      user: null,
      prefs: null,
    });
    expect(app.queryClient.getQueryData(['cached-per-user'])).toBeUndefined();
    expect(hasSignedInHint()).toBe(false);
  });

  it('navigates once for a burst of concurrent 401s', async () => {
    expired();
    const app = await renderApp({ path: '/probe', extraRoutes: probeRoute });
    const navigate = vi.spyOn(app.router, 'navigate');
    await waitFor(() => expect(app.where()).toContain('/login'));
    const toLogin = navigate.mock.calls.filter(([to]) => String(to).startsWith('/login'));
    expect(toLogin).toHaveLength(1);
  });

  it('can handle a later expiry again once the first navigation is done', async () => {
    expired();
    const app = await renderApp({ path: '/probe', extraRoutes: probeRoute });
    await waitFor(() => expect(app.where()).toContain('/login'));
    await app.router.navigate('/account/interface').catch(() => {});
    await waitFor(() => expect(app.where()).toContain('/login?next='));
  });
});
