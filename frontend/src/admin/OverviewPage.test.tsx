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

function adminApi() {
  server.use(
    http.get(`${API}/auth/session`, () => adminSession()),
    http.get(`${API}/admin/overview`, () => ok({ catalog: CATALOG })),
  );
}

/** KPI value for a label, read from the tile inside the live `main` landmark. */
async function tileValue(label: string): Promise<string> {
  let value = '';
  await waitFor(() => {
    const term = screen.queryAllByText(label).find((element) => element.closest('main') !== null);
    expect(term).toBeDefined();
    value = ((term as HTMLElement).parentElement?.textContent ?? '').replace(label, '');
  }, LONG);
  return value;
}

describe('OverviewPage (F13-a S6)', () => {
  it('shows the four catalog counters, axe clean', { timeout: 30000 }, async () => {
    adminApi();
    const { container } = await renderApp({ path: '/admin', width: 1280 });
    expect(await screen.findByRole('heading', { level: 1, name: 'Resumen' }, LONG)).toBeVisible();
    expect(await tileValue('Sets')).toBe('3');
    expect(await tileValue('Sets sin fecha de salida')).toBe('2');
    expect(await tileValue('Cartas')).toBe('4');
    expect(await tileValue('Cartas sin imagen')).toBe('1');
    expect(await axe(container)).toHaveNoViolations();
  });

  it('sets the document title', { timeout: 30000 }, async () => {
    adminApi();
    await renderApp({ path: '/admin', width: 1280 });
    await screen.findByRole('heading', { level: 1, name: 'Resumen' }, LONG);
    await waitFor(() => expect(document.title).toContain('Resumen'), LONG);
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
        return ok({ catalog: CATALOG });
      }),
    );
    await renderApp({ path: '/admin', width: 1280 });
    await screen.findByRole('heading', { level: 1, name: 'Resumen' }, LONG);
    expect(document.querySelectorAll('[aria-busy="true"]').length).toBeGreaterThan(0);
    release(null);
    expect(await tileValue('Cartas')).toBe('4');
  });

  it('a failure shows the error state, and retry recovers', { timeout: 30000 }, async () => {
    let failing = true;
    server.use(
      http.get(`${API}/auth/session`, () => adminSession()),
      http.get(`${API}/admin/overview`, () =>
        failing ? failure(500, { message: 'boom' }) : ok({ catalog: CATALOG }),
      ),
    );
    await renderApp({ path: '/admin', width: 1280 });
    expect(await screen.findByRole('alert', undefined, LONG)).toBeVisible();
    failing = false;
    await userEvent.click(screen.getByRole('button', { name: 'Reintentar' }));
    expect(await tileValue('Cartas')).toBe('4');
  });
});
