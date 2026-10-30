import { screen, within } from '@testing-library/react';
import { http } from 'msw';
import { describe, expect, it } from 'vitest';
import { API, adminSession, ok, signedInSession } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';
import { NAV } from '@/shell/navRegistry';
import { expectCollapsible } from '@/test/sidePanel';

const CATALOG = { sets: 3, sets_without_release_date: 2, cards: 4, cards_without_image: 1 };

function adminApi() {
  server.use(
    http.get(`${API}/auth/session`, () => adminSession()),
    http.get(`${API}/admin/overview`, () => ok({ catalog: CATALOG })),
  );
}

const NAV_LABEL = 'Secciones de administración';

describe('AdminLayout (F13-a S6)', () => {
  it('≥1240 px: a left navigation, no select', async () => {
    adminApi();
    await renderApp({ path: '/admin', width: 1280 });
    const nav = await screen.findByRole('navigation', { name: NAV_LABEL }, { timeout: 10000 });
    expect(nav).toBeVisible();
    const link = screen.getByRole('link', { name: 'Resumen' });
    expect(link).toHaveAttribute('href', '/riftbound/app/admin');
    expect(link).toHaveAttribute('aria-current', 'page');
    expect(screen.queryByRole('combobox', { name: NAV_LABEL })).toBeNull();
  });

  it('≥1240 px: the navigation folds away (owner feedback S23)', async () => {
    adminApi();
    // the whole overview, so the page renders (a bare catalog makes OverviewPage throw)
    server.use(
      http.get(`${API}/admin/overview`, () =>
        ok({
          catalog: CATALOG,
          riot: { pending_changes: 0, active_sets: [], last_sync: null, placeholder_sets: [] },
        }),
      ),
    );
    await renderApp({ path: '/admin', width: 1280 });
    await screen.findByRole('heading', { name: 'Resumen' }, { timeout: 10000 });
    const nav = screen.getByRole('navigation', { name: NAV_LABEL });
    await expectCollapsible(
      nav,
      { hide: 'Ocultar menú', show: 'Mostrar menú' },
      'rb_panel_admin-nav_v1',
    );
    expect(screen.getByRole('navigation', { name: NAV_LABEL })).toBe(nav);
  });

  it('<1240 px: the sections are a select', async () => {
    adminApi();
    await renderApp({ path: '/admin', width: 1000 });
    expect(
      await screen.findByRole('combobox', { name: NAV_LABEL }, { timeout: 10000 }),
    ).toBeVisible();
    expect(screen.queryByRole('navigation', { name: NAV_LABEL })).toBeNull();
  });

  it('<860 px: shows the "easier on a computer" hint', async () => {
    adminApi();
    await renderApp({ path: '/admin', width: 390 });
    expect(
      await screen.findByText('Más cómodo en un ordenador.', undefined, { timeout: 10000 }),
    ).toBeVisible();
  });

  it('a signed-in non-admin lands on the 404 view', async () => {
    server.use(http.get(`${API}/auth/session`, () => signedInSession()));
    await renderApp({ path: '/admin', width: 1280 });
    expect(
      await screen.findByRole('heading', { name: 'Página no encontrada' }, { timeout: 10000 }),
    ).toBeVisible();
  });

  it('the nav registry entry points at /admin (S7)', () => {
    const entry = NAV.find((item) => item.id === 'admin');
    expect(entry).toMatchObject({ status: 'spa', to: '/admin', adminOnly: true });
  });

  it('shows the pending changes count on the changes entry (F13-g S1)', async () => {
    server.use(
      http.get(`${API}/auth/session`, () => adminSession()),
      http.get(`${API}/admin/overview`, () =>
        ok({
          catalog: CATALOG,
          riot: { pending_changes: 5, active_sets: [], last_sync: null, placeholder_sets: [] },
        }),
      ),
    );
    await renderApp({ path: '/admin', width: 1280 });
    expect(
      await screen.findByRole('link', { name: 'Cambios (5)' }, { timeout: 10000 }),
    ).toBeVisible();
  });

  it('links the products section (F14-d S5)', async () => {
    adminApi();
    await renderApp({ path: '/admin', width: 1280 });
    const nav = await screen.findByRole('navigation', { name: NAV_LABEL }, { timeout: 10000 });
    expect(within(nav).getByRole('link', { name: 'Productos' })).toHaveAttribute(
      'href',
      '/riftbound/app/admin/products',
    );
  });

  it('shows no count when nothing is pending', async () => {
    adminApi();
    await renderApp({ path: '/admin', width: 1280 });
    await screen.findByRole('navigation', { name: NAV_LABEL }, { timeout: 10000 });
    expect(screen.getByRole('link', { name: 'Cambios' })).toBeVisible();
  });
});
