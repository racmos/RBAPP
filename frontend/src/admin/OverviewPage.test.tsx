import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { axe } from 'vitest-axe';
import { describe, expect, it } from 'vitest';
import { API, adminSession, failure, ok } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';

const CATALOG = { sets: 3, sets_without_release_date: 2, cards: 4, cards_without_image: 1 };
const LONG = { timeout: 10000 };

const RIOT = {
  pending_changes: 2,
  active_sets: [
    { id: 'OGN', name: 'Origins', window: 'pre_release', next_run_at: '2030-01-01T08:00:00+01:00' },
  ],
  last_sync: {
    job_id: 7,
    status: 'success',
    finished_at: '2030-01-01T12:00:00',
    trigger: 'manual',
  },
  placeholder_sets: ['NEW'],
};

function adminApi() {
  server.use(
    http.get(`${API}/auth/session`, () => adminSession()),
    http.get(`${API}/admin/overview`, () => ok({ catalog: CATALOG, riot: RIOT })),
  );
}

/** KPI value for a label, read from the tile inside the live `main` landmark. */
async function tileValue(label: string): Promise<string> {
  let value = '';
  await waitFor(() => {
    const term = screen
      .queryAllByText(label)
      .find((element) => element.tagName !== 'A' && element.closest('main') !== null);
    expect(term).toBeDefined();
    value = ((term as HTMLElement).parentElement?.textContent ?? '').replace(label, '');
  }, LONG);
  return value;
}

describe('OverviewPage (F13-a S6)', () => {
  it('shows the four catalog counters, axe clean', { timeout: 30000 }, async () => {
    adminApi();
    const { container } = await renderApp({ path: '/admin', width: 1280 });
    expect(await screen.findByRole('heading', { level: 1, name: 'Overview' }, LONG)).toBeVisible();
    expect(await tileValue('Sets')).toBe('3');
    expect(await tileValue('Sets without release date')).toBe('2');
    expect(await tileValue('Cards')).toBe('4');
    expect(await tileValue('Cards without image')).toBe('1');
    expect(await screen.findByRole('heading', { level: 2, name: 'Riot' }, LONG)).toBeVisible();
    expect(screen.getByRole('link', { name: '2' })).toHaveAttribute(
      'href',
      '/riftbound/app/admin/riot/changes',
    );
    expect(screen.getByText('Last sync')).toBeVisible();
    expect(screen.getByRole('link', { name: /NEW/ })).toHaveAttribute(
      'href',
      '/riftbound/app/admin/sets',
    );
    expect(await axe(container)).toHaveNoViolations();
  });

  it(
    'shows no-sync and no placeholders when there was no sync yet',
    { timeout: 30000 },
    async () => {
      server.use(
        http.get(`${API}/auth/session`, () => adminSession()),
        http.get(`${API}/admin/overview`, () =>
          ok({
            catalog: CATALOG,
            riot: { pending_changes: 0, active_sets: [], last_sync: null, placeholder_sets: [] },
          }),
        ),
      );
      await renderApp({ path: '/admin', width: 1280 });
      expect(await screen.findByText('No sync yet.', {}, LONG)).toBeVisible();
    },
  );

  it('sets the document title', { timeout: 30000 }, async () => {
    adminApi();
    await renderApp({ path: '/admin', width: 1280 });
    await screen.findByRole('heading', { level: 1, name: 'Overview' }, LONG);
    await waitFor(() => expect(document.title).toContain('Overview'), LONG);
  });

  it('shows skeletons while the counters load', { timeout: 30000 }, async () => {
    let release!: (value: unknown) => void;
    const gate = new Promise((resolve) => {
      release = resolve;
    });
    server.use(
      http.get(`${API}/auth/session`, () => adminSession()),
      http.get(`${API}/admin/overview`, async () => {
        await gate;
        return ok({
          catalog: CATALOG,
          riot: { pending_changes: 0, active_sets: [], last_sync: null, placeholder_sets: [] },
        });
      }),
    );
    await renderApp({ path: '/admin', width: 1280 });
    await screen.findByRole('heading', { level: 1, name: 'Overview' }, LONG);
    expect(document.querySelectorAll('[aria-busy="true"]').length).toBeGreaterThan(0);
    release(null);
    expect(await tileValue('Cards')).toBe('4');
  });

  it('a failure shows the error state, and retry recovers', { timeout: 30000 }, async () => {
    let failing = true;
    server.use(
      http.get(`${API}/auth/session`, () => adminSession()),
      http.get(`${API}/admin/overview`, () =>
        failing
          ? failure(500, { message: 'boom' })
          : ok({
              catalog: CATALOG,
              riot: { pending_changes: 0, active_sets: [], last_sync: null, placeholder_sets: [] },
            }),
      ),
    );
    await renderApp({ path: '/admin', width: 1280 });
    expect(await screen.findByRole('alert', undefined, LONG)).toBeVisible();
    failing = false;
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await tileValue('Cards')).toBe('4');
  });
});
