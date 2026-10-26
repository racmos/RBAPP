import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { axe } from 'vitest-axe';
import { describe, expect, it } from 'vitest';
import { http } from 'msw';
import { API, adminSession, failure, ok } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';

const SETS = [
  {
    id: 'OGN',
    name: 'Origen',
    release_date: '2026-01-01',
    card_count: 2,
    declared_count: 2,
    window: 'monthly',
    next_run_at: '2030-02-01T08:00:00+01:00',
  },
  {
    id: 'SFD',
    name: 'Segundo',
    release_date: null,
    card_count: 0,
    declared_count: null,
    window: 'monthly',
    next_run_at: '2030-02-01T08:00:00+01:00',
  },
];

function setsApi() {
  server.use(
    http.get(`${API}/auth/session`, () => adminSession()),
    http.get(`${API}/admin/sets`, () => ok(SETS)),
  );
}

describe('SetsPage (F13-f S4-S6)', () => {
  it('table at 1280 px with sortable headers and mode creation', async () => {
    setsApi();
    const { container } = await renderApp({ path: '/admin/sets', width: 1280 });
    expect(await screen.findByRole('table', { name: 'Sets del catálogo' })).toBeVisible();
    expect(screen.getByRole('columnheader', { name: /Código/ })).toHaveAttribute(
      'aria-sort',
      'ascending',
    );
    expect(screen.getByRole('button', { name: 'Nuevo set' })).toBeVisible();
    expect(await axe(container)).toHaveNoViolations();
  });

  it('cards at 390 px with an actions menu, editor in a bottom sheet', async () => {
    setsApi();
    await renderApp({ path: '/admin/sets', width: 390 });
    expect(await screen.findByRole('heading', { name: /OGN/ })).toBeVisible();
    await userEvent.click(screen.getAllByText('Acciones')[0]);
    expect(screen.getByRole('button', { name: 'Editar OGN' })).toBeVisible();
  });

  it('persistent editor panel at 1700 px', async () => {
    setsApi();
    await renderApp({ path: '/admin/sets', width: 1700 });
    expect(await screen.findByText('Elige un set para editarlo.')).toBeVisible();
  });

  it('create flow shows the API error per field', async () => {
    server.use(
      http.get(`${API}/auth/session`, () => adminSession()),
      http.get(`${API}/admin/sets`, () => ok([])),
      http.post(`${API}/admin/sets`, () =>
        failure(400, {
          message: 'Invalid request data',
          code: 'validation_error',
          details: [{ field: 'release_date', message: 'x', type: 'missing', code: 'required' }],
        }),
      ),
    );
    await renderApp({ path: '/admin/sets', width: 1280 });
    await userEvent.click(await screen.findByRole('button', { name: 'Nuevo set' }));
    await userEvent.type(screen.getByLabelText('Código'), 'TST');
    await userEvent.type(screen.getByLabelText('Nombre'), 'Test');
    await userEvent.type(screen.getByLabelText('Fecha de salida'), '2026-12-04');
    await userEvent.click(screen.getByRole('button', { name: 'Guardar' }));
    expect(await screen.findByText('Este campo es obligatorio.')).toBeVisible();
  });

  it('delete asks for confirmation', async () => {
    setsApi();
    server.use(http.delete(`${API}/admin/sets/OGN`, () => ok({ deleted: 'OGN' })));
    await renderApp({ path: '/admin/sets', width: 1280 });
    await userEvent.click((await screen.findAllByRole('button', { name: 'Borrar OGN' }))[0]);
    expect(await screen.findByText('¿Borrar el set OGN?')).toBeVisible();
  });
});
