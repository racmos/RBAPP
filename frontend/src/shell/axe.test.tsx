import { act, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { onlineManager } from '@tanstack/react-query';
import { HttpResponse, http } from 'msw';
import { axe } from 'vitest-axe';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { setSignedInHint } from '@/auth';
import { API, adminSession, signedInSession } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';

/** SHELL-9: the structure of the shell has no axe violations in either layout. */
describe('shell accessibility (SHELL-9)', () => {
  it('has no violations at 1280 px (topbar navigation)', async () => {
    server.use(http.get(`${API}/auth/session`, () => signedInSession()));
    await renderApp({ path: '/', width: 1280 });
    await screen.findByRole('banner');
    expect(await axe(document.body)).toHaveNoViolations();
  });

  it('has no violations at 390 px (bottom navigation)', async () => {
    server.use(http.get(`${API}/auth/session`, () => signedInSession()));
    await renderApp({ path: '/', width: 390 });
    await screen.findByRole('banner');
    expect(await axe(document.body)).toHaveNoViolations();
  });

  it('has no violations with the "Más" sheet open (member)', async () => {
    server.use(http.get(`${API}/auth/session`, () => signedInSession()));
    await renderApp({ path: '/', width: 390 });
    await userEvent.click(await screen.findByRole('button', { name: 'Más' }));
    expect(screen.getByRole('dialog', { name: 'Más opciones' })).toBeVisible();
    expect(await axe(document.body)).toHaveNoViolations();
  });

  it('has no violations with the "Más" sheet open (admin)', async () => {
    server.use(http.get(`${API}/auth/session`, () => adminSession()));
    await renderApp({ path: '/', width: 390 });
    await userEvent.click(await screen.findByRole('button', { name: 'Más' }));
    expect(screen.getByRole('link', { name: 'Administración' })).toBeVisible();
    expect(await axe(document.body)).toHaveNoViolations();
  });

  it('has no violations on the 404 view and in English', async () => {
    server.use(http.get(`${API}/auth/session`, () => signedInSession()));
    await renderApp({ path: '/nope', width: 1280, lang: 'en' });
    await screen.findByRole('heading', { name: 'Page not found' });
    expect(await axe(document.body)).toHaveNoViolations();
  });
});

function Thrower(): never {
  throw new Error('boom');
}

/** F1 unit g S4: the error states and the offline banner, rendered through the real routes. */
describe('error states and offline banner accessibility (F1 unit g)', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    onlineManager.setOnline(true);
  });

  it('has no violations on the route error state (RouteError)', async () => {
    server.use(http.get(`${API}/auth/session`, () => signedInSession()));
    await renderApp({
      path: '/boom',
      width: 1280,
      extraRoutes: () => [{ path: '/boom', Component: Thrower }],
    });
    await screen.findByRole('heading', { name: 'Algo ha salido mal' });
    expect(await axe(document.body)).toHaveNoViolations();
  });

  it('has no violations on the error state inside the shell (ShellError)', async () => {
    server.use(http.get(`${API}/auth/session`, () => signedInSession()));
    await renderApp({
      path: '/crash',
      width: 390,
      shellRoutes: () => [{ path: '/crash', Component: Thrower }],
    });
    await screen.findByRole('banner');
    expect(within(screen.getByRole('main')).getByRole('alert')).toBeVisible();
    expect(await axe(document.body)).toHaveNoViolations();
  });

  it('has no violations with the offline banner (going offline in the shell)', async () => {
    server.use(http.get(`${API}/auth/session`, () => signedInSession()));
    await renderApp({ path: '/', width: 1280 });
    await screen.findByRole('banner');
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    act(() => void window.dispatchEvent(new Event('offline')));
    await waitFor(() => expect(screen.getAllByText(/Sin conexión/).length).toBeGreaterThan(0));
    expect(await axe(document.body)).toHaveNoViolations();
  });

  it('has no violations after an offline boot (banner and read-only shell)', async () => {
    setSignedInHint();
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    server.use(http.get(`${API}/auth/session`, () => HttpResponse.error()));
    await renderApp({ path: '/account/interface', width: 390 });
    await screen.findByRole('banner');
    await waitFor(() => expect(screen.getAllByText(/Sin conexión/).length).toBeGreaterThan(0));
    expect(await axe(document.body)).toHaveNoViolations();
  });
});
