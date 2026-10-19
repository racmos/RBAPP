import { useQuery } from '@tanstack/react-query';
import { screen, waitFor } from '@testing-library/react';
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

const interfaceRoute = () => [{ path: '/account/interface', element: <PrefsProbe /> }];

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
    const app = await renderApp({ path: '/account/interface', extraRoutes: interfaceRoute });
    expect(await screen.findByLabelText('Usuario')).toBeVisible();
    expect(app.where()).toBe('/login?next=%2Friftbound%2Fapp%2Faccount%2Finterface');
    expect(app.queryClient.getQueryData(['session'])).toEqual({
      authenticated: false,
      user: null,
      prefs: null,
    });
    expect(app.queryClient.getQueryCache().find({ queryKey: ['probe', 'a'] })).toBeUndefined();
    expect(hasSignedInHint()).toBe(false);
  });

  it('navigates once for a burst of concurrent 401s', async () => {
    expired();
    const app = await renderApp({ path: '/account/interface', extraRoutes: interfaceRoute });
    const navigate = vi.spyOn(app.router, 'navigate');
    await waitFor(() => expect(app.where()).toContain('/login'));
    const toLogin = navigate.mock.calls.filter(([to]) => String(to).startsWith('/login'));
    expect(toLogin).toHaveLength(1);
  });

  it('can handle a later expiry again once the first navigation is done', async () => {
    expired();
    const app = await renderApp({ path: '/account/interface', extraRoutes: interfaceRoute });
    await waitFor(() => expect(app.where()).toContain('/login'));
    await app.router.navigate('/account/interface').catch(() => {});
    await waitFor(() => expect(app.where()).toContain('/login?next='));
  });
});
