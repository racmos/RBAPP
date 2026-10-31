import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { axe } from 'vitest-axe';
import { describe, expect, it } from 'vitest';
import { http } from 'msw';
import { API, adminSession, failure, ok } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';
import { expectCollapsible } from '@/test/sidePanel';

const SETS = [
  {
    id: 'OGN',
    name: 'Origins',
    release_date: '2026-01-01',
    card_count: 2,
    declared_count: 2,
    window: 'monthly',
    next_run_at: '2030-02-01T08:00:00+01:00',
  },
  {
    id: 'SFD',
    name: 'Second',
    release_date: null,
    card_count: 0,
    declared_count: null,
    window: 'monthly',
    next_run_at: '2030-02-01T08:00:00+01:00',
  },
];

function setsApi() {
  server.use(
    http.get(`${API}/auth/session`, () => adminSession()),
    http.get(`${API}/admin/sets`, () => ok(SETS)),
  );
}

describe('SetsPage (F13-f S4-S6)', () => {
  it('table at 1280 px with plain headers, a sort section and the new button', async () => {
    setsApi();
    const { container } = await renderApp({ path: '/admin/sets', width: 1280 });
    // First render of the file pays for the lazy admin chunk.
    const table = await screen.findByRole('table', { name: 'Catalog sets' }, { timeout: 10000 });
    expect(table).toBeVisible();
    const [head] = within(table).getAllByRole('rowgroup');
    expect(within(head!).queryAllByRole('button')).toHaveLength(0);
    expect(screen.getByRole('columnheader', { name: 'Code' })).toHaveAttribute(
      'aria-sort',
      'ascending',
    );
    expect(screen.getByLabelText('Search set')).toBeVisible();
    expect(screen.getByLabelText('Sort by')).toHaveValue('id');
    expect(screen.getByLabelText('Direction')).toHaveValue('asc');
    expect(screen.getByRole('button', { name: 'New set' })).toBeVisible();
    expect(await axe(container)).toHaveNoViolations();
  });

  it('search, sort and direction live in the URL', async () => {
    server.use(
      http.get(`${API}/auth/session`, () => adminSession()),
      http.get(`${API}/admin/sets`, () =>
        ok([
          ...SETS,
          { ...SETS[1], id: 'ARC', name: 'Zeta', release_date: '2025-06-01', card_count: 5 },
        ]),
      ),
    );
    const { where } = await renderApp({ path: '/admin/sets?sort=name&dir=desc', width: 1280 });
    await screen.findByRole('table', { name: 'Catalog sets' });
    // Re-query: a navigation may remount the table.
    const firstCells = () =>
      within(screen.getByRole('table', { name: 'Catalog sets' }))
        .getAllByRole('row')
        .slice(1)
        .map((row) => within(row).getAllByRole('cell')[0]!.textContent);
    expect(firstCells()).toEqual(['ARC', 'SFD', 'OGN']);
    expect(screen.getByRole('columnheader', { name: 'Name' })).toHaveAttribute(
      'aria-sort',
      'descending',
    );

    await userEvent.selectOptions(screen.getByLabelText('Sort by'), 'releaseDate');
    await waitFor(() => expect(where()).toBe('/admin/sets?sort=releaseDate&dir=desc'));
    await waitFor(() => expect(firstCells()).toEqual(['OGN', 'ARC', 'SFD']));
    await userEvent.selectOptions(screen.getByLabelText('Direction'), 'asc');
    await waitFor(() => expect(where()).toBe('/admin/sets?sort=releaseDate&dir=asc'));
    await waitFor(() => expect(firstCells()).toEqual(['SFD', 'ARC', 'OGN']));

    await userEvent.type(screen.getByLabelText('Search set'), 'orig');
    await waitFor(() => expect(where()).toBe('/admin/sets?sort=releaseDate&dir=asc&q=orig'));
    await waitFor(() => expect(firstCells()).toEqual(['OGN']));
  });

  it('a search without matches says so', async () => {
    setsApi();
    await renderApp({ path: '/admin/sets?q=zzz', width: 1280 });
    expect(await screen.findByText('No set matches the search.')).toBeVisible();
    expect(screen.getByLabelText('Search set')).toHaveValue('zzz');
  });

  it.each([1280, 1700])('new set opens the form and creates the set at %i px', async (width) => {
    const created: unknown[] = [];
    let sets = [...SETS];
    server.use(
      http.get(`${API}/auth/session`, () => adminSession()),
      http.get(`${API}/admin/sets`, () => ok(sets)),
      http.post(`${API}/admin/sets`, async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        created.push(body);
        const row = {
          ...SETS[1],
          id: 'TST',
          name: 'Test',
          release_date: '2026-12-04',
          declared_count: 12,
        };
        sets = [...sets, row];
        return ok(row, 201);
      }),
    );
    await renderApp({ path: '/admin/sets', width });
    await userEvent.click(await screen.findByRole('button', { name: 'New set' }));
    await userEvent.type(await screen.findByLabelText('Code'), 'TST');
    await userEvent.type(screen.getByLabelText('Name'), 'Test');
    await userEvent.type(screen.getByLabelText('Release date'), '2026-12-04');
    await userEvent.type(screen.getByLabelText('Announced cards'), '12');
    await userEvent.click(screen.getByRole('button', { name: 'Save' }));
    expect((await screen.findAllByText('Set saved.')).length).toBeGreaterThan(0);
    expect(created).toEqual([
      { id: 'TST', name: 'Test', release_date: '2026-12-04', declared_count: 12 },
    ]);
    expect(await screen.findByRole('cell', { name: 'TST' })).toBeVisible();
    expect(screen.queryByLabelText('Code')).not.toBeInTheDocument();
  });

  it('cards at 390 px with an actions menu, editor in a bottom sheet', async () => {
    setsApi();
    await renderApp({ path: '/admin/sets', width: 390 });
    expect(await screen.findByRole('heading', { name: /OGN/ })).toBeVisible();
    await userEvent.click(screen.getAllByText('Actions')[0]);
    expect(screen.getByRole('button', { name: 'Edit OGN' })).toBeVisible();
  });

  it('persistent editor panel at 1700 px', async () => {
    setsApi();
    await renderApp({ path: '/admin/sets', width: 1700 });
    expect(await screen.findByText('Pick a set to edit it.')).toBeVisible();
    await expectCollapsible(
      screen.getByRole('complementary', { name: 'Editor' }),
      { hide: 'Hide editor', show: 'Show editor' },
      'rb_panel_admin-sets-editor_v1',
    );
  });

  it('create flow shows the API error per field', async () => {
    server.use(
      http.get(`${API}/auth/session`, () => adminSession()),
      http.get(`${API}/admin/sets`, () => ok([])),
      http.post(`${API}/admin/sets`, () =>
        failure(400, {
          message: 'Invalid request data',
          code: 'validation_error',
          details: [{ field: 'release_date', message: 'x', type: 'missing', code: 'required' }],
        }),
      ),
    );
    await renderApp({ path: '/admin/sets', width: 1280 });
    await userEvent.click(await screen.findByRole('button', { name: 'New set' }));
    await userEvent.type(screen.getByLabelText('Code'), 'TST');
    await userEvent.type(screen.getByLabelText('Name'), 'Test');
    await userEvent.type(screen.getByLabelText('Release date'), '2026-12-04');
    await userEvent.click(screen.getByRole('button', { name: 'Save' }));
    expect(await screen.findByText('This field is required.')).toBeVisible();
  });

  it('delete asks for confirmation', async () => {
    setsApi();
    server.use(http.delete(`${API}/admin/sets/OGN`, () => ok({ deleted: 'OGN' })));
    await renderApp({ path: '/admin/sets', width: 1280 });
    await userEvent.click((await screen.findAllByRole('button', { name: 'Delete OGN' }))[0]);
    expect(await screen.findByText('Delete set OGN?')).toBeVisible();
  });
});

describe('SetsPage delete outcome (owner feedback S20)', () => {
  it('closes the question and shows why a set in use cannot be deleted', async () => {
    setsApi();
    server.use(
      http.delete(`${API}/admin/sets/OGN`, () =>
        failure(409, {
          error: 'Conflict',
          message: 'Set in use',
          code: 'set_in_use',
          params: { cards: 3 },
        }),
      ),
    );
    await renderApp({ path: '/admin/sets', width: 1280 });
    await userEvent.click((await screen.findAllByRole('button', { name: 'Delete OGN' }))[0]!);
    const dialog = await screen.findByRole('dialog', { name: 'Delete set OGN?' });
    await userEvent.click(within(dialog).getByRole('button', { name: 'Delete' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(
      (
        await screen.findAllByText(
          /The set has cards; its code cannot be changed and it cannot be deleted/,
        )
      )[0],
    ).toBeVisible();
  }, 20000);

  it('confirms a deleted set with a toast', async () => {
    setsApi();
    server.use(http.delete(`${API}/admin/sets/OGN`, () => ok({ deleted: 'OGN' })));
    await renderApp({ path: '/admin/sets', width: 1280 });
    await userEvent.click((await screen.findAllByRole('button', { name: 'Delete OGN' }))[0]!);
    const dialog = await screen.findByRole('dialog', { name: 'Delete set OGN?' });
    await userEvent.click(within(dialog).getByRole('button', { name: 'Delete' }));
    expect((await screen.findAllByText('Set deleted.'))[0]).toBeVisible();
  }, 20000);
});

describe('SetsPage row actions (owner feedback S20)', () => {
  it('are the shared Button with an icon, like the cards table', async () => {
    setsApi();
    await renderApp({ path: '/admin/sets', width: 1280 });
    const edit = await screen.findByRole('button', { name: 'Edit OGN' });
    const remove = screen.getByRole('button', { name: 'Delete OGN' });
    const buttonClass = screen.getByRole('button', { name: 'New set' }).classList[0]!;
    for (const action of [edit, remove]) {
      expect(action).toHaveClass(buttonClass);
      expect(action.querySelector('svg')).not.toBeNull();
      expect(action.textContent).toBe('');
    }
  });
});
