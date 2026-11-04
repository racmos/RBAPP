import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';
import { binder, deckLocation, storageLocations } from '@/test/fixtures/locations';
import { recordRequests, signedIn, withLocations, writes } from '@/test/locations';
import { API, failure, ok } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';

const LONG = { timeout: 10000 };
const PHONE = 390;

afterEach(() => {
  vi.restoreAllMocks();
  server.events.removeAllListeners();
});

const list = () => screen.findByRole('list', { name: 'Your locations in order' }, LONG);
const codes = (element: HTMLElement) =>
  within(element)
    .getAllByRole('listitem')
    .map((item) => item.querySelector('[data-slot="code"]')?.textContent);
const openButton = (code: string) => screen.getByRole('button', { name: new RegExp(`^${code}`) });

async function openPage() {
  signedIn();
  return renderApp({ path: '/locations', width: PHONE });
}

describe('LocationsPage at 390 px (F16-c)', () => {
  it('lists the locations in the user order with counts, badges and the unassigned copies', async () => {
    withLocations();
    await openPage();
    const ordered = await list();
    expect(codes(ordered)).toEqual(['B001-F001-P0001', 'B001-F001-P0002', 'DECK-001']);
    expect(screen.getByRole('heading', { level: 1, name: 'Locations' })).toBeVisible();
    expect(document.title).toBe('Locations · Rift Manager');

    const [first, second, deck] = within(ordered).getAllByRole('listitem');
    expect(within(first).getByText('Red binder')).toBeVisible();
    expect(within(first).getByText('5 copies · 3 cards')).toBeVisible();
    expect(within(first).queryByText('Locked')).toBeNull();
    expect(within(second).getByText('Locked')).toBeVisible();
    expect(within(second).getByText('No description')).toBeVisible();
    expect(within(deck).getByText('Locked')).toBeVisible();
    expect(within(deck).getByText('Deck')).toBeVisible();
    expect(within(deck).getByText('40 copies · 12 cards')).toBeVisible();

    // the unassigned copies close the list and cannot be moved
    const unassigned = screen.getByText('Unassigned: 7 copies');
    expect(unassigned).toBeVisible();
    expect(ordered).not.toContainElement(unassigned);
    expect(screen.getByText('Always last: it cannot be moved.')).toBeVisible();
    // the ends cannot move further
    expect(screen.getByRole('button', { name: 'Move B001-F001-P0001 up' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Move DECK-001 down' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Move DECK-001 up' })).toBeEnabled();
  }, 20000);

  it('the nav entry opens this screen in the app', async () => {
    signedIn();
    await renderApp({ path: '/', width: 1280 });
    const links = await screen.findAllByRole('link', { name: /Locations/ }, LONG);
    expect(links.length).toBeGreaterThan(0);
    for (const link of links) expect(link).toHaveAttribute('href', '/riftbound/app/locations');
  }, 15000);

  it('creates a location with the suggested code and the next block, row and pack buttons', async () => {
    withLocations();
    server.use(
      http.get(`${API}/locations/next-code`, ({ request }) => {
        const url = new URL(request.url);
        const bump = url.searchParams.get('bump');
        const after = url.searchParams.get('after');
        if (after === null) return ok({ code: `B001-F001-P0003` });
        if (after === 'Shelf') return ok({ code: null });
        const next = { block: 'B002-F001-P0001', row: 'B001-F002-P0001', pack: 'B001-F001-P0004' };
        return ok({ code: next[bump as keyof typeof next] });
      }),
    );
    const sent = recordRequests();
    await openPage();
    await list();
    await userEvent.click(screen.getByRole('button', { name: 'New location' }));
    const dialog = await screen.findByRole('dialog', { name: 'New location' });
    const code = within(dialog).getByRole('textbox', { name: 'Code' });
    await waitFor(() => expect(code).toHaveValue('B001-F001-P0003'), LONG);
    expect(sent.some((r) => r.path === '/locations/next-code' && r.search === '?bump=pack')).toBe(
      true,
    );

    await userEvent.click(within(dialog).getByRole('button', { name: 'Next row' }));
    await waitFor(() => expect(code).toHaveValue('B001-F002-P0001'), LONG);
    expect(
      sent.find((r) => r.path === '/locations/next-code' && r.search.includes('bump=row')),
    ).toMatchObject({ search: '?bump=row&after=B001-F001-P0003' });
    await userEvent.click(within(dialog).getByRole('button', { name: 'Next block' }));
    await waitFor(() => expect(code).toHaveValue('B002-F001-P0001'), LONG);

    // the user can type any code; a code without the pattern gets no suggestion
    await userEvent.clear(code);
    await userEvent.type(code, 'Shelf');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Next pack' }));
    expect(
      await within(dialog).findByText('This code has no block-row-pack pattern to continue.'),
    ).toBeVisible();
    expect(code).toHaveValue('Shelf');

    await userEvent.type(within(dialog).getByRole('textbox', { name: 'Description' }), 'Top shelf');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Create' }));
    await waitFor(() => expect(writes(sent)).toHaveLength(1), LONG);
    expect(writes(sent)[0]).toMatchObject({
      method: 'POST',
      path: '/locations',
      body: { code: 'Shelf', description: 'Top shelf' },
    });
    expect(await screen.findByText('Location created.', {}, LONG)).toBeVisible();
    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'New location' })).toBeNull());
  }, 30000);

  it('checks the code before sending it', async () => {
    withLocations();
    const sent = recordRequests();
    await openPage();
    await list();
    await userEvent.click(screen.getByRole('button', { name: 'New location' }));
    const dialog = await screen.findByRole('dialog', { name: 'New location' });
    const code = within(dialog).getByRole('textbox', { name: 'Code' });
    await waitFor(() => expect(code).toHaveValue('B001-F001-P0001'), LONG);
    await userEvent.clear(code);
    await userEvent.type(code, 'bad code!');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Create' }));
    expect(within(dialog).getByText('Use 1 to 32 letters, digits or hyphens.')).toBeVisible();
    expect(code).toHaveAttribute('aria-invalid', 'true');
    await userEvent.clear(code);
    await userEvent.click(within(dialog).getByRole('button', { name: 'Create' }));
    expect(within(dialog).getByText('Enter a code.')).toBeVisible();
    expect(writes(sent)).toEqual([]);
  }, 20000);

  it('a repeated code keeps the sheet open with the 409 message on the code', async () => {
    withLocations();
    server.use(
      http.post(`${API}/locations`, () =>
        failure(409, { error: 'Conflict', code: 'already_exists', message: 'exists' }),
      ),
    );
    await openPage();
    await list();
    await userEvent.click(screen.getByRole('button', { name: 'New location' }));
    const dialog = await screen.findByRole('dialog', { name: 'New location' });
    const code = within(dialog).getByRole('textbox', { name: 'Code' });
    await waitFor(() => expect(code).toHaveValue('B001-F001-P0001'), LONG);
    await userEvent.click(within(dialog).getByRole('button', { name: 'Create' }));
    expect(
      await within(dialog).findByText('You already have a location with this code.', {}, LONG),
    ).toBeVisible();
    expect(code).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByRole('dialog', { name: 'New location' })).toBeVisible();
  }, 20000);

  it('moves a location up at once and saves the whole order', async () => {
    withLocations();
    // the server answers only when the test lets it: the list must change before that
    let answer = () => undefined as void;
    const answered = new Promise<void>((resolve) => (answer = resolve));
    server.use(
      http.put(`${API}/locations/order`, async ({ request }) => {
        const { ids } = (await request.json()) as { ids: number[] };
        await answered;
        return ok({ items: ids.map((id) => storageLocations.find((item) => item.id === id)) });
      }),
    );
    const sent = recordRequests();
    await openPage();
    const ordered = await list();
    await userEvent.click(screen.getByRole('button', { name: 'Move B001-F001-P0002 up' }));
    await waitFor(() =>
      expect(codes(ordered)).toEqual(['B001-F001-P0002', 'B001-F001-P0001', 'DECK-001']),
    );
    await waitFor(() => expect(writes(sent)).toHaveLength(1), LONG);
    expect(writes(sent)[0]).toMatchObject({
      method: 'PUT',
      path: '/locations/order',
      body: { ids: [12, 11, 13] },
    });
    answer();
    await userEvent.click(screen.getByRole('button', { name: 'Move B001-F001-P0002 down' }));
    await waitFor(() => expect(writes(sent)).toHaveLength(2), LONG);
    expect(writes(sent)[1].body).toEqual({ ids: [11, 12, 13] });
    await waitFor(() =>
      expect(codes(ordered)).toEqual(['B001-F001-P0001', 'B001-F001-P0002', 'DECK-001']),
    );
  }, 20000);

  it('puts the order back when saving it fails', async () => {
    withLocations();
    server.use(
      http.put(`${API}/locations/order`, () =>
        failure(400, { error: 'Validation Error', code: 'validation_error' }),
      ),
    );
    await openPage();
    const ordered = await list();
    await userEvent.click(screen.getByRole('button', { name: 'Move DECK-001 up' }));
    expect(await screen.findByText('Check the form data.', {}, LONG)).toBeVisible();
    await waitFor(() =>
      expect(codes(ordered)).toEqual(['B001-F001-P0001', 'B001-F001-P0002', 'DECK-001']),
    );
  }, 20000);

  it('edits the code and the description, and locks the location', async () => {
    withLocations();
    server.use(
      http.patch(`${API}/locations/:id`, async ({ request }) =>
        ok({ ...binder, ...((await request.json()) as object) }),
      ),
    );
    const sent = recordRequests();
    await openPage();
    await list();
    await userEvent.click(openButton('B001-F001-P0001'));
    const dialog = await screen.findByRole('dialog', { name: 'Location B001-F001-P0001' });
    expect(within(dialog).getByText('5 copies · 3 cards')).toBeVisible();
    const description = within(dialog).getByRole('textbox', { name: 'Description' });
    expect(description).toHaveValue('Red binder');
    await userEvent.clear(description);
    await userEvent.type(description, 'Blue binder');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(writes(sent)).toHaveLength(1), LONG);
    // only what changed is sent
    expect(writes(sent)[0]).toMatchObject({
      method: 'PATCH',
      path: '/locations/11',
      body: { description: 'Blue binder' },
    });
    expect(await screen.findByText('Location saved.', {}, LONG)).toBeVisible();

    await userEvent.click(within(dialog).getByRole('switch', { name: 'Lock this location' }));
    await waitFor(() => expect(writes(sent)).toHaveLength(2), LONG);
    expect(writes(sent)[1]).toMatchObject({ path: '/locations/11', body: { locked: true } });
    expect(within(dialog).getByRole('link', { name: 'View cards' })).toHaveAttribute(
      'href',
      '/riftbound/app/collection?location=B001-F001-P0001',
    );
  }, 20000);

  it('deletes after a confirmation that says where the copies go', async () => {
    withLocations();
    server.use(http.delete(`${API}/locations/:id`, () => ok({ deleted: binder })));
    const sent = recordRequests();
    await openPage();
    await list();
    await userEvent.click(openButton('B001-F001-P0001'));
    const dialog = await screen.findByRole('dialog', { name: 'Location B001-F001-P0001' });
    await userEvent.click(within(dialog).getByRole('button', { name: 'Delete location' }));
    const confirm = await screen.findByRole('dialog', { name: 'Delete B001-F001-P0001?' });
    expect(within(confirm).getByText('Its 5 copies go back to unassigned.')).toBeVisible();
    await userEvent.click(within(confirm).getByRole('button', { name: 'Delete' }));
    await waitFor(() => expect(writes(sent)).toHaveLength(1), LONG);
    expect(writes(sent)[0]).toMatchObject({ method: 'DELETE', path: '/locations/11' });
    expect(await screen.findByText('Location deleted.', {}, LONG)).toBeVisible();
    await waitFor(() =>
      expect(screen.queryByRole('dialog', { name: 'Location B001-F001-P0001' })).toBeNull(),
    );
  }, 20000);

  it('shows why a locked deck location cannot be deleted (409)', async () => {
    withLocations();
    server.use(
      http.delete(`${API}/locations/:id`, () =>
        failure(409, { error: 'Conflict', code: 'location_locked', message: 'locked' }),
      ),
    );
    await openPage();
    await list();
    await userEvent.click(openButton(deckLocation.code));
    const dialog = await screen.findByRole('dialog', { name: 'Location DECK-001' });
    // a locked location can still be renamed
    expect(within(dialog).getByRole('textbox', { name: 'Code' })).toBeEnabled();
    expect(within(dialog).getByText('Deck')).toBeVisible();
    await userEvent.click(within(dialog).getByRole('button', { name: 'Delete location' }));
    const confirm = await screen.findByRole('dialog', { name: 'Delete DECK-001?' });
    await userEvent.click(within(confirm).getByRole('button', { name: 'Delete' }));
    const alert = await within(dialog).findByRole('alert', {}, LONG);
    expect(alert).toHaveTextContent('This location is locked. Unlock it first.');
    expect(screen.getByRole('dialog', { name: 'Location DECK-001' })).toBeVisible();
  }, 20000);

  it('empty: says so and offers to create the first location', async () => {
    withLocations([], 12);
    await openPage();
    expect(await screen.findByRole('heading', { name: 'No locations yet' }, LONG)).toBeVisible();
    expect(screen.getByText('Unassigned: 12 copies')).toBeVisible();
    const create = screen.getAllByRole('button', { name: 'New location' });
    await userEvent.click(create[create.length - 1]);
    expect(await screen.findByRole('dialog', { name: 'New location' })).toBeVisible();
  }, 20000);

  it('error: can be retried', async () => {
    signedIn();
    let calls = 0;
    server.use(
      http.get(`${API}/locations`, () => {
        calls += 1;
        return calls === 1
          ? failure(500, { error: 'Internal Server Error' })
          : ok({ items: storageLocations });
      }),
    );
    await renderApp({ path: '/locations', width: PHONE });
    expect(await screen.findByText('Your locations could not be loaded.', {}, LONG)).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await list()).toBeVisible();
  }, 20000);

  it('offline: shows the cached list and disables every change', async () => {
    withLocations();
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    await openPage();
    await list();
    expect(screen.getByText('You need a connection to make changes.')).toBeVisible();
    expect(screen.getByRole('button', { name: 'New location' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Move DECK-001 up' })).toBeDisabled();
    await userEvent.click(openButton('B001-F001-P0001'));
    const dialog = await screen.findByRole('dialog', { name: 'Location B001-F001-P0001' });
    expect(within(dialog).getByRole('textbox', { name: 'Code' })).toBeDisabled();
    expect(within(dialog).getByRole('switch', { name: 'Lock this location' })).toBeDisabled();
    expect(within(dialog).getByRole('button', { name: 'Delete location' })).toBeDisabled();
  }, 20000);

  it('is axe clean', async () => {
    withLocations();
    const { container } = await openPage();
    await list();
    expect(await axe(container)).toHaveNoViolations();
  }, 30000);
});
