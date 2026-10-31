/** English-only app (owner feedback S21): no language toggle, no language preference. */
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { API, NO_PREFS, ok, signedInSession } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';

const LONG = { timeout: 10000 };
/** The backend still stores and sends `lang` (column `rbprf_lang`); the app ignores it. */
const SPANISH_ACCOUNT = { ...NO_PREFS, lang: 'es' };
const patches: Array<Record<string, unknown>> = [];

const languageControls = () => [
  ...screen.queryAllByRole('group', { name: /^(Language|Idioma)$/ }),
  ...screen.queryAllByRole('radiogroup', { name: /^(Language|Idioma)$/ }),
  ...screen.queryAllByRole('button', { name: /^(ES|EN|Español|English)$/ }),
];

function signedIn(prefs: Record<string, unknown> = SPANISH_ACCOUNT) {
  server.use(
    http.get(`${API}/auth/session`, () => signedInSession(prefs)),
    http.patch(`${API}/me/prefs`, async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      patches.push(body);
      return ok({ prefs: { ...prefs, ...body } });
    }),
  );
}

beforeEach(() => {
  patches.length = 0;
});
afterEach(() => localStorage.clear());

describe('English-only app (owner feedback S21)', () => {
  it('the login screen is English, with no language toggle', async () => {
    localStorage.setItem('rb_lang', 'es'); // a choice left by the old toggle changes nothing
    await renderApp({ path: '/login' });
    expect(await screen.findByRole('button', { name: 'Sign in' }, LONG)).toBeVisible();
    expect(languageControls()).toEqual([]);
    expect(document.documentElement.lang).toBe('en');
  });

  it('an account that stored Spanish still gets English, and the topbar has no toggle', async () => {
    signedIn();
    await renderApp({ path: '/', width: 1440 });
    const banner = await screen.findByRole('banner', {}, LONG);
    expect(
      await within(banner).findByRole('navigation', { name: 'Main navigation' }, LONG),
    ).toBeVisible();
    expect(languageControls()).toEqual([]);
    expect(document.documentElement.lang).toBe('en');
  });

  it('the phone "More" sheet has no language section', async () => {
    signedIn();
    await renderApp({ path: '/', width: 390 });
    await userEvent.click(await screen.findByRole('button', { name: 'More' }, LONG));
    const sheet = await screen.findByRole('dialog', { name: 'More options' }, LONG);
    expect(within(sheet).queryByText('Language')).toBeNull();
    expect(languageControls()).toEqual([]);
  });

  it('the interface settings have no language setting and never send `lang`', async () => {
    signedIn();
    await renderApp({ path: '/account/interface', width: 390 });
    await screen.findByRole('spinbutton', { name: 'Playset size' }, LONG);
    expect(languageControls()).toEqual([]);
    expect(screen.queryByText('Language')).toBeNull();
    await userEvent.click(screen.getByRole('radio', { name: 'Cyan' }));
    await waitFor(() => expect(patches).toContainEqual({ accent: 'cyan' }), LONG);
    expect(patches.some((patch) => 'lang' in patch)).toBe(false);
  }, 20000);

  it('the preferences mirror does not keep a language', async () => {
    signedIn();
    await renderApp({ path: '/', width: 1440 });
    await waitFor(() => expect(localStorage.getItem('rb_prefs_v1')).not.toBeNull(), LONG);
    expect(JSON.parse(localStorage.getItem('rb_prefs_v1')!)).not.toHaveProperty('lang');
  });
});
