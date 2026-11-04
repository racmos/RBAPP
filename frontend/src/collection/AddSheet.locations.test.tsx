import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { I18nextProvider } from 'react-i18next';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import type { GameMeta } from '@/api/types';
import { ToastStack } from '@/components/ui/Toast';
import { clearToasts } from '@/components/ui/toastStore';
import { createI18n } from '@/i18n';
import { recordRequests, withLocations, writes } from '@/test/locations';
import { API, failure } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { AddSheet } from './AddSheet';
import { QUICK_ADD_KEY } from './quickAdd';

const META: Pick<GameMeta, 'conditions' | 'languages' | 'sets'> = {
  conditions: ['NM', 'EX'],
  languages: ['English'],
  sets: [{ id: 'OGN', name: 'Origins', released_on: '2024-01-15', card_count: 6 }],
};

async function open() {
  const i18n = await createI18n();
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <I18nextProvider i18n={i18n}>
      <QueryClientProvider client={client}>
        <AddSheet open onClose={() => undefined} meta={META} offline={false} />
        <ToastStack />
      </QueryClientProvider>
    </I18nextProvider>,
  );
}

beforeEach(() => clearToasts());
afterEach(() => server.events.removeAllListeners());

const locationSelect = () => screen.getByRole('combobox', { name: 'Location' });

async function addEmber() {
  await userEvent.type(screen.getByRole('combobox', { name: 'Card' }), 'em');
  await userEvent.click(await screen.findByRole('option', { name: /Ember Wisp/ }));
  await userEvent.click(screen.getByRole('button', { name: 'Add' }));
}

describe('AddSheet location (F16-R4a)', () => {
  it('offers None and the user locations in order, locked ones disabled', async () => {
    withLocations();
    await open();
    await waitFor(() => expect(within(locationSelect()).getAllByRole('option')).toHaveLength(4));
    const options = within(locationSelect()).getAllByRole('option');
    expect(options.map((option) => option.textContent)).toEqual([
      'None',
      'B001-F001-P0001 — Red binder',
      'B001-F001-P0002 · Locked',
      'DECK-001 — Ayla aggro · Locked',
    ]);
    expect(options[1]).toBeEnabled();
    expect(options[2]).toBeDisabled();
    expect(options[3]).toBeDisabled();
    expect(locationSelect()).toHaveValue('');
  });

  it('places every added card in the chosen location and keeps the choice', async () => {
    withLocations();
    const sent = recordRequests();
    const view = await open();
    await waitFor(() => expect(within(locationSelect()).getAllByRole('option')).toHaveLength(4));
    await userEvent.selectOptions(locationSelect(), 'B001-F001-P0001 — Red binder');
    await addEmber();
    await waitFor(() => expect(writes(sent)).toHaveLength(2));
    expect(writes(sent)[0]).toMatchObject({ method: 'POST', path: '/collection' });
    // the new copies go from unassigned into the location; the line's other places stay
    expect(writes(sent)[1]).toMatchObject({
      method: 'POST',
      path: '/collection/9001/locations/move',
      body: { from_location_id: null, to_location_id: 11, qty: 1 },
    });
    expect(await screen.findByText('Added to your collection in B001-F001-P0001.')).toBeVisible();
    expect(JSON.parse(sessionStorage.getItem(QUICK_ADD_KEY) ?? '{}')).toMatchObject({
      location_id: 11,
    });

    // the next card of the session goes to the same place
    await addEmber();
    await waitFor(() => expect(writes(sent)).toHaveLength(4));
    expect(writes(sent)[3].body).toEqual({ from_location_id: null, to_location_id: 11, qty: 1 });

    // reopened later in the session, the sheet remembers it
    view.unmount();
    await open();
    await waitFor(() => expect(locationSelect()).toHaveValue('11'));
  });

  it('forgets a stored location that no longer exists', async () => {
    withLocations();
    sessionStorage.setItem(QUICK_ADD_KEY, JSON.stringify({ qty: 2, location_id: 77 }));
    const sent = recordRequests();
    await open();
    await waitFor(() => expect(within(locationSelect()).getAllByRole('option')).toHaveLength(4));
    expect(locationSelect()).toHaveValue('');
    await addEmber();
    await waitFor(() => expect(writes(sent)).toHaveLength(1));
    expect(await screen.findByText('Added to your collection.')).toBeVisible();
    expect(writes(sent)[0].body).toMatchObject({ qty: 2 });
  });

  it('keeps the added card unassigned and says so when placing it fails', async () => {
    withLocations();
    server.use(
      http.post(`${API}/collection/:id/locations/move`, () =>
        failure(409, { error: 'Conflict', code: 'location_locked' }),
      ),
    );
    const sent = recordRequests();
    await open();
    await waitFor(() => expect(within(locationSelect()).getAllByRole('option')).toHaveLength(4));
    await userEvent.selectOptions(locationSelect(), 'B001-F001-P0001 — Red binder');
    await addEmber();
    expect(
      await screen.findByText(
        'The card was added but stays unassigned: This location is locked. Unlock it first.',
      ),
    ).toBeVisible();
    expect(writes(sent).filter((r) => r.method === 'DELETE')).toEqual([]);
    const session = screen.getByRole('list', { name: 'Added in this session' });
    expect(within(session).getByText('Ember Wisp')).toBeVisible();
  });
});
