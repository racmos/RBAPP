import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { axe } from 'vitest-axe';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { API, failure, ok } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';
import { clearToasts } from '@/components/ui/toastStore';
import {
  EXPANSIONS,
  UNNAMED,
  callsTo,
  expansion,
  matchingApi,
} from '@/test/fixtures/cardmarketMatching';

const LONG = { timeout: 10000 };
const PATH = '/admin/cardmarket/matching';
const BASE = `${API}/admin/cardmarket`;

async function openTab(search = '') {
  const rendered = await renderApp({ path: `${PATH}?tab=expansions${search}`, width: 1280 });
  const table = await screen.findByRole('table', { name: 'Cardmarket expansions' }, LONG);
  return { ...rendered, table };
}

const rowOf = (table: HTMLElement, text: string) =>
  within(table)
    .getAllByRole('row')
    .find((row) => within(row).queryByText(text) !== null)!;

async function openMap(table: HTMLElement, name: string, button = `Map ${name} to a set`) {
  await userEvent.click(within(rowOf(table, name)).getByRole('button', { name: button }));
  return screen.findByRole('dialog', { name: `Map ${name}` });
}

afterEach(() => {
  vi.restoreAllMocks();
  // the toast store outlives a render: an Undo left by one test must not reach the next
  clearToasts();
});

describe('Expansions tab (CM-d)', () => {
  it('is the sixth tab and lists the unmapped expansions by default', async () => {
    const calls = matchingApi();
    const { table } = await openTab();
    expect(screen.getByRole('tab', { name: 'Expansions' })).toHaveAttribute(
      'aria-selected',
      'true',
    );
    expect(screen.getByRole('checkbox', { name: 'Not mapped only' })).toBeChecked();
    expect(
      screen.getByText(
        'Mapping lets the matcher prefer cards of that set; it does not change prices.',
      ),
    ).toBeVisible();
    expect(callsTo(calls, 'GET', '/expansions')[0]!.search.toString()).toBe('unmapped=true');
    expect(within(table).getAllByRole('row')).toHaveLength(3);
    const cells = within(rowOf(table, 'Spiritforged')).getAllByRole('cell');
    expect(cells.map((cell) => cell.textContent)).toEqual([
      'Spiritforged',
      '6399',
      '310',
      '300',
      '10',
      'Not mapped',
      'Map to a set',
    ]);
    expect(screen.getByText('2 expansions')).toBeVisible();
  });

  it('Not mapped only off shows the mapped ones with their set; it goes to the URL', async () => {
    const calls = matchingApi();
    const user = userEvent.setup();
    const { where } = await openTab();
    await user.click(screen.getByRole('checkbox', { name: 'Not mapped only' }));
    await vi.waitFor(() => expect(where()).toBe(`${PATH}?tab=expansions&show=all`));
    const table = await screen.findByRole('table', { name: 'Cardmarket expansions' });
    await vi.waitFor(() => expect(within(table).getAllByRole('row')).toHaveLength(4));
    expect(callsTo(calls, 'GET', '/expansions').at(-1)!.search.toString()).toBe('');
    const origins = within(rowOf(table, '6286')).getAllByRole('cell');
    expect(origins[5]).toHaveTextContent('Origins (OGN)');
    expect(
      within(origins[6]!).getByRole('button', { name: 'Change the set of Origins' }),
    ).toBeEnabled();
    expect(within(origins[6]!).getByRole('button', { name: 'Unmap Origins' })).toBeEnabled();
  });

  it('a mapped expansion whose set is gone shows its id', async () => {
    matchingApi({ expansions: [expansion(1, 'Ghost', 'GONE')] });
    const { table } = await openTab('&show=all');
    expect(within(rowOf(table, 'Ghost')).getAllByRole('cell')[5]).toHaveTextContent(
      'GONE (not a set)',
    );
  });

  it('Map to an existing set sends the set; Undo unmaps', async () => {
    const calls = matchingApi();
    const user = userEvent.setup();
    const { table } = await openTab();
    const dialog = await openMap(table, 'Spiritforged');
    const select = within(dialog).getByRole('combobox', { name: 'Set' });
    expect(
      within(select)
        .getAllByRole('option')
        .map((option) => option.textContent),
    ).toEqual(['Choose a set', 'Origins (OGN)', 'Proving Grounds (OGS)', 'Create a new set…']);
    expect(within(dialog).getByRole('button', { name: 'Map' })).toBeDisabled();
    await user.selectOptions(select, 'OGS');
    await user.click(within(dialog).getByRole('button', { name: 'Map' }));
    expect((await screen.findAllByText('Mapped Spiritforged to OGS.')).length).toBeGreaterThan(0);
    expect(callsTo(calls, 'PUT', '/expansions/6399').map((call) => call.body)).toEqual([
      { set_id: 'OGS' },
    ]);
    expect(screen.queryByRole('dialog', { name: 'Map Spiritforged' })).toBeNull();
    // the list and the counters reload
    await vi.waitFor(() => expect(callsTo(calls, 'GET', '/expansions').length).toBeGreaterThan(1));
    await vi.waitFor(() => expect(callsTo(calls, 'GET', '/status').length).toBeGreaterThan(1));
    await user.click(screen.getByRole('button', { name: 'Undo' }));
    await vi.waitFor(() =>
      expect(callsTo(calls, 'DELETE', '/expansions/6399/mapping')).toHaveLength(1),
    );
  });

  it('Create a new set opens the set fields and sends them with the mapping', async () => {
    const calls = matchingApi();
    const user = userEvent.setup();
    const { table } = await openTab();
    const dialog = await openMap(table, 'Spiritforged');
    await user.selectOptions(
      within(dialog).getByRole('combobox', { name: 'Set' }),
      'Create a new set…',
    );
    await user.type(within(dialog).getByRole('textbox', { name: /Code/ }), 'sfd');
    await user.type(within(dialog).getByRole('textbox', { name: /Name/ }), 'Spiritforged');
    await user.type(within(dialog).getByLabelText(/Release date/), '2026-02-13');
    await user.type(within(dialog).getByRole('spinbutton', { name: /Announced cards/ }), '220');
    await user.click(within(dialog).getByRole('button', { name: 'Save' }));
    expect(
      (await screen.findAllByText('Created set SFD and mapped Spiritforged to it.')).length,
    ).toBeGreaterThan(0);
    expect(callsTo(calls, 'PUT', '/expansions/6399').map((call) => call.body)).toEqual([
      {
        set_id: 'sfd',
        create_set: { name: 'Spiritforged', release_date: '2026-02-13', declared_count: 220 },
      },
    ]);
    // Undo only unmaps: the new set stays
    await user.click(screen.getByRole('button', { name: 'Undo' }));
    await vi.waitFor(() =>
      expect(callsTo(calls, 'DELETE', '/expansions/6399/mapping')).toHaveLength(1),
    );
    expect(callsTo(calls, 'DELETE', /^\/sets/)).toHaveLength(0);
  });

  it('Cancel in the new set fields goes back to the set list', async () => {
    matchingApi();
    const user = userEvent.setup();
    const { table } = await openTab();
    const dialog = await openMap(table, 'Spiritforged');
    await user.selectOptions(
      within(dialog).getByRole('combobox', { name: 'Set' }),
      'Create a new set…',
    );
    await user.click(within(dialog).getByRole('button', { name: 'Cancel' }));
    expect(within(dialog).getByRole('combobox', { name: 'Set' })).toHaveValue('');
    expect(within(dialog).queryByRole('textbox', { name: /Code/ })).toBeNull();
  });

  it('Change maps to another set; Undo maps back to the previous one', async () => {
    const calls = matchingApi();
    const user = userEvent.setup();
    const { table } = await openTab('&show=all');
    const dialog = await openMap(table, 'Origins', 'Change the set of Origins');
    const select = within(dialog).getByRole('combobox', { name: 'Set' });
    expect(select).toHaveValue('OGN');
    await user.selectOptions(select, 'OGS');
    await user.click(within(dialog).getByRole('button', { name: 'Map' }));
    expect((await screen.findAllByText('Mapped Origins to OGS.')).length).toBeGreaterThan(0);
    await user.click(screen.getByRole('button', { name: 'Undo' }));
    await vi.waitFor(() =>
      expect(callsTo(calls, 'PUT', '/expansions/6286').map((call) => call.body)).toEqual([
        { set_id: 'OGS' },
        { set_id: 'OGN' },
      ]),
    );
  });

  it('Unmap removes the set; Undo maps it back', async () => {
    const calls = matchingApi();
    const user = userEvent.setup();
    const { table } = await openTab('&show=all');
    await user.click(within(rowOf(table, '6286')).getByRole('button', { name: 'Unmap Origins' }));
    expect((await screen.findAllByText('Unmapped Origins.')).length).toBeGreaterThan(0);
    expect(callsTo(calls, 'DELETE', '/expansions/6286/mapping')).toHaveLength(1);
    await user.click(screen.getByRole('button', { name: 'Undo' }));
    await vi.waitFor(() =>
      expect(callsTo(calls, 'PUT', '/expansions/6286').map((call) => call.body)).toEqual([
        { set_id: 'OGN' },
      ]),
    );
  });

  it('a refused new set shows the server errors on its fields', async () => {
    matchingApi();
    server.use(
      http.put(`${BASE}/expansions/:id`, () =>
        failure(400, {
          error: 'Validation Error',
          message: 'Invalid request data',
          code: 'validation_error',
          details: [
            {
              field: 'set_id',
              message: 'String should match pattern',
              type: 'string_pattern_mismatch',
              code: 'invalid_format',
            },
          ],
        }),
      ),
    );
    const user = userEvent.setup();
    const { table } = await openTab();
    const dialog = await openMap(table, 'Spiritforged');
    await user.selectOptions(
      within(dialog).getByRole('combobox', { name: 'Set' }),
      'Create a new set…',
    );
    await user.type(within(dialog).getByRole('textbox', { name: /Code/ }), 's');
    await user.type(within(dialog).getByRole('textbox', { name: /Name/ }), 'X');
    await user.type(within(dialog).getByLabelText(/Release date/), '2026-02-13');
    await user.click(within(dialog).getByRole('button', { name: 'Save' }));
    const code = within(dialog).getByRole('textbox', { name: /Code/ });
    await vi.waitFor(() => expect(code).toHaveAttribute('aria-invalid', 'true'));
  });

  it('a set that already exists is shown on the code', async () => {
    matchingApi();
    server.use(
      http.put(`${BASE}/expansions/:id`, () =>
        failure(409, {
          error: 'Conflict',
          message: "Set 'OGN' already exists.",
          code: 'already_exists',
          params: { field: 'set_id' },
        }),
      ),
    );
    const user = userEvent.setup();
    const { table } = await openTab();
    const dialog = await openMap(table, 'Spiritforged');
    await user.selectOptions(
      within(dialog).getByRole('combobox', { name: 'Set' }),
      'Create a new set…',
    );
    await user.type(within(dialog).getByRole('textbox', { name: /Code/ }), 'OGN');
    await user.type(within(dialog).getByRole('textbox', { name: /Name/ }), 'Origins');
    await user.type(within(dialog).getByLabelText(/Release date/), '2026-02-13');
    await user.click(within(dialog).getByRole('button', { name: 'Save' }));
    expect(
      await within(dialog).findByText(
        'A set with this code already exists; choose it in the list.',
      ),
    ).toBeVisible();
  });

  it('a failed map of an existing set keeps the dialog with the error', async () => {
    matchingApi();
    server.use(
      http.put(`${BASE}/expansions/:id`, () =>
        failure(404, { error: 'Not Found', message: 'Cardmarket expansion 6399 not found.' }),
      ),
    );
    const user = userEvent.setup();
    const { table } = await openTab();
    const dialog = await openMap(table, 'Spiritforged');
    await user.selectOptions(within(dialog).getByRole('combobox', { name: 'Set' }), 'OGN');
    await user.click(within(dialog).getByRole('button', { name: 'Map' }));
    expect(await within(dialog).findByRole('alert')).toBeVisible();
    expect(screen.getByRole('dialog', { name: 'Map Spiritforged' })).toBeVisible();
  });

  it('a failed list shows the error with a retry', async () => {
    matchingApi();
    server.use(
      http.get(`${BASE}/expansions`, () =>
        failure(500, { error: 'Internal Server Error', message: 'boom' }),
      ),
    );
    await renderApp({ path: `${PATH}?tab=expansions`, width: 1280 });
    expect(await screen.findByRole('button', { name: /retry/i }, LONG)).toBeVisible();
  });

  it('nothing left to map says so', async () => {
    matchingApi({ expansions: [] });
    await renderApp({ path: `${PATH}?tab=expansions`, width: 1280 });
    expect(await screen.findByText('Every expansion is mapped', undefined, LONG)).toBeVisible();
  });

  it('offline: every write is disabled', async () => {
    matchingApi();
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    const { table } = await openTab('&show=all');
    expect(
      within(rowOf(table, 'Spiritforged')).getByRole('button', {
        name: 'Map Spiritforged to a set',
      }),
    ).toBeDisabled();
    expect(
      within(rowOf(table, '6286')).getByRole('button', { name: 'Unmap Origins' }),
    ).toBeDisabled();
    expect(
      within(rowOf(table, '6286')).getByRole('button', { name: 'Change the set of Origins' }),
    ).toBeDisabled();
  });

  it('has no axe violations, with the map dialog open too', async () => {
    matchingApi();
    const { container, table } = await openTab('&show=all');
    expect(await axe(container)).toHaveNoViolations();
    const dialog = await openMap(table, 'Spiritforged');
    await userEvent.selectOptions(
      within(dialog).getByRole('combobox', { name: 'Set' }),
      'Create a new set…',
    );
    expect(await axe(dialog)).toHaveNoViolations();
  }, 20000);
});

describe('Expansion context (CM-d samples)', () => {
  const HINT = 'Looks like Proving Grounds (OGS) — 4 of 5 linked products';

  it('an unnamed expansion shows its samples, price range, first seen and the hint', async () => {
    matchingApi({ expansions: [UNNAMED, ...EXPANSIONS] });
    const { table } = await openTab();
    const row = rowOf(table, 'Expansion #6567');
    const cell = within(row).getAllByRole('cell')[0]!;
    const samples = within(cell).getByText(
      'Ahri, Nine-Tailed Fox, Vi, Enforcer, Jinx, Loose Cannon +2',
    );
    expect(samples).toHaveAttribute(
      'title',
      'Ahri, Nine-Tailed Fox, Vi, Enforcer, Jinx, Loose Cannon, Proving Grounds Booster Box, Proving Grounds Booster',
    );
    expect(within(cell).getByText('0.02 € - 34.00 €')).toBeVisible();
    expect(within(cell).getByText('First seen 14 Jul 2025')).toBeVisible();
    expect(within(cell).getByRole('button', { name: HINT })).toBeEnabled();
    // the other columns keep their place
    expect(within(row).getAllByRole('cell')[1]).toHaveTextContent('6567');
  });

  it('three samples or fewer have no +N', async () => {
    matchingApi({
      expansions: [
        expansion(1, 'Small', null, { sample_products: UNNAMED.sample_products.slice(0, 2) }),
      ],
    });
    const { table } = await openTab();
    const samples = within(rowOf(table, 'Small')).getByText('Ahri, Nine-Tailed Fox, Vi, Enforcer');
    expect(samples).toHaveAttribute('title', 'Ahri, Nine-Tailed Fox, Vi, Enforcer');
  });

  it('no context shows the name alone, and no hint', async () => {
    matchingApi();
    const { table } = await openTab();
    const cell = within(rowOf(table, 'Spiritforged')).getAllByRole('cell')[0]!;
    expect(cell).toHaveTextContent(/^Spiritforged$/);
    expect(within(cell).queryByRole('button')).toBeNull();
  });

  it('no hint when the suggestion is the set it is mapped to', async () => {
    matchingApi();
    const { table } = await openTab('&show=all');
    expect(within(rowOf(table, '6286')).queryByRole('button', { name: /Looks like/ })).toBeNull();
  });

  it('the hint opens the map dialog with the suggested set chosen; the user confirms', async () => {
    const calls = matchingApi({ expansions: [UNNAMED, ...EXPANSIONS] });
    const user = userEvent.setup();
    const { table } = await openTab();
    await user.click(within(rowOf(table, 'Expansion #6567')).getByRole('button', { name: HINT }));
    const dialog = await screen.findByRole('dialog', { name: 'Map Expansion #6567' });
    expect(within(dialog).getByRole('combobox', { name: 'Set' })).toHaveValue('OGS');
    // nothing is written until Map
    expect(callsTo(calls, 'PUT', '/expansions/6567')).toHaveLength(0);
    await user.click(within(dialog).getByRole('button', { name: 'Map' }));
    await vi.waitFor(() =>
      expect(callsTo(calls, 'PUT', '/expansions/6567').map((call) => call.body)).toEqual([
        { set_id: 'OGS' },
      ]),
    );
  });

  it('Map to a set keeps no set chosen, and the dialog lists the samples', async () => {
    matchingApi({ expansions: [UNNAMED, ...EXPANSIONS] });
    const { table } = await openTab();
    const dialog = await openMap(table, 'Expansion #6567');
    expect(within(dialog).getByRole('combobox', { name: 'Set' })).toHaveValue('');
    const list = within(dialog).getByRole('list', { name: 'Sample products of the latest load' });
    expect(
      within(list)
        .getAllByRole('listitem')
        .map((item) => item.textContent),
    ).toEqual([
      'Ahri, Nine-Tailed Fox · 34.00 €',
      'Vi, Enforcer · 12.50 €',
      'Jinx, Loose Cannon · 3.20 €',
      'Proving Grounds Booster Box (sealed) · 95.00 €',
      'Proving Grounds Booster (sealed) · no price',
    ]);
  });

  it('a dialog without samples says so', async () => {
    matchingApi();
    const { table } = await openTab();
    const dialog = await openMap(table, 'Spiritforged');
    expect(within(dialog).getByText('No products on the latest load.')).toBeVisible();
    expect(within(dialog).queryByRole('list')).toBeNull();
  });

  it('offline: the hint is disabled', async () => {
    matchingApi({ expansions: [UNNAMED] });
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    const { table } = await openTab();
    expect(
      within(rowOf(table, 'Expansion #6567')).getByRole('button', { name: HINT }),
    ).toBeDisabled();
  });

  it('has no axe violations with the context and the dialog samples', async () => {
    matchingApi({ expansions: [UNNAMED, ...EXPANSIONS] });
    const { container, table } = await openTab();
    expect(await axe(container)).toHaveNoViolations();
    await userEvent.click(
      within(rowOf(table, 'Expansion #6567')).getByRole('button', { name: HINT }),
    );
    const dialog = await screen.findByRole('dialog', { name: 'Map Expansion #6567' });
    expect(await axe(dialog)).toHaveNoViolations();
  }, 20000);
});

describe('Unmapped expansions counters link to the tab (CM-d)', () => {
  it('in the workbench header', async () => {
    matchingApi();
    const user = userEvent.setup();
    const { where } = await renderApp({ path: PATH, width: 1280 });
    const counter = await screen.findByRole('link', { name: 'Unmapped expansions: 2' }, LONG);
    expect(counter).toHaveAttribute(
      'href',
      '/riftbound/app/admin/cardmarket/matching?tab=expansions',
    );
    await user.click(counter);
    await vi.waitFor(() => expect(where()).toBe(`${PATH}?tab=expansions`));
    expect(await screen.findByRole('table', { name: 'Cardmarket expansions' }, LONG)).toBeVisible();
  });

  it('in the Cardmarket page header', async () => {
    matchingApi();
    server.use(
      http.get(`${BASE}/loads`, () => ok({ items: [] })),
      http.get(`${API}/admin/jobs`, () => ok({ items: [] })),
    );
    await renderApp({ path: '/admin/cardmarket', width: 1280 });
    const header = await screen.findByRole('region', { name: 'Status' }, LONG);
    expect(
      await within(header).findByRole('link', { name: 'Unmapped expansions: 2' }),
    ).toHaveAttribute('href', '/riftbound/app/admin/cardmarket/matching?tab=expansions');
  });
});
