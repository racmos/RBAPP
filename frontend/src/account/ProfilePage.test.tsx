import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';
import type { Session } from '@/api/types';
import { API, NO_PREFS, USER, USER_TOKEN, failure, ok, signedInSession } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';

const LONG = { timeout: 10000 };
const PHONE = 390;
const patches: Array<Record<string, unknown>> = [];

beforeEach(() => {
  patches.length = 0;
});
afterEach(() => {
  vi.restoreAllMocks();
});

type Answer = (body: Record<string, unknown>) => Response;

/** Signed in as `USER`; `PATCH /me/account` records its body and answers with `answer`. */
function signedIn(answer: Answer = (body) => ok({ user: { ...USER, ...pick(body) } })) {
  server.use(
    http.get(`${API}/auth/session`, () => signedInSession()),
    http.patch(`${API}/me/account`, async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      patches.push(body);
      return answer(body);
    }),
  );
}
const pick = (body: Record<string, unknown>) =>
  typeof body.email === 'string' ? { email: body.email } : {};

async function openPage(width = PHONE) {
  const app = await renderApp({ path: '/account/profile', width });
  await screen.findByRole('heading', { level: 1, name: 'Profile' }, LONG);
  return app;
}

const emailForm = () => screen.getByRole('form', { name: 'Email' });
const passwordForm = () => screen.getByRole('form', { name: 'Password' });
const emailInput = () => within(emailForm()).getByLabelText('Email');
const saveEmail = () => within(emailForm()).getByRole('button', { name: 'Save email' });
const current = () => within(passwordForm()).getByLabelText('Current password');
const fresh = () => within(passwordForm()).getByLabelText('New password');
const confirm = () => within(passwordForm()).getByLabelText('Confirm new password');
const changePassword = () =>
  within(passwordForm()).getByRole('button', { name: 'Change password' });

async function fillPassword(values: { current: string; fresh: string; confirm: string }) {
  if (values.current) await userEvent.type(current(), values.current);
  if (values.fresh) await userEvent.type(fresh(), values.fresh);
  if (values.confirm) await userEvent.type(confirm(), values.confirm);
}

describe('Profile page (/account/profile)', () => {
  it('shows the username and the current email', async () => {
    signedIn();
    await openPage();
    expect(within(screen.getByRole('region', { name: 'Account' })).getByText('ada')).toBeVisible();
    expect(emailInput()).toHaveValue('ada@example.com');
    expect(emailInput()).toHaveAttribute('type', 'email');
    expect(emailInput()).toHaveAttribute('autocomplete', 'email');
    expect(saveEmail()).toBeDisabled();
    expect(current()).toHaveAttribute('autocomplete', 'current-password');
    expect(fresh()).toHaveAttribute('autocomplete', 'new-password');
    expect(confirm()).toHaveAttribute('autocomplete', 'new-password');
  }, 20000);

  it('an account without an email shows an empty field and can add one (F9-b S14)', async () => {
    signedIn();
    server.use(
      http.get(`${API}/auth/session`, () =>
        ok({
          authenticated: true,
          csrf_token: USER_TOKEN,
          user: { ...USER, email: null },
          prefs: NO_PREFS,
        }),
      ),
    );
    await openPage();
    expect(emailInput()).toHaveValue('');
    expect(saveEmail()).toBeDisabled();
    await userEvent.type(emailInput(), 'ada@new.example');
    await userEvent.click(saveEmail());
    expect(await screen.findByText('Email updated.', {}, LONG)).toBeVisible();
    expect(patches).toEqual([{ email: 'ada@new.example' }]);
  }, 20000);

  it('saves only the email and updates the session everywhere', async () => {
    signedIn();
    const { queryClient } = await openPage();
    await userEvent.clear(emailInput());
    await userEvent.type(emailInput(), 'ada@new.example');
    await userEvent.click(saveEmail());
    expect(await screen.findByText('Email updated.', {}, LONG)).toBeVisible();
    expect(patches).toEqual([{ email: 'ada@new.example' }]);
    const session = queryClient.getQueryData<Session>(['session']);
    expect(session?.user?.email).toBe('ada@new.example');
    expect(session?.authenticated).toBe(true);
    expect(session?.prefs).not.toBeNull();
    expect(saveEmail()).toBeDisabled();
  }, 20000);

  it('shows a server validation error on the email field', async () => {
    signedIn(() =>
      failure(400, {
        error: 'Validation Error',
        code: 'validation_error',
        details: [
          {
            field: 'email',
            message: 'value is not a valid email address',
            type: 'value_error',
            code: 'invalid_format',
          },
        ],
      }),
    );
    await openPage();
    await userEvent.clear(emailInput());
    await userEvent.type(emailInput(), 'ada@bad.example');
    await userEvent.click(saveEmail());
    expect(
      await within(emailForm()).findByText('Enter a valid email address.', {}, LONG),
    ).toBeVisible();
    expect(emailInput()).toHaveAttribute('aria-invalid', 'true');
  }, 20000);

  it('shows a taken email on the email field', async () => {
    signedIn(() =>
      failure(409, {
        error: 'Conflict',
        code: 'email_taken',
        message: 'That email address is already in use',
      }),
    );
    await openPage();
    await userEvent.clear(emailInput());
    await userEvent.type(emailInput(), 'bob@example.com');
    await userEvent.click(saveEmail());
    expect(
      await within(emailForm()).findByText('That email is already registered.', {}, LONG),
    ).toBeVisible();
    expect(emailInput()).toHaveAttribute('aria-invalid', 'true');
    await waitFor(() => expect(emailInput()).toHaveFocus());
  }, 20000);

  it('blocks a confirmation that does not match, without a request', async () => {
    signedIn();
    await openPage();
    await fillPassword({
      current: 'old-password',
      fresh: 'brand-new-pass',
      confirm: 'brand-new-pazz',
    });
    await userEvent.click(changePassword());
    expect(await within(passwordForm()).findByText('The passwords do not match.')).toBeVisible();
    expect(confirm()).toHaveAttribute('aria-invalid', 'true');
    expect(patches).toEqual([]);
  }, 20000);

  it('blocks a short new password and a missing current one, without a request', async () => {
    signedIn();
    await openPage();
    await fillPassword({ current: '', fresh: 'short', confirm: 'short' });
    await userEvent.click(changePassword());
    expect(
      await within(passwordForm()).findByText('The password must be at least 8 characters.'),
    ).toBeVisible();
    expect(within(passwordForm()).getByText('This field is required.')).toBeVisible();
    expect(current()).toHaveAttribute('aria-invalid', 'true');
    expect(fresh()).toHaveAttribute('aria-invalid', 'true');
    expect(patches).toEqual([]);
  }, 20000);

  it('shows a wrong current password on its field and keeps what was typed', async () => {
    signedIn(() =>
      failure(400, {
        error: 'Bad Request',
        code: 'current_password_incorrect',
        message: 'The current password is incorrect',
      }),
    );
    await openPage();
    await fillPassword({ current: 'not-it', fresh: 'brand-new-pass', confirm: 'brand-new-pass' });
    await userEvent.click(changePassword());
    expect(
      await within(passwordForm()).findByText('The current password is incorrect.', {}, LONG),
    ).toBeVisible();
    expect(current()).toHaveAttribute('aria-invalid', 'true');
    await waitFor(() => expect(current()).toHaveFocus());
    expect(current()).toHaveValue('not-it');
    expect(fresh()).toHaveValue('brand-new-pass');
    expect(confirm()).toHaveValue('brand-new-pass');
    expect(patches).toEqual([{ current_password: 'not-it', password: 'brand-new-pass' }]);
  }, 20000);

  it('changes the password: sends only the passwords, clears the fields and toasts', async () => {
    signedIn();
    await openPage();
    await fillPassword({
      current: 'old-password',
      fresh: 'brand-new-pass',
      confirm: 'brand-new-pass',
    });
    await userEvent.click(changePassword());
    expect(await screen.findByText('Password changed.', {}, LONG)).toBeVisible();
    expect(patches).toEqual([{ current_password: 'old-password', password: 'brand-new-pass' }]);
    expect(current()).toHaveValue('');
    expect(fresh()).toHaveValue('');
    expect(confirm()).toHaveValue('');
  }, 20000);

  it('shows the countdown after too many changes', async () => {
    signedIn(() =>
      failure(429, { error: 'Too Many Requests', code: 'rate_limited' }, { 'Retry-After': '30' }),
    );
    await openPage();
    await userEvent.clear(emailInput());
    await userEvent.type(emailInput(), 'ada@new.example');
    await userEvent.click(saveEmail());
    expect(
      await screen.findByText('Too many attempts. You can try again in 30 seconds.', {}, LONG),
    ).toBeVisible();
    expect(saveEmail()).toBeDisabled();
    expect(changePassword()).toBeDisabled();
  }, 20000);

  it('shows any other failure as a form alert', async () => {
    signedIn(() => failure(500, { error: 'Internal Server Error', message: 'Boom' }));
    await openPage();
    await fillPassword({
      current: 'old-password',
      fresh: 'brand-new-pass',
      confirm: 'brand-new-pass',
    });
    await userEvent.click(changePassword());
    expect(await within(passwordForm()).findByRole('alert', {}, LONG)).toHaveTextContent('Boom');
  }, 20000);

  it('offline: every input and button is disabled', async () => {
    signedIn();
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    await openPage();
    expect(emailInput()).toBeDisabled();
    expect(saveEmail()).toBeDisabled();
    expect(current()).toBeDisabled();
    expect(fresh()).toBeDisabled();
    expect(confirm()).toBeDisabled();
    expect(changePassword()).toBeDisabled();
  }, 20000);

  it('links to the interface settings', async () => {
    signedIn();
    await openPage();
    expect(screen.getByRole('link', { name: 'Interface settings' })).toHaveAttribute(
      'href',
      '/riftbound/app/account/interface',
    );
  }, 20000);

  it('is axe clean', async () => {
    signedIn();
    const { container } = await openPage(1280);
    expect(await axe(container)).toHaveNoViolations();
  }, 30000);

  it('sends an anonymous visitor to the login screen', async () => {
    const { where } = await renderApp({ path: '/account/profile', width: PHONE });
    await waitFor(() => expect(where()).toMatch(/^\/login\?next=/), LONG);
    expect(where()).toContain(encodeURIComponent('/riftbound/app/account/profile'));
  }, 20000);
});

describe('Profile in the navigation', () => {
  it('opens from the home hub and the More sheet as a router link', async () => {
    signedIn();
    await renderApp({ path: '/', width: PHONE });
    await screen.findByRole('heading', { level: 1, name: 'Hello, ada' }, LONG);
    const main = screen.getByRole('main');
    const tile = await within(main).findByRole('link', { name: /^Profile/ }, LONG);
    expect(tile).toHaveAttribute('href', '/riftbound/app/account/profile');
    expect(within(tile).queryByText('Classic version')).toBeNull();

    await userEvent.click(screen.getByRole('button', { name: 'More' }));
    const sheet = await screen.findByRole('dialog', { name: 'More options' }, LONG);
    const item = within(sheet).getByRole('link', { name: /^Profile/ });
    expect(item).toHaveAttribute('href', '/riftbound/app/account/profile');
    await userEvent.click(item);
    expect(await screen.findByRole('heading', { level: 1, name: 'Profile' }, LONG)).toBeVisible();
  }, 30000);
});
