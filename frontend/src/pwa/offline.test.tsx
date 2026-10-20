import { act, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { onlineManager } from '@tanstack/react-query';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { setSignedInHint } from '@/auth';
import { API, failure, signedInSession } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';

const networkError = () => server.use(http.get(`${API}/auth/session`, () => HttpResponse.error()));
const signedIn = () => server.use(http.get(`${API}/auth/session`, () => signedInSession()));

/** What the browser reports; `fire` also dispatches the event the page listens to. */
function setOnline(online: boolean, fire = false) {
  vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(online);
  if (fire) act(() => void window.dispatchEvent(new Event(online ? 'online' : 'offline')));
}

const BANNER = /Sin conexión/;
/** The offline banner: the status region that says it, not the live announcer. */
const banner = () =>
  screen.queryAllByRole('status').find((element) => BANNER.test(element.textContent ?? '')) ?? null;
const findBanner = () => waitFor(() => expect(banner()).toBeVisible());

afterEach(() => {
  vi.restoreAllMocks();
  onlineManager.setOnline(true); // the query client's own idea of the connection is global
});

describe('boot with the session request failing (PWA-7, FAUTH-1)', () => {
  it('renders the shell and the offline banner when the browser was signed in', async () => {
    setSignedInHint();
    setOnline(false);
    networkError();
    const app = await renderApp({ path: '/', width: 1280 });
    expect(await screen.findByRole('banner')).toBeVisible(); // the shell's topbar
    expect(screen.getByRole('main')).toBeVisible();
    expect(banner()).toBeVisible();
    expect(app.where()).toBe('/');
  });

  it('also does it when the network is up but the server cannot be reached', async () => {
    setSignedInHint();
    networkError();
    await renderApp({ path: '/', width: 390 });
    // one retry first (the browser says it is online), so this takes a second
    expect(await screen.findByRole('banner', {}, { timeout: 4000 })).toBeVisible();
    expect(banner()).toBeVisible();
  });

  it('says it in English', async () => {
    setSignedInHint();
    setOnline(false);
    networkError();
    await renderApp({ path: '/', lang: 'en' });
    expect(await screen.findByText(/You are offline/)).toBeVisible();
  });

  it('shows an ErrorState with a retry action when there is no hint', async () => {
    setOnline(false);
    networkError();
    await renderApp({ path: '/', width: 1280 });
    const alert = await screen.findByRole('alert');
    expect(within(alert).getByRole('button', { name: 'Reintentar' })).toBeVisible();
    expect(screen.queryByRole('banner')).not.toBeInTheDocument(); // no shell
  });

  it('retry boots the app once the server answers', async () => {
    setOnline(false);
    networkError();
    await renderApp({ path: '/', width: 1280 });
    const retry = await screen.findByRole('button', { name: 'Reintentar' });
    setOnline(true);
    signedIn();
    await userEvent.click(retry);
    expect(await screen.findByRole('banner')).toBeVisible();
    expect(banner()).not.toBeInTheDocument();
  });

  it('a 401 goes to login, even with the hint', async () => {
    setSignedInHint();
    server.use(
      http.get(`${API}/auth/session`, () =>
        failure(401, { error: 'Unauthorized', message: 'Authentication required' }),
      ),
    );
    const app = await renderApp({ path: '/', width: 1280 });
    expect(await screen.findByLabelText('Usuario')).toBeVisible();
    expect(app.where()).toMatch(/^\/login/);
    expect(banner()).not.toBeInTheDocument();
  });
});

describe('the offline banner (PWA-7)', () => {
  it('is not there while online', async () => {
    signedIn();
    await renderApp({ path: '/', width: 1280 });
    await screen.findByRole('banner');
    expect(banner()).not.toBeInTheDocument();
  });

  it('appears when the browser goes offline and disappears when it is back', async () => {
    signedIn();
    await renderApp({ path: '/', width: 1280 });
    await screen.findByRole('banner');

    setOnline(false, true);
    expect(banner()).toBeVisible();
    expect(banner()).toHaveAttribute('role', 'status');

    setOnline(true, true);
    expect(banner()).not.toBeInTheDocument();
  });

  it('after an offline boot, going online asks the server again and drops the banner', async () => {
    setSignedInHint();
    setOnline(false);
    networkError();
    await renderApp({ path: '/', width: 1280 });
    await findBanner();

    signedIn();
    setOnline(true, true);
    await waitFor(() => expect(banner()).not.toBeInTheDocument());
    expect(await screen.findByText('Hola, ada')).toBeVisible(); // the real session arrived
  });

  it('after an offline boot, going online with an expired session goes to login', async () => {
    setSignedInHint();
    setOnline(false);
    networkError();
    const app = await renderApp({ path: '/', width: 1280 });
    await findBanner();

    server.use(
      http.get(`${API}/auth/session`, () =>
        HttpResponse.json({
          success: true,
          data: { authenticated: false, csrf_token: 't' },
        }),
      ),
    );
    setOnline(true, true);
    expect(await screen.findByLabelText('Usuario')).toBeVisible();
    expect(app.where()).toMatch(/^\/login/);
  });
});

describe('read-only while offline (PWA-7)', () => {
  it('disables the Interface controls and logout, and sends no PATCH', async () => {
    const patch = vi.fn();
    server.use(
      http.patch(`${API}/me/prefs`, () => {
        patch();
        return HttpResponse.json({ success: true, data: {} });
      }),
    );
    signedIn();
    await renderApp({ path: '/account/interface', width: 1280 });
    const density = await screen.findByRole('radiogroup', { name: /Densidad/ });
    expect(within(density).getByRole('radio', { name: 'Compacta' })).toBeEnabled();

    setOnline(false, true);

    for (const radio of screen.getAllByRole('radio')) {
      if (radio.closest('[role="radiogroup"]')?.getAttribute('aria-label') === 'Idioma') continue;
      expect(radio).toBeDisabled();
    }
    expect(screen.getByRole('slider')).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Cerrar sesión' })).toBeDisabled();

    await userEvent.click(within(density).getByRole('radio', { name: 'Compacta' }));
    expect(patch).not.toHaveBeenCalled();

    setOnline(true, true);
    expect(within(density).getByRole('radio', { name: 'Compacta' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Cerrar sesión' })).toBeEnabled();
  });

  it('shows no controls that look usable after an offline boot', async () => {
    setSignedInHint();
    setOnline(false);
    networkError();
    await renderApp({ path: '/account/interface', width: 1280 });
    await findBanner();
    expect(screen.getByRole('button', { name: 'Cerrar sesión' })).toBeDisabled();
    for (const radio of screen.getAllByRole('radio')) {
      if (radio.closest('[role="radiogroup"]')?.getAttribute('aria-label') === 'Idioma') continue;
      expect(radio).toBeDisabled();
    }
  });
});
