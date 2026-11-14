/** F9-i S10 (AC5): the e-mail is optional at registration (D-F9-1). */
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';
import { API, ok } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';
import { checkRegister } from './registerChecks';

const LONG = { timeout: 10000 };
const bodies: Array<Record<string, unknown>> = [];

beforeEach(() => {
  bodies.length = 0;
  server.use(
    http.post(`${API}/auth/register`, async ({ request }) => {
      bodies.push((await request.json()) as Record<string, unknown>);
      return ok({ user: { id: 8, username: 'newbie' } }, 201);
    }),
  );
});

async function openRegister() {
  const app = await renderApp({ path: '/register', width: 390 });
  await screen.findByRole('heading', { level: 1, name: 'Create account' }, LONG);
  await screen.findByLabelText('Username', {}, LONG);
  return app;
}

async function fill(values: { username: string; email: string; password: string }) {
  await userEvent.type(screen.getByLabelText('Username'), values.username);
  if (values.email) await userEvent.type(screen.getByLabelText('Email (optional)'), values.email);
  await userEvent.type(screen.getByLabelText('Password'), values.password);
  await userEvent.click(screen.getByRole('button', { name: 'Create account' }));
}

describe('Register: optional email (F9-i S10)', () => {
  it('labels the email as optional, with the hint, and does not require it', async () => {
    await openRegister();
    const email = screen.getByLabelText('Email (optional)');
    expect(email).not.toBeRequired();
    expect(email).toHaveAccessibleDescription(
      'Used only to identify your account. There is no password recovery by email.',
    );
  }, 20000);

  it('accepts an empty email and leaves it out of the body', async () => {
    const { where } = await openRegister();
    await fill({ username: 'newbie', email: '', password: 'long-enough-pass' });
    await waitFor(() => expect(where()).toBe('/login'), LONG);
    expect(bodies).toEqual([{ username: 'newbie', password: 'long-enough-pass' }]);
  }, 20000);

  it('sends a non-empty email as before', async () => {
    const { where } = await openRegister();
    await fill({ username: 'newbie', email: 'new@example.com', password: 'long-enough-pass' });
    await waitFor(() => expect(where()).toBe('/login'), LONG);
    expect(bodies).toEqual([
      { username: 'newbie', email: 'new@example.com', password: 'long-enough-pass' },
    ]);
  }, 20000);

  it('still refuses a bad email, without a request', async () => {
    await openRegister();
    await fill({ username: 'newbie', email: 'not-an-email', password: 'long-enough-pass' });
    expect(await screen.findByText('Enter a valid email address.')).toBeVisible();
    expect(screen.getByLabelText('Email (optional)')).toHaveAttribute('aria-invalid', 'true');
    expect(bodies).toEqual([]);
  }, 20000);
});

describe('checkRegister (F9-i S10)', () => {
  it('lets an empty or blank email pass and checks a non-empty one', () => {
    const base = { username: 'newbie', password: 'long-enough-pass' };
    expect(checkRegister({ ...base, email: '' })).toEqual([]);
    expect(checkRegister({ ...base, email: '   ' })).toEqual([]);
    expect(checkRegister({ ...base, email: 'nope' }).map((p) => [p.field, p.code])).toEqual([
      ['email', 'invalid_format'],
    ]);
  });
});
