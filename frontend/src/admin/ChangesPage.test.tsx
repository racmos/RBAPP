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
import { expectCollapsible } from '@/test/sidePanel';

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
      // The table scrolls with the page (S11), so the wrapper is no extra tab stop.
      expect(region).not.toHaveAttribute('tabindex');
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
      // the wrapper is the shared TableScroll in fit mode (its CSS is pinned in TableScroll.test.tsx)
      expect(region).toHaveAttribute('data-slot', 'table-scroll');
      // URLs and abilities break anywhere; the other cells only between words (S18 n)
      // `.table .valueCell` outranks `.table td` (a bare `.valueCell` would lose to it)
      expect(decls('.table .valueCell')).toContainEqual({
        prop: 'overflow-wrap',
        value: 'anywhere',
      });
      expect(decls('.table td')).toContainEqual({ prop: 'overflow-wrap', value: 'break-word' });
    },
  );

  it(
    'the card column is wide enough for a name, which wraps only between words (owner feedback S18 n)',
    { timeout: 30000 },
    async () => {
      changesApi();
      await renderApp({ path: '/admin/riot/changes', width: 1280 });
      const table = await screen.findByRole('table', { name: 'Cambios detectados' }, LONG);
      const cell = within(table).getByText('Alpha Unit').closest('td');
      expect(cell?.className).toMatch(/cardCell/);
      const card: Array<{ prop: string; value: string }> = [];
      postcss.parse(readFileSync('src/admin/ChangesPage.module.css', 'utf8')).walkRules((rule) => {
        if (!rule.selectors.map((item) => item.trim()).includes('.table .cardCell')) return;
        rule.walkDecls((decl) => {
          card.push({ prop: decl.prop, value: decl.value });
        });
      });
      expect(card).toContainEqual({ prop: 'min-width', value: '18ch' });
      expect(card).not.toContainEqual({ prop: 'overflow-wrap', value: 'anywhere' });
    },
  );

  it(
    'one scroll: the table has no vertical cap and scrolls with the page (owner feedback S11)',
    { timeout: 30000 },
    async () => {
      changesApi();
      await renderApp({ path: '/admin/riot/changes', width: 1280 });
      const region = await screen.findByRole('region', { name: 'Cambios detectados' }, LONG);
      expect(region).toHaveAttribute('data-fit');
      const tableCss = readFileSync('src/components/ui/TableScroll.module.css', 'utf8');
      const fit: Array<{ prop: string; value: string }> = [];
      postcss.parse(tableCss).walkRules((rule) => {
        if (!rule.selectors.map((item) => item.trim()).includes('.fit')) return;
        rule.walkDecls((decl) => {
          fit.push({ prop: decl.prop, value: decl.value });
        });
      });
      expect(fit.map((decl) => decl.prop)).not.toContain('max-height');
      expect(fit).not.toContainEqual({ prop: 'overflow', value: 'auto' });
      expect(fit).not.toContainEqual({ prop: 'overflow-y', value: 'auto' });
    },
  );

  it(
    'selected rows keep the bulk bar sticky at the bottom of the viewport (owner feedback S11)',
    { timeout: 30000 },
    async () => {
      changesApi();
      await renderApp({ path: '/admin/riot/changes', width: 1280 });
      const region = await screen.findByRole('region', { name: 'Cambios detectados' }, LONG);
      expect(screen.queryByRole('region', { name: /seleccionados?$/ })).toBeNull();
      await userEvent.click(screen.getAllByRole('checkbox', { name: /Aprobar el cambio/ })[0]);
      const bar = await screen.findByRole('region', { name: /seleccionados?$/ }, LONG);
      expect(within(bar).getByText('1 cambio seleccionado')).toBeVisible();
      expect(region.contains(bar)).toBe(false);

      const bulk: Array<{ prop: string; value: string }> = [];
      postcss.parse(readFileSync('src/admin/ChangesPage.module.css', 'utf8')).walkRules((rule) => {
        if (!rule.selectors.map((item) => item.trim()).includes('.bulkBar')) return;
        rule.walkDecls((decl) => {
          bulk.push({ prop: decl.prop, value: decl.value });
        });
      });
      expect(bulk).toContainEqual({ prop: 'position', value: 'sticky' });
      expect(bulk.map((decl) => decl.prop)).toContain('bottom');
      // above the sticky header (z-index 2) and the rows, opaque so rows never show through
      expect(Number(bulk.find((decl) => decl.prop === 'z-index')?.value)).toBeGreaterThan(2);
      expect(bulk).toContainEqual({ prop: 'background', value: 'var(--table-head)' });
    },
  );

  it(
    'page size 50 / 100 / 200 lands in the URL and the request, resets the page (owner feedback S11)',
    { timeout: 30000 },
    async () => {
      const requested: string[] = [];
      server.use(
        http.get(`${API}/auth/session`, () => adminSession()),
        http.get(`${API}/admin/sets`, () => ok([])),
        http.get(`${API}/admin/riot/changes`, ({ request }) => {
          requested.push(new URL(request.url).search);
          return ok(PAGE);
        }),
      );
      const { router } = await renderApp({ path: '/admin/riot/changes?page=2', width: 1280 });
      await screen.findByRole('table', { name: 'Cambios detectados' }, LONG);
      const size = screen.getByRole('combobox', { name: 'Por página' });
      expect(size).toHaveValue('50');
      expect(
        within(size)
          .getAllByRole('option')
          .map((option) => option.textContent),
      ).toEqual(['50', '100', '200']);
      const last = () => new URLSearchParams(requested.at(-1));
      expect(last().get('per_page')).toBe('50');
      expect(last().get('page')).toBe('2');

      await userEvent.selectOptions(size, '200');
      await waitFor(() => expect(router.state.location.search).toBe('?per_page=200'), LONG);
      await waitFor(() => expect(last().get('per_page')).toBe('200'), LONG);
      expect(last().get('page')).toBeNull();

      await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Por página' }), '50');
      await waitFor(() => expect(router.state.location.search).toBe(''), LONG);
      await waitFor(() => expect(last().get('per_page')).toBe('50'), LONG);
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

  it(
    'the status filter says what it filters (owner feedback S24)',
    { timeout: 30000 },
    async () => {
      changesApi();
      await renderApp({ path: '/admin/riot/changes', width: 1280 });
      await screen.findByRole('table', { name: 'Cambios detectados' }, LONG);
      const group = screen.getByRole('radiogroup', { name: 'Estado' });
      const label = document.getElementById(group.getAttribute('aria-labelledby') ?? '');
      expect(label).toHaveTextContent('Estado');
      expect(label).toBeVisible();
      expect(within(group).getByRole('radio', { name: 'Pendientes' })).toBeChecked();
      // the selects are named after what they filter, "all" is their empty option
      for (const [name, empty] of [
        ['Set', 'Todos los sets'],
        ['Campo', 'Todos los campos'],
      ]) {
        const select = screen.getByRole('combobox', { name });
        expect(select.closest('label')).toHaveTextContent(name);
        expect(within(select).getByRole('option', { name: empty })).toHaveValue('');
      }
    },
  );

  it('lists the obsolete proposals (owner feedback S17)', { timeout: 30000 }, async () => {
    changesApi();
    const { router } = await renderApp({ path: '/admin/riot/changes', width: 1280 });
    await screen.findByRole('table', { name: 'Cambios detectados' }, LONG);
    await userEvent.click(screen.getByRole('radio', { name: 'Obsoletos' }));
    await waitFor(() => expect(router.state.location.search).toContain('status=obsolete'), LONG);
  });

  it('persistent panel at 1700 px shows the selected change', { timeout: 30000 }, async () => {
    changesApi();
    await renderApp({ path: '/admin/riot/changes', width: 1700 });
    await userEvent.click(
      (await screen.findAllByRole('checkbox', { name: /Aprobar el cambio/ }, LONG))[0],
    );
    expect(await screen.findAllByText('Alpha Unit', undefined, LONG)).toHaveLength(2);
    await expectCollapsible(
      screen.getByRole('complementary', { name: 'Detalle' }),
      { hide: 'Ocultar detalle', show: 'Mostrar detalle' },
      'rb_panel_admin-changes-detail_v1',
    );
    // the pagination stays under the table, not in the side column
    const panel = screen.getByRole('complementary', { name: 'Detalle' });
    expect(panel.parentElement).toBe(
      screen.getByRole('region', { name: 'Cambios detectados' }).parentElement!.parentElement,
    );
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

describe('ChangesPage set order (owner feedback S19)', () => {
  it('the set filter lists the sets newest first and the undated ones last', async () => {
    const base = {
      name: 'Set',
      card_count: 1,
      declared_count: 1,
      window: 'monthly',
      next_run_at: null,
    };
    server.use(
      http.get(`${API}/auth/session`, () => adminSession()),
      http.get(`${API}/admin/sets`, () =>
        ok([
          { ...base, id: 'NOD', release_date: null },
          { ...base, id: 'OGN', release_date: '2025-10-31' },
          { ...base, id: 'VEN', release_date: '2026-08-01' },
        ]),
      ),
      http.get(`${API}/admin/riot/changes`, () => ok(PAGE)),
    );
    await renderApp({ path: '/admin/riot/changes', width: 1280 });
    const select = await screen.findByRole('combobox', { name: 'Todos los sets' }, LONG);
    await within(select).findByRole('option', { name: 'VEN' }, LONG);
    expect(
      within(select)
        .getAllByRole('option')
        .map((option) => option.getAttribute('value')),
    ).toEqual(['', 'VEN', 'OGN', 'NOD']);
  });
});
