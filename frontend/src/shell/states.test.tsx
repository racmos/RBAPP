import { useQuery } from '@tanstack/react-query';
import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { describe, expect, it } from 'vitest';
import { request } from '@/api/client';
import { ErrorState } from '@/components/ui/ErrorState';
import { API, failure, ok, signedInSession } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';

const signedIn = () => server.use(http.get(`${API}/auth/session`, () => signedInSession()));

function Thrower(): never {
  throw new Error('boom');
}

/** Reads `/me/prefs`; a failure is thrown to the route error boundary. */
function Crashing() {
  const { data } = useQuery({
    queryKey: ['probe'],
    queryFn: () => request<{ prefs: { lang: string | null } }>('/me/prefs'),
    retry: false,
    throwOnError: true,
  });
  return <p>Cargado {String(data?.prefs.lang)}</p>;
}

/** A query failure rendered in place with its own retry (SHELL-8 "Retry"). */
function Inline() {
  const { error, refetch, data } = useQuery({
    queryKey: ['inline'],
    queryFn: () => request<{ prefs: { lang: string | null } }>('/me/prefs'),
    retry: false,
  });
  if (error) return <ErrorState message="Falló la carga" onRetry={() => void refetch()} />;
  return <p>Recibido {String(data?.prefs.lang)}</p>;
}

describe('standard states (SHELL-8)', () => {
  it('shows the 404 view inside the shell, with a link home', async () => {
    signedIn();
    await renderApp({ path: '/does-not-exist', width: 1280 });
    await screen.findByRole('banner');
    const main = screen.getByRole('main');
    expect(
      within(main).getByRole('heading', { level: 1, name: 'Página no encontrada' }),
    ).toBeVisible();
    expect(within(main).getByRole('link', { name: 'Ir al inicio' })).toHaveAttribute(
      'href',
      '/riftbound/app',
    );
    expect(screen.getByRole('banner')).toBeVisible(); // still inside the shell
    expect(document.title).toBe('Página no encontrada · Rift Manager');
  });

  it('the link home works', async () => {
    signedIn();
    const app = await renderApp({ path: '/does-not-exist', width: 1280 });
    await userEvent.click(await screen.findByRole('link', { name: 'Ir al inicio' }));
    expect(await screen.findByRole('heading', { name: 'Hola, ada' })).toBeVisible();
    expect(app.where()).toBe('/');
  });

  it('a route that throws shows the error state while the topbar stays usable', async () => {
    signedIn();
    const app = await renderApp({
      path: '/crash',
      width: 1280,
      shellRoutes: () => [{ path: '/crash', Component: Thrower }],
    });
    await screen.findByRole('banner');
    const main = screen.getByRole('main');
    expect(within(main).getByRole('alert')).toHaveTextContent('No se pudo mostrar esta pantalla.');
    const banner = screen.getByRole('banner');
    await userEvent.click(within(banner).getByRole('link', { name: 'Inicio' }));
    expect(await screen.findByRole('heading', { name: 'Hola, ada' })).toBeVisible();
    expect(app.where()).toBe('/');
  });

  it('the error state of a throwing route refetches the failed query on retry', async () => {
    signedIn();
    let calls = 0;
    server.use(
      http.get(`${API}/me/prefs`, () => {
        calls += 1;
        return calls === 1 ? failure(500) : ok({ prefs: { lang: 'es' } });
      }),
    );
    await renderApp({
      path: '/crash',
      width: 1280,
      shellRoutes: () => [{ path: '/crash', Component: Crashing }],
    });
    const retry = await screen.findByRole('button', { name: 'Reintentar' });
    expect(calls).toBe(1);
    await userEvent.click(retry);
    expect(await screen.findByText('Cargado es')).toBeVisible();
    expect(calls).toBe(2);
  });

  it('an ErrorState with a retry action refetches the failed query', async () => {
    signedIn();
    let calls = 0;
    server.use(
      http.get(`${API}/me/prefs`, () => {
        calls += 1;
        return calls === 1 ? failure(500) : ok({ prefs: { lang: 'en' } });
      }),
    );
    await renderApp({
      path: '/inline',
      width: 1280,
      shellRoutes: () => [{ path: '/inline', Component: Inline }],
    });
    await userEvent.click(await screen.findByRole('button', { name: 'Reintentar' }));
    expect(await screen.findByText('Recibido en')).toBeVisible();
    expect(calls).toBe(2);
  });

  it('a stale-deploy chunk error offers Recargar inside the shell', async () => {
    signedIn();
    await renderApp({
      path: '/chunk',
      width: 1280,
      shellRoutes: () => [
        {
          path: '/chunk',
          Component: () => {
            throw new TypeError('Failed to fetch dynamically imported module: /assets/x.js');
          },
        },
      ],
    });
    expect(await screen.findByText(/versión nueva de la aplicación/)).toBeVisible();
    expect(screen.getByRole('button', { name: 'Recargar' })).toBeVisible();
  });
});
