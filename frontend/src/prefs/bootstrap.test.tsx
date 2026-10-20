import { act, screen, waitFor } from '@testing-library/react';
import { http } from 'msw';
import { afterEach, describe, expect, it } from 'vitest';
import { setSignedInHint } from '@/auth';
import { API, NO_PREFS, USER, ok } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';
import { setViewport } from '@/test/viewport';
import { bootstrapPrefs } from './bootstrap';
import { MIRROR_KEY } from './storage';

const html = document.documentElement;
const browserLanguages = (...languages: string[]) =>
  Object.defineProperty(navigator, 'languages', { value: languages, configurable: true });

afterEach(() => browserLanguages('en-US', 'en'));

const signedInWith = (prefs: Record<string, unknown>) =>
  server.use(
    http.get(`${API}/auth/session`, () =>
      ok({
        authenticated: true,
        csrf_token: 'token-user',
        user: USER,
        prefs: { ...NO_PREFS, ...prefs },
      }),
    ),
  );

describe('bootstrapPrefs (PREF-6, PREF-7, D18)', () => {
  it('applies the mirror to <html> without any session', () => {
    localStorage.setItem(MIRROR_KEY, JSON.stringify({ accent: 'cyan' }));
    bootstrapPrefs();
    expect(html.dataset.accent).toBe('cyan');
    expect(html.dataset.bg).toBe('on');
  });

  it('Auto density is compact at 390 px', () => {
    setViewport(390);
    bootstrapPrefs();
    expect(html.dataset.density).toBe('compact');
  });

  it('Auto density is absent and the accent orange at 1280 px', () => {
    setViewport(1280);
    bootstrapPrefs();
    expect(html.hasAttribute('data-density')).toBe(false);
    expect(html.dataset.accent).toBe('orange');
  });

  it('an explicit density wins at 390 px', () => {
    setViewport(390);
    localStorage.setItem(MIRROR_KEY, JSON.stringify({ density: 'comfy' }));
    bootstrapPrefs();
    expect(html.dataset.density).toBe('comfy');
  });

  it('ignores a corrupt mirror and falls back to the defaults', () => {
    localStorage.setItem(MIRROR_KEY, '{not json');
    expect(() => bootstrapPrefs()).not.toThrow();
    expect(html.dataset.accent).toBe('orange');
    expect(html.dataset.bg).toBe('on');
  });

  it('applies the background intensity of the mirror', () => {
    localStorage.setItem(MIRROR_KEY, JSON.stringify({ bg_intensity: 0 }));
    bootstrapPrefs();
    expect(html.dataset.bg).toBe('off');
  });

  it('uses the mirror language only for a browser that was signed in', () => {
    browserLanguages('es-ES');
    localStorage.setItem(MIRROR_KEY, JSON.stringify({ lang: 'en' }));
    expect(bootstrapPrefs().lang).toBe('es');
    setSignedInHint();
    expect(bootstrapPrefs().lang).toBe('en');
  });

  it('prefers the device language rb_lang when there is no account language', () => {
    localStorage.setItem('rb_lang', 'en');
    browserLanguages('es-ES');
    expect(bootstrapPrefs().lang).toBe('en');
  });
});

describe('PrefsProvider (PREF-6, PREF-7, R4)', () => {
  it('the server prefs replace the mirror, the DOM and the language', async () => {
    localStorage.setItem(MIRROR_KEY, JSON.stringify({ accent: 'cyan' }));
    bootstrapPrefs();
    expect(html.dataset.accent).toBe('cyan');
    signedInWith({ accent: 'orange', lang: 'en', density: 'comfy', bg_intensity: 30 });
    await renderApp({ path: '/', lang: 'es' });
    await screen.findByText('Hello, ada');
    expect(html.dataset.accent).toBe('orange');
    expect(html.dataset.density).toBe('comfy');
    expect(html.lang).toBe('en');
    expect(html.style.getPropertyValue('--bg-image-opacity')).toBe('0.3');
    expect(JSON.parse(localStorage.getItem(MIRROR_KEY)!)).toEqual({
      lang: 'en',
      density: 'comfy',
      accent: 'orange',
      bg_intensity: 30,
      collection_view: null,
    });
  });

  it('a stored Auto stays Auto in the mirror', async () => {
    signedInWith({});
    await renderApp({ path: '/' });
    await screen.findByText('Hola, ada');
    expect(JSON.parse(localStorage.getItem(MIRROR_KEY)!)).toEqual(NO_PREFS);
  });

  it('Auto values re-resolve when the viewport crosses 860 px', async () => {
    signedInWith({});
    await renderApp({ path: '/', width: 1280 });
    await screen.findByText('Hola, ada');
    expect(html.hasAttribute('data-density')).toBe(false);
    act(() => setViewport(859));
    await waitFor(() => expect(html.dataset.density).toBe('compact'));
    act(() => setViewport(860));
    await waitFor(() => expect(html.hasAttribute('data-density')).toBe(false));
  });

  it('an explicit density is not touched by the viewport', async () => {
    signedInWith({ density: 'regular' });
    await renderApp({ path: '/', width: 1280 });
    await screen.findByText('Hola, ada');
    act(() => setViewport(390));
    expect(html.hasAttribute('data-density')).toBe(false);
  });

  it('an anonymous visit keeps the mirror and applies it', async () => {
    localStorage.setItem(MIRROR_KEY, JSON.stringify({ accent: 'cyan' }));
    await renderApp({ path: '/login' });
    await screen.findByLabelText('Usuario');
    expect(html.dataset.accent).toBe('cyan');
    expect(JSON.parse(localStorage.getItem(MIRROR_KEY)!).accent).toBe('cyan');
  });
});
