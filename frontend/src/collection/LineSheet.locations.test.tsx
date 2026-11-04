import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { I18nextProvider } from 'react-i18next';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { axe } from 'vitest-axe';
import type { CollectionGroup, LineLocations } from '@/api/types';
import { ToastStack } from '@/components/ui/Toast';
import { clearToasts } from '@/components/ui/toastStore';
import { createI18n } from '@/i18n';
import { aylaGroup, aylaLines } from '@/test/fixtures/collection';
import { aylaLineLocations } from '@/test/fixtures/locations';
import { recordRequests, withLocations, writes } from '@/test/locations';
import { API, failure, ok } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { LineSheet } from './LineSheet';

const META = { conditions: ['NM', 'EX'], languages: ['English', 'Spanish'] };

const place = (index: number) => ({
  location_id: 100 + index,
  code: `B001-F001-P000${index}`,
  description: index === 1 ? 'Red binder' : null,
  qty: 1,
});

/** Line 1201 (3 copies) spread over 7 locations: the list has the first 5 and "2 more". */
const spread: CollectionGroup = {
  ...aylaGroup,
  lines: [
    {
      ...aylaLines[0],
      qty: 9,
      locations: [1, 2, 3, 4, 5].map(place),
      locations_more: 2,
      unassigned: 2,
    },
    { ...aylaLines[1], locations: [], locations_more: 0, unassigned: 1 },
  ],
};

/** Line 1201 as the fixture places it: binder 1, locked box 1, unassigned 1. */
const placed: CollectionGroup = {
  ...aylaGroup,
  lines: [
    {
      ...aylaLines[0],
      locations: aylaLineLocations.locations.map((item) => ({
        location_id: item.location_id,
        code: item.code,
        description: item.description,
        qty: item.qty,
      })),
      locations_more: 0,
      unassigned: 1,
    },
    { ...aylaLines[1], locations: [], locations_more: 0, unassigned: 1 },
  ],
};

async function open(group: CollectionGroup, { offline = false } = {}) {
  const i18n = await createI18n();
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <I18nextProvider i18n={i18n}>
      <QueryClientProvider client={client}>
        <LineSheet
          group={group}
          open
          onClose={() => undefined}
          meta={META}
          playsetSize={3}
          offline={offline}
        />
        <ToastStack />
      </QueryClientProvider>
    </I18nextProvider>,
  );
}

beforeEach(() => clearToasts());
afterEach(() => server.events.removeAllListeners());

const whereOf = (index: number) =>
  within(screen.getByRole('group', { name: `Line ${index}` })).getByRole('group', {
    name: 'Where they are',
  });

describe('LineSheet "Where they are" (F16-R5)', () => {
  it('lists the first 5 locations, the unassigned copies and "and N more"', async () => {
    const full: LineLocations = {
      locations: [1, 2, 3, 4, 5, 6, 7].map((index) => ({ ...place(index), locked: index === 7 })),
      unassigned: 2,
      total: 9,
    };
    server.use(http.get(`${API}/collection/1201/locations`, () => ok(full)));
    const sent = recordRequests();
    await open(spread);
    const where = whereOf(1);
    const items = within(where).getAllByRole('listitem');
    expect(items.map((item) => item.textContent)).toEqual([
      'B001-F001-P0001 — Red binder × 1',
      'B001-F001-P0002 × 1',
      'B001-F001-P0003 × 1',
      'B001-F001-P0004 × 1',
      'B001-F001-P0005 × 1',
    ]);
    expect(within(where).getByText('Unassigned: 2')).toBeVisible();
    // nothing is read until it is asked for
    expect(sent.filter((r) => r.path.endsWith('/locations'))).toEqual([]);

    await userEvent.click(within(where).getByRole('button', { name: 'and 2 more' }));
    await waitFor(() => expect(within(where).getAllByRole('listitem')).toHaveLength(7));
    expect(sent.some((r) => r.method === 'GET' && r.path === '/collection/1201/locations')).toBe(
      true,
    );
    expect(within(where).getAllByRole('listitem')[6]).toHaveTextContent(
      'B001-F001-P0007 × 1 · Locked',
    );

    // a line in no location
    expect(within(whereOf(2)).getByText('In no location yet.')).toBeVisible();
    expect(within(whereOf(2)).getByText('Unassigned: 1')).toBeVisible();
  });

  it('assigns unassigned copies to a location', async () => {
    withLocations();
    const sent = recordRequests();
    await open(placed);
    const where = whereOf(1);
    await userEvent.click(within(where).getByRole('button', { name: 'Change locations' }));
    const from = await within(where).findByRole('combobox', { name: 'From' });
    await waitFor(() => expect(within(from).getAllByRole('option')).toHaveLength(3));
    expect(from).toHaveValue('none');
    expect(within(from).getByRole('option', { name: 'Unassigned (1)' })).toBeEnabled();
    // a locked location is read-only: its copies cannot leave it
    expect(
      within(from).getByRole('option', { name: 'B001-F001-P0002 (1) · Locked' }),
    ).toBeDisabled();
    const to = within(where).getByRole('combobox', { name: 'To' });
    expect(within(to).getByRole('option', { name: 'B001-F001-P0002 · Locked' })).toBeDisabled();
    expect(
      within(to).getByRole('option', { name: 'DECK-001 — Ayla aggro · Locked' }),
    ).toBeDisabled();
    await userEvent.selectOptions(to, 'B001-F001-P0001 — Red binder');
    // the quantity cannot go above the copies of the source
    expect(within(where).getByRole('spinbutton', { name: 'Copies to move' })).toHaveAttribute(
      'max',
      '1',
    );
    await userEvent.click(within(where).getByRole('button', { name: 'Move copies' }));
    await waitFor(() => expect(writes(sent)).toHaveLength(1));
    expect(writes(sent)[0]).toMatchObject({
      method: 'POST',
      path: '/collection/1201/locations/move',
      body: { from_location_id: null, to_location_id: 11, qty: 1 },
    });
    expect(await screen.findByText('Copies moved.')).toBeVisible();
  });

  it('moves copies from a location back to unassigned', async () => {
    withLocations();
    const sent = recordRequests();
    await open(placed);
    const where = whereOf(1);
    await userEvent.click(within(where).getByRole('button', { name: 'Change locations' }));
    const from = await within(where).findByRole('combobox', { name: 'From' });
    await waitFor(() => expect(within(from).getAllByRole('option')).toHaveLength(3));
    await userEvent.selectOptions(from, 'B001-F001-P0001 (1)');
    await userEvent.selectOptions(
      within(where).getByRole('combobox', { name: 'To' }),
      'Unassigned',
    );
    await userEvent.click(within(where).getByRole('button', { name: 'Move copies' }));
    await waitFor(() => expect(writes(sent)).toHaveLength(1));
    expect(writes(sent)[0].body).toEqual({ from_location_id: 11, to_location_id: null, qty: 1 });
  });

  it('shows the over-quantity error translated', async () => {
    withLocations();
    server.use(
      http.post(`${API}/collection/:id/locations/move`, () =>
        failure(409, {
          error: 'Conflict',
          code: 'location_over_quantity',
          params: { max: 1, requested: 2 },
        }),
      ),
    );
    await open(placed);
    const where = whereOf(1);
    await userEvent.click(within(where).getByRole('button', { name: 'Change locations' }));
    const from = await within(where).findByRole('combobox', { name: 'From' });
    await waitFor(() => expect(within(from).getAllByRole('option')).toHaveLength(3));
    await userEvent.selectOptions(
      within(where).getByRole('combobox', { name: 'To' }),
      'B001-F001-P0001 — Red binder',
    );
    await userEvent.click(within(where).getByRole('button', { name: 'Move copies' }));
    expect(
      await within(where).findByText('Too many copies: at most 1 can be placed (requested: 2).'),
    ).toBeVisible();
  });

  it('offline: the editor cannot be opened', async () => {
    await open(placed, { offline: true });
    expect(within(whereOf(1)).getByRole('button', { name: 'Change locations' })).toBeDisabled();
  });

  it('is axe clean with the editor open', async () => {
    withLocations();
    const { container } = await open(placed);
    const where = whereOf(1);
    await userEvent.click(within(where).getByRole('button', { name: 'Change locations' }));
    await within(where).findByRole('combobox', { name: 'From' });
    expect(await axe(container)).toHaveNoViolations();
  });
});
