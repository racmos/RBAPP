import { screen, waitFor } from '@testing-library/react';
import { QueryClient } from '@tanstack/react-query';
import { http } from 'msw';
import { describe, expect, it } from 'vitest';
import { API, anonymousSession, signedInSession } from '@/test/msw/handlers';
import { renderApp } from '@/test/renderApp';
import { server } from '@/test/msw/server';
import { requireAnon } from './guards';

const signedIn = () => server.use(http.get(`${API}/auth/session`, () => signedInSession()));
describe('requireAuth (FAUTH-1, FAUTH-8)', () => {
  it('shows a loading state first, then home, and never renders the login form', async () => {
    signedIn();
    const sawLogin: string[] = [];
    const observer = new MutationObserver(() => {
      if (document.body.textContent?.includes('Iniciar sesión')) sawLogin.push('login form');
    });
    observer.observe(document.body, { childList: true, subtree: true, characterData: true });

    const app = await renderApp({ path: '/' });
    expect(screen.getByText('Cargando contenido')).toBeInTheDocument();
    expect(await screen.findByText('Hola, ada')).toBeVisible();

    observer.disconnect();
    expect(sawLogin).toEqual([]);
    expect(app.where()).toBe('/');
    expect(screen.queryByLabelText('Usuario')).not.toBeInTheDocument();
  });

  it('sends an anonymous visitor of a guarded route to /login with an absolute next', async () => {
    const app = await renderApp({ path: '/cards?page=2' });
    await waitFor(() =>
      expect(app.where()).toBe('/login?next=' + encodeURIComponent('/riftbound/app/cards?page=2')),
    );
    expect(await screen.findByLabelText('Usuario')).toBeVisible();
  });

  it('sends an anonymous visitor of home to /login with next=home', async () => {
    const app = await renderApp({ path: '/' });
    await waitFor(() =>
      expect(app.where()).toBe('/login?next=' + encodeURIComponent('/riftbound/app/')),
    );
  });
});

describe('requireAnon (FAUTH-8)', () => {
  it('redirects a signed-in user from /login to home', async () => {
    signedIn();
    const app = await renderApp({ path: '/login' });
    expect(await screen.findByText('Hola, ada')).toBeVisible();
    expect(app.where()).toBe('/');
  });

  it('honours a safe next', async () => {
    signedIn();
    const app = await renderApp({
      path: '/register?next=' + encodeURIComponent('/riftbound/app/cards'),
    });
    await waitFor(() => expect(app.where()).toBe('/cards'));
  });

  it('ignores an unsafe next', async () => {
    signedIn();
    const app = await renderApp({
      path: '/login?next=' + encodeURIComponent('https://evil.example/'),
    });
    await waitFor(() => expect(app.where()).toBe('/'));
  });

  it('lets an anonymous user see the login form', async () => {
    server.use(http.get(`${API}/auth/session`, () => anonymousSession()));
    await renderApp({ path: '/login' });
    expect(await screen.findByLabelText('Usuario')).toBeVisible();
  });

  it('answers a legacy next with a document redirect', async () => {
    signedIn();
    const queryClient = new QueryClient();
    const url =
      'http://localhost/riftbound/app/login?next=' + encodeURIComponent('/riftbound/collection');
    const thrown = await requireAnon(queryClient)({ request: new Request(url) } as never).catch(
      (response: Response) => response,
    );
    expect(thrown).toBeInstanceOf(Response);
    expect((thrown as Response).headers.get('Location')).toBe('/riftbound/collection');
    expect((thrown as Response).headers.get('X-Remix-Reload-Document')).toBe('true');
  });
});
