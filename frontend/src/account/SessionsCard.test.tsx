/** AC3 (F9-j S9): the signed-in devices card of the Security section. */
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import type { DeviceSession } from '@/api/types';
import { clearToasts } from '@/components/ui/toastStore';
import { deviceSessions, meWith } from '@/test/fixtures/security';
import { API, failure, ok, signedInSession } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';

const LONG = { timeout: 10000 };

type Sent = { method: string; path: string };
let sent: Sent[];
beforeEach(() => {
  sent = [];
});
// Toasts live in a module store: one test's toast must not show in the next.
afterEach(() => clearToasts());

type Answers = {
  items?: () => DeviceSession[];
  revokeOne?: () => Response;
  revokeOthers?: () => Response;
};

function signedIn({
  items = deviceSessions,
  revokeOne = () => ok({ revoked: 1, current: false }),
  revokeOthers = () => ok({ revoked: 2 }),
}: Answers = {}) {
  server.use(
    http.get(`${API}/auth/session`, () => signedInSession()),
    http.get(`${API}/me`, () => ok(meWith())),
    http.get(`${API}/me/sessions`, () => {
      sent.push({ method: 'GET', path: '/me/sessions' });
      return ok({ items: items() });
    }),
    http.delete(`${API}/me/sessions/:id`, ({ params }) => {
      sent.push({ method: 'DELETE', path: `/me/sessions/${String(params.id)}` });
      return revokeOne();
    }),
    http.delete(`${API}/me/sessions`, () => {
      sent.push({ method: 'DELETE', path: '/me/sessions' });
      return revokeOthers();
    }),
    http.post(`${API}/auth/logout`, () => {
      sent.push({ method: 'POST', path: '/auth/logout' });
      return ok({});
    }),
  );
}

async function openDevices(width: number) {
  const app = await renderApp({ path: '/account/security', width });
  const region = await screen.findByRole('region', { name: 'Signed-in devices' }, LONG);
  await within(region).findByText('Chrome on Android', {}, LONG);
  return { ...app, region };
}

const reads = () =>
  sent.filter((request) => request.path === '/me/sessions' && request.method === 'GET').length;
const deletes = () => sent.filter((request) => request.method === 'DELETE');

describe('Signed-in devices (F9-j S9)', () => {
  it('below 860 px: one card per device with its labels and badges', async () => {
    signedIn();
    const { region } = await openDevices(390);
    expect(within(region).getByText('Where your account is signed in now.')).toBeVisible();
    expect(within(region).queryByRole('table')).toBeNull();
    const items = within(region).getAllByRole('listitem');
    expect(items).toHaveLength(3);
    const [current, phone, tablet] = items;
    expect(within(current).getByText('Firefox on Linux')).toBeVisible();
    expect(within(current).getByText('This device')).toBeVisible();
    expect(within(current).getByText('Signed in with Password')).toBeVisible();
    expect(within(current).getByText('2FA')).toBeVisible();
    expect(within(current).getByText('Network 192.0.2.0/24')).toBeVisible();
    expect(within(current).getByText('Last active now')).toBeVisible();
    expect(within(current).getByText('Signed in 14 Nov 2026')).toBeVisible();
    expect(within(current).queryByText(/Stays signed in until/)).toBeNull();
    expect(within(phone).queryByText('This device')).toBeNull();
    expect(within(phone).queryByText('2FA')).toBeNull();
    expect(within(phone).getByText('Last active 5 minutes ago')).toBeVisible();
    expect(within(phone).getByText('Stays signed in until 1 Dec 2026')).toBeVisible();
    expect(within(tablet).getByText('Signed in with Google')).toBeVisible();
    expect(within(tablet).queryByText(/^Network/)).toBeNull();
    expect(within(tablet).getByText('Last active 20 Oct 2026')).toBeVisible();
  }, 20000);

  it('from 860 px: a table with a hidden caption and the six columns', async () => {
    signedIn();
    const { region } = await openDevices(860);
    const table = within(region).getByRole('table', { name: 'Signed-in devices' });
    expect(table.querySelector('caption')).toHaveClass('sr-only');
    expect(
      within(table)
        .getAllByRole('columnheader')
        .map((cell) => cell.textContent),
    ).toEqual(['Device', 'Method', 'Network', 'Last active', 'Signed in', 'Actions']);
    const rows = within(table).getAllByRole('row').slice(1);
    expect(rows).toHaveLength(3);
    expect(within(rows[0]).getByText('This device')).toBeVisible();
    expect(within(rows[0]).getByText('Password')).toBeVisible();
    expect(within(rows[0]).getByText('2FA')).toBeVisible();
    expect(within(rows[0]).getByText('192.0.2.0/24')).toBeVisible();
    expect(within(rows[1]).getByText('5 minutes ago')).toBeVisible();
    expect(within(rows[1]).getByText('Stays signed in until 1 Dec 2026')).toBeVisible();
    expect(within(rows[2]).getByText('Google')).toBeVisible();
  }, 20000);

  it('signs out another device after confirming, with a toast and a fresh list', async () => {
    signedIn();
    const { region } = await openDevices(390);
    const phone = within(region).getAllByRole('listitem')[1];
    const before = reads();
    await userEvent.click(within(phone).getByRole('button', { name: 'Sign out' }));
    const confirm = await screen.findByRole('dialog', { name: 'Sign out this device?' });
    expect(
      within(confirm).getByText('Chrome on Android will need to sign in again.'),
    ).toBeVisible();
    await userEvent.click(within(confirm).getByRole('button', { name: 'Sign out' }));
    expect(await screen.findByText('Device signed out.', { selector: 'p' }, LONG)).toBeVisible();
    expect(deletes()).toEqual([{ method: 'DELETE', path: '/me/sessions/4' }]);
    await waitFor(() => expect(reads()).toBeGreaterThan(before), LONG);
  }, 20000);

  it('cancelling the confirmation sends nothing', async () => {
    signedIn();
    const { region } = await openDevices(1280);
    const row = within(region).getAllByRole('row')[2];
    await userEvent.click(within(row).getByRole('button', { name: 'Sign out' }));
    const confirm = await screen.findByRole('dialog', { name: 'Sign out this device?' });
    await userEvent.click(within(confirm).getByRole('button', { name: 'Cancel' }));
    expect(deletes()).toEqual([]);
  }, 20000);

  it('a device already gone (404) refreshes the list without a toast', async () => {
    signedIn({ revokeOne: () => failure(404, { error: 'Not Found' }) });
    const { region } = await openDevices(390);
    const before = reads();
    await userEvent.click(
      within(within(region).getAllByRole('listitem')[1]).getByRole('button', { name: 'Sign out' }),
    );
    const confirm = await screen.findByRole('dialog', { name: 'Sign out this device?' });
    await userEvent.click(within(confirm).getByRole('button', { name: 'Sign out' }));
    await waitFor(() => expect(reads()).toBeGreaterThan(before), LONG);
    expect(screen.queryByText('Device signed out.', { selector: 'p' })).toBeNull();
    expect(screen.queryByRole('alert')).toBeNull();
  }, 20000);

  it('"Sign out" on this device is the logout flow', async () => {
    signedIn();
    const { region, where } = await openDevices(390);
    const current = within(region).getAllByRole('listitem')[0];
    await userEvent.click(within(current).getByRole('button', { name: 'Sign out' }));
    await waitFor(() => expect(where()).toBe('/login'), LONG);
    expect(sent).toContainEqual({ method: 'POST', path: '/auth/logout' });
    expect(deletes()).toEqual([]);
  }, 20000);

  it('signs out all other devices after confirming, with a plural toast', async () => {
    signedIn();
    const { region } = await openDevices(1280);
    await userEvent.click(
      within(region).getByRole('button', { name: 'Sign out all other devices' }),
    );
    const confirm = await screen.findByRole('dialog', { name: 'Sign out all other devices?' });
    expect(
      within(confirm).getByText('Every other browser and app will need to sign in again.'),
    ).toBeVisible();
    await userEvent.click(within(confirm).getByRole('button', { name: 'Sign out others' }));
    expect(await screen.findByText('Signed out 2 devices', { selector: 'p' }, LONG)).toBeVisible();
    expect(deletes()).toEqual([{ method: 'DELETE', path: '/me/sessions' }]);
  }, 20000);

  it('one other device is a singular toast', async () => {
    signedIn({ revokeOthers: () => ok({ revoked: 1 }) });
    const { region } = await openDevices(390);
    await userEvent.click(
      within(region).getByRole('button', { name: 'Sign out all other devices' }),
    );
    const confirm = await screen.findByRole('dialog', { name: 'Sign out all other devices?' });
    await userEvent.click(within(confirm).getByRole('button', { name: 'Sign out others' }));
    expect(await screen.findByText('Signed out 1 device', { selector: 'p' }, LONG)).toBeVisible();
  }, 20000);

  it('with only this device there is no "Sign out all other devices"', async () => {
    signedIn({ items: () => deviceSessions().slice(0, 1) });
    await renderApp({ path: '/account/security', width: 390 });
    const region = await screen.findByRole('region', { name: 'Signed-in devices' }, LONG);
    await within(region).findByText('Firefox on Linux', {}, LONG);
    expect(within(region).queryByRole('button', { name: 'Sign out all other devices' })).toBeNull();
  }, 20000);
});
