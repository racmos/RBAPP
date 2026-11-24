import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { axe } from 'vitest-axe';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { API, failure } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';
import { clearToasts } from '@/components/ui/toastStore';
import {
  ZIGGS_GROUP,
  callsTo,
  matchingApi,
  missingPrintings,
} from '@/test/fixtures/cardmarketMatching';

const LONG = { timeout: 10000 };
const PATH = '/admin/cardmarket/matching';
const BASE = `${API}/admin/cardmarket`;
const ZIGGS = 'Ziggs, Hexplosives Expert';

async function openPrintings(search = '', width = 1280) {
  const rendered = await renderApp({ path: `${PATH}?tab=missing${search}`, width });
  const section = await screen.findByRole('region', { name: 'Extra printings' }, LONG);
  return { ...rendered, section };
}

async function openTable(search = '') {
  const rendered = await openPrintings(search);
  const table = await within(rendered.section).findByRole(
    'table',
    { name: 'Extra printings' },
    LONG,
  );
  return { ...rendered, table };
}

const rowOf = (table: HTMLElement, text: string) =>
  within(table)
    .getAllByRole('row')
    .find((row) => within(row).queryByText(text) !== null)!;

const box = (name: string, ref: string) =>
  screen.getByRole('checkbox', { name: `Create the signed printing of ${name} (${ref})` });

afterEach(() => {
  vi.restoreAllMocks();
  clearToasts();
});

describe('Extra printings in the Missing cards tab (CM-m)', () => {
  it('lists every group with its products, the cards here, the new card and its status', async () => {
    const calls = matchingApi();
    const { section, table } = await openTable();
    expect(
      within(section).getByText(
        /Cardmarket lists more printings of these cards than the catalog has/,
      ),
    ).toBeVisible();
    expect(
      within(table)
        .getAllByRole('columnheader')
        .map((cell) => cell.textContent),
    ).toEqual(['Create', 'Set', 'Cardmarket products', 'Cards here', 'New card', 'Status']);
    const ziggs = within(rowOf(table, ZIGGS)).getAllByRole('cell');
    expect(ziggs.map((cell) => cell.textContent)).toEqual([
      `Create the signed printing of ${ZIGGS} (RAD-169s)`,
      'RAD',
      `${ZIGGS}#917343 · 0.02 € · linked to RAD-141#917370 · 45.00 €#917487 · no price`,
      'RAD-141 · RareRAD-169 · Showcase',
      'RAD-169s (Showcase)',
      'To createCopy of RAD-169, rarity Showcase.',
    ]);
    const last = (text: string) =>
      within(rowOf(table, text)).getAllByRole('cell').at(-1)!.textContent;
    expect(last('Bright Twin')).toBe('By handMore than one extra product: link them by hand.');
    expect(last('Ahri, Alluring')).toBe(
      'By handOGN-066 already has a letter variant: create the card by hand.',
    );
    expect(within(rowOf(table, 'Bright Twin')).getAllByRole('cell')[4]!.textContent).toBe('—');
    expect(callsTo(calls, 'GET', '/missing-printings')).toHaveLength(1);
  });

  it('create rows start checked and manual rows are disabled', async () => {
    matchingApi();
    await openTable();
    expect(box(ZIGGS, 'RAD-169s')).toBeChecked();
    expect(box('Vex, Cheerless', 'RAD-172s')).toBeChecked();
    const twin = screen.getByRole('checkbox', {
      name: 'Create the signed printing of Bright Twin',
    });
    expect(twin).toBeDisabled();
    expect(twin).not.toBeChecked();
    expect(screen.getByText('2 signed printings to create')).toBeVisible();
    expect(screen.getByText('2 groups to handle by hand.')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Create 2 printings' })).toBeEnabled();
  });

  it('the set filter lives in the URL and narrows the list and the request', async () => {
    const calls = matchingApi();
    const user = userEvent.setup();
    const { where } = await openTable();
    const select = screen.getByRole('combobox', { name: 'Extra printings set' });
    expect(
      within(select)
        .getAllByRole('option')
        .map((option) => option.textContent),
    ).toEqual(['All sets', 'Origins (OGN), nothing to create', 'Radiance (RAD), 2 to create']);
    await user.selectOptions(select, 'OGN');
    await vi.waitFor(() => expect(where()).toBe(`${PATH}?tab=missing&printings=OGN`));
    await vi.waitFor(() =>
      expect(
        within(screen.getByRole('table', { name: 'Extra printings' })).queryByText(ZIGGS),
      ).toBeNull(),
    );
    const table = screen.getByRole('table', { name: 'Extra printings' });
    expect(within(table).getByText('Ahri, Alluring')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Create 0 printings' })).toBeDisabled();
    await user.selectOptions(select, 'RAD');
    await user.click(
      await screen.findByRole('checkbox', {
        name: 'Create the signed printing of Vex, Cheerless (RAD-172s)',
      }),
    );
    await user.click(screen.getByRole('button', { name: 'Create 1 printing' }));
    const dialog = await screen.findByRole('dialog', { name: 'Create 1 signed printing?' });
    await user.click(within(dialog).getByRole('button', { name: 'Create 1 printing' }));
    expect(
      (await screen.findAllByText('1 printing created. Run Auto-match to link its products.'))
        .length,
    ).toBeGreaterThan(0);
    expect(callsTo(calls, 'POST', '/missing-printings').map((call) => call.body)).toEqual([
      { items: [{ set_id: 'RAD', card_id: '169s' }] },
    ]);
  });

  it('opens filtered by the set of the URL', async () => {
    matchingApi();
    const { table } = await openTable('&printings=RAD');
    expect(within(table).queryByText('Ahri, Alluring')).toBeNull();
    expect(screen.getByRole('combobox', { name: 'Extra printings set' })).toHaveValue('RAD');
  });

  it('creates every checked printing after confirming, then refreshes', async () => {
    const calls = matchingApi();
    const user = userEvent.setup();
    await openTable();
    await user.click(screen.getByRole('button', { name: 'Create 2 printings' }));
    const dialog = await screen.findByRole('dialog', { name: 'Create 2 signed printings?' });
    expect(
      within(dialog).getByText(
        'Each card copies the highest printing of its group, without the image, with the rarity Showcase. Nothing is linked yet: run Auto-match afterwards.',
      ),
    ).toBeVisible();
    const before = callsTo(calls, 'GET', '/missing-printings').length;
    await user.click(within(dialog).getByRole('button', { name: 'Create 2 printings' }));
    expect(
      (await screen.findAllByText('2 printings created. Run Auto-match to link their products.'))
        .length,
    ).toBeGreaterThan(0);
    expect(callsTo(calls, 'POST', '/missing-printings')[0]!.body).toEqual({
      items: [
        { set_id: 'RAD', card_id: '172s' },
        { set_id: 'RAD', card_id: '169s' },
      ],
    });
    await vi.waitFor(() =>
      expect(callsTo(calls, 'GET', '/missing-printings').length).toBeGreaterThan(before),
    );
  });

  it('cancel writes nothing', async () => {
    const calls = matchingApi();
    const user = userEvent.setup();
    await openTable();
    await user.click(screen.getByRole('button', { name: 'Create 2 printings' }));
    const dialog = await screen.findByRole('dialog', { name: 'Create 2 signed printings?' });
    await user.click(within(dialog).getByRole('button', { name: 'Cancel' }));
    expect(callsTo(calls, 'POST', '/missing-printings')).toEqual([]);
  });

  it('a refused create shows what the server says', async () => {
    matchingApi();
    const user = userEvent.setup();
    const message = 'These cards are not proposed by the missing printings list: RAD-169s.';
    server.use(
      http.post(`${BASE}/missing-printings`, () =>
        failure(400, { error: 'Validation Error', message, code: 'validation_error' }),
      ),
    );
    await openTable();
    await user.click(screen.getByRole('button', { name: 'Create 2 printings' }));
    const dialog = await screen.findByRole('dialog', { name: 'Create 2 signed printings?' });
    await user.click(within(dialog).getByRole('button', { name: 'Create 2 printings' }));
    expect((await screen.findAllByText(message)).length).toBeGreaterThan(0);
  });

  it('an existing signed card says Auto-match links it', async () => {
    matchingApi({
      printings: missingPrintings([
        {
          set_id: 'RAD',
          set_name: 'Radiance',
          groups: [{ ...ZIGGS_GROUP, status: 'exists', reason: 'in_catalog' }],
        },
      ]),
    });
    const { table } = await openTable();
    expect(within(rowOf(table, ZIGGS)).getAllByRole('cell').at(-1)!.textContent).toBe(
      'In the catalogAuto-match links it.',
    );
    expect(box(ZIGGS, 'RAD-169s')).toBeDisabled();
    expect(screen.getByText('1 group already has its card.')).toBeVisible();
  });

  it('an empty list says so', async () => {
    matchingApi({ printings: missingPrintings([]) });
    const { section } = await openPrintings();
    expect(
      await within(section).findByText(
        'No card has more printings on Cardmarket than in the catalog.',
        undefined,
        LONG,
      ),
    ).toBeVisible();
  });

  it('a failed list can be retried', async () => {
    matchingApi();
    server.use(http.get(`${BASE}/missing-printings`, () => failure(500, { error: 'Internal' })));
    const { section } = await openPrintings();
    expect(await within(section).findByRole('button', { name: 'Retry' }, LONG)).toBeVisible();
  });

  it('offline: Create is disabled', async () => {
    matchingApi();
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    await openTable();
    expect(screen.getByRole('button', { name: 'Create 2 printings' })).toBeDisabled();
  });

  it('on a phone each group is a card with its checkbox and the card it creates', async () => {
    matchingApi();
    const { container, section } = await openPrintings('', 390);
    const list = await within(section).findByRole('list', { name: 'Extra printings' }, LONG);
    expect(within(section).queryByRole('table')).toBeNull();
    const items = within(list).getAllByRole('listitem');
    expect(items).toHaveLength(4);
    const ziggs = items.find((item) => within(item).queryByText(ZIGGS) !== null)!;
    expect(within(ziggs).getByText('Will create RAD-169s (Showcase)')).toBeVisible();
    expect(within(ziggs).getByText('Cards here: RAD-141 · Rare, RAD-169 · Showcase')).toBeVisible();
    expect(box(ZIGGS, 'RAD-169s')).toBeChecked();
    expect(await axe(container)).toHaveNoViolations();
  }, 20000);

  it('has no axe violations, with the confirm dialog open too', async () => {
    matchingApi();
    const { container } = await openTable();
    expect(await axe(container)).toHaveNoViolations();
    await userEvent.click(screen.getByRole('button', { name: 'Create 2 printings' }));
    const dialog = await screen.findByRole('dialog', { name: 'Create 2 signed printings?' });
    expect(await axe(dialog)).toHaveNoViolations();
  }, 20000);
});
