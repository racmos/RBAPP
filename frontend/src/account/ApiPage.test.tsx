/** AC4 (F9-j S10, S11, S15, S16): the API section. */
import { join } from 'node:path';
import { act, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';
import type { ApiKeyInfo } from '@/api/types';
import { up } from '@/lib/breakpoints';
import { SRC_DIR, readCss, rules } from '@/test/css';
import { API_KEY_INFO, NEW_KEY, meWith } from '@/test/fixtures/security';
import { API, failure, ok, signedInSession } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { clearToasts } from '@/components/ui/toastStore';
import { renderApp } from '@/test/renderApp';

const LONG = { timeout: 10000 };
const FRESH: ApiKeyInfo = {
  prefix: 'rb_live_ffeedd',
  created_at: '2026-11-15T10:00:00Z',
  last_used_at: null,
};

type Sent = { method: string; path: string };
let sent: Sent[];
let writeText: ReturnType<typeof vi.fn>;
beforeEach(() => {
  sent = [];
  writeText = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
});
afterEach(() => {
  vi.restoreAllMocks();
  // A test that went offline tells TanStack Query's online manager it is back.
  window.dispatchEvent(new Event('online'));
  // Toasts live in a module store: one test's toast must not show in the next.
  clearToasts();
});

function signedIn({
  key = null as ApiKeyInfo | null,
  create = [() => ok({ key: NEW_KEY, api_key: FRESH }, 201)] as Array<() => Response>,
} = {}) {
  let current = key;
  let creates = 0;
  server.use(
    http.get(`${API}/auth/session`, () => signedInSession()),
    http.get(`${API}/me`, () => ok(meWith({ api_key: current }))),
    http.get(`${API}/me/api-key`, () => {
      sent.push({ method: 'GET', path: '/me/api-key' });
      return ok({ api_key: current });
    }),
    http.post(`${API}/me/api-key`, () => {
      sent.push({ method: 'POST', path: '/me/api-key' });
      const answer = create[Math.min(creates, create.length - 1)]();
      creates += 1;
      if (answer.status === 201) current = FRESH;
      return answer;
    }),
    http.delete(`${API}/me/api-key`, () => {
      sent.push({ method: 'DELETE', path: '/me/api-key' });
      current = null;
      return ok({ api_key: null });
    }),
    http.post(`${API}/me/reauth`, () => {
      sent.push({ method: 'POST', path: '/me/reauth' });
      return ok({ reauth_until: '2026-11-15T12:10:00Z' });
    }),
  );
}

async function openApi(width = 390) {
  const app = await renderApp({ path: '/account/api', width });
  await screen.findByRole('heading', { level: 1, name: 'API' }, LONG);
  const region = await screen.findByRole('region', { name: 'API key' }, LONG);
  return { ...app, region };
}

const writes = () => sent.filter((request) => request.method !== 'GET');

describe('API key card (F9-j S10)', () => {
  it('without a key: the intro, "You have no API key." and "Create key"', async () => {
    signedIn();
    const { region } = await openApi();
    expect(
      within(region).getByText(
        "A personal key to read your data (collection, decks, wishlists, products) from scripts and other tools. It can't change anything or open your account settings.",
      ),
    ).toBeVisible();
    expect(await within(region).findByText('You have no API key.', {}, LONG)).toBeVisible();
    expect(within(region).getByRole('button', { name: 'Create key' })).toBeEnabled();
    expect(within(region).queryByRole('button', { name: 'Revoke key' })).toBeNull();
  }, 20000);

  it('with a key: its prefix, dates and the two actions', async () => {
    signedIn({ key: { ...API_KEY_INFO, last_used_at: '2026-11-12T08:00:00Z' } });
    const { region } = await openApi();
    expect(await within(region).findByText('Key rb_live_a1b2c3…', {}, LONG)).toBeVisible();
    expect(within(region).getByText('Created 10 Nov 2026')).toBeVisible();
    expect(within(region).getByText(/^Last used /)).toBeVisible();
    expect(within(region).getByRole('button', { name: 'Replace key' })).toBeVisible();
    expect(within(region).getByRole('button', { name: 'Revoke key' })).toBeVisible();
  }, 20000);

  it('a key never used says so', async () => {
    signedIn({ key: API_KEY_INFO });
    const { region } = await openApi();
    expect(await within(region).findByText('Never used', {}, LONG)).toBeVisible();
  }, 20000);

  it('creates a key through re-authentication and shows it once; Done drops it', async () => {
    signedIn({
      create: [
        () =>
          failure(403, {
            error: 'Forbidden',
            code: 'reauth_required',
            params: { methods: ['password'] },
          }),
        () => ok({ key: NEW_KEY, api_key: FRESH }, 201),
      ],
    });
    const { region } = await openApi();
    await userEvent.click(await within(region).findByRole('button', { name: 'Create key' }, LONG));
    const confirm = await screen.findByRole('dialog', { name: "Confirm it's you" }, LONG);
    await userEvent.type(within(confirm).getByLabelText('Password'), 'my-password');
    await userEvent.click(within(confirm).getByRole('button', { name: 'Confirm' }));
    const dialog = await screen.findByRole('dialog', { name: 'Your new API key' }, LONG);
    const field = within(dialog).getByLabelText('API key');
    expect(field).toHaveValue(NEW_KEY);
    expect(field).toHaveAttribute('readonly');
    expect(within(dialog).getByText('Copy it now. You will not see it again.')).toBeVisible();
    await userEvent.click(within(dialog).getByRole('button', { name: 'Copy key' }));
    expect(writeText).toHaveBeenCalledWith(NEW_KEY);
    expect(await screen.findByText(/^Copied\./)).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole('button', { name: 'Done' }));
    await waitFor(() =>
      expect(screen.queryByRole('dialog', { name: 'Your new API key' })).toBeNull(),
    );
    expect(screen.queryByDisplayValue(NEW_KEY)).toBeNull();
    expect(document.body.textContent).not.toContain(NEW_KEY);
    expect(await within(region).findByText('Key rb_live_ffeedd…', {}, LONG)).toBeVisible();
    expect(writes()).toEqual([
      { method: 'POST', path: '/me/api-key' },
      { method: 'POST', path: '/me/reauth' },
      { method: 'POST', path: '/me/api-key' },
    ]);
  }, 20000);

  it('replace asks first; cancelling sends nothing', async () => {
    signedIn({ key: API_KEY_INFO });
    const { region } = await openApi();
    await userEvent.click(await within(region).findByRole('button', { name: 'Replace key' }, LONG));
    let confirm = await screen.findByRole('dialog', { name: 'Replace your API key?' });
    expect(within(confirm).getByText('The current key stops working at once.')).toBeVisible();
    await userEvent.click(within(confirm).getByRole('button', { name: 'Cancel' }));
    expect(writes()).toEqual([]);
    await userEvent.click(within(region).getByRole('button', { name: 'Replace key' }));
    confirm = await screen.findByRole('dialog', { name: 'Replace your API key?' });
    await userEvent.click(within(confirm).getByRole('button', { name: 'Replace' }));
    expect(await screen.findByRole('dialog', { name: 'Your new API key' }, LONG)).toBeVisible();
    expect(writes()).toEqual([{ method: 'POST', path: '/me/api-key' }]);
  }, 20000);

  it('revoke asks first, then the card has no key and a toast says so', async () => {
    signedIn({ key: API_KEY_INFO });
    const { region } = await openApi();
    await userEvent.click(await within(region).findByRole('button', { name: 'Revoke key' }, LONG));
    const confirm = await screen.findByRole('dialog', { name: 'Revoke your API key?' });
    expect(within(confirm).getByText('Scripts using it stop working at once.')).toBeVisible();
    await userEvent.click(within(confirm).getByRole('button', { name: 'Revoke' }));
    expect(await screen.findByText('API key revoked.', { selector: 'p' }, LONG)).toBeVisible();
    expect(await within(region).findByText('You have no API key.', {}, LONG)).toBeVisible();
    expect(writes()).toEqual([{ method: 'DELETE', path: '/me/api-key' }]);
  }, 20000);

  it('offline: the cached key stays and the actions are disabled with the reason', async () => {
    signedIn({ key: API_KEY_INFO });
    const { region } = await openApi();
    await within(region).findByText('Key rb_live_a1b2c3…', {}, LONG);
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    act(() => {
      window.dispatchEvent(new Event('offline'));
    });
    expect(
      await screen.findByText('You need a connection to make changes.', {}, LONG),
    ).toBeVisible();
    expect(within(region).getByText('Key rb_live_a1b2c3…')).toBeVisible();
    expect(within(region).getByRole('button', { name: 'Replace key' })).toBeDisabled();
    expect(within(region).getByRole('button', { name: 'Revoke key' })).toBeDisabled();
  }, 20000);
});

describe('API example (F9-j S11)', () => {
  it('uses the runtime origin and a placeholder key, and copies it', async () => {
    signedIn();
    await openApi();
    const example = await screen.findByRole('region', { name: 'Example' }, LONG);
    const command = `curl -H "Authorization: Bearer rb_live_<your key>" ${window.location.origin}/riftbound/api/v1/collection`;
    expect(within(example).getByText(command)).toBeVisible();
    expect(
      within(example).getByText('Only GET requests are allowed. Limit: 60 requests per minute.'),
    ).toBeVisible();
    await userEvent.click(within(example).getByRole('button', { name: 'Copy' }));
    expect(writeText).toHaveBeenCalledWith(command);
  }, 20000);

  it('sits under the key card, and beside it from 1600 px', async () => {
    const css = rules(readCss(join(SRC_DIR, 'account/SecurityPage.module.css')));
    const columns = (media?: string) =>
      css
        .filter(
          (rule) =>
            rule.selectors.includes('.apiGrid') &&
            (media
              ? rule.atRules.includes(`media ${media}`)
              : !rule.atRules.some((at) => at.startsWith('media'))),
        )
        .flatMap((rule) => rule.decls)
        .find((decl) => decl.prop === 'grid-template-columns')?.value;
    expect(columns()).toBeUndefined();
    expect(columns(up('xl'))).toBeUndefined();
    expect(columns(up('2xl'))).toBe('repeat(2, minmax(0, 1fr))');
    signedIn();
    await openApi(1600);
    const key = screen.getByRole('region', { name: 'API key' });
    const example = await screen.findByRole('region', { name: 'Example' }, LONG);
    expect(key.parentElement).toBe(example.parentElement);
    expect(key.parentElement?.className).toMatch(/apiGrid/);
  }, 20000);

  it.each([390, 1280])(
    'is axe clean at %i px',
    async (width) => {
      signedIn({ key: API_KEY_INFO });
      const { container, region } = await openApi(width);
      await within(region).findByText('Key rb_live_a1b2c3…', {}, LONG);
      expect(await axe(container)).toHaveNoViolations();
    },
    30000,
  );
});
