/** AC1 (F9-j S2, S3): `withReauth` and the re-authentication dialog. */
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { useState } from 'react';
import { describe, expect, it } from 'vitest';
import { createApiKey } from '@/api/endpoints';
import { API, failure, ok, signedInSession } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';
import { ReauthProvider, useReauth } from './ReauthProvider';
import { isReauthCancelled } from './withReauth';

const LONG = { timeout: 10000 };
const KEY = {
  key: 'rb_live_0123456789abcdef0123456789abcdef01234567',
  api_key: { prefix: 'rb_live_012345', created_at: '2026-11-15T10:00:00Z', last_used_at: null },
};

/** A caller of `withReauth`: shows the result, "cancelled" or "failed". */
function Harness() {
  const withReauth = useReauth();
  const [result, setResult] = useState('');
  const run = async () => {
    try {
      const created = await withReauth(() => createApiKey());
      setResult(`created ${created.api_key.prefix}`);
    } catch (error) {
      setResult(isReauthCancelled(error) ? 'cancelled' : 'failed');
    }
  };
  return (
    <>
      <button type="button" onClick={() => void run()}>
        Run
      </button>
      <p data-testid="result">{result}</p>
    </>
  );
}

const reauthRequired = (methods: string[]) =>
  failure(403, {
    error: 'Forbidden',
    message: 'Confirm your identity to continue',
    code: 'reauth_required',
    params: { methods },
  });

type Setup = {
  /** Answers of `POST /me/api-key`, in order; the last one repeats. */
  action: Array<() => Response>;
  reauth?: (body: Record<string, unknown>) => Response;
};

function setup({ action, reauth = () => ok({ reauth_until: '2026-11-15T12:10:00Z' }) }: Setup) {
  const calls = { action: 0, reauth: [] as Array<Record<string, unknown>> };
  server.use(
    http.get(`${API}/auth/session`, () => signedInSession()),
    http.post(`${API}/me/api-key`, () => {
      const answer = action[Math.min(calls.action, action.length - 1)];
      calls.action += 1;
      return answer();
    }),
    http.post(`${API}/me/reauth`, async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      calls.reauth.push(body);
      return reauth(body);
    }),
  );
  return calls;
}

async function open() {
  await renderApp({
    path: '/test-reauth',
    shellRoutes: () => [
      {
        path: '/test-reauth',
        element: (
          <ReauthProvider>
            <Harness />
          </ReauthProvider>
        ),
      },
    ],
  });
  await userEvent.click(await screen.findByRole('button', { name: 'Run' }, LONG));
}

const result = () => screen.getByTestId('result');
const dialog = () => screen.findByRole('dialog', { name: "Confirm it's you" }, LONG);

describe('withReauth (F9-j S2)', () => {
  it('runs the action without a dialog when no re-authentication is needed', async () => {
    const calls = setup({ action: [() => ok(KEY, 201)] });
    await open();
    await waitFor(() => expect(result()).toHaveTextContent('created rb_live_012345'), LONG);
    expect(screen.queryByRole('dialog', { name: "Confirm it's you" })).toBeNull();
    expect(calls.action).toBe(1);
  }, 20000);

  it('asks for the password, then runs the action once more and returns its result', async () => {
    const calls = setup({ action: [() => reauthRequired(['password']), () => ok(KEY, 201)] });
    await open();
    const box = await dialog();
    expect(
      within(box).getByText('For your security, confirm your identity to continue.'),
    ).toBeVisible();
    expect(within(box).queryByLabelText('Code from your authenticator app')).toBeNull();
    expect(within(box).queryByRole('button', { name: /authenticator app instead/ })).toBeNull();
    await userEvent.type(within(box).getByLabelText('Password'), 'my-password');
    await userEvent.click(within(box).getByRole('button', { name: 'Confirm' }));
    await waitFor(() => expect(result()).toHaveTextContent('created rb_live_012345'), LONG);
    expect(calls.reauth).toEqual([{ password: 'my-password' }]);
    expect(calls.action).toBe(2);
    expect(screen.queryByRole('dialog', { name: "Confirm it's you" })).toBeNull();
  }, 20000);

  it('with both methods starts with the password and switches to a code and back', async () => {
    const calls = setup({
      action: [() => reauthRequired(['password', 'totp']), () => ok(KEY, 201)],
    });
    await open();
    const box = await dialog();
    expect(within(box).getByLabelText('Password')).toBeVisible();
    await userEvent.click(
      within(box).getByRole('button', { name: 'Use your authenticator app instead' }),
    );
    const code = within(box).getByLabelText('Code from your authenticator app');
    expect(code).toHaveAttribute('inputmode', 'numeric');
    expect(code).toHaveAttribute('autocomplete', 'one-time-code');
    expect(code).toHaveAttribute('maxlength', '6');
    expect(within(box).queryByLabelText('Password')).toBeNull();
    await userEvent.click(within(box).getByRole('button', { name: 'Use your password instead' }));
    expect(within(box).getByLabelText('Password')).toBeVisible();
    await userEvent.click(
      within(box).getByRole('button', { name: 'Use your authenticator app instead' }),
    );
    await userEvent.type(within(box).getByLabelText('Code from your authenticator app'), '123456');
    await userEvent.click(within(box).getByRole('button', { name: 'Confirm' }));
    await waitFor(() => expect(result()).toHaveTextContent('created'), LONG);
    expect(calls.reauth).toEqual([{ code: '123456' }]);
  }, 20000);

  it('with only totp shows the code field and no switch', async () => {
    setup({ action: [() => reauthRequired(['totp']), () => ok(KEY, 201)] });
    await open();
    const box = await dialog();
    expect(within(box).getByLabelText('Code from your authenticator app')).toBeVisible();
    expect(within(box).queryByLabelText('Password')).toBeNull();
    expect(within(box).queryByRole('button', { name: /instead/ })).toBeNull();
  }, 20000);

  it('Cancel closes the dialog and rejects with a cancellation, without a toast', async () => {
    const calls = setup({ action: [() => reauthRequired(['password'])] });
    await open();
    const box = await dialog();
    await userEvent.click(within(box).getByRole('button', { name: 'Cancel' }));
    await waitFor(() => expect(result()).toHaveTextContent('cancelled'), LONG);
    expect(screen.queryByRole('dialog', { name: "Confirm it's you" })).toBeNull();
    expect(screen.queryByText('Confirm your identity to continue.')).toBeNull();
    expect(calls.reauth).toEqual([]);
    expect(calls.action).toBe(1);
  }, 20000);

  it('a second reauth_required after the retry is an error toast, not another dialog', async () => {
    const calls = setup({ action: [() => reauthRequired(['password'])] });
    await open();
    const box = await dialog();
    await userEvent.type(within(box).getByLabelText('Password'), 'my-password');
    await userEvent.click(within(box).getByRole('button', { name: 'Confirm' }));
    expect(
      await screen.findByText('Confirm your identity to continue.', { selector: 'p' }, LONG),
    ).toBeVisible();
    await waitFor(() => expect(result()).toHaveTextContent('cancelled'), LONG);
    expect(calls.action).toBe(2);
    expect(screen.queryByRole('dialog', { name: "Confirm it's you" })).toBeNull();
  }, 20000);

  it('any other failure reaches the caller as is', async () => {
    setup({ action: [() => failure(500, { error: 'Internal Server Error' })] });
    await open();
    await waitFor(() => expect(result()).toHaveTextContent('failed'), LONG);
  }, 20000);
});

describe('ReauthDialog (F9-j S3)', () => {
  it('a wrong password is an error on its field, focused; the action does not run', async () => {
    const calls = setup({
      action: [() => reauthRequired(['password'])],
      reauth: () => failure(400, { error: 'Validation Error', code: 'current_password_incorrect' }),
    });
    await open();
    const box = await dialog();
    await userEvent.type(within(box).getByLabelText('Password'), 'not-it');
    await userEvent.click(within(box).getByRole('button', { name: 'Confirm' }));
    expect(
      await within(box).findByText('The current password is incorrect.', {}, LONG),
    ).toBeVisible();
    const field = within(box).getByLabelText('Password');
    expect(field).toHaveAttribute('aria-invalid', 'true');
    await waitFor(() => expect(field).toHaveFocus());
    expect(calls.action).toBe(1);
  }, 20000);

  it('a wrong code is an error on the code field', async () => {
    setup({
      action: [() => reauthRequired(['totp'])],
      reauth: () => failure(400, { error: 'Validation Error', code: 'mfa_invalid' }),
    });
    await open();
    const box = await dialog();
    await userEvent.type(within(box).getByLabelText('Code from your authenticator app'), '000000');
    await userEvent.click(within(box).getByRole('button', { name: 'Confirm' }));
    expect(
      await within(box).findByText(
        'That code is not valid. Check your authenticator app and try again.',
        {},
        LONG,
      ),
    ).toBeVisible();
    expect(within(box).getByLabelText('Code from your authenticator app')).toHaveAttribute(
      'aria-invalid',
      'true',
    );
  }, 20000);

  it('an empty field is required, without a request', async () => {
    const calls = setup({ action: [() => reauthRequired(['password'])] });
    await open();
    const box = await dialog();
    await userEvent.click(within(box).getByRole('button', { name: 'Confirm' }));
    expect(await within(box).findByText('This field is required.')).toBeVisible();
    expect(calls.reauth).toEqual([]);
  }, 20000);

  it('too many attempts show the countdown and disable Confirm', async () => {
    setup({
      action: [() => reauthRequired(['password'])],
      reauth: () =>
        failure(429, { error: 'Too Many Requests', code: 'rate_limited' }, { 'Retry-After': '30' }),
    });
    await open();
    const box = await dialog();
    await userEvent.type(within(box).getByLabelText('Password'), 'my-password');
    await userEvent.click(within(box).getByRole('button', { name: 'Confirm' }));
    expect(
      await within(box).findByText('Too many attempts. You can try again in 30 seconds.', {}, LONG),
    ).toBeVisible();
    expect(within(box).getByRole('button', { name: 'Confirm' })).toBeDisabled();
  }, 20000);
});
