/** AC5 (F9-j S12): the login page sends a 2FA account to the code step. */
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';
import { API, ANON_TOKEN, USER, ok, signedInSession } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';

const LONG = { timeout: 10000 };
let sessionReads: number;
let pending: boolean;
let signedIn: boolean;

beforeEach(() => {
  sessionReads = 0;
  pending = false;
  signedIn = false;
  server.use(
    http.get(`${API}/auth/session`, () => {
      sessionReads += 1;
      if (signedIn) return signedInSession();
      return ok({
        authenticated: false,
        csrf_token: ANON_TOKEN,
        ...(pending ? { mfa_pending: true } : {}),
      });
    }),
  );
});

async function signIn(path: string) {
  const app = await renderApp({ path, width: 390 });
  await screen.findByRole('heading', { level: 1, name: 'Sign in' }, LONG);
  await userEvent.type(screen.getByLabelText('Username'), 'ada');
  await userEvent.type(screen.getByLabelText('Password'), 'right-password');
  return app;
}

describe('Login with two-factor authentication (F9-j S12)', () => {
  it('mfa_required goes to /login/2fa keeping next, without reading the session first', async () => {
    server.use(
      http.post(`${API}/auth/login`, () => {
        pending = true;
        return ok({ mfa_required: true, methods: ['totp', 'recovery'] });
      }),
    );
    const { where, router } = await signIn('/login?next=%2Friftbound%2Fapp%2Fdecks');
    const before = sessionReads;
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    await waitFor(() => expect(where()).toBe('/login/2fa?next=%2Friftbound%2Fapp%2Fdecks'), LONG);
    expect(router.state.historyAction).toBe('REPLACE');
    await screen.findByRole('heading', { level: 1, name: 'Two-step verification' }, LONG);
    // Only the 2FA screen reads the session (to find the pending step), never the login page.
    expect(sessionReads - before).toBeLessThanOrEqual(1);
  }, 20000);

  it('without next goes to /login/2fa', async () => {
    server.use(
      http.post(`${API}/auth/login`, () => {
        pending = true;
        return ok({ mfa_required: true, methods: ['totp', 'recovery'] });
      }),
    );
    const { where } = await signIn('/login');
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    await waitFor(() => expect(where()).toBe('/login/2fa'), LONG);
  }, 20000);

  it('an account without 2FA still signs in and goes to next', async () => {
    server.use(
      http.post(`${API}/auth/login`, () => {
        signedIn = true;
        return ok({ user: USER });
      }),
    );
    const { where } = await signIn('/login?next=%2Friftbound%2Fapp%2Faccount%2Finterface');
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    await waitFor(() => expect(where()).toBe('/account/interface'), LONG);
  }, 20000);
});
