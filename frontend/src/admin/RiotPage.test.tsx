import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { axe } from 'vitest-axe';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { API, adminSession, failure, ok } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';

const OVERVIEW = {
  catalog: { sets: 1, sets_without_release_date: 0, cards: 1, cards_without_image: 0 },
  riot: {
    pending_changes: 2,
    active_sets: [
      {
        id: 'OGN',
        name: 'Origen',
        window: 'pre_release',
        next_run_at: '2030-01-01T08:00:00+01:00',
      },
    ],
    last_sync: {
      job_id: 3,
      status: 'success',
      finished_at: '2030-01-01T12:00:00',
      trigger: 'manual',
    },
    placeholder_sets: [],
  },
};
const SETS = [
  {
    id: 'OGN',
    name: 'Origen',
    release_date: '2026-01-01',
    card_count: 1,
    declared_count: 1,
    window: 'pre_release',
    next_run_at: '2030-01-01T08:00:00+01:00',
  },
];

function riotApi() {
  server.use(
    http.get(`${API}/auth/session`, () => adminSession()),
    http.get(`${API}/admin/overview`, () => ok(OVERVIEW)),
    http.get(`${API}/admin/sets`, () => ok(SETS)),
    http.get(`${API}/admin/jobs`, () => ok({ items: [] })),
  );
}

afterEach(() => {
  vi.useRealTimers();
});

describe('RiotPage (F13-f S9)', () => {
  it(
    'shows active sets, syncs one set and polls the job until success',
    { timeout: 30000 },
    async () => {
      const user = userEvent.setup();
      vi.useRealTimers();
      const jobs: Record<number, { status: string }> = { 9: { status: 'running' } };
      server.use(
        http.get(`${API}/auth/session`, () => adminSession()),
        http.get(`${API}/admin/overview`, () => ok(OVERVIEW)),
        http.get(`${API}/admin/sets`, () => ok(SETS)),
        http.get(`${API}/admin/jobs`, () => ok({ items: [] })),
        http.post(`${API}/admin/riot/sync`, async () => ok({ job_id: 9 }, 202)),
        http.get(`${API}/admin/jobs/9`, () => {
          if (jobs[9].status === 'running') {
            jobs[9].status = 'success';
            return ok({
              id: 9,
              kind: 'riot_sync',
              status: 'running',
              requested_by: 'root',
              requested_at: null,
              started_at: null,
              finished_at: null,
              message: null,
              params: {},
              result: { trigger: 'manual', sets: [] },
            });
          }
          return ok({
            id: 9,
            kind: 'riot_sync',
            status: 'success',
            requested_by: 'root',
            requested_at: null,
            started_at: null,
            finished_at: '2030-01-01T12:00:00',
            message: null,
            params: {},
            result: { trigger: 'manual', sets: [] },
          });
        }),
      );
      const { container } = await renderApp({ path: '/admin/riot', width: 1280 });
      expect(
        await screen.findByRole('heading', { name: 'Sincronización con Riot' }, { timeout: 10000 }),
      ).toBeVisible();
      expect(await screen.findByText('OGN')).toBeVisible();
      await user.click(screen.getByRole('checkbox', { name: 'OGN' }));
      await user.click(screen.getByRole('button', { name: 'Sincronizar ahora' }));
      expect(await screen.findByText('En curso')).toBeVisible();
      expect(await screen.findByText('Terminado', undefined, { timeout: 15000 })).toBeVisible();
      expect(await axe(container)).toHaveNoViolations();
    },
  );

  it('job_running shows the translated error', async () => {
    riotApi();
    server.use(
      http.post(`${API}/admin/riot/sync`, () =>
        failure(409, { message: 'busy', code: 'job_running' }),
      ),
    );
    await renderApp({ path: '/admin/riot', width: 1280 });
    await userEvent.click(await screen.findByRole('button', { name: 'Sincronizar ahora' }));
    expect(
      await screen.findByText('Ya hay una sincronización en curso. Espera a que termine.'),
    ).toBeVisible();
  });

  it('recent runs open their JobStatus in a modal', async () => {
    const recent = {
      id: 3,
      kind: 'riot_sync',
      status: 'success',
      requested_by: 'root',
      requested_at: null,
      started_at: null,
      finished_at: '2030-01-01T12:00:00',
      message: null,
    };
    server.use(
      http.get(`${API}/auth/session`, () => adminSession()),
      http.get(`${API}/admin/overview`, () => ok(OVERVIEW)),
      http.get(`${API}/admin/sets`, () => ok(SETS)),
      http.get(`${API}/admin/jobs`, () => ok({ items: [recent] })),
      http.get(`${API}/admin/jobs/3`, () =>
        ok({ ...recent, params: { trigger: 'manual' }, result: { trigger: 'manual', sets: [] } }),
      ),
    );
    await renderApp({ path: '/admin/riot', width: 1280 });
    await userEvent.click((await screen.findAllByRole('button', { name: /Manual/ }))[0]);
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText('Terminado')).toBeVisible();
  });

  it('no active sets shows the empty hint', async () => {
    server.use(
      http.get(`${API}/auth/session`, () => adminSession()),
      http.get(`${API}/admin/overview`, () =>
        ok({ ...OVERVIEW, riot: { ...OVERVIEW.riot, active_sets: [] } }),
      ),
      http.get(`${API}/admin/sets`, () => ok(SETS)),
      http.get(`${API}/admin/jobs`, () => ok({ items: [] })),
    );
    await renderApp({ path: '/admin/riot', width: 1280 });
    expect(await screen.findByText('Ningún set está cerca de su salida.')).toBeVisible();
  });
});
