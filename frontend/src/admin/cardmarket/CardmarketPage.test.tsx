import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { axe } from 'vitest-axe';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { API, adminSession, failure, ok, signedInSession } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';

const LONG = { timeout: 10000 };
const PATH = '/admin/cardmarket';

type Job = {
  id: number;
  status: string;
  queued_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  message: string | null;
};

const JOB_OK: Job = {
  id: 41,
  status: 'success',
  queued_at: '2026-11-06T05:30:00',
  started_at: '2026-11-06T05:30:05',
  finished_at: '2026-11-06T05:30:15',
  message: null,
};

const STATUS = {
  last_load: { date: '2026-11-06', status: 'success', loaded_at: '2026-11-06T05:30:14' },
  loaded_today: true,
  job: JOB_OK,
  unmatched: 12,
  unmapped_expansions: 2,
  prices_as_of: '2026-11-06',
};

const files = (status = 'success') => [
  {
    type: 'price_guide',
    rows: 9100,
    status,
    message: 'ok',
    loaded_at: '2026-11-06T05:30:10',
  },
  { type: 'singles', rows: 1200, status, message: 'ok', loaded_at: '2026-11-06T05:30:12' },
  { type: 'nonsingles', rows: 300, status, message: 'ok', loaded_at: '2026-11-06T05:30:14' },
];

const sample = (id: number, name: string) => ({
  id_product: id,
  name,
  category: 'Riftbound Booster',
  type: 'nonsingle',
  low_price: 4.5,
});

const DAY_NEW = {
  date: '2026-11-06',
  files: files(),
  status: 'success',
  products_total: 1500,
  new_products: 3,
  new_products_sample: [sample(1, 'Booster A'), sample(2, 'Booster B'), sample(3, 'Booster C')],
  unmatched_singles: 12,
  duration_seconds: 10,
  job_id: 41,
};
const DAY_OLD = {
  date: '2026-11-05',
  files: files('skipped'),
  status: 'skipped',
  products_total: 0,
  new_products: null,
  new_products_sample: [],
  unmatched_singles: null,
  duration_seconds: null,
  job_id: null,
};

const RECENT = [
  {
    id: 41,
    kind: 'daily_prices',
    status: 'success',
    requested_by: null,
    requested_at: '2026-11-06T05:30:00',
    started_at: '2026-11-06T05:30:05',
    finished_at: '2026-11-06T05:30:15',
    message: null,
  },
  {
    id: 40,
    kind: 'daily_prices',
    status: 'error',
    requested_by: 'root',
    requested_at: '2026-11-05T05:30:00',
    started_at: '2026-11-05T05:30:01',
    finished_at: '2026-11-05T05:30:03',
    message: 'Download of the price guide failed',
  },
];

function cardmarketApi({
  status = STATUS as unknown,
  loads = [DAY_NEW, DAY_OLD] as unknown[],
  jobs = RECENT as unknown[],
} = {}) {
  server.use(
    http.get(`${API}/auth/session`, () => adminSession()),
    http.get(`${API}/admin/overview`, () =>
      ok({
        catalog: { sets: 1, sets_without_release_date: 0, cards: 1, cards_without_image: 0 },
        riot: { pending_changes: 0, active_sets: [], last_sync: null, placeholder_sets: [] },
      }),
    ),
    http.get(`${API}/admin/cardmarket/status`, () => ok(status)),
    http.get(`${API}/admin/cardmarket/loads`, () => ok({ items: loads })),
    http.get(`${API}/admin/jobs`, () => ok({ items: jobs })),
  );
}

async function openPage(width = 1280) {
  const rendered = await renderApp({ path: PATH, width });
  await screen.findByRole('heading', { name: 'Cardmarket', level: 1 }, LONG);
  return rendered;
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('CardmarketPage header (CM-a)', () => {
  it('shows the last load, today, prices, the latest job and the counters', async () => {
    cardmarketApi();
    await openPage();
    const header = await screen.findByRole('region', { name: 'Status' }, LONG);
    expect(await within(header).findByText('Loaded today')).toBeVisible();
    expect(within(header).getAllByText('6 Nov 2026').length).toBeGreaterThan(0);
    expect(within(header).getByText('Success')).toBeVisible();
    expect(within(header).getByText('Finished')).toBeVisible();
    expect(within(header).getByText('Unmatched products: 12')).toBeVisible();
    expect(within(header).getByText('Unmapped expansions: 2')).toBeVisible();
    // CM-b: the unmatched counter opens the matching workbench; expansions wait for CM-d
    expect(
      within(header)
        .getAllByRole('link')
        .map((link) => link.textContent),
    ).toEqual(['Unmatched products: 12']);
    expect(within(header).getByRole('link', { name: 'Unmatched products: 12' })).toHaveAttribute(
      'href',
      '/riftbound/app/admin/cardmarket/matching?type=single',
    );
    expect(within(header).getByRole('button', { name: 'Load now' })).toBeEnabled();
  });

  it('warns when nothing was loaded today', async () => {
    cardmarketApi({ status: { ...STATUS, loaded_today: false } });
    await openPage();
    expect(await screen.findByText('No load today yet', undefined, LONG)).toBeVisible();
    expect(screen.queryByText('Loaded today')).toBeNull();
  });

  it('says so when there is no load and no job yet', async () => {
    cardmarketApi({
      status: { ...STATUS, last_load: null, loaded_today: false, job: null, prices_as_of: null },
      loads: [],
      jobs: [],
    });
    await openPage();
    expect(await screen.findByText('No load yet.', undefined, LONG)).toBeVisible();
    expect(screen.getByText('No load job yet.')).toBeVisible();
    expect(screen.getByRole('heading', { name: 'No loads yet' })).toBeVisible();
  });

  it('a running job disables Load now', async () => {
    cardmarketApi({
      status: { ...STATUS, job: { ...JOB_OK, status: 'running', finished_at: null } },
    });
    await openPage();
    const header = await screen.findByRole('region', { name: 'Status' }, LONG);
    expect(await within(header).findByText('Running')).toBeVisible();
    expect(within(header).getByRole('button', { name: 'Load now' })).toBeDisabled();
  });

  it('shows the message of a failed job', async () => {
    cardmarketApi({
      status: { ...STATUS, job: { ...JOB_OK, status: 'error', message: 'Price guide invalid' } },
    });
    await openPage();
    const header = await screen.findByRole('region', { name: 'Status' }, LONG);
    expect(await within(header).findByText('Error')).toBeVisible();
    expect(within(header).getByText('Price guide invalid')).toBeVisible();
  });

  it('offline: Load now is disabled', async () => {
    cardmarketApi();
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    await openPage();
    const header = await screen.findByRole('region', { name: 'Status' }, LONG);
    expect(await within(header).findByRole('button', { name: 'Load now' })).toBeDisabled();
  });

  it('a status failure offers a retry', async () => {
    cardmarketApi();
    let calls = 0;
    server.use(
      http.get(`${API}/admin/cardmarket/status`, () => {
        calls += 1;
        return calls === 1 ? failure(500) : ok(STATUS);
      }),
    );
    await openPage();
    await userEvent.click(await screen.findByRole('button', { name: 'Retry' }, LONG));
    expect(await screen.findByText('Unmatched products: 12')).toBeVisible();
  });
});

describe('CardmarketPage Load now (CM-a)', () => {
  it(
    'asks, queues the load, polls the status and refreshes the list when it ends',
    { timeout: 30000 },
    async () => {
      const user = userEvent.setup();
      let posts = 0;
      let loadCalls = 0;
      let statusJob: Job = JOB_OK;
      let polls = 0;
      cardmarketApi();
      server.use(
        http.get(`${API}/admin/cardmarket/loads`, () => {
          loadCalls += 1;
          return ok({ items: [DAY_NEW, DAY_OLD] });
        }),
        http.get(`${API}/admin/cardmarket/status`, () => {
          if (statusJob.status === 'queued') {
            polls += 1;
            // the first poll still sees it running, the next one finished
            if (polls > 1) statusJob = { ...statusJob, status: 'success' };
          }
          return ok({ ...STATUS, job: statusJob });
        }),
        http.post(`${API}/admin/cardmarket/load`, () => {
          posts += 1;
          statusJob = { ...JOB_OK, id: 42, status: 'queued', started_at: null, finished_at: null };
          return ok({ job_id: 42, job: statusJob }, 202);
        }),
      );
      await openPage();
      await screen.findByText('Unmatched products: 12', undefined, LONG);
      const loadsBefore = loadCalls;
      await user.click(screen.getByRole('button', { name: 'Load now' }));
      const dialog = await screen.findByRole('dialog', {
        name: 'Load the Cardmarket files now?',
      });
      await user.click(within(dialog).getByRole('button', { name: 'Load now' }));
      expect((await screen.findAllByText('Load queued.')).length).toBeGreaterThan(0);
      expect(posts).toBe(1);
      const header = screen.getByRole('region', { name: 'Status' });
      expect(within(header).getByRole('button', { name: 'Load now' })).toBeDisabled();
      expect(within(header).getByText('Queued')).toBeVisible();
      await vi.waitFor(
        () => expect(within(header).getByRole('button', { name: 'Load now' })).toBeEnabled(),
        { timeout: 15000 },
      );
      await vi.waitFor(() => expect(loadCalls).toBeGreaterThan(loadsBefore), { timeout: 5000 });
    },
  );

  it('cancel sends nothing', async () => {
    let posts = 0;
    cardmarketApi();
    server.use(
      http.post(`${API}/admin/cardmarket/load`, () => {
        posts += 1;
        return ok({}, 202);
      }),
    );
    await openPage();
    await userEvent.click(await screen.findByRole('button', { name: 'Load now' }, LONG));
    const dialog = await screen.findByRole('dialog');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }));
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(posts).toBe(0);
  });

  it('a load already active (409 job_running) shows the translated toast', async () => {
    cardmarketApi();
    server.use(
      http.post(`${API}/admin/cardmarket/load`, () =>
        failure(409, { message: 'busy', code: 'job_running' }),
      ),
    );
    await openPage();
    await userEvent.click(await screen.findByRole('button', { name: 'Load now' }, LONG));
    const dialog = await screen.findByRole('dialog');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Load now' }));
    expect(
      (await screen.findAllByText('A Cardmarket load is already queued or running.')).length,
    ).toBeGreaterThan(0);
  });
});

describe('CardmarketPage load days (CM-a)', () => {
  it('lists one row per day with files, products, new products and duration', async () => {
    cardmarketApi();
    const { container } = await openPage();
    const table = await screen.findByRole('table', { name: 'Cardmarket load days' }, LONG);
    const rows = within(table).getAllByRole('row');
    expect(rows).toHaveLength(3);
    const latest = within(rows[1]!).getAllByRole('cell');
    expect(latest[0]).toHaveTextContent('6 Nov 2026');
    expect(latest[1]).toHaveTextContent('Success');
    for (const label of ['Price guide', 'Singles', 'Non-singles']) {
      expect(within(latest[2]!).getByText(label)).toBeVisible();
    }
    expect(within(latest[2]!).getByText('9,100')).toBeVisible();
    expect(latest[3]).toHaveTextContent('1,500');
    expect(within(latest[4]!).getByText('3')).toHaveAttribute('data-highlight');
    expect(latest[5]).toHaveTextContent('12');
    expect(latest[6]).toHaveTextContent('10 s');
    const older = within(rows[2]!).getAllByRole('cell');
    expect(older[1]).toHaveTextContent(/^Skipped$/);
    expect(older[3]).toHaveTextContent('0');
    // no new products count, no unmatched (older day) and no duration
    expect([older[4], older[5], older[6]].map((cell) => cell!.textContent)).toEqual([
      '—',
      '—',
      '—',
    ]);
    expect(await axe(container)).toHaveNoViolations();
  });

  it('Show more asks for 120 days', async () => {
    const days = Array.from({ length: 30 }, (_, index) => ({
      ...DAY_OLD,
      date: `2026-10-${String(30 - index).padStart(2, '0')}`,
    }));
    const limits: string[] = [];
    cardmarketApi();
    server.use(
      http.get(`${API}/admin/cardmarket/loads`, ({ request }) => {
        limits.push(new URL(request.url).searchParams.get('limit') ?? '');
        return ok({ items: days });
      }),
    );
    await openPage();
    await userEvent.click(await screen.findByRole('button', { name: 'Show more' }, LONG));
    await vi.waitFor(() => expect(limits).toEqual(['30', '120']));
  });

  it('no Show more when the list is shorter than the limit', async () => {
    cardmarketApi();
    await openPage();
    await screen.findByRole('table', { name: 'Cardmarket load days' }, LONG);
    expect(screen.queryByRole('button', { name: 'Show more' })).toBeNull();
  });

  it('a list failure offers a retry', async () => {
    cardmarketApi();
    let calls = 0;
    server.use(
      http.get(`${API}/admin/cardmarket/loads`, () => {
        calls += 1;
        return calls === 1 ? failure(500) : ok({ items: [DAY_NEW] });
      }),
    );
    await openPage();
    await userEvent.click(await screen.findByRole('button', { name: 'Retry' }, LONG));
    expect(await screen.findByRole('table', { name: 'Cardmarket load days' })).toBeVisible();
  });

  it('phones get cards instead of the table', async () => {
    cardmarketApi();
    const { container } = await openPage(390);
    const list = await screen.findByRole('list', { name: 'Cardmarket load days' }, LONG);
    expect(screen.queryByRole('table')).toBeNull();
    const cards = within(list).getAllByRole('listitem');
    expect(cards).toHaveLength(2);
    expect(within(cards[0]!).getByText('6 Nov 2026')).toBeVisible();
    expect(within(cards[0]!).getByText('3')).toHaveAttribute('data-highlight');
    expect(within(cards[0]!).getByRole('button', { name: 'Details of 6 Nov 2026' })).toBeVisible();
    expect(await axe(container)).toHaveNoViolations();
  });
});

describe('CardmarketPage day detail (CM-a)', () => {
  const detail = {
    ...DAY_NEW,
    new_products_sample: undefined,
    files: [
      { ...files('error')[0], message: 'timeout', loaded_at: '2026-11-06T05:00:00' },
      ...files(),
    ],
    new_products: 502,
    new_products_list: [
      sample(1, 'Booster A'),
      { ...sample(2, 'Booster B'), low_price: null, category: null, type: null },
    ],
    truncated: true,
    job: {
      ...JOB_OK,
      result: {
        validation: { date: '20261106', price_rows: 9100, products_today: 1500, new_products: 3 },
        auto_match: { linked: 4, proposed: 6, review: 2 },
        review: [],
        review_total: 2,
        queued: ['value_snapshot'],
        extra: { unknown: true },
      },
    },
  };

  it('shows every run, the new products, the job and its result', async () => {
    cardmarketApi();
    server.use(http.get(`${API}/admin/cardmarket/loads/2026-11-06`, () => ok(detail)));
    const { container } = await openPage();
    await userEvent.click(
      await screen.findByRole('button', { name: 'Details of 6 Nov 2026' }, LONG),
    );
    const dialog = await screen.findByRole('dialog', { name: 'Load of 6 Nov 2026' });
    const runs = await within(dialog).findByRole('list', { name: 'Files' });
    expect(within(runs).getAllByRole('listitem')).toHaveLength(4);
    expect(within(runs).getByText('timeout')).toBeVisible();
    const fresh = within(dialog).getByRole('list', { name: 'New products' });
    expect(within(fresh).getByText('Booster A')).toBeVisible();
    expect(within(fresh).getByText(/4\.50 €/)).toBeVisible();
    expect(within(fresh).getByText('Booster B')).toBeVisible();
    expect(within(dialog).getByText('500 more')).toBeVisible();
    expect(within(dialog).getByText('Auto-linked')).toBeVisible();
    expect(within(dialog).getByText('Follow-up jobs')).toBeVisible();
    expect(within(dialog).getByText('value_snapshot')).toBeVisible();
    expect(within(dialog).getByText('Raw result')).toBeVisible();
    expect(within(dialog).getByText('10 s')).toBeVisible();
    expect(await axe(container)).toHaveNoViolations();
  });

  it('a day without job or new products says so', async () => {
    cardmarketApi();
    server.use(
      http.get(`${API}/admin/cardmarket/loads/2026-11-05`, () =>
        ok({ ...DAY_OLD, new_products_list: [], truncated: false, job: null }),
      ),
    );
    await openPage();
    await userEvent.click(
      await screen.findByRole('button', { name: 'Details of 5 Nov 2026' }, LONG),
    );
    const dialog = await screen.findByRole('dialog', { name: 'Load of 5 Nov 2026' });
    expect(await within(dialog).findByText('No new products.')).toBeVisible();
    expect(within(dialog).getByText('No job is linked to this day.')).toBeVisible();
  });

  it('a job result of an unknown shape still renders', async () => {
    cardmarketApi();
    server.use(
      http.get(`${API}/admin/cardmarket/loads/2026-11-06`, () =>
        ok({ ...detail, truncated: false, job: { ...JOB_OK, result: 'weird' } }),
      ),
    );
    await openPage();
    await userEvent.click(
      await screen.findByRole('button', { name: 'Details of 6 Nov 2026' }, LONG),
    );
    const dialog = await screen.findByRole('dialog', { name: 'Load of 6 Nov 2026' });
    expect(await within(dialog).findByText('Raw result')).toBeVisible();
    expect(within(dialog).queryByText('Auto-linked')).toBeNull();
    expect(within(dialog).queryByText(/more$/)).toBeNull();
  });
});

describe('CardmarketPage recent jobs (CM-a)', () => {
  it('lists the daily_prices jobs, a failed one with its message', async () => {
    const kinds: string[] = [];
    cardmarketApi();
    server.use(
      http.get(`${API}/admin/jobs`, ({ request }) => {
        kinds.push(new URL(request.url).searchParams.get('kind') ?? '');
        return ok({ items: RECENT });
      }),
    );
    await openPage();
    const section = await screen.findByRole('region', { name: 'Recent jobs' }, LONG);
    const items = await within(section).findAllByRole('listitem');
    expect(items).toHaveLength(2);
    expect(within(items[1]!).getByText('Error')).toBeVisible();
    expect(within(items[1]!).getByText('Download of the price guide failed')).toBeVisible();
    expect(within(items[1]!).getByText('2 s')).toBeVisible();
    expect(kinds).toContain('daily_prices');
  });
});

describe('CardmarketPage routing (CM-a)', () => {
  it('the admin nav links Cardmarket between Products and Riot', async () => {
    cardmarketApi();
    await openPage();
    const nav = screen.getByRole('navigation', { name: 'Administration sections' });
    const labels = within(nav)
      .getAllByRole('link')
      .map((link) => link.textContent);
    expect(labels.indexOf('Cardmarket')).toBe(labels.indexOf('Products') + 1);
    expect(labels.indexOf('Riot')).toBe(labels.indexOf('Cardmarket') + 1);
    const link = within(nav).getByRole('link', { name: 'Cardmarket' });
    expect(link).toHaveAttribute('href', '/riftbound/app/admin/cardmarket');
    expect(link).toHaveAttribute('aria-current', 'page');
  });

  it('a signed-in non-admin lands on the 404 view', async () => {
    server.use(http.get(`${API}/auth/session`, () => signedInSession()));
    await renderApp({ path: PATH, width: 1280 });
    expect(await screen.findByRole('heading', { name: 'Page not found' }, LONG)).toBeVisible();
  });
});
