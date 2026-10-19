import { screen } from '@testing-library/react';
import { http } from 'msw';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { API, signedInSession } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { startApp } from './bootstrap';

let host: HTMLDivElement;
let stop: () => void;
const browserLanguages = (...languages: string[]) =>
  Object.defineProperty(navigator, 'languages', { value: languages, configurable: true });

beforeEach(() => {
  host = document.createElement('div');
  document.body.append(host);
  browserLanguages('es-ES', 'es'); // jsdom defaults to en-US
});
afterEach(() => {
  stop?.();
  host.remove();
  browserLanguages('en-US', 'en');
  window.history.replaceState({}, '', '/');
  document.documentElement.removeAttribute('data-bg');
  document.documentElement.removeAttribute('lang');
});

describe('startApp (task 4.36)', () => {
  it('renders the login screen for an anonymous visitor of the SPA', async () => {
    window.history.replaceState({}, '', '/riftbound/app/login');
    stop = await startApp(host);
    expect(await screen.findByLabelText('Usuario')).toBeVisible();
    expect(document.documentElement.lang).toBe('es');
  });

  it('starts in the language stored in rb_lang', async () => {
    localStorage.setItem('rb_lang', 'en');
    window.history.replaceState({}, '', '/riftbound/app/login');
    stop = await startApp(host);
    expect(await screen.findByLabelText('Username')).toBeVisible();
    expect(document.documentElement.lang).toBe('en');
  });

  it('falls back to the browser language when rb_lang is unset', async () => {
    browserLanguages('fr-FR', 'en-US');
    window.history.replaceState({}, '', '/riftbound/app/login');
    stop = await startApp(host);
    expect(await screen.findByLabelText('Username')).toBeVisible();
  });

  it('sends a signed-in visitor to home under the router basename', async () => {
    server.use(http.get(`${API}/auth/session`, () => signedInSession()));
    window.history.replaceState({}, '', '/riftbound/app/login');
    stop = await startApp(host);
    expect(await screen.findByText('Hola, ada')).toBeVisible();
    expect(window.location.pathname).toMatch(/^\/riftbound\/app\/?$/);
  });

  it('shows the background layer by default (the auth screens sit on it)', async () => {
    window.history.replaceState({}, '', '/riftbound/app/login');
    stop = await startApp(host);
    await screen.findByLabelText('Usuario');
    expect(document.documentElement.dataset.bg).toBe('on');
  });

  it('reloads once when a lazy chunk fails to preload', async () => {
    window.history.replaceState({}, '', '/riftbound/app/login');
    let reloads = 0;
    stop = await startApp(host, { reload: () => (reloads += 1) });
    await screen.findByLabelText('Usuario');
    const event = new Event('vite:preloadError', { cancelable: true });
    window.dispatchEvent(event);
    window.dispatchEvent(new Event('vite:preloadError', { cancelable: true }));
    expect(reloads).toBe(1);
  });
});
