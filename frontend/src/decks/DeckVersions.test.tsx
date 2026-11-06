import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';
import type { DeckContentV2, DeckDetail, DeckVersionItem } from '@/api/types';
import { recordDeckRequests } from '@/test/decks';
import {
  battlefields,
  deckDetail,
  listItemOf,
  mainCards,
  rivenContent,
  sideCards,
} from '@/test/fixtures/decks';
import { signedIn, writes } from '@/test/locations';
import { API, failure, ok } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';

const LONG = { timeout: 10000 };
const SAVE = { timeout: 5000 };

afterEach(() => {
  vi.restoreAllMocks();
  server.events.removeAllListeners();
});

/** Version 1: two copies of Discipline and only two battlefields. */
const firstContent: DeckContentV2 = {
  ...rivenContent,
  main: rivenContent.main.map((entry, index) => (index === 0 ? { ...entry, qty: 2 } : entry)),
  battlefields: rivenContent.battlefields.slice(0, 2),
};
const head = { id: 41, name: 'Riven, The Exile', updated_at: '2026-11-05T10:00:00Z' };
const current = { ...deckDetail(head, rivenContent), current_seq: 3 };
const versions: DeckVersionItem[] = [
  { seq: 3, note: null, created_at: '2026-11-05T10:00:00Z', is_current: true },
  { seq: 2, note: 'Before the cup', created_at: '2026-11-04T09:00:00Z', is_current: false },
  { seq: 1, note: null, created_at: '2026-11-01T08:00:00Z', is_current: false },
];
const emptyZones = () =>
  Object.fromEntries(
    ['legend', 'champion', 'main', 'runes', 'battlefields', 'sideboard', 'workbench'].map(
      (zone) => [zone, { added: [], removed: [], changed: [] }],
    ),
  );
const cardsOf = (...list: (typeof mainCards)[number][]) =>
  Object.fromEntries(list.map((card) => [card.key, card]));

/** 2 → 3: Rakelstake in, one Hush out, a third Discipline. 1 → 2: nothing changed. */
const diffs: Record<string, unknown> = {
  '2-3': {
    a: 2,
    b: 3,
    zones: {
      ...emptyZones(),
      main: { added: [], removed: [], changed: [{ set: 'OGN', id: '310', before: 2, after: 3 }] },
      battlefields: {
        added: [{ set: 'OGN', id: '332', before: 0, after: 1 }],
        removed: [],
        changed: [],
      },
      sideboard: {
        added: [],
        removed: [{ set: 'OGN', id: '342', before: 1, after: 0 }],
        changed: [],
      },
    },
    cards: cardsOf(mainCards[0], battlefields[2], sideCards[2]),
  },
  '1-2': { a: 1, b: 2, zones: emptyZones(), cards: {} },
};

/** The deck server of these tests: versions, diffs, restore, autosave; `GET` gives `deck`. */
function versionServer() {
  const state: { deck: DeckDetail; versions: DeckVersionItem[] } = { deck: current, versions };
  server.use(
    http.get(`${API}/decks`, () => ok({ items: [listItemOf(state.deck)] })),
    http.get(`${API}/decks/:id`, () => ok(state.deck)),
    http.get(`${API}/decks/:id/versions`, () => ok({ items: state.versions })),
    http.get(`${API}/decks/:id/diff`, ({ request }) => {
      const url = new URL(request.url);
      const diff = diffs[`${url.searchParams.get('a')}-${url.searchParams.get('b')}`];
      return diff ? ok(diff) : failure(404, { error: 'Not Found' });
    }),
    http.post(`${API}/decks/:id/versions/:seq/restore`, ({ params }) => {
      const restored = { ...deckDetail(head, firstContent), current_seq: 4 };
      state.deck = restored;
      const item = {
        seq: 4,
        note: `Restored from version ${String(params.seq)}.`,
        created_at: '2026-11-06T12:00:00Z',
        is_current: true,
      };
      state.versions = [item, ...versions.map((v) => ({ ...v, is_current: false }))];
      return ok({ ...restored, ...item }, 201);
    }),
    http.put(`${API}/decks/:id/content`, async ({ request }) => {
      const { content } = (await request.json()) as { content: DeckContentV2 };
      return ok({ ...deckDetail(head, content), current_seq: state.deck.current_seq });
    }),
  );
  return state;
}

async function openDeck(width = 390) {
  signedIn();
  const state = versionServer();
  const sent = recordDeckRequests();
  const app = await renderApp({ path: '/decks/41', width });
  await screen.findByRole('heading', { level: 1 }, LONG);
  await waitFor(() => expect(screen.getAllByRole('combobox').length).toBeGreaterThan(0), LONG);
  return { ...app, sent, state };
}

async function openVersions() {
  await userEvent.click(screen.getByRole('button', { name: 'Versions' }));
  const dialog = await screen.findByRole('dialog', { name: 'Versions' });
  await within(dialog).findByRole('list', { name: 'Versions of the deck' }, LONG);
  return dialog;
}

const versionList = (dialog: HTMLElement) =>
  within(dialog).getByRole('list', { name: 'Versions of the deck' });
const rows = (dialog: HTMLElement) =>
  within(versionList(dialog)).getAllByRole('listitem', { name: /^Version \d+$/ });
const row = (dialog: HTMLElement, seq: number) =>
  within(versionList(dialog)).getByRole('listitem', { name: `Version ${seq}` });
const section = (name: RegExp) =>
  screen.getByText(name, { selector: 'summary *' }).closest('details') as HTMLElement;
const qtyOf = (name: string) =>
  within(section(/^Main deck$/))
    .getAllByRole('listitem')
    .find((item) => item.querySelector('[data-slot="name"]')?.textContent === name)
    ?.querySelector('[data-slot="qty"]')
    ?.textContent?.replace('×', '');
const toast = async (text: string) =>
  expect((await screen.findAllByText(text, {}, LONG)).length).toBeGreaterThan(0);
const puts = (sent: ReturnType<typeof recordDeckRequests>) =>
  writes(sent).filter((r) => r.method === 'PUT' && r.path === '/decks/41/content');

describe('Versions modal (F5-i step 6)', () => {
  it('lists the versions newest first, the current one marked, with date and note', async () => {
    await openDeck();
    const dialog = await openVersions();
    expect(rows(dialog).map((item) => item.querySelector('[id$="-title"]')?.textContent)).toEqual([
      'Version 3',
      'Version 2',
      'Version 1',
    ]);
    expect(within(row(dialog, 3)).getByText('Current')).toBeVisible();
    expect(within(row(dialog, 2)).queryByText('Current')).toBeNull();
    expect(within(row(dialog, 2)).getByText('Before the cup')).toBeVisible();
    expect(within(row(dialog, 1)).getByText(/1 Nov 2026/)).toBeVisible();
    // only older versions can be restored
    expect(within(row(dialog, 3)).queryByRole('button', { name: /Restore/ })).toBeNull();
    expect(within(row(dialog, 2)).getByRole('button', { name: 'Restore version 2' })).toBeEnabled();
  }, 20000);

  it('expands a version to its changes against the previous one, by zone', async () => {
    const { sent } = await openDeck();
    const dialog = await openVersions();
    const toggle = within(row(dialog, 3)).getByRole('button', { name: 'Changes in version 3' });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    const changes = await within(row(dialog, 3)).findByRole(
      'region',
      {
        name: 'Changes in version 3',
      },
      LONG,
    );
    await within(changes).findByText('+1 Rakelstake', {}, LONG);
    const zone = (name: string) =>
      within(changes).getByRole('heading', { name }).closest('section') as HTMLElement;
    expect(within(zone('Battlefields')).getByText('+1 Rakelstake')).toBeVisible();
    expect(within(zone('Sideboard')).getByText('−1 Hush')).toBeVisible();
    expect(within(zone('Main deck')).getByText('Discipline 2 → 3')).toBeVisible();
    expect(within(changes).queryByRole('heading', { name: 'Runes' })).toBeNull();
    expect(sent.find((r) => r.path === '/decks/41/diff')).toMatchObject({ search: '?a=2&b=3' });

    await userEvent.click(
      within(row(dialog, 2)).getByRole('button', { name: 'Changes in version 2' }),
    );
    expect(await within(row(dialog, 2)).findByText('No changes.', {}, LONG)).toBeVisible();
    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(within(row(dialog, 3)).queryByRole('region')).toBeNull();
  }, 20000);

  it('the first version has no diff', async () => {
    const { sent } = await openDeck();
    const dialog = await openVersions();
    await userEvent.click(
      within(row(dialog, 1)).getByRole('button', { name: 'Changes in version 1' }),
    );
    expect(within(row(dialog, 1)).getByText('First version.')).toBeVisible();
    expect(sent.filter((r) => r.path === '/decks/41/diff')).toEqual([]);
  }, 20000);

  it('restores after a confirmation: the editor shows the restored deck and keeps it', async () => {
    const { sent } = await openDeck();
    expect(qtyOf('Discipline')).toBe('3');
    const dialog = await openVersions();
    await userEvent.click(
      within(row(dialog, 1)).getByRole('button', { name: 'Restore version 1' }),
    );
    const confirm = await screen.findByRole('dialog', { name: 'Restore version 1?' });
    expect(
      within(confirm).getByText('Your current deck stays in the history as a version.'),
    ).toBeVisible();
    await userEvent.click(within(confirm).getByRole('button', { name: 'Restore' }));
    await toast('Version 1 restored as version 4.');
    expect(writes(sent).filter((r) => r.method === 'POST')).toMatchObject([
      { path: '/decks/41/versions/1/restore' },
    ]);
    // the open editor now holds the restored content
    await waitFor(() => expect(qtyOf('Discipline')).toBe('2'), LONG);
    expect(within(section(/^Battlefields$/)).getAllByRole('listitem')).toHaveLength(2);
    expect(screen.getByText(/^Version 4 ·/)).toBeVisible();
    expect(document.querySelector('[data-slot="save-state"]')).toHaveTextContent(
      'All changes saved.',
    );
    // and the autosave never sends the old content back
    await new Promise((resolve) => setTimeout(resolve, 1300));
    expect(puts(sent)).toEqual([]);
    // the list shows the new current version
    const again = await openVersions();
    await waitFor(() => expect(within(row(again, 4)).getByText('Current')).toBeVisible(), LONG);
    expect(within(row(again, 4)).getByText('Restored from version 1.')).toBeVisible();
  }, 30000);

  it('Cancel in the confirmation restores nothing', async () => {
    const { sent } = await openDeck();
    const dialog = await openVersions();
    await userEvent.click(
      within(row(dialog, 2)).getByRole('button', { name: 'Restore version 2' }),
    );
    const confirm = await screen.findByRole('dialog', { name: 'Restore version 2?' });
    await userEvent.click(within(confirm).getByRole('button', { name: 'Cancel' }));
    expect(screen.queryByRole('dialog', { name: 'Restore version 2?' })).toBeNull();
    expect(screen.getByRole('dialog', { name: 'Versions' })).toBeVisible();
    expect(writes(sent)).toEqual([]);
  }, 20000);

  it('a failed restore is an error toast and the editor keeps its deck', async () => {
    await openDeck();
    server.use(
      http.post(`${API}/decks/:id/versions/:seq/restore`, () =>
        failure(500, { error: 'Internal Server Error', message: 'Restore failed.' }),
      ),
    );
    const dialog = await openVersions();
    await userEvent.click(
      within(row(dialog, 1)).getByRole('button', { name: 'Restore version 1' }),
    );
    const confirm = await screen.findByRole('dialog', { name: 'Restore version 1?' });
    await userEvent.click(within(confirm).getByRole('button', { name: 'Restore' }));
    await toast('Restore failed.');
    expect(qtyOf('Discipline')).toBe('3');
  }, 20000);

  it('restore waits while a change is not saved', async () => {
    const { sent } = await openDeck();
    server.use(
      http.put(`${API}/decks/:id/content`, () =>
        failure(500, { error: 'Internal Server Error', message: 'Save failed.' }),
      ),
    );
    await userEvent.click(screen.getByRole('button', { name: 'Remove a copy of Defy' }));
    await waitFor(() => expect(puts(sent)).toHaveLength(1), SAVE);
    const dialog = await openVersions();
    const restore = within(row(dialog, 1)).getByRole('button', { name: 'Restore version 1' });
    expect(restore).toBeDisabled();
    expect(restore).toHaveAccessibleDescription('Wait until the changes are saved.');
    expect(writes(sent).filter((r) => r.method === 'POST')).toEqual([]);
  }, 20000);

  it('offline the Versions button is disabled', async () => {
    signedIn();
    versionServer();
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    await renderApp({ path: '/decks/41', width: 390 });
    await screen.findByRole('heading', { level: 1 }, LONG);
    expect(screen.getByRole('button', { name: 'Versions' })).toBeDisabled();
  }, 20000);

  it('a list that fails says so and can retry', async () => {
    await openDeck();
    server.use(http.get(`${API}/decks/:id/versions`, () => failure(500, { error: 'Internal' })));
    await userEvent.click(screen.getByRole('button', { name: 'Versions' }));
    const dialog = await screen.findByRole('dialog', { name: 'Versions' });
    expect(
      await within(dialog).findByText('The versions could not be loaded.', {}, LONG),
    ).toBeVisible();
    server.use(http.get(`${API}/decks/:id/versions`, () => ok({ items: versions })));
    await userEvent.click(within(dialog).getByRole('button', { name: 'Retry' }));
    expect(
      await within(dialog).findByRole('list', { name: 'Versions of the deck' }, LONG),
    ).toBeVisible();
  }, 20000);

  it('Escape closes the modal', async () => {
    await openDeck();
    await openVersions();
    await userEvent.keyboard('{Escape}');
    expect(screen.queryByRole('dialog', { name: 'Versions' })).toBeNull();
  }, 20000);

  it('Save as version refreshes the list', async () => {
    const { state } = await openDeck();
    server.use(
      http.post(`${API}/decks/:id/versions`, () => {
        const item = { seq: 4, note: 'Cup', created_at: '2026-11-06T12:00:00Z', is_current: true };
        state.versions = [item, ...versions.map((v) => ({ ...v, is_current: false }))];
        return ok(item, 201);
      }),
    );
    let dialog = await openVersions();
    await userEvent.keyboard('{Escape}');
    await userEvent.click(screen.getByRole('button', { name: 'Save as version' }));
    const form = await screen.findByRole('dialog', { name: 'Save as version' });
    await userEvent.click(within(form).getByRole('button', { name: 'Save version' }));
    await toast('Saved as version 4.');
    dialog = await openVersions();
    await waitFor(() => expect(within(row(dialog, 4)).getByText('Cup')).toBeVisible(), LONG);
  }, 30000);

  it('is axe clean with a diff open at 390 and 1280 px', async () => {
    for (const width of [390, 1280]) {
      const { unmount } = await openDeck(width);
      const dialog = await openVersions();
      await userEvent.click(
        within(row(dialog, 3)).getByRole('button', { name: 'Changes in version 3' }),
      );
      await within(dialog).findByText('+1 Rakelstake', {}, LONG);
      expect(await axe(dialog)).toHaveNoViolations();
      unmount();
    }
  }, 40000);
});
