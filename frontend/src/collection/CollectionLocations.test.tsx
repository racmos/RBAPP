import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { afterEach, describe, expect, it } from 'vitest';
import { axe } from 'vitest-axe';
import type { CollectionGroup } from '@/api/types';
import { aylaGroup, collectionMeta, emberGroup } from '@/test/fixtures/collection';
import { recordRequests, signedIn, withLocations } from '@/test/locations';
import { API } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';

const LONG = { timeout: 10000 };

/** Ayla's first line is in two locations and one more; Ember is in none. */
const placedAyla: CollectionGroup = {
  ...aylaGroup,
  lines: [
    {
      ...aylaGroup.lines[0],
      locations: [
        { location_id: 11, code: 'B001-F001-P0001', description: 'Red binder', qty: 1 },
        { location_id: 12, code: 'B001-F001-P0002', description: null, qty: 1 },
      ],
      locations_more: 1,
      unassigned: 0,
    },
    { ...aylaGroup.lines[1], locations: [], locations_more: 0, unassigned: 1 },
  ],
};

function list(items: CollectionGroup[] = [placedAyla, emberGroup]) {
  server.use(
    http.get(`${API}/collection`, () =>
      HttpResponse.json({
        success: true,
        data: { items },
        meta: { ...collectionMeta, total_groups: items.length },
      }),
    ),
  );
}

afterEach(() => server.events.removeAllListeners());

const collectionReads = (sent: ReturnType<typeof recordRequests>) =>
  sent.filter((request) => request.method === 'GET' && request.path === '/collection');

describe('Collection filter by location (F16-R5)', () => {
  it('filters by a location code from the filter sheet, in the URL and the request', async () => {
    signedIn();
    withLocations();
    list();
    const sent = recordRequests();
    const { where } = await renderApp({ path: '/collection', width: 390 });
    await screen.findByRole('button', { name: /Ayla/ }, LONG);
    await userEvent.click(screen.getByRole('button', { name: 'Filters' }));
    const sheet = await screen.findByRole('dialog', { name: 'Filter collection' });
    const group = await within(sheet).findByRole('group', { name: 'Location' }, LONG);
    expect(
      within(group)
        .getAllByRole('button')
        .map((chip) => chip.textContent),
    ).toEqual(['B001-F001-P0001', 'B001-F001-P0002', 'DECK-001']);
    await userEvent.click(within(group).getByRole('button', { name: 'DECK-001' }));
    await waitFor(() => expect(where()).toBe('/collection?location=DECK-001'), LONG);
    await waitFor(() =>
      expect(collectionReads(sent).some((r) => r.search === '?location=DECK-001')).toBe(true),
    );
    expect(within(group).getByRole('button', { name: 'DECK-001' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
  }, 20000);

  it('opens with the codes of the URL (the link of a location) and lets them be removed', async () => {
    signedIn();
    withLocations();
    list();
    const sent = recordRequests();
    const { where } = await renderApp({
      path: '/collection?location=B001-F001-P0001',
      width: 390,
    });
    await screen.findByRole('button', { name: /Ayla/ }, LONG);
    expect(collectionReads(sent)[0].search).toBe('?location=B001-F001-P0001');
    await userEvent.click(
      screen.getByRole('button', { name: 'Remove filter Location: B001-F001-P0001' }),
    );
    await waitFor(() => expect(where()).toBe('/collection'), LONG);
  }, 20000);

  it('shows the location summary on the mobile items', async () => {
    signedIn();
    list();
    await renderApp({ path: '/collection', width: 390 });
    const ayla = await screen.findByRole('button', { name: /Ayla/ }, LONG);
    expect(ayla.querySelector('[data-slot="where"]')).toHaveTextContent(
      'Location: B001-F001-P0001 +2',
    );
  }, 20000);
});

describe('Collection table "Where" column (F16-d)', () => {
  it('shows the first location and opens the line sheet with the locations', async () => {
    signedIn();
    withLocations();
    list();
    await renderApp({ path: '/collection', width: 1440 });
    const grid = await screen.findByRole(
      'table',
      { name: 'Your collection grouped by card' },
      LONG,
    );
    expect(within(grid).getByRole('columnheader', { name: 'Where' })).toBeVisible();
    const row = within(grid)
      .getByRole('button', { name: /Show the lines of Ayla/ })
      .closest('tr')!;
    const cell = within(row).getByRole('button', { name: 'Where: B001-F001-P0001 +2' });
    expect(cell).toHaveTextContent('B001-F001-P0001 +2');
    await userEvent.click(cell);
    const sheet = await screen.findByRole('dialog', { name: "Copies of Ayla, Fury's Champion" });
    expect(within(sheet).getAllByRole('group', { name: 'Where they are' })).toHaveLength(2);
  }, 20000);

  it('the sidebar has the location filter and stays axe clean', async () => {
    signedIn();
    withLocations();
    list();
    const { container } = await renderApp({ path: '/collection', width: 1440 });
    await screen.findByRole('table', { name: 'Your collection grouped by card' }, LONG);
    const sidebar = screen.getByRole('complementary', { name: 'Filter collection' });
    expect(await within(sidebar).findByRole('group', { name: 'Location' }, LONG)).toBeVisible();
    expect(await axe(container)).toHaveNoViolations();
  }, 30000);
});
