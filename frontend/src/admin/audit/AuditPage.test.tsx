import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { axe } from 'vitest-axe';
import { describe, expect, it } from 'vitest';
import { API, adminSession, failure, ok, signedInSession } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';

const LONG = { timeout: 10000 };

const ROWS = [
  {
    id: 3,
    created_at: '2030-01-03T07:00:00',
    actor: { id: 1, username: 'root' },
    action: 'cardmarket.link',
    target_type: 'cardmarket_product',
    target_id: '501',
    detail: { set_id: 'OGN', card_id: '001', foil: 'N' },
  },
  {
    id: 2,
    created_at: '2030-01-02T23:59:59',
    actor: null,
    action: 'riot.apply',
    target_type: 'card',
    target_id: 'OGN-001',
    detail: { fields: { name: ['A', 'B'] } },
  },
  {
    id: 1,
    created_at: '2030-01-01T09:00:00',
    actor: { id: null, username: 'former' },
    action: 'future.thing',
    target_type: 'job',
    target_id: '12',
    detail: null,
  },
];

const FACETS = {
  actions: [
    { action: 'cardmarket.link', count: 4 },
    { action: 'riot.apply', count: 2 },
    { action: 'future.thing', count: 1 },
  ],
  target_types: [
    { target_type: 'card', count: 2 },
    { target_type: 'cardmarket_product', count: 4 },
  ],
};

const page = (items = ROWS, meta: Partial<Record<string, number>> = {}) => ({
  items,
  meta: { page: 1, per_page: 50, total: items.length, pages: 1, ...meta },
});

/** The audit API; returns the search params of every list request. */
function auditApi(body = page()) {
  const calls: URLSearchParams[] = [];
  server.use(
    http.get(`${API}/auth/session`, () => adminSession()),
    http.get(`${API}/admin/overview`, () => ok({ catalog: {}, riot: { pending_changes: 0 } })),
    http.get(`${API}/admin/audit/facets`, () => ok(FACETS)),
    http.get(`${API}/admin/audit`, ({ request }) => {
      calls.push(new URL(request.url).searchParams);
      return ok(body);
    }),
  );
  return calls;
}

const table = () => screen.findByRole('table', { name: 'Admin actions' }, LONG);

describe('AuditPage (CM-e)', { timeout: 30000 }, () => {
  it('lists the rows: time, actor or System, readable action, target, axe clean', async () => {
    auditApi();
    const { container } = await renderApp({ path: '/admin/audit', width: 1280 });
    expect(await screen.findByRole('heading', { level: 1, name: 'Audit' }, LONG)).toBeVisible();
    const rows = within(await table())
      .getAllByRole('row')
      .slice(1);
    expect(rows).toHaveLength(3);
    const first = within(rows[0]!);
    expect(first.getByText('root')).toBeVisible();
    expect(first.getByText('Link a Cardmarket product')).toHaveAttribute(
      'title',
      'cardmarket.link',
    );
    expect(first.getByRole('link', { name: /501/ })).toHaveAttribute(
      'href',
      '/riftbound/app/admin/cardmarket/matching?tab=linked&q=501',
    );
    expect(first.getByText('3 Jan 2030', { exact: false })).toBeVisible();
    const second = within(rows[1]!);
    expect(second.getByText('System')).toBeVisible();
    expect(second.getByText('Riot sync applied a card change')).toBeVisible();
    expect(second.getByRole('link', { name: /OGN-001/ })).toHaveAttribute(
      'href',
      '/riftbound/app/admin/cards?q=OGN-001',
    );
    const third = within(rows[2]!);
    expect(third.getByText('former')).toBeVisible();
    // an unknown action shows its code; a target without a safe route is plain text
    expect(third.getByText('future.thing')).toBeVisible();
    expect(third.queryByRole('link')).toBeNull();
    expect(third.getByText(/12/)).toBeVisible();
    expect(await axe(container)).toHaveNoViolations();
  });

  it('the details disclosure shows the stored JSON pretty-printed', async () => {
    auditApi();
    await renderApp({ path: '/admin/audit', width: 1280 });
    const rows = within(await table())
      .getAllByRole('row')
      .slice(1);
    const summary = within(rows[1]!).getByText('Details');
    const pre = rows[1]!.querySelector('pre');
    expect(pre?.textContent).toBe(JSON.stringify({ fields: { name: ['A', 'B'] } }, null, 2));
    expect(pre).not.toBeVisible();
    await userEvent.click(summary);
    expect(pre).toBeVisible();
    // no detail, no disclosure
    expect(within(rows[2]!).queryByText('Details')).toBeNull();
  });

  it('filters land in the URL and are sent to the API', async () => {
    const calls = auditApi();
    await renderApp({ path: '/admin/audit', width: 1280 });
    await table();
    expect(calls.at(-1)!.toString()).toBe('per_page=50');

    const action = screen.getByRole('combobox', { name: 'Action' });
    await waitFor(() =>
      expect(
        within(action).getByRole('option', { name: 'Riot sync applied a card change (2)' }),
      ).toBeTruthy(),
    );
    await userEvent.selectOptions(action, 'riot.apply');
    await waitFor(() => expect(calls.at(-1)!.get('action')).toBe('riot.apply'));

    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Target type' }), 'card');
    await waitFor(() => expect(calls.at(-1)!.get('target_type')).toBe('card'));

    await userEvent.type(screen.getByRole('textbox', { name: 'Actor' }), 'roo');
    await waitFor(() => expect(calls.at(-1)!.get('actor')).toBe('roo'), LONG);

    const from = screen.getByLabelText('From');
    await userEvent.type(from, '2030-01-02');
    await waitFor(() => expect(calls.at(-1)!.get('from')).toBe('2030-01-02'));
    await userEvent.type(screen.getByLabelText('To'), '2030-01-03');
    await waitFor(() => expect(calls.at(-1)!.get('to')).toBe('2030-01-03'));

    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Rows per page' }), '100');
    await waitFor(() => expect(calls.at(-1)!.get('per_page')).toBe('100'));
    const last = calls.at(-1)!;
    expect(Object.fromEntries(last)).toEqual({
      action: 'riot.apply',
      target_type: 'card',
      actor: 'roo',
      from: '2030-01-02',
      to: '2030-01-03',
      per_page: '100',
    });
  });

  it('opens with the filters of the URL, target id included', async () => {
    const calls = auditApi();
    await renderApp({
      path: '/admin/audit?action=cardmarket.link&target_type=cardmarket_product&target_id=501',
      width: 1280,
    });
    await table();
    expect(Object.fromEntries(calls.at(-1)!)).toEqual({
      action: 'cardmarket.link',
      target_type: 'cardmarket_product',
      target_id: '501',
      per_page: '50',
    });
    expect(screen.getByRole('combobox', { name: 'Action' })).toHaveValue('cardmarket.link');
  });

  it('pages through the rows', async () => {
    const calls = auditApi(page(ROWS, { total: 120, pages: 3 }));
    await renderApp({ path: '/admin/audit', width: 1280 });
    await table();
    expect(screen.getByText('Page 1 of 3')).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: 'Next' }));
    await waitFor(() => expect(calls.at(-1)!.get('page')).toBe('2'));
  });

  it('an empty log says so', async () => {
    auditApi(page([]));
    await renderApp({ path: '/admin/audit', width: 1280 });
    expect(await screen.findByRole('heading', { name: 'Nothing recorded' }, LONG)).toBeVisible();
    expect(screen.getByText('No admin action matches these filters.')).toBeVisible();
  });

  it('a failure shows the error state, and retry recovers', async () => {
    let failing = true;
    server.use(
      http.get(`${API}/auth/session`, () => adminSession()),
      http.get(`${API}/admin/overview`, () => ok({ catalog: {}, riot: { pending_changes: 0 } })),
      http.get(`${API}/admin/audit/facets`, () => ok(FACETS)),
      http.get(`${API}/admin/audit`, () =>
        failing ? failure(500, { message: 'boom' }) : ok(page()),
      ),
    );
    await renderApp({ path: '/admin/audit', width: 1280 });
    expect(await screen.findByRole('alert', undefined, LONG)).toBeVisible();
    failing = false;
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await table()).toBeVisible();
  });

  it('shows skeletons while loading', async () => {
    let release!: (value: unknown) => void;
    const gate = new Promise((resolve) => {
      release = resolve;
    });
    server.use(
      http.get(`${API}/auth/session`, () => adminSession()),
      http.get(`${API}/admin/overview`, () => ok({ catalog: {}, riot: { pending_changes: 0 } })),
      http.get(`${API}/admin/audit/facets`, () => ok(FACETS)),
      http.get(`${API}/admin/audit`, async () => {
        await gate;
        return ok(page());
      }),
    );
    await renderApp({ path: '/admin/audit', width: 1280 });
    await screen.findByRole('heading', { level: 1, name: 'Audit' }, LONG);
    expect(document.querySelectorAll('[aria-busy="true"]').length).toBeGreaterThan(0);
    release(null);
    expect(await table()).toBeVisible();
  });

  it('cards at 390 px with the hint, details and System, axe clean', async () => {
    auditApi();
    const { container } = await renderApp({ path: '/admin/audit', width: 390 });
    expect(await screen.findByText('Easier on a computer.', undefined, LONG)).toBeVisible();
    const cards = await screen.findAllByRole('article', undefined, LONG);
    expect(cards).toHaveLength(3);
    expect(screen.queryByRole('table')).toBeNull();
    expect(within(cards[1]!).getByText('System')).toBeVisible();
    expect(within(cards[0]!).getByText('Details')).toBeVisible();
    expect(await axe(container)).toHaveNoViolations();
  });

  it('a signed-in non-admin lands on the 404 view', async () => {
    server.use(http.get(`${API}/auth/session`, () => signedInSession()));
    await renderApp({ path: '/admin/audit', width: 1280 });
    expect(await screen.findByRole('heading', { name: 'Page not found' }, LONG)).toBeVisible();
  });
});
