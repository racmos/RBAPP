import { createEvent, fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';
import { binder, storageLocations } from '@/test/fixtures/locations';
import { recordRequests, signedIn, withLocations, writes } from '@/test/locations';
import { API, ok } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';
import { expectCollapsible } from '@/test/sidePanel';

const LONG = { timeout: 10000 };
const DESKTOP = 1280;
const WIDE = 1700;

afterEach(() => {
  vi.restoreAllMocks();
  server.events.removeAllListeners();
});

const table = () => screen.findByRole('table', { name: 'Your locations in order' }, LONG);
const rowOf = (code: string) =>
  screen.getByRole('button', { name: `Edit ${code}` }).closest('tr') as HTMLElement;
const bodyCodes = (element: HTMLElement) =>
  within(element)
    .getAllByRole('row')
    .slice(1)
    .map((row) => row.querySelector('[data-slot="code"]')?.textContent);

async function openPage(width = DESKTOP) {
  signedIn();
  withLocations();
  server.use(
    http.patch(`${API}/locations/:id`, async ({ params, request }) => {
      const current = storageLocations.find((item) => String(item.id) === params.id) ?? binder;
      return ok({ ...current, ...((await request.json()) as object) });
    }),
    http.put(`${API}/locations/order`, async ({ request }) => {
      const { ids } = (await request.json()) as { ids: number[] };
      return ok({ items: ids.map((id) => storageLocations.find((item) => item.id === id)) });
    }),
  );
  return renderApp({ path: '/locations', width });
}

describe('LocationsPage from 1240 px (F16-d)', () => {
  it('shows the locations as a table with every column and no detail panel', async () => {
    await openPage();
    const grid = await table();
    const headers = within(grid)
      .getAllByRole('columnheader')
      .map((cell) => cell.textContent);
    expect(headers).toEqual([
      'Position',
      'Code',
      'Description',
      'Copies',
      'Cards',
      'Lock',
      'Actions',
    ]);
    expect(bodyCodes(grid)).toEqual(['B001-F001-P0001', 'B001-F001-P0002', 'DECK-001']);
    const first = within(rowOf('B001-F001-P0001'));
    expect(first.getByText('1')).toBeVisible();
    expect(first.getByText('5')).toBeVisible();
    expect(first.getByText('3')).toBeVisible();
    expect(within(rowOf('DECK-001')).getByText('Deck')).toBeVisible();
    expect(screen.getByText('Unassigned: 7 copies')).toBeVisible();
    expect(grid.closest('[data-slot="table-scroll"]')).toHaveAttribute('data-fit');
    expect(screen.queryByRole('complementary', { name: 'Location details' })).toBeNull();
    expect(document.title).toBe('Locations · Rift Manager');
  }, 20000);

  it('edits the description inline and locks a row', async () => {
    const sent = recordRequests();
    await openPage();
    await table();
    const description = screen.getByRole('textbox', { name: 'Description of B001-F001-P0001' });
    await userEvent.clear(description);
    await userEvent.type(description, 'Blue binder');
    await waitFor(() => expect(writes(sent)).toHaveLength(1), LONG);
    expect(writes(sent)[0]).toMatchObject({
      method: 'PATCH',
      path: '/locations/11',
      body: { description: 'Blue binder' },
    });
    const lock = screen.getByRole('switch', { name: 'Lock B001-F001-P0001' });
    expect(lock).toHaveAttribute('aria-checked', 'false');
    expect(screen.getByRole('switch', { name: 'Lock DECK-001' })).toHaveAttribute(
      'aria-checked',
      'true',
    );
    await userEvent.click(lock);
    await waitFor(() => expect(writes(sent)).toHaveLength(2), LONG);
    expect(writes(sent)[1]).toMatchObject({ path: '/locations/11', body: { locked: true } });
  }, 20000);

  it('reorders with the row buttons', async () => {
    const sent = recordRequests();
    await openPage();
    const grid = await table();
    await userEvent.click(screen.getByRole('button', { name: 'Move DECK-001 up' }));
    await waitFor(() =>
      expect(bodyCodes(grid)).toEqual(['B001-F001-P0001', 'DECK-001', 'B001-F001-P0002']),
    );
    await waitFor(() => expect(writes(sent)).toHaveLength(1), LONG);
    expect(writes(sent)[0]).toMatchObject({
      method: 'PUT',
      path: '/locations/order',
      body: { ids: [11, 13, 12] },
    });
  }, 20000);

  it('reorders by dragging a row onto another (pointer devices)', async () => {
    // jsdom has no layout or pointer: the drag is driven by its DOM events, which is what the
    // browser fires; the drop target and the resulting order are what this checks.
    const sent = recordRequests();
    await openPage();
    const grid = await table();
    const store = new Map<string, string>();
    const dataTransfer = {
      setData: (type: string, value: string) => store.set(type, value),
      getData: (type: string) => store.get(type) ?? '',
      effectAllowed: 'move',
      dropEffect: 'move',
    };
    fireEvent.dragStart(rowOf('DECK-001'), { dataTransfer });
    fireEvent.dragOver(rowOf('B001-F001-P0001'), { dataTransfer });
    const drop = createEvent.drop(rowOf('B001-F001-P0001'), { dataTransfer });
    fireEvent(rowOf('B001-F001-P0001'), drop);
    expect(drop.defaultPrevented).toBe(true);
    await waitFor(() =>
      expect(bodyCodes(grid)).toEqual(['DECK-001', 'B001-F001-P0001', 'B001-F001-P0002']),
    );
    await waitFor(() => expect(writes(sent)).toHaveLength(1), LONG);
    expect(writes(sent)[0].body).toEqual({ ids: [13, 11, 12] });
  }, 20000);

  it('opens the edit sheet from the row action', async () => {
    await openPage();
    await table();
    await userEvent.click(screen.getByRole('button', { name: 'Edit B001-F001-P0002' }));
    const dialog = await screen.findByRole('dialog', { name: 'Location B001-F001-P0002' });
    expect(within(dialog).getByRole('switch', { name: 'Lock this location' })).toHaveAttribute(
      'aria-checked',
      'true',
    );
  }, 20000);

  it('is axe clean', async () => {
    const { container } = await openPage();
    await table();
    expect(await axe(container)).toHaveNoViolations();
  }, 30000);
});

describe('LocationsPage from 1600 px (F16-d)', () => {
  it('shows the selected location in a panel with a link to its cards', async () => {
    await openPage(WIDE);
    await table();
    const panel = await screen.findByRole('complementary', { name: 'Location details' }, LONG);
    // the first location until one is picked
    expect(within(panel).getByRole('heading', { name: 'B001-F001-P0001' })).toBeVisible();
    expect(within(panel).getByText('Red binder')).toBeVisible();
    expect(within(panel).getByRole('link', { name: 'View cards' })).toHaveAttribute(
      'href',
      '/riftbound/app/collection?location=B001-F001-P0001',
    );
    await userEvent.click(within(rowOf('DECK-001')).getByText('40'));
    expect(within(panel).getByRole('heading', { name: 'DECK-001' })).toBeVisible();
    expect(within(panel).getByText('Ayla aggro')).toBeVisible();
    expect(within(panel).getByText('Deck')).toBeVisible();
    expect(rowOf('DECK-001')).toHaveAttribute('data-active');
    expect(within(panel).getByRole('link', { name: 'View cards' })).toHaveAttribute(
      'href',
      '/riftbound/app/collection?location=DECK-001',
    );
  }, 20000);

  it('the panel folds away', async () => {
    await openPage(WIDE);
    await table();
    await expectCollapsible(
      await screen.findByRole('complementary', { name: 'Location details' }, LONG),
      { hide: 'Hide details', show: 'Show details' },
      'rb_panel_locations-detail_v1',
    );
  }, 20000);

  it('is axe clean', async () => {
    const { container } = await openPage(WIDE);
    await table();
    expect(await axe(container)).toHaveNoViolations();
  }, 30000);
});
