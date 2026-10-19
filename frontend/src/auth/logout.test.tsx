import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { describe, expect, it } from 'vitest';
import { hasSignedInHint } from './hint';
import { API, anonymousSession, failure, ok, signedInSession } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';

const signedInUntilLogout = (logout: () => Response | Promise<Response>) => {
  let signedIn = true;
  const calls: string[] = [];
  server.use(
    http.get(`${API}/auth/session`, () => (signedIn ? signedInSession() : anonymousSession())),
    http.post(`${API}/auth/logout`, async ({ request }) => {
      calls.push(request.headers.get('x-csrftoken') ?? '');
      const response = await logout();
      if (response.ok || response.status === 401) signedIn = false;
      return response;
    }),
  );
  return calls;
};

async function openHomeAndLogOut(lang: 'es' | 'en' = 'es') {
  const app = await renderApp({ path: '/', lang });
  await screen.findByText(lang === 'es' ? 'Hola, ada' : 'Hello, ada');
  app.queryClient.setQueryData(['cached-per-user'], { secret: 'ada' });
  await userEvent.click(
    screen.getByRole('button', { name: lang === 'es' ? 'Cerrar sesión' : 'Sign out' }),
  );
  return app;
}

describe('logout (FAUTH-5)', () => {
  it('clears the cache and the hint, goes anonymous and lands on /login after a 200', async () => {
    const calls = signedInUntilLogout(() => ok({}));
    const app = await openHomeAndLogOut();
    expect(await screen.findByLabelText('Usuario')).toBeVisible();
    expect(app.where()).toBe('/login');
    expect(calls).toEqual(['token-user']); // sent with the CSRF token
    expect(app.queryClient.getQueryData(['cached-per-user'])).toBeUndefined();
    expect(app.queryClient.getQueryData(['session'])).toEqual({
      authenticated: false,
      user: null,
      prefs: null,
    });
    expect(hasSignedInHint()).toBe(false);
  });

  it('treats a 401 (already signed out) exactly like a 200', async () => {
    signedInUntilLogout(() => failure(401, { error: 'Unauthorized', code: 'unauthenticated' }));
    const app = await openHomeAndLogOut();
    expect(await screen.findByLabelText('Usuario')).toBeVisible();
    expect(app.where()).toBe('/login');
    expect(app.queryClient.getQueryData(['cached-per-user'])).toBeUndefined();
    expect(hasSignedInHint()).toBe(false);
  });

  it('writes the current language to rb_lang so the login screen does not flip', async () => {
    signedInUntilLogout(() => ok({}));
    await openHomeAndLogOut('en');
    expect(await screen.findByLabelText('Username')).toBeVisible();
    expect(localStorage.getItem('rb_lang')).toBe('en');
  });

  it('stays in the shell with an error toast after a 500', async () => {
    signedInUntilLogout(() =>
      failure(500, { error: 'Internal Server Error', message: 'An unexpected error occurred' }),
    );
    const app = await openHomeAndLogOut();
    const toasts = await screen.findByRole('region', { name: 'Notificaciones' });
    expect(toasts).toHaveTextContent('An unexpected error occurred');
    expect(app.where()).toBe('/');
    expect(screen.getByText('Hola, ada')).toBeVisible();
    expect(hasSignedInHint()).toBe(true);
    expect(app.queryClient.getQueryData(['cached-per-user'])).toEqual({ secret: 'ada' });
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Cerrar sesión' })).toBeEnabled(),
    );
  });

  it('shows the translated message for a network failure', async () => {
    signedInUntilLogout(() => Response.error());
    await openHomeAndLogOut();
    expect(await screen.findByRole('region', { name: 'Notificaciones' })).toHaveTextContent(
      'No hay conexión con el servidor',
    );
  });
});
