import { join } from 'node:path';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { delay, http } from 'msw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';
import type { MeData, Session } from '@/api/types';
import { clearToasts } from '@/components/ui/toastStore';
import { up } from '@/lib/breakpoints';
import { SRC_DIR, readCss, rules } from '@/test/css';
import {
  API,
  ME,
  NO_PREFS,
  USER,
  USER_TOKEN,
  failure,
  ok,
  signedInSession,
} from '@/test/msw/handlers';
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
  // Toasts live in a module store: one test's toast must not show in the next.
  clearToasts();
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
const emailInput = () => within(emailForm()).getByLabelText('Email');
const saveEmail = () => within(emailForm()).getByRole('button', { name: 'Save email' });

describe('Profile page (/account/profile)', () => {
  it('shows the username and the current email', async () => {
    signedIn();
    await openPage();
    const identity = await screen.findByRole('region', { name: 'Identity' }, LONG);
    expect(within(identity).getByText('@ada')).toBeVisible();
    expect(emailInput()).toHaveValue('ada@example.com');
    expect(emailInput()).toHaveAttribute('type', 'email');
    expect(emailInput()).toHaveAttribute('autocomplete', 'email');
    expect(saveEmail()).toBeDisabled();
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
  }, 20000);

  it('offline: every input and button is disabled', async () => {
    signedIn();
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    await openPage();
    expect(emailInput()).toBeDisabled();
    expect(saveEmail()).toBeDisabled();
    // F9-i S12: the new cards are read-only too, with the identity from the session
    const identity = screen.getByRole('region', { name: 'Identity' });
    expect(within(identity).getByText('@ada')).toBeVisible();
    expect(within(identity).getByRole('button', { name: 'Change photo' })).toBeDisabled();
    const details = screen.getByRole('form', { name: 'Details' });
    for (const control of within(details).getAllByRole('textbox')) {
      expect(control).toBeDisabled();
    }
    expect(within(details).getByRole('combobox', { name: 'Country' })).toBeDisabled();
    expect(within(details).getByRole('button', { name: 'Save details' })).toBeDisabled();
  }, 20000);

  it('links to the interface section from its section navigation', async () => {
    signedIn();
    await openPage();
    const nav = screen.getByRole('navigation', { name: 'Account sections' });
    expect(within(nav).getByRole('link', { name: 'Interface' })).toHaveAttribute(
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

// --- F9-i: identity, details, email removal, layout and states (AC2) ---

type MeOverrides = { user?: Partial<typeof USER>; profile?: Partial<MeData['profile']> };
const mePatches: Array<Record<string, unknown>> = [];
beforeEach(() => {
  mePatches.length = 0;
});

/** Signed in, with `GET /me` built from `ME`; `PATCH /me` echoes the changes (`""` clears). */
function withProfile({ user = {}, profile = {} }: MeOverrides = {}) {
  const sessionUser = { ...USER, ...user };
  let current = {
    ...ME,
    user: sessionUser,
    profile: { ...ME.profile, ...profile },
  } as MeData;
  signedIn();
  server.use(
    http.get(`${API}/auth/session`, () =>
      ok({ authenticated: true, csrf_token: USER_TOKEN, user: sessionUser, prefs: NO_PREFS }),
    ),
    http.get(`${API}/me`, () => ok(current)),
    http.patch(`${API}/me`, async ({ request }) => {
      const body = (await request.json()) as Record<string, string | null>;
      mePatches.push(body);
      const cleared = Object.fromEntries(
        Object.entries(body).map(([key, value]) => [key, value ? value : null]),
      );
      const nextProfile = { ...current.profile, ...cleared };
      current = {
        ...current,
        profile: nextProfile,
        user: { ...current.user, display_name: nextProfile.display_name },
      };
      return ok(current);
    }),
  );
}

const detailsForm = () => screen.getByRole('form', { name: 'Details' });
const saveDetails = () => within(detailsForm()).getByRole('button', { name: 'Save details' });

async function openProfile(width = PHONE) {
  const app = await openPage(width);
  await screen.findByRole('form', { name: 'Details' }, LONG);
  return app;
}

describe('Profile layout (F9-i S3)', () => {
  const css = rules(readCss(join(SRC_DIR, 'account/ProfilePage.module.css')));
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

  it('one column on phones, two from md, three from 2xl', () => {
    expect(value('.columns', 'grid-template-columns')).toBeUndefined();
    expect(value('.columns', 'grid-template-columns', up('md'))).toBe('repeat(2, minmax(0, 1fr))');
    expect(value('.columns', 'grid-template-columns', up('2xl'))).toBe('repeat(3, minmax(0, 1fr))');
    // From 2xl the identity and details cards become columns of their own.
    expect(value('.stack', 'display', up('2xl'))).toBe('contents');
  });

  it('stacks Identity + Details beside Email, in that order; no password card (F9-j S1)', async () => {
    withProfile();
    await openProfile(1280);
    const parent = (name: string) =>
      screen.getByRole('region', { name }).parentElement as HTMLElement;
    expect(parent('Identity')).toBe(parent('Details'));
    expect(parent('Identity')).not.toBe(parent('Email'));
    expect(parent('Identity').parentElement).toBe(parent('Email').parentElement);
    const order = screen
      .getAllByRole('region')
      .map((region) => region.getAttribute('aria-labelledby'))
      .map((id) => document.getElementById(id ?? '')?.textContent);
    expect(order).toEqual(['Identity', 'Details', 'Email']);
  }, 20000);
});

describe('Identity card (F9-i S4)', () => {
  it('shows the initials, the username, the member date and only "Change photo"', async () => {
    withProfile();
    await openProfile();
    const card = within(screen.getByRole('region', { name: 'Identity' }));
    expect(card.getByRole('img', { name: 'Profile photo of ada' })).toHaveTextContent('AD');
    expect(card.getByText('ada')).toBeVisible();
    expect(card.getByText('@ada')).toBeVisible();
    expect(card.getByText('Member since 5 Mar 2026')).toBeVisible();
    expect(card.getByRole('button', { name: 'Change photo' })).toBeEnabled();
    expect(card.queryByRole('button', { name: 'Remove photo' })).toBeNull();
    expect(
      card.getByText('JPEG, PNG, WebP or GIF, up to 5 MB. It is cropped to a square.'),
    ).toBeVisible();
  }, 20000);

  it('shows the display name and the photo, and offers to remove it', async () => {
    const avatar = '/riftbound/api/v1/users/7/avatar?v=3';
    withProfile({
      user: { display_name: 'Ada L.', avatar_url: avatar },
      profile: { display_name: 'Ada L.', avatar_url: avatar },
    });
    await openProfile();
    const card = within(screen.getByRole('region', { name: 'Identity' }));
    const img = card.getByRole('img', { name: 'Profile photo of Ada L.' });
    expect(img).toHaveAttribute('src', `${avatar}&size=256`);
    expect(card.getByText('Ada L.')).toBeVisible();
    expect(card.getByText('@ada')).toBeVisible();
    expect(card.getByRole('button', { name: 'Remove photo' })).toBeEnabled();
  }, 20000);
});

describe('Details card (F9-i S7)', () => {
  it('shows the saved values and the privacy hint; save only after a change', async () => {
    withProfile({ profile: { display_name: 'Ada L.', bio: 'Hi', country: 'ES', city: 'Madrid' } });
    await openProfile();
    const form = within(detailsForm());
    expect(
      screen.getByText(
        'Your display name and photo are shown to signed-in users. Your bio, country and city are only for you.',
      ),
    ).toBeVisible();
    expect(form.getByLabelText('Display name')).toHaveValue('Ada L.');
    expect(form.getByLabelText('Display name')).toHaveAccessibleDescription(
      'Up to 40 characters. Empty shows your username.',
    );
    expect(form.getByLabelText('Bio')).toHaveValue('Hi');
    expect(form.getByRole('combobox', { name: 'Country' })).toHaveValue('ES');
    expect(form.getByLabelText('City')).toHaveValue('Madrid');
    expect(saveDetails()).toBeDisabled();
    await userEvent.type(form.getByLabelText('City'), 'x');
    expect(saveDetails()).toBeEnabled();
    await userEvent.type(form.getByLabelText('City'), '{Backspace}');
    expect(saveDetails()).toBeDisabled();
  }, 20000);

  it('lists the countries by English name after "Not set"; the code when there is no name', async () => {
    withProfile();
    server.use(
      http.get(`${API}/meta/config`, () =>
        ok({
          env: 'test',
          registration_open: true,
          captcha: { provider: 'none', required_for: [] },
          csrf: { header: 'X-CSRFToken' },
          countries: ['AA', 'ES', 'FR', 'GB', 'US'],
        }),
      ),
    );
    await openProfile();
    const select = within(detailsForm()).getByRole('combobox', { name: 'Country' });
    await waitFor(() => expect(within(select).getAllByRole('option')).toHaveLength(6), LONG);
    expect(
      within(select)
        .getAllByRole('option')
        .map((option) => option.textContent),
    ).toEqual(['Not set', 'AA', 'France', 'Spain', 'United Kingdom', 'United States']);
    expect(within(select).getByRole('option', { name: 'Spain' })).toHaveValue('ES');
    expect(within(select).getByRole('option', { name: 'Not set' })).toHaveValue('');
  }, 20000);

  it('sends only the changed fields, "" for a cleared one, and updates the session', async () => {
    withProfile({ profile: { display_name: null, city: 'Madrid' } });
    const { queryClient } = await openProfile();
    const form = within(detailsForm());
    await userEvent.type(form.getByLabelText('Display name'), 'Ada L.');
    await userEvent.selectOptions(form.getByRole('combobox', { name: 'Country' }), 'ES');
    await userEvent.clear(form.getByLabelText('City'));
    await userEvent.click(saveDetails());
    expect(await screen.findByText('Details saved.', {}, LONG)).toBeVisible();
    expect(mePatches).toEqual([{ display_name: 'Ada L.', country: 'ES', city: '' }]);
    expect(queryClient.getQueryData<Session>(['session'])?.user?.display_name).toBe('Ada L.');
    await waitFor(() => expect(saveDetails()).toBeDisabled());
    expect(
      within(screen.getByRole('region', { name: 'Identity' })).getByText('Ada L.'),
    ).toBeVisible();
  }, 20000);

  it('shows "Saving…" while the change is sent', async () => {
    withProfile();
    server.use(
      http.patch(`${API}/me`, async () => {
        await delay(300);
        return ok(ME);
      }),
    );
    await openProfile();
    await userEvent.type(within(detailsForm()).getByLabelText('City'), 'Rome');
    await userEvent.click(saveDetails());
    expect(
      await within(detailsForm()).findByRole('button', { name: 'Saving…' }, LONG),
    ).toBeVisible();
  }, 20000);

  it('counts the bio characters, tied to the field', async () => {
    withProfile({ profile: { bio: 'Hello' } });
    await openProfile();
    const bio = within(detailsForm()).getByLabelText('Bio');
    expect(bio.tagName).toBe('TEXTAREA');
    expect(bio).toHaveAccessibleDescription('5 of 240 characters');
    await userEvent.type(bio, '!');
    expect(bio).toHaveAccessibleDescription('6 of 240 characters');
  }, 20000);

  it('refuses values over the limits without a request and focuses the first one', async () => {
    withProfile();
    await openProfile();
    const form = within(detailsForm());
    await userEvent.click(form.getByLabelText('Display name'));
    await userEvent.paste('x'.repeat(41));
    await userEvent.click(form.getByLabelText('Bio'));
    await userEvent.paste('y'.repeat(241));
    await userEvent.click(form.getByLabelText('City'));
    await userEvent.paste('z'.repeat(81));
    await userEvent.click(saveDetails());
    expect(await form.findByText('Must be at most 40 characters.')).toBeVisible();
    expect(form.getByText('Must be at most 240 characters.')).toBeVisible();
    expect(form.getByText('Must be at most 80 characters.')).toBeVisible();
    expect(form.getByLabelText('Display name')).toHaveAttribute('aria-invalid', 'true');
    expect(form.getByLabelText('Bio')).toHaveAttribute('aria-invalid', 'true');
    expect(form.getByLabelText('City')).toHaveAttribute('aria-invalid', 'true');
    await waitFor(() => expect(form.getByLabelText('Display name')).toHaveFocus());
    expect(mePatches).toEqual([]);
  }, 20000);

  it('shows the server details on their fields and focuses the first', async () => {
    withProfile();
    server.use(
      http.patch(`${API}/me`, () =>
        failure(400, {
          error: 'Validation Error',
          code: 'validation_error',
          details: [
            {
              field: 'city',
              message: 'String should have at most 80 characters',
              type: 'string_too_long',
              code: 'too_long',
              params: { max: 80 },
            },
          ],
        }),
      ),
    );
    await openProfile();
    const form = within(detailsForm());
    await userEvent.type(form.getByLabelText('City'), 'Rome');
    await userEvent.click(saveDetails());
    expect(await form.findByText('Must be at most 80 characters.', {}, LONG)).toBeVisible();
    expect(form.getByLabelText('City')).toHaveAttribute('aria-invalid', 'true');
    await waitFor(() => expect(form.getByLabelText('City')).toHaveFocus());
  }, 20000);

  it('any other failure is a form alert', async () => {
    withProfile();
    server.use(
      http.patch(`${API}/me`, () =>
        failure(500, { error: 'Internal Server Error', message: 'Boom' }),
      ),
    );
    await openProfile();
    await userEvent.type(within(detailsForm()).getByLabelText('City'), 'Rome');
    await userEvent.click(saveDetails());
    expect(await within(detailsForm()).findByRole('alert', {}, LONG)).toHaveTextContent('Boom');
  }, 20000);
});

describe('Email card (F9-i S8)', () => {
  it('an emptied email offers "Remove email" and removes it after confirming', async () => {
    signedIn((body) => ok({ user: { ...USER, email: body.email ?? null } }));
    const { queryClient } = await openPage();
    await userEvent.clear(emailInput());
    expect(within(emailForm()).queryByRole('button', { name: 'Save email' })).toBeNull();
    await userEvent.click(within(emailForm()).getByRole('button', { name: 'Remove email' }));
    const dialog = await screen.findByRole('dialog', { name: 'Remove your email?' }, LONG);
    expect(
      within(dialog).getByText(
        'Your account will have no email address. There is no password recovery by email either way.',
      ),
    ).toBeVisible();
    await userEvent.click(within(dialog).getByRole('button', { name: 'Remove' }));
    expect(await screen.findByText('Email removed.', {}, LONG)).toBeVisible();
    expect(patches).toEqual([{ email: null }]);
    expect(queryClient.getQueryData<Session>(['session'])?.user?.email).toBeNull();
    expect(await within(emailForm()).findByText('No email on file.')).toBeVisible();
  }, 20000);

  it('cancelling the removal sends nothing and keeps the field', async () => {
    signedIn();
    await openPage();
    await userEvent.clear(emailInput());
    await userEvent.click(within(emailForm()).getByRole('button', { name: 'Remove email' }));
    const dialog = await screen.findByRole('dialog', { name: 'Remove your email?' }, LONG);
    await userEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(patches).toEqual([]);
    expect(emailInput()).toHaveValue('');
  }, 20000);

  it('without an email on file says so above the field; the field is optional', async () => {
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
    expect(within(emailForm()).getByText('No email on file.')).toBeVisible();
    expect(emailInput()).not.toBeRequired();
    expect(within(emailForm()).queryByRole('button', { name: 'Remove email' })).toBeNull();
  }, 20000);
});

describe('Profile states (F9-i S12)', () => {
  it('shows skeletons while the profile loads, the section navigation stays', async () => {
    signedIn();
    server.use(
      http.get(`${API}/me`, async () => {
        await delay('infinite');
        return ok(ME);
      }),
    );
    await openPage();
    expect(screen.getAllByText('Loading content').length).toBeGreaterThan(0);
    expect(screen.queryByRole('form', { name: 'Details' })).toBeNull();
    expect(screen.getByRole('navigation', { name: 'Account sections' })).toBeVisible();
    // The email card does not wait for the profile.
    expect(emailForm()).toBeVisible();
  }, 20000);

  it('shows an error with a retry that loads the profile', async () => {
    signedIn();
    let calls = 0;
    server.use(
      http.get(`${API}/me`, () => {
        calls += 1;
        return calls === 1
          ? failure(500, { error: 'Internal Server Error', message: 'Boom' })
          : ok(ME);
      }),
    );
    await openPage();
    const alert = await screen.findByRole('alert', {}, LONG);
    expect(alert).toHaveTextContent('Boom');
    expect(screen.getByRole('navigation', { name: 'Account sections' })).toBeVisible();
    await userEvent.click(within(alert).getByRole('button', { name: 'Retry' }));
    expect(await screen.findByRole('form', { name: 'Details' }, LONG)).toBeVisible();
  }, 20000);
});
