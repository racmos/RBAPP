/** AC2 (F9-j S1, S4-S8, S15, S16): the Security section without the devices card. */
import { join } from 'node:path';
import { act, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';
import type { MeData } from '@/api/types';
import { up } from '@/lib/breakpoints';
import { SRC_DIR, readCss, rules } from '@/test/css';
import {
  MFA_OFF,
  MFA_ON,
  MFA_UNAVAILABLE,
  RECOVERY_CODES,
  SETUP,
  deviceSessions,
  meWith,
} from '@/test/fixtures/security';
import { API, USER, failure, ok, signedInSession } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { clearToasts } from '@/components/ui/toastStore';
import { renderApp } from '@/test/renderApp';

const LONG = { timeout: 10000 };
const PHONE = 390;

type Sent = { method: string; path: string; body: unknown };
let sent: Sent[];
let writeText: ReturnType<typeof vi.fn>;
const createObjectURL = vi.fn((blob: Blob) => (void blob, 'blob:codes-1'));
const revokeObjectURL = vi.fn();

beforeEach(() => {
  sent = [];
  writeText = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
  createObjectURL.mockClear();
  revokeObjectURL.mockClear();
  Object.assign(URL, { createObjectURL, revokeObjectURL });
});
afterEach(() => {
  vi.restoreAllMocks();
  // A test that went offline tells TanStack Query's online manager it is back.
  window.dispatchEvent(new Event('online'));
  // Toasts live in a module store: one test's toast must not show in the next.
  clearToasts();
});

const reauthRequired = () =>
  failure(403, { error: 'Forbidden', code: 'reauth_required', params: { methods: ['password'] } });

type Answers = {
  me?: () => MeData | Response;
  account?: (body: Record<string, unknown>, call: number) => Response;
  setup?: (call: number) => Response;
  enable?: (body: Record<string, unknown>) => Response;
  disable?: (body: Record<string, unknown>) => Response;
  codes?: () => Response;
};

/** Signed in as `USER`; every write is recorded in `sent`, and so are the reads of /me. */
function signedIn(answers: Answers = {}) {
  const me = answers.me ?? (() => meWith({ mfa: MFA_OFF }));
  const count = (path: string) => sent.filter((request) => request.path === path).length;
  const record = async (request: Request, path: string) => {
    const text = await request.text();
    sent.push({ method: request.method, path, body: text ? JSON.parse(text) : null });
  };
  server.use(
    http.get(`${API}/auth/session`, () => signedInSession()),
    http.get(`${API}/me`, async ({ request }) => {
      await record(request, '/me');
      const answer = me();
      return answer instanceof Response ? answer : ok(answer);
    }),
    http.get(`${API}/me/sessions`, async ({ request }) => {
      await record(request, '/me/sessions');
      return ok({ items: deviceSessions() });
    }),
    http.patch(`${API}/me/account`, async ({ request }) => {
      await record(request, '/me/account');
      const body = sent[sent.length - 1].body as Record<string, unknown>;
      return answers.account ? answers.account(body, count('/me/account')) : ok({ user: USER });
    }),
    http.post(`${API}/me/reauth`, async ({ request }) => {
      await record(request, '/me/reauth');
      return ok({ reauth_until: '2026-11-15T12:10:00Z' });
    }),
    http.post(`${API}/me/2fa/setup`, async ({ request }) => {
      await record(request, '/me/2fa/setup');
      return answers.setup ? answers.setup(count('/me/2fa/setup')) : ok(SETUP);
    }),
    http.post(`${API}/me/2fa/enable`, async ({ request }) => {
      await record(request, '/me/2fa/enable');
      const body = sent[sent.length - 1].body as Record<string, unknown>;
      return answers.enable
        ? answers.enable(body)
        : ok({ recovery_codes: RECOVERY_CODES, revoked_sessions: 2 });
    }),
    http.post(`${API}/me/2fa/disable`, async ({ request }) => {
      await record(request, '/me/2fa/disable');
      const body = sent[sent.length - 1].body as Record<string, unknown>;
      return answers.disable ? answers.disable(body) : ok({ revoked_sessions: 1 });
    }),
    http.post(`${API}/me/2fa/recovery-codes`, async ({ request }) => {
      await record(request, '/me/2fa/recovery-codes');
      return answers.codes
        ? answers.codes()
        : ok({ recovery_codes: RECOVERY_CODES, revoked_sessions: 0 });
    }),
  );
  return { count };
}

async function openSecurity(width = PHONE) {
  const app = await renderApp({ path: '/account/security', width });
  await screen.findByRole('heading', { level: 1, name: 'Security' }, LONG);
  return app;
}

const card = (name: string) => screen.findByRole('region', { name }, LONG);
const writes = () => sent.filter((request) => request.method !== 'GET');

describe('Security section (F9-j S1)', () => {
  it('the sections are Profile, Security, API, Interface; Profile has no password card', async () => {
    signedIn();
    await renderApp({ path: '/account/profile', width: PHONE });
    await screen.findByRole('heading', { level: 1, name: 'Profile' }, LONG);
    const nav = screen.getByRole('navigation', { name: 'Account sections' });
    expect(
      within(nav)
        .getAllByRole('link')
        .map((link) => link.textContent),
    ).toEqual(['Profile', 'Security', 'API', 'Interface']);
    expect(within(nav).getByRole('link', { name: 'Security' })).toHaveAttribute(
      'href',
      '/riftbound/app/account/security',
    );
    await screen.findByRole('region', { name: 'Email' }, LONG);
    expect(screen.queryByRole('region', { name: 'Password' })).toBeNull();
    expect(screen.getByText('Your photo, display name and email.')).toBeVisible();
  }, 20000);

  it('sends an anonymous visitor to the login screen', async () => {
    const { where } = await renderApp({ path: '/account/security', width: PHONE });
    await waitFor(() => expect(where()).toMatch(/^\/login\?next=/), LONG);
  }, 20000);
});

describe('Password card (F9-j S4)', () => {
  const form = () => screen.getByRole('form', { name: 'Password' });
  const field = (label: string) => within(form()).getByLabelText(label);

  async function fill(values: Record<string, string>) {
    for (const [label, value] of Object.entries(values)) {
      if (value) await userEvent.type(field(label), value);
    }
  }

  it('changes the password with the current one and says other devices are signed out', async () => {
    const { count } = signedIn();
    await openSecurity();
    await card('Password');
    expect(
      within(form()).getByText('Changing your password signs out your other devices.'),
    ).toBeVisible();
    expect(field('Current password')).toHaveAttribute('autocomplete', 'current-password');
    expect(field('New password')).toHaveAttribute('autocomplete', 'new-password');
    expect(field('Confirm new password')).toHaveAttribute('autocomplete', 'new-password');
    const before = count('/me/sessions');
    await fill({
      'Current password': 'old-password',
      'New password': 'brand-new-pass',
      'Confirm new password': 'brand-new-pass',
    });
    await userEvent.click(within(form()).getByRole('button', { name: 'Change password' }));
    expect(await screen.findByText('Password changed.', {}, LONG)).toBeVisible();
    expect(writes()).toEqual([
      {
        method: 'PATCH',
        path: '/me/account',
        body: { current_password: 'old-password', password: 'brand-new-pass' },
      },
    ]);
    expect(field('Current password')).toHaveValue('');
    expect(field('New password')).toHaveValue('');
    await waitFor(() => expect(count('/me/sessions')).toBeGreaterThan(before), LONG);
  }, 20000);

  it('blocks a confirmation that does not match and a short password, without a request', async () => {
    signedIn();
    await openSecurity();
    await card('Password');
    await fill({ 'New password': 'short', 'Confirm new password': 'short' });
    await userEvent.click(within(form()).getByRole('button', { name: 'Change password' }));
    expect(
      await within(form()).findByText('The password must be at least 8 characters.'),
    ).toBeVisible();
    expect(within(form()).getByText('This field is required.')).toBeVisible();
    await waitFor(() => expect(field('Current password')).toHaveFocus());
    await userEvent.clear(field('New password'));
    await userEvent.type(field('New password'), 'brand-new-pass');
    await userEvent.type(field('Current password'), 'old-password');
    await userEvent.click(within(form()).getByRole('button', { name: 'Change password' }));
    expect(await within(form()).findByText('The passwords do not match.')).toBeVisible();
    expect(writes()).toEqual([]);
  }, 20000);

  it('shows a wrong current password on its field', async () => {
    signedIn({
      account: () => failure(400, { error: 'Bad Request', code: 'current_password_incorrect' }),
    });
    await openSecurity();
    await card('Password');
    await fill({
      'Current password': 'not-it',
      'New password': 'brand-new-pass',
      'Confirm new password': 'brand-new-pass',
    });
    await userEvent.click(within(form()).getByRole('button', { name: 'Change password' }));
    expect(
      await within(form()).findByText('The current password is incorrect.', {}, LONG),
    ).toBeVisible();
    await waitFor(() => expect(field('Current password')).toHaveFocus());
  }, 20000);

  it('shows the countdown after too many changes, and any other failure as an alert', async () => {
    signedIn({
      account: (_body, call) =>
        call === 1
          ? failure(500, { error: 'Internal Server Error', message: 'Boom' })
          : failure(
              429,
              { error: 'Too Many Requests', code: 'rate_limited' },
              { 'Retry-After': '30' },
            ),
    });
    await openSecurity();
    await card('Password');
    await fill({
      'Current password': 'old-password',
      'New password': 'brand-new-pass',
      'Confirm new password': 'brand-new-pass',
    });
    const submit = () => within(form()).getByRole('button', { name: 'Change password' });
    await userEvent.click(submit());
    expect(await within(form()).findByRole('alert', {}, LONG)).toHaveTextContent('Boom');
    await userEvent.click(submit());
    expect(
      await screen.findByText('Too many attempts. You can try again in 30 seconds.', {}, LONG),
    ).toBeVisible();
    expect(submit()).toBeDisabled();
  }, 20000);

  it('without a password offers "Set a password" and sets it through re-authentication', async () => {
    const { count } = signedIn({
      me: () => meWith({ has_password: false, mfa: MFA_OFF }),
      account: (_body, call) => (call === 1 ? reauthRequired() : ok({ user: USER })),
    });
    await openSecurity();
    const region = await card('Set a password');
    expect(
      within(region).getByText('Add a password to sign in without Discord or Google.'),
    ).toBeVisible();
    expect(within(region).queryByLabelText('Current password')).toBeNull();
    await userEvent.type(within(region).getByLabelText('New password'), 'brand-new-pass');
    await userEvent.type(within(region).getByLabelText('Confirm new password'), 'brand-new-pass');
    const reads = count('/me');
    await userEvent.click(within(region).getByRole('button', { name: 'Set password' }));
    const dialog = await screen.findByRole('dialog', { name: "Confirm it's you" }, LONG);
    await userEvent.type(within(dialog).getByLabelText('Password'), 'brand-new-pass');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Confirm' }));
    expect(await screen.findByText('Password set.', {}, LONG)).toBeVisible();
    expect(writes()).toEqual([
      { method: 'PATCH', path: '/me/account', body: { password: 'brand-new-pass' } },
      { method: 'POST', path: '/me/reauth', body: { password: 'brand-new-pass' } },
      { method: 'PATCH', path: '/me/account', body: { password: 'brand-new-pass' } },
    ]);
    await waitFor(() => expect(count('/me')).toBeGreaterThan(reads), LONG);
  }, 20000);
});

describe('Two-factor card (F9-j S5)', () => {
  it('unavailable: says so, no actions', async () => {
    signedIn({ me: () => meWith({ mfa: MFA_UNAVAILABLE }) });
    await openSecurity();
    const region = await card('Two-factor authentication');
    expect(
      await within(region).findByText(
        'Two-factor authentication is not available on this server.',
        {},
        LONG,
      ),
    ).toBeVisible();
    expect(within(region).queryAllByRole('button')).toEqual([]);
  }, 20000);

  it('off: the hint, the badge "Off" and "Turn on"', async () => {
    signedIn();
    await openSecurity();
    const region = await card('Two-factor authentication');
    expect(
      within(region).getByText('Ask for a code from an authenticator app when you sign in.'),
    ).toBeVisible();
    expect(await within(region).findByText('Off', {}, LONG)).toBeVisible();
    expect(within(region).getByRole('button', { name: 'Turn on' })).toBeEnabled();
    expect(within(region).queryByRole('button', { name: 'Turn off' })).toBeNull();
  }, 20000);

  it('on: the badge "On", the codes left (warning when 3 or fewer) and the two actions', async () => {
    signedIn({ me: () => meWith({ mfa: { ...MFA_ON, recovery_codes_left: 3 } }) });
    await openSecurity();
    const region = await card('Two-factor authentication');
    expect(await within(region).findByText('On', {}, LONG)).toBeVisible();
    const left = within(region).getByText('Recovery codes left: 3');
    expect(left.className).toMatch(/low/);
    expect(within(region).getByRole('button', { name: 'New recovery codes' })).toBeVisible();
    expect(within(region).getByRole('button', { name: 'Turn off' })).toBeVisible();
    expect(within(region).queryByRole('button', { name: 'Turn on' })).toBeNull();
  }, 20000);

  it('more than 3 codes left are not a warning', async () => {
    signedIn({ me: () => meWith({ mfa: MFA_ON }) });
    await openSecurity();
    const region = await card('Two-factor authentication');
    const left = await within(region).findByText('Recovery codes left: 8', {}, LONG);
    expect(left.className).not.toMatch(/low/);
  }, 20000);
});

describe('Two-factor wizard (F9-j S6)', () => {
  const wizard = () =>
    screen.findByRole('dialog', { name: 'Turn on two-factor authentication' }, LONG);

  async function startWizard(answers: Answers = {}) {
    const calls = signedIn(answers);
    await openSecurity();
    const region = await card('Two-factor authentication');
    await userEvent.click(await within(region).findByRole('button', { name: 'Turn on' }, LONG));
    return { ...calls, dialog: await wizard() };
  }

  it('step 1: the QR with its alt text and the key grouped by 4 as its text alternative', async () => {
    const { dialog } = await startWizard();
    expect(within(dialog).getByText('Step 1 of 3')).toBeVisible();
    const heading = within(dialog).getByRole('heading', {
      name: 'Scan the QR code with your authenticator app, or enter this key by hand.',
    });
    await waitFor(() => expect(heading).toHaveFocus());
    const qr = within(dialog).getByRole('img', { name: 'QR code for your authenticator app' });
    expect(qr).toHaveAttribute('src', SETUP.qr);
    expect(qr).toHaveAttribute('width', '220');
    const key = within(dialog).getByText(SETUP.secret);
    expect(qr.getAttribute('aria-describedby')).toBe(key.id);
    await userEvent.click(within(dialog).getByRole('button', { name: 'Copy key' }));
    expect(writeText).toHaveBeenCalledWith(SETUP.secret);
    expect(await screen.findByText(/^Copied\./)).toBeInTheDocument();
    expect(writes()).toEqual([{ method: 'POST', path: '/me/2fa/setup', body: null }]);
  }, 20000);

  it('the setup asks to confirm it is you first when needed', async () => {
    signedIn({ setup: (call) => (call === 1 ? reauthRequired() : ok(SETUP)) });
    await openSecurity();
    const region = await card('Two-factor authentication');
    await userEvent.click(await within(region).findByRole('button', { name: 'Turn on' }, LONG));
    const confirm = await screen.findByRole('dialog', { name: "Confirm it's you" }, LONG);
    await userEvent.type(within(confirm).getByLabelText('Password'), 'my-password');
    await userEvent.click(within(confirm).getByRole('button', { name: 'Confirm' }));
    expect(await wizard()).toBeVisible();
    expect(writes().map((request) => request.path)).toEqual([
      '/me/2fa/setup',
      '/me/reauth',
      '/me/2fa/setup',
    ]);
  }, 20000);

  it('step 2: a wrong code stays on the field, Back returns to step 1, a right code goes on', async () => {
    const { dialog } = await startWizard({
      enable: (body) =>
        body.code === '000000'
          ? failure(400, { error: 'Validation Error', code: 'mfa_invalid' })
          : ok({ recovery_codes: RECOVERY_CODES, revoked_sessions: 2 }),
    });
    await userEvent.click(within(dialog).getByRole('button', { name: 'Next' }));
    expect(within(dialog).getByText('Step 2 of 3')).toBeVisible();
    const heading = within(dialog).getByRole('heading', {
      name: 'Enter the 6-digit code your app shows.',
    });
    await waitFor(() => expect(heading).toHaveFocus());
    await userEvent.click(within(dialog).getByRole('button', { name: 'Back' }));
    expect(within(dialog).getByText('Step 1 of 3')).toBeVisible();
    await userEvent.click(within(dialog).getByRole('button', { name: 'Next' }));
    const code = within(dialog).getByLabelText('Code from your authenticator app');
    expect(code).toHaveAttribute('inputmode', 'numeric');
    expect(code).toHaveAttribute('autocomplete', 'one-time-code');
    await userEvent.type(code, '000000');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Turn on' }));
    expect(
      await within(dialog).findByText(
        'That code is not valid. Check your authenticator app and try again.',
        {},
        LONG,
      ),
    ).toBeVisible();
    expect(code).toHaveAttribute('aria-invalid', 'true');
    await waitFor(() => expect(code).toHaveFocus());
    await userEvent.clear(code);
    await userEvent.type(code, '123456');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Turn on' }));
    expect(await within(dialog).findByText('Step 3 of 3', {}, LONG)).toBeVisible();
    expect(writes().filter((request) => request.path === '/me/2fa/enable')).toEqual([
      { method: 'POST', path: '/me/2fa/enable', body: { code: '000000' } },
      { method: 'POST', path: '/me/2fa/enable', body: { code: '123456' } },
    ]);
  }, 20000);

  it('step 3: codes to copy and download; Done waits for the checkbox; Esc is ignored', async () => {
    const { dialog, count } = await startWizard();
    await userEvent.click(within(dialog).getByRole('button', { name: 'Next' }));
    await userEvent.type(
      within(dialog).getByLabelText('Code from your authenticator app'),
      '123456',
    );
    await userEvent.click(within(dialog).getByRole('button', { name: 'Turn on' }));
    const heading = await within(dialog).findByRole(
      'heading',
      { name: 'Save your recovery codes' },
      LONG,
    );
    await waitFor(() => expect(heading).toHaveFocus());
    expect(
      within(dialog).getByText(
        'Each code works once if you lose your phone. Keep them somewhere safe; you will not see them again.',
      ),
    ).toBeVisible();
    expect(
      within(dialog)
        .getAllByRole('listitem')
        .map((item) => item.textContent),
    ).toEqual(RECOVERY_CODES);

    await userEvent.click(within(dialog).getByRole('button', { name: 'Copy codes' }));
    expect(writeText).toHaveBeenCalledWith(RECOVERY_CODES.join('\n'));

    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    await userEvent.click(within(dialog).getByRole('button', { name: 'Download' }));
    expect(click).toHaveBeenCalledTimes(1);
    const link = click.mock.contexts[0] as HTMLAnchorElement;
    expect(link.download).toBe('rift-manager-recovery-codes.txt');
    expect(link.getAttribute('href')).toBe('blob:codes-1');
    const blob = createObjectURL.mock.calls[0][0];
    expect(await blob.text()).toBe(`${RECOVERY_CODES.join('\n')}\n`);
    await waitFor(() => expect(revokeObjectURL).toHaveBeenCalledWith('blob:codes-1'));

    const done = within(dialog).getByRole('button', { name: 'Done' });
    expect(done).toBeDisabled();
    expect(within(dialog).queryByRole('button', { name: 'Close' })).toBeNull();
    await userEvent.keyboard('{Escape}');
    expect(dialog).toHaveAttribute('open');

    const me = count('/me');
    const devices = count('/me/sessions');
    await userEvent.click(
      within(dialog).getByRole('checkbox', { name: 'I saved these codes somewhere safe' }),
    );
    expect(done).toBeEnabled();
    await userEvent.click(done);
    expect(
      await screen.findByText(
        'Two-factor authentication is on. Your other devices were signed out.',
        { selector: 'p' },
        LONG,
      ),
    ).toBeVisible();
    expect(screen.queryByRole('dialog', { name: 'Turn on two-factor authentication' })).toBeNull();
    expect(screen.queryByText(RECOVERY_CODES[0])).toBeNull();
    await waitFor(() => {
      expect(count('/me')).toBeGreaterThan(me);
      expect(count('/me/sessions')).toBeGreaterThan(devices);
    }, LONG);
  }, 30000);
});

describe('Turn off and new recovery codes (F9-j S7, S8)', () => {
  it('turn off asks for a code; a wrong one stays on the field; then it is off', async () => {
    signedIn({
      me: () => meWith({ mfa: MFA_ON }),
      disable: (body) =>
        body.code === '000000'
          ? failure(400, { error: 'Validation Error', code: 'mfa_invalid' })
          : ok({ revoked_sessions: 1 }),
    });
    await openSecurity();
    const region = await card('Two-factor authentication');
    await userEvent.click(await within(region).findByRole('button', { name: 'Turn off' }, LONG));
    const dialog = await screen.findByRole('dialog', {
      name: 'Turn off two-factor authentication?',
    });
    expect(
      within(dialog).getByText('Enter a code from your app or one of your recovery codes.'),
    ).toBeVisible();
    const code = within(dialog).getByLabelText('Code');
    expect(code).toHaveAttribute('autocomplete', 'one-time-code');
    await userEvent.type(code, '000000');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Turn off' }));
    expect(
      await within(dialog).findByText(
        'That code is not valid. Check your authenticator app and try again.',
        {},
        LONG,
      ),
    ).toBeVisible();
    expect(code).toHaveAttribute('aria-invalid', 'true');
    await userEvent.clear(code);
    await userEvent.type(code, 'abcde-fghjk');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Turn off' }));
    expect(
      await screen.findByText(
        'Two-factor authentication is off. Your other devices were signed out.',
        { selector: 'p' },
        LONG,
      ),
    ).toBeVisible();
    expect(writes().map((request) => request.body)).toEqual([
      { code: '000000' },
      { code: 'abcde-fghjk' },
    ]);
  }, 20000);

  it('new recovery codes: confirm, then the codes in their own dialog gated by the checkbox', async () => {
    signedIn({ me: () => meWith({ mfa: MFA_ON }) });
    await openSecurity();
    const region = await card('Two-factor authentication');
    await userEvent.click(
      await within(region).findByRole('button', { name: 'New recovery codes' }, LONG),
    );
    const confirm = await screen.findByRole('dialog', { name: 'Create new recovery codes?' });
    expect(
      within(confirm).getByText(
        'Your current codes stop working and your other devices are signed out.',
      ),
    ).toBeVisible();
    await userEvent.click(within(confirm).getByRole('button', { name: 'Create codes' }));
    const dialog = await screen.findByRole('dialog', { name: 'New recovery codes' }, LONG);
    expect(within(dialog).getAllByRole('listitem')).toHaveLength(10);
    const done = within(dialog).getByRole('button', { name: 'Done' });
    expect(done).toBeDisabled();
    await userEvent.keyboard('{Escape}');
    expect(dialog).toHaveAttribute('open');
    await userEvent.click(
      within(dialog).getByRole('checkbox', { name: 'I saved these codes somewhere safe' }),
    );
    await userEvent.click(done);
    await waitFor(() =>
      expect(screen.queryByRole('dialog', { name: 'New recovery codes' })).toBeNull(),
    );
    expect(writes()).toEqual([{ method: 'POST', path: '/me/2fa/recovery-codes', body: null }]);
  }, 20000);

  it('cancelling the confirmation sends nothing', async () => {
    signedIn({ me: () => meWith({ mfa: MFA_ON }) });
    await openSecurity();
    const region = await card('Two-factor authentication');
    await userEvent.click(
      await within(region).findByRole('button', { name: 'New recovery codes' }, LONG),
    );
    const confirm = await screen.findByRole('dialog', { name: 'Create new recovery codes?' });
    await userEvent.click(within(confirm).getByRole('button', { name: 'Cancel' }));
    expect(writes()).toEqual([]);
  }, 20000);
});

describe('Security states (F9-j UI, S16)', () => {
  it('a failed GET /me is an error with a retry', async () => {
    let fail = true;
    signedIn({
      me: () =>
        fail ? failure(500, { error: 'Internal Server Error', message: 'Boom' }) : meWith(),
    });
    await openSecurity();
    const alerts = await screen.findAllByRole('alert', {}, LONG);
    expect(alerts[0]).toHaveTextContent('Boom');
    fail = false;
    await userEvent.click(within(alerts[0]).getByRole('button', { name: 'Retry' }));
    expect(await card('Password')).toBeVisible();
  }, 20000);

  it('offline: the cached data stays and every action is disabled with the reason', async () => {
    signedIn({ me: () => meWith({ mfa: MFA_ON }) });
    await openSecurity();
    const region = await card('Two-factor authentication');
    await within(region).findByText('Recovery codes left: 8', {}, LONG);
    await screen.findByText('Chrome on Android', {}, LONG);
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    act(() => {
      window.dispatchEvent(new Event('offline'));
    });
    expect(
      await screen.findByText('You need a connection to make changes.', {}, LONG),
    ).toBeVisible();
    expect(within(region).getByText('Recovery codes left: 8')).toBeVisible();
    expect(within(region).getByRole('button', { name: 'Turn off' })).toBeDisabled();
    expect(within(region).getByRole('button', { name: 'New recovery codes' })).toBeDisabled();
    const password = screen.getByRole('form', { name: 'Password' });
    expect(within(password).getByLabelText('Current password')).toBeDisabled();
    expect(within(password).getByRole('button', { name: 'Change password' })).toBeDisabled();
    const devices = screen.getByRole('region', { name: 'Signed-in devices' });
    for (const button of within(devices).getAllByRole('button')) expect(button).toBeDisabled();
  }, 20000);

  it.each([PHONE, 1280])(
    'is axe clean at %i px',
    async (width) => {
      signedIn({ me: () => meWith({ mfa: MFA_ON }) });
      const { container } = await openSecurity(width);
      await screen.findByText('Chrome on Android', {}, LONG);
      await screen.findByText('Recovery codes left: 8', {}, LONG);
      expect(await axe(container)).toHaveNoViolations();
    },
    30000,
  );

  it('the wizard is axe clean', async () => {
    signedIn();
    const { container } = await openSecurity(1280);
    const region = await card('Two-factor authentication');
    await userEvent.click(await within(region).findByRole('button', { name: 'Turn on' }, LONG));
    await screen.findByRole('dialog', { name: 'Turn on two-factor authentication' }, LONG);
    expect(await axe(container)).toHaveNoViolations();
  }, 30000);
});

describe('Security layout (F9-j UI table)', () => {
  const css = rules(readCss(join(SRC_DIR, 'account/SecurityPage.module.css')));
  const value = (selector: string, prop: string, media?: string) =>
    css
      .filter(
        (rule) =>
          rule.selectors.includes(selector) &&
          (media
            ? rule.atRules.includes(`media ${media}`)
            : !rule.atRules.some((at) => at.startsWith('media'))),
      )
      .flatMap((rule) => rule.decls)
      .find((decl) => decl.prop === prop)?.value;
  const areas = (media?: string) =>
    value('.grid', 'grid-template-areas', media)?.replace(/\s+/g, ' ').trim();

  it('one column on phones, then the devices below, beside, and in a third column', () => {
    expect(areas()).toBe("'password' 'mfa' 'devices'");
    expect(areas(up('md'))).toBe("'password mfa' 'devices devices'");
    expect(areas(up('xl'))).toBe("'password devices' 'mfa devices'");
    expect(areas(up('2xl'))).toBe("'password mfa devices'");
    expect(value('.grid', 'grid-template-columns', up('2xl'))).toBe('repeat(3, minmax(0, 1fr))');
  });
});
