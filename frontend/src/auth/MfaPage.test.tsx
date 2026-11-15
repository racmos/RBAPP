/** AC5 (F9-j S13, S15, S16): the two-step verification screen `/login/2fa`. */
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';
import { API, ANON_TOKEN, USER, failure, ok, signedInSession } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { clearToasts } from '@/components/ui/toastStore';
import { renderApp } from '@/test/renderApp';

const LONG = { timeout: 10000 };
const NEXT = '/login/2fa?next=%2Friftbound%2Fapp%2Faccount%2Finterface';
let pending: boolean;
let signedIn: boolean;
let bodies: Array<Record<string, unknown>>;

beforeEach(() => {
  pending = true;
  signedIn = false;
  bodies = [];
  server.use(
    http.get(`${API}/auth/session`, () =>
      signedIn
        ? signedInSession()
        : ok({
            authenticated: false,
            csrf_token: ANON_TOKEN,
            ...(pending ? { mfa_pending: true } : {}),
          }),
    ),
  );
});
afterEach(() => {
  vi.restoreAllMocks();
  // A test that went offline tells TanStack Query's online manager it is back.
  window.dispatchEvent(new Event('online'));
  // Toasts live in a module store: one test's toast must not show in the next.
  clearToasts();
});

function answer(reply: (body: Record<string, unknown>) => Response) {
  server.use(
    http.post(`${API}/auth/mfa`, async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      bodies.push(body);
      return reply(body);
    }),
  );
}

const done = (left = 10, used = false) => {
  signedIn = true;
  pending = false;
  return ok({ user: USER, recovery_code_used: used, recovery_codes_left: left });
};

async function openStep(path = '/login/2fa', width = 390) {
  const app = await renderApp({ path, width });
  await screen.findByRole('heading', { level: 1, name: 'Two-step verification' }, LONG);
  return app;
}

const verify = () => screen.getByRole('button', { name: 'Verify' });

describe('/login/2fa (F9-j S13)', () => {
  it('without a pending step goes back to /login, keeping next', async () => {
    pending = false;
    const { where } = await renderApp({ path: NEXT, width: 390 });
    await waitFor(
      () => expect(where()).toBe('/login?next=%2Friftbound%2Fapp%2Faccount%2Finterface'),
      LONG,
    );
  }, 20000);

  it('asks for the 6-digit code in a focused numeric field, with a way back', async () => {
    await openStep();
    expect(screen.getByText('Enter the 6-digit code from your authenticator app.')).toBeVisible();
    const code = screen.getByLabelText('Code');
    expect(code).toHaveAttribute('inputmode', 'numeric');
    expect(code).toHaveAttribute('autocomplete', 'one-time-code');
    await waitFor(() => expect(code).toHaveFocus());
    expect(screen.getByRole('link', { name: 'Back to sign in' })).toHaveAttribute(
      'href',
      '/riftbound/app/login',
    );
  }, 20000);

  it('switches to a recovery code and back', async () => {
    await openStep();
    await userEvent.click(screen.getByRole('button', { name: 'Use a recovery code' }));
    const recovery = screen.getByLabelText('Recovery code');
    expect(recovery).toHaveAttribute('autocomplete', 'off');
    expect(screen.getByText('Enter one of the recovery codes you saved.')).toBeVisible();
    expect(screen.queryByLabelText('Code')).toBeNull();
    await userEvent.click(screen.getByRole('button', { name: 'Use your authenticator app' }));
    expect(screen.getByLabelText('Code')).toBeVisible();
  }, 20000);

  it('a right code signs in, reads the session and goes to next', async () => {
    answer(() => done());
    const { where, queryClient } = await openStep(NEXT);
    await userEvent.type(screen.getByLabelText('Code'), '123456');
    await userEvent.click(verify());
    await waitFor(() => expect(where()).toBe('/account/interface'), LONG);
    expect(bodies).toEqual([{ code: '123456' }]);
    expect(queryClient.getQueryData(['session'])).toMatchObject({ authenticated: true });
  }, 20000);

  it('an empty code is required, without a request', async () => {
    answer(() => done());
    await openStep();
    await userEvent.click(verify());
    expect(await screen.findByText('This field is required.')).toBeVisible();
    expect(bodies).toEqual([]);
  }, 20000);

  it.each([
    [1, 'You have 1 recovery code left. Create new ones in Security.'],
    [4, 'You have 4 recovery codes left. Create new ones in Security.'],
  ])(
    'a recovery code with %i left says so',
    async (left, text) => {
      answer(() => done(left, true));
      const { where } = await openStep();
      await userEvent.click(screen.getByRole('button', { name: 'Use a recovery code' }));
      await userEvent.type(screen.getByLabelText('Recovery code'), 'abcde-fghjk');
      await userEvent.click(verify());
      expect(await screen.findByText(text, { selector: 'p' }, LONG)).toBeVisible();
      await waitFor(() => expect(where()).toBe('/'), LONG);
      expect(bodies).toEqual([{ recovery_code: 'abcde-fghjk' }]);
    },
    20000,
  );

  it('a wrong code is an error on the field, focused', async () => {
    answer(() => failure(401, { error: 'Unauthorized', code: 'mfa_invalid' }));
    await openStep();
    const code = screen.getByLabelText('Code');
    await userEvent.type(code, '000000');
    await userEvent.click(verify());
    expect(
      await screen.findByText(
        'That code is not valid. Check your authenticator app and try again.',
        {},
        LONG,
      ),
    ).toBeVisible();
    expect(code).toHaveAttribute('aria-invalid', 'true');
    await waitFor(() => expect(code).toHaveFocus());
  }, 20000);

  it('an expired step goes back to /login with the alert', async () => {
    answer(() => {
      pending = false;
      return failure(401, { error: 'Unauthorized', code: 'mfa_expired' });
    });
    const { where } = await openStep(NEXT);
    await userEvent.type(screen.getByLabelText('Code'), '123456');
    await userEvent.click(verify());
    await waitFor(
      () => expect(where()).toBe('/login?next=%2Friftbound%2Fapp%2Faccount%2Finterface'),
      LONG,
    );
    const alert = await screen.findByRole('alert', {}, LONG);
    expect(alert).toHaveTextContent('The sign-in step expired. Sign in again.');
    expect(within(alert).queryByRole('button')).toBeNull();
  }, 20000);

  it.each(['locked', 'rate_limited'])(
    '%s shows the countdown and disables Verify',
    async (code) => {
      answer(() =>
        failure(
          429,
          { error: 'Too Many Requests', code, params: { retry_after: 30 } },
          {
            'Retry-After': '30',
          },
        ),
      );
      await openStep();
      await userEvent.type(screen.getByLabelText('Code'), '123456');
      await userEvent.click(verify());
      expect(
        await screen.findByText('Too many attempts. You can try again in 30 seconds.', {}, LONG),
      ).toBeVisible();
      expect(verify()).toBeDisabled();
    },
    20000,
  );

  it('offline: Verify is disabled with the reason', async () => {
    await openStep();
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    window.dispatchEvent(new Event('offline'));
    expect(
      await screen.findByText('You are offline. Connect to verify the code.', {}, LONG),
    ).toBeVisible();
    expect(verify()).toBeDisabled();
  }, 20000);

  it.each([390, 1280])(
    'is axe clean at %i px',
    async (width) => {
      const { container } = await openStep('/login/2fa', width);
      expect(await axe(container)).toHaveNoViolations();
      await userEvent.click(screen.getByRole('button', { name: 'Use a recovery code' }));
      expect(await axe(container)).toHaveNoViolations();
    },
    30000,
  );
});
