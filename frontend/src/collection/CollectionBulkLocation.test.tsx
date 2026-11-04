import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { axe } from 'vitest-axe';
import type { CollectionGroup, CollectionLine } from '@/api/types';
import { clearToasts, getToasts } from '@/components/ui/toastStore';
import { aylaGroup, collectionMeta, emberGroup, runeGroup } from '@/test/fixtures/collection';
import { recordRequests, signedIn, withLocations, writes } from '@/test/locations';
import { API } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';

const LONG = { timeout: 10000 };
const binder = { location_id: 11, code: 'B001-F001-P0001', description: 'Red binder' };

const placed = (line: CollectionLine, qty: number, unassigned = 0): CollectionLine => ({
  ...line,
  locations: qty ? [{ ...binder, qty }] : [],
  locations_more: 0,
  unassigned,
});

/** Ayla 1201 in the binder, Ayla 1202 unassigned; Ember and the rune in the binder. */
const groups: CollectionGroup[] = [
  { ...aylaGroup, lines: [placed(aylaGroup.lines[0], 3), placed(aylaGroup.lines[1], 0, 1)] },
  { ...emberGroup, lines: [placed(emberGroup.lines[0], 2)] },
  { ...runeGroup, lines: [placed(runeGroup.lines[0], 10)] },
];

beforeEach(() => {
  clearToasts();
  signedIn();
  withLocations();
  server.use(
    http.get(`${API}/collection`, () =>
      HttpResponse.json({
        success: true,
        data: { items: groups },
        meta: { ...collectionMeta, total_groups: groups.length },
      }),
    ),
  );
});
afterEach(() => server.events.removeAllListeners());

async function open(width = 1280) {
  const sent = recordRequests();
  const app = await renderApp({ path: '/collection', width });
  await screen.findByRole('table', { name: 'Your collection grouped by card' }, LONG);
  return { ...app, sent };
}

const box = (name: string) => screen.getByRole('checkbox', { name });
const bar = () => within(screen.getByRole('region', { name: /selected$/ }));
const bulkBody = (sent: ReturnType<typeof recordRequests>) =>
  writes(sent).find((r) => r.path === '/collection/bulk')?.body;

async function selectAll() {
  await userEvent.click(box('Select all on this page'));
  await screen.findByText('4 lines selected');
}

async function applyAndConfirm(expected?: string) {
  await userEvent.click(bar().getByRole('button', { name: 'Apply' }));
  const dialog = await screen.findByRole('dialog', { name: 'Apply' });
  if (expected) expect(within(dialog).getByText(expected)).toBeVisible();
  await userEvent.click(within(dialog).getByRole('button', { name: 'Apply' }));
}

describe.each([1280, 1700])('bulk location at %i px (F16-x)', (width) => {
  it('offers "Keep current locations" first and by default, the locations in order, then Unassigned', async () => {
    await open(width);
    await selectAll();
    const select = bar().getByRole('combobox', { name: 'Location' }) as HTMLSelectElement;
    await waitFor(() => expect(select.options).toHaveLength(5), LONG);
    expect([...select.options].map((option) => option.textContent)).toEqual([
      'Keep current locations',
      'B001-F001-P0001',
      'B001-F001-P0002',
      'DECK-001',
      'Unassigned',
    ]);
    expect(select.value).toBe('');
    // the locked box and the mounted deck cannot be chosen
    expect([...select.options].map((option) => option.disabled)).toEqual([
      false,
      false,
      true,
      true,
      false,
    ]);
  }, 30000);

  it('says the lines keep their places when they are in more than one', async () => {
    await open(width);
    await selectAll();
    const select = bar().getByRole('combobox', { name: 'Location' });
    const hint = bar().getByText('Mixed: lines keep their locations unless you pick one');
    expect(hint).toBeVisible();
    expect(select).toHaveAccessibleDescription(
      'Mixed: lines keep their locations unless you pick one',
    );
  }, 30000);

  it('has no "mixed" hint when every selected line is in the same place', async () => {
    await open(width);
    await userEvent.click(box('Select Ember Wisp'));
    await userEvent.click(box('Select Fury Rune'));
    await screen.findByText('2 lines selected');
    expect(bar().queryByText(/^Mixed:/)).toBeNull();
  }, 30000);

  it('a language change alone sends no location', async () => {
    const { sent } = await open(width);
    await selectAll();
    await userEvent.selectOptions(bar().getByLabelText('Language'), 'German');
    await applyAndConfirm('Apply the changes to 4 lines?');
    await waitFor(() => expect(bulkBody(sent)).toBeDefined(), LONG);
    expect(bulkBody(sent)).toEqual({
      ids: [1201, 1202, 1301, 1401],
      set: { language: 'German' },
    });
    expect(bulkBody(sent)!.set).not.toHaveProperty('location_id');
  }, 30000);

  it('a chosen location moves every copy there, with the language, and refreshes the locations', async () => {
    const { sent } = await open(width);
    await selectAll();
    await waitFor(
      () =>
        expect(sent.filter((r) => r.method === 'GET' && r.path === '/locations')).toHaveLength(1),
      LONG,
    );
    await userEvent.selectOptions(bar().getByLabelText('Language'), 'French');
    await userEvent.selectOptions(bar().getByLabelText('Location'), 'B001-F001-P0001');
    await applyAndConfirm('Apply the changes to 4 lines? All their copies go to B001-F001-P0001.');
    await waitFor(() => expect(bulkBody(sent)).toBeDefined(), LONG);
    expect(bulkBody(sent)).toEqual({
      ids: [1201, 1202, 1301, 1401],
      set: { language: 'French', location_id: 11 },
    });
    expect((await screen.findAllByText('Changes applied.')).length).toBeGreaterThan(0);
    await waitFor(
      () =>
        expect(
          sent.filter((r) => r.method === 'GET' && r.path === '/locations').length,
        ).toBeGreaterThan(1),
      LONG,
    );
    await waitFor(
      () =>
        expect(
          sent.filter((r) => r.method === 'GET' && r.path === '/collection').length,
        ).toBeGreaterThan(1),
      LONG,
    );
  }, 30000);

  it('"Unassigned" takes every copy out of its locations', async () => {
    const { sent } = await open(width);
    await selectAll();
    await userEvent.selectOptions(bar().getByLabelText('Location'), 'Unassigned');
    await applyAndConfirm('Apply the changes to 4 lines? All their copies become unassigned.');
    await waitFor(() => expect(bulkBody(sent)).toBeDefined(), LONG);
    expect(bulkBody(sent)).toEqual({ ids: [1201, 1202, 1301, 1401], set: { location_id: null } });
  }, 30000);

  it('shows the locked locations in the bar when the server refuses', async () => {
    server.use(
      http.post(`${API}/collection/bulk`, () =>
        HttpResponse.json(
          {
            success: false,
            error: 'Conflict',
            message: 'Locked locations cannot change: B001-F001-P0002. Unlock them first.',
            code: 'location_locked',
            params: { codes: 'B001-F001-P0002' },
          },
          { status: 409 },
        ),
      ),
    );
    await open(width);
    await selectAll();
    await userEvent.selectOptions(bar().getByLabelText('Location'), 'Unassigned');
    await applyAndConfirm();
    const alert = await bar().findByRole('alert', {}, LONG);
    expect(alert).toHaveTextContent(
      "Locked locations can't change: B001-F001-P0002. Unlock them first.",
    );
    // the message is in the bar, not in a toast
    expect(getToasts()).toHaveLength(0);
  }, 30000);

  it('is axe clean with the location field and the hint', async () => {
    const { container } = await open(width);
    await selectAll();
    await bar().findByText('Mixed: lines keep their locations unless you pick one');
    expect(await axe(container)).toHaveNoViolations();
  }, 30000);
});
