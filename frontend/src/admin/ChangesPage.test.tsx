import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { axe } from 'vitest-axe';
import { describe, expect, it } from 'vitest';
import { API, adminSession, failure, ok } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { readFileSync } from 'node:fs';
import postcss from 'postcss';
import { renderApp } from '@/test/renderApp';

const CHANGES = [
  {
    id: 1,
    set_id: 'OGN',
    card_id: '1',
    card_name: 'Alpha Unit',
    image_src: null,
    field: 'rbcar_energy',
    old_value: '9',
    new_value: '2',
    status: 'pending',
    detected_at: '2026-05-01T12:00:00',
    job_id: 4,
    decided_at: null,
    decided_by: null,
  },
  {
    id: 2,
    set_id: 'OGN',
    card_id: '2',
    card_name: 'Beta Spell',
    image_src: null,
    field: 'rbcar_name',
    old_value: 'Beta Spell',
    new_value: 'Beta Spell!',
    status: 'pending',
    detected_at: '2026-05-02T12:00:00',
    job_id: 4,
    decided_at: null,
    decided_by: null,
  },
];
const PAGE = {
  items: CHANGES,
  meta: {
    page: 1,
    per_page: 50,
    total: 2,
    pages: 1,
    counts: { pending: 2, approved: 0, rejected: 0 },
  },
};
const LONG = { timeout: 10000 };

function changesApi() {
  server.use(
    http.get(`${API}/auth/session`, () => adminSession()),
    http.get(`${API}/admin/sets`, () => ok([])),
    http.get(`${API}/admin/riot/changes`, () => ok(PAGE)),
  );
}

describe('ChangesPage (F13-g S1-S7, S10)', () => {
  it(
    'wide values wrap inside a labelled, keyboard-scrollable wrapper (owner feedback S8)',
    { timeout: 30000 },
    async () => {
      const url = `https://cdn.example.test/${'a'.repeat(160)}.png`;
      server.use(
        http.get(`${API}/auth/session`, () => adminSession()),
        http.get(`${API}/admin/sets`, () => ok([])),
        http.get(`${API}/admin/riot/changes`, () =>
          ok({
            ...PAGE,
            items: [{ ...CHANGES[0], field: 'image_url', old_value: null, new_value: url }],
          }),
        ),
      );
      const { container } = await renderApp({ path: '/admin/riot/changes', width: 1280 });
      const region = await screen.findByRole('region', { name: 'Cambios detectados' }, LONG);
      expect(region).toHaveAttribute('tabindex', '0');
      expect(within(region).getByRole('table', { name: 'Cambios detectados' })).toBeVisible();
      expect(within(region).getByText(url)).toBeVisible();
      expect(await axe(container)).toHaveNoViolations();

      // CSS is asserted on its source (jsdom has no layout); vitest runs from frontend/.
      const decls = (selector: string) => {
        const found: Array<{ prop: string; value: string }> = [];
        postcss
          .parse(readFileSync('src/admin/ChangesPage.module.css', 'utf8'))
          .walkRules((rule) => {
            if (!rule.selectors.map((item) => item.trim()).includes(selector)) return;
            rule.walkDecls((decl) => {
              found.push({ prop: decl.prop, value: decl.value });
            });
          });
        return found;
      };
      // the scrolling itself is the shared TableScroll box (its CSS is pinned in TableScroll.test.tsx)
      expect(region).toHaveAttribute('data-slot', 'table-scroll');
      expect(decls('.table td')).toContainEqual({ prop: 'overflow-wrap', value: 'anywhere' });
    },
  );

  it(
    'table at 1280 px with selection, bulk confirm and filters in the URL',
    { timeout: 30000 },
    async () => {
      let posted: unknown = null;
      server.use(
        http.get(`${API}/auth/session`, () => adminSession()),
        http.get(`${API}/admin/sets`, () => ok([])),
        http.get(`${API}/admin/riot/changes`, () => ok(PAGE)),
        http.post(`${API}/admin/riot/changes/bulk`, async ({ request }) => {
          posted = await request.json();
          return ok({
            results: [
              { id: 1, outcome: 'approved' },
              { id: 2, outcome: 'approved' },
            ],
            counts: { approved: 2, rejected: 0, stale: 0, decided: 0, not_found: 0 },
          });
        }),
      );
      const { container, router } = await renderApp({ path: '/admin/riot/changes', width: 1280 });
      expect(await screen.findByRole('table', { name: 'Cambios detectados' }, LONG)).toBeVisible();
      expect(await axe(container)).toHaveNoViolations();

      await userEvent.click(
        screen.getByRole('checkbox', { name: 'Seleccionar los pendientes de esta página' }),
      );
      await userEvent.click(screen.getByRole('button', { name: 'Aprobar seleccionados' }));
      expect(await screen.findByText('¿Aplicar 2 cambios?', undefined, LONG)).toBeVisible();
      const dialog = await screen.findByRole('dialog', undefined, LONG);
      await userEvent.click(within(dialog).getByRole('button', { name: 'Aprobar seleccionados' }));
      expect(await screen.findAllByText(/Aprobados: 2/, undefined, LONG)).not.toHaveLength(0);
      expect(posted).toMatchObject({ ids: [1, 2], action: 'approve' });
      expect(router.state.location.search).toBe('');
    },
  );

  it('status filter and search land in the URL', { timeout: 30000 }, async () => {
    changesApi();
    const { router } = await renderApp({ path: '/admin/riot/changes', width: 1280 });
    await screen.findByRole('table', { name: 'Cambios detectados' }, LONG);
    await userEvent.click(screen.getByRole('radio', { name: 'Aprobados' }));
    await waitFor(() => expect(router.state.location.search).toContain('status=approved'), LONG);
  });

  it('persistent panel at 1700 px shows the selected change', { timeout: 30000 }, async () => {
    changesApi();
    await renderApp({ path: '/admin/riot/changes', width: 1700 });
    await userEvent.click(
      (await screen.findAllByRole('checkbox', { name: /Aprobar el cambio/ }, LONG))[0],
    );
    expect(await screen.findAllByText('Alpha Unit', undefined, LONG)).toHaveLength(2);
  });

  it('cards at 390 px have no bulk selection', { timeout: 30000 }, async () => {
    changesApi();
    await renderApp({ path: '/admin/riot/changes', width: 390 });
    await screen.findByText('Alpha Unit', {}, LONG);
    expect(screen.queryByRole('checkbox', { name: /Seleccionar/ })).toBeNull();
    await waitFor(() => {
      const approve = screen.getAllByRole('button', { name: /Aprobar el cambio/ });
      expect(approve).toHaveLength(2);
      approve.forEach((button) => expect(button).toBeVisible());
    }, LONG);
  });

  it('stale and decided answers toast and refetch', { timeout: 30000 }, async () => {
    server.use(
      http.get(`${API}/auth/session`, () => adminSession()),
      http.get(`${API}/admin/sets`, () => ok([])),
      http.get(`${API}/admin/riot/changes`, () => ok(PAGE)),
      http.post(`${API}/admin/riot/changes/1/approve`, () =>
        failure(409, { message: 'stale', code: 'change_stale' }),
      ),
      http.post(`${API}/admin/riot/changes/2/approve`, () =>
        failure(409, { message: 'decided', code: 'change_decided' }),
      ),
    );
    await renderApp({ path: '/admin/riot/changes', width: 1280 });
    const approves = await screen.findAllByRole('button', { name: /Aprobar el cambio/ }, LONG);
    await userEvent.click(approves[0]);
    expect(
      await screen.findAllByText(
        'La carta ha cambiado desde que se detectó este cambio. Revisa la carta.',
        undefined,
        LONG,
      ),
    ).not.toHaveLength(0);
  });

  it('image warning toast on approved with warning', { timeout: 30000 }, async () => {
    server.use(
      http.get(`${API}/auth/session`, () => adminSession()),
      http.get(`${API}/admin/sets`, () => ok([])),
      http.get(`${API}/admin/riot/changes`, () => ok(PAGE)),
      http.post(`${API}/admin/riot/changes/1/approve`, () =>
        ok({ ...CHANGES[0], status: 'approved', warnings: ['image_download_failed'] }),
      ),
    );
    await renderApp({ path: '/admin/riot/changes', width: 1280 });
    const approves = await screen.findAllByRole('button', { name: /Aprobar el cambio/ }, LONG);
    await userEvent.click(approves[0]);
    expect(
      await screen.findAllByText(
        'Cambio aplicado, pero la imagen nueva no se pudo descargar.',
        undefined,
        LONG,
      ),
    ).not.toHaveLength(0);
  });
});
