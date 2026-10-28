import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { I18nextProvider } from 'react-i18next';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { axe } from 'vitest-axe';
import { ToastStack } from '@/components/ui/Toast';
import { clearToasts } from '@/components/ui/toastStore';
import { createI18n } from '@/i18n';
import { aylaGroup, emberGroup } from '@/test/fixtures/collection';
import { API, failure } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import type { CollectionGroup } from '@/api/types';
import { LineSheet } from './LineSheet';

const META = {
  conditions: ['MT', 'NM', 'EX', 'GD', 'LP', 'PL', 'PO'],
  languages: ['English', 'French', 'German', 'Spanish', 'Italian'],
};

type Sent = { method: string; path: string; body: Record<string, unknown> | null };

function record() {
  const sent: Sent[] = [];
  server.events.on('request:start', async ({ request }) => {
    if (!request.url.includes('/collection')) return;
    const clone = request.clone();
    let body: Record<string, unknown> | null = null;
    try {
      body = (await clone.json()) as Record<string, unknown>;
    } catch {
      body = null;
    }
    sent.push({
      method: request.method,
      path: new URL(request.url).pathname.replace(API, ''),
      body,
    });
  });
  return sent;
}

async function open(group: CollectionGroup = aylaGroup, { offline = false } = {}) {
  const i18n = await createI18n('es');
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(
    <I18nextProvider i18n={i18n}>
      <QueryClientProvider client={client}>
        <LineSheet
          group={group}
          open
          onClose={() => undefined}
          meta={META}
          playsetSize={3}
          offline={offline}
        />
        <ToastStack />
      </QueryClientProvider>
    </I18nextProvider>,
  );
  return { ...view, client };
}

beforeEach(() => clearToasts());
afterEach(() => server.events.removeAllListeners());

const legend = (index: number) => screen.getByRole('group', { name: `Línea ${index}` });

describe('LineSheet (F3-g S6)', () => {
  it('shows the card, the lines and their values', async () => {
    await open();
    expect(screen.getByRole('dialog', { name: "Copias de Ayla, Fury's Champion" })).toBeVisible();
    const first = within(legend(1));
    expect(first.getByRole('spinbutton', { name: 'Copias' })).toHaveValue(3);
    expect(first.getByRole('combobox', { name: 'Estado' })).toHaveValue('NM');
    expect(first.getByRole('combobox', { name: 'Idioma' })).toHaveValue('English');
    expect(first.getByRole('switch', { name: 'En venta' })).toBeChecked();
    expect(first.getByRole('spinbutton', { name: 'Copias a vender' })).toHaveValue(2);
    expect(first.getByRole('spinbutton', { name: 'Precio de venta (unidad)' })).toHaveValue(1.3);
    expect(within(legend(2)).getByRole('combobox', { name: 'Estado' })).toHaveValue('EX');
  });

  it('adds the foil to the title', async () => {
    await open(emberGroup);
    expect(screen.getByRole('dialog', { name: 'Copias de Ember Wisp (Foil)' })).toBeVisible();
  });

  it('saves a condition with the change time it read (if_updated_at)', async () => {
    const sent = record();
    await open();
    await userEvent.selectOptions(
      within(legend(1)).getByRole('combobox', { name: 'Estado' }),
      'Excelente (EX)',
    );
    await waitFor(() => expect(sent.some((r) => r.method === 'PATCH')).toBe(true));
    const patch = sent.find((r) => r.method === 'PATCH')!;
    expect(patch.path).toBe('/collection/1201');
    expect(patch.body).toEqual({ condition: 'EX', if_updated_at: '2026-10-25T09:12:00Z' });
    expect(await screen.findByText('Guardado.')).toBeVisible();
  });

  it('sends null for the empty choice of language', async () => {
    const sent = record();
    await open();
    await userEvent.selectOptions(
      within(legend(1)).getByRole('combobox', { name: 'Idioma' }),
      'Sin especificar',
    );
    await waitFor(() => expect(sent.some((r) => r.method === 'PATCH')).toBe(true));
    expect(sent.find((r) => r.method === 'PATCH')!.body).toMatchObject({ language: null });
  });

  it('keeps a language the list does not have', async () => {
    await open({
      ...aylaGroup,
      lines: [{ ...aylaGroup.lines[0], language: 'Klingon' }, aylaGroup.lines[1]],
    });
    const select = within(legend(1)).getByRole('combobox', { name: 'Idioma' });
    expect(select).toHaveValue('Klingon');
  });

  it('the stepper buttons change the quantity at once', async () => {
    const sent = record();
    await open();
    await userEvent.click(within(legend(1)).getByRole('button', { name: 'Más copias: Copias' }));
    await waitFor(() => expect(sent.some((r) => r.method === 'PATCH')).toBe(true));
    expect(sent.find((r) => r.method === 'PATCH')!.body).toMatchObject({ qty: 4 });
  });

  it('the switch saves selling', async () => {
    const sent = record();
    await open();
    await userEvent.click(within(legend(2)).getByRole('switch', { name: 'En venta' }));
    await waitFor(() => expect(sent.some((r) => r.method === 'PATCH')).toBe(true));
    expect(sent.find((r) => r.method === 'PATCH')).toMatchObject({
      path: '/collection/1202',
      body: { selling: true },
    });
  });

  it('a typed price is saved after a pause, once', async () => {
    const sent = record();
    await open();
    const price = within(legend(1)).getByRole('spinbutton', { name: 'Precio de compra (unidad)' });
    await userEvent.clear(price);
    await userEvent.type(price, '2.5');
    await waitFor(() => expect(sent.filter((r) => r.method === 'PATCH')).toHaveLength(1), {
      timeout: 3000,
    });
    expect(sent.find((r) => r.method === 'PATCH')!.body).toMatchObject({ purchase_price: 2.5 });
  });

  it('an emptied price is saved as null', async () => {
    const sent = record();
    await open();
    const price = within(legend(1)).getByRole('spinbutton', { name: 'Precio de venta (unidad)' });
    await userEvent.clear(price);
    await waitFor(() => expect(sent.some((r) => r.method === 'PATCH')).toBe(true), {
      timeout: 3000,
    });
    expect(sent.find((r) => r.method === 'PATCH')!.body).toMatchObject({ sell_price: null });
  });

  it('a stale line shows the translated message', async () => {
    server.use(
      http.patch(`${API}/collection/:id`, () =>
        failure(409, { error: 'Conflict', message: 'stale', code: 'stale_line' }),
      ),
    );
    await open();
    await userEvent.selectOptions(
      within(legend(1)).getByRole('combobox', { name: 'Estado' }),
      'Buena (GD)',
    );
    expect(
      await screen.findByText(
        'Esta línea ha cambiado en otra ventana. Recarga y vuelve a intentarlo.',
      ),
    ).toBeVisible();
  });

  it('splits copies into another line', async () => {
    const sent = record();
    await open();
    const first = within(legend(1));
    await userEvent.click(first.getByRole('button', { name: 'Separar copias' }));
    await userEvent.click(first.getByRole('button', { name: 'Más copias: Copias a separar' }));
    await userEvent.selectOptions(
      first.getAllByRole('combobox', { name: 'Estado' })[1],
      'Buena (GD)',
    );
    await userEvent.click(first.getByRole('button', { name: 'Separar' }));
    await waitFor(() => expect(sent.some((r) => r.path.endsWith('/split'))).toBe(true));
    expect(sent.find((r) => r.path.endsWith('/split'))).toMatchObject({
      path: '/collection/1201/split',
      body: { qty: 2, condition: 'GD', language: 'English', sell_price: 1.3 },
    });
    expect(await screen.findByText('Copias separadas.')).toBeVisible();
  });

  it('cannot split a line of one copy', async () => {
    await open();
    expect(within(legend(2)).getByRole('button', { name: 'Separar copias' })).toBeDisabled();
  });

  it('asks before deleting, deletes, and undoes by posting the line back', async () => {
    const sent = record();
    await open();
    await userEvent.click(within(legend(2)).getByRole('button', { name: 'Eliminar' }));
    const dialog = await screen.findByRole('dialog', { name: '¿Eliminar esta línea?' });
    expect(within(dialog).getByText('Se quitará 1 copia de tu colección.')).toBeVisible();
    await userEvent.click(within(dialog).getByRole('button', { name: 'Eliminar' }));
    expect(await screen.findByText('Línea eliminada.')).toBeVisible();
    expect(sent.some((r) => r.method === 'DELETE' && r.path === '/collection/1202')).toBe(true);

    await userEvent.click(screen.getByRole('button', { name: 'Deshacer' }));
    await waitFor(() =>
      expect(sent.some((r) => r.method === 'POST' && r.path === '/collection')).toBe(true),
    );
    expect(sent.find((r) => r.method === 'POST' && r.path === '/collection')!.body).toMatchObject({
      set_id: 'OGN',
      card_id: '79',
      foil: false,
      qty: 3,
    });
    expect(await screen.findByText('Línea restaurada.')).toBeVisible();
  });

  it('the undo toast lasts 8 seconds', async () => {
    await open();
    await userEvent.click(within(legend(2)).getByRole('button', { name: 'Eliminar' }));
    const dialog = await screen.findByRole('dialog', { name: '¿Eliminar esta línea?' });
    await userEvent.click(within(dialog).getByRole('button', { name: 'Eliminar' }));
    expect(await screen.findByText('Línea eliminada.')).toBeVisible();
    const { getToasts } = await import('@/components/ui/toastStore');
    expect(getToasts().find((toast) => toast.message === 'Línea eliminada.')?.duration).toBe(8000);
  });

  it('cancelling the confirmation deletes nothing', async () => {
    const sent = record();
    await open();
    await userEvent.click(within(legend(2)).getByRole('button', { name: 'Eliminar' }));
    const dialog = await screen.findByRole('dialog', { name: '¿Eliminar esta línea?' });
    await userEvent.click(within(dialog).getByRole('button', { name: 'Cancelar' }));
    expect(sent.filter((r) => r.method === 'DELETE')).toHaveLength(0);
  });
});

describe('LineSheet playset (F3-g S6)', () => {
  it('shows the keep checkbox checked and the warning when short', async () => {
    await open();
    expect(
      screen.getByRole('checkbox', { name: 'Mantener un playset de esta carta' }),
    ).toBeChecked();
    expect(screen.getByText('Copias sin vender: 2 de 3.')).toBeVisible();
  });

  it('has no warning when the playset is not short', async () => {
    await open(emberGroup);
    expect(screen.queryByText(/Copias sin vender/)).toBeNull();
    expect(
      screen.getByRole('checkbox', { name: 'Mantener un playset de esta carta' }),
    ).not.toBeChecked();
  });

  it('toggling the checkbox calls keep-playset', async () => {
    const sent = record();
    await open(emberGroup);
    await userEvent.click(
      screen.getByRole('checkbox', { name: 'Mantener un playset de esta carta' }),
    );
    await waitFor(() => expect(sent.some((r) => r.path === '/collection/keep-playset')).toBe(true));
    expect(sent.find((r) => r.path === '/collection/keep-playset')!.body).toEqual({
      set_id: 'OGN',
      card_id: '12',
      keep: true,
    });
  });
});

describe('LineSheet offline and accessibility', () => {
  it('disables every edit control offline and says why', async () => {
    await open(aylaGroup, { offline: true });
    expect(screen.getByText('Necesitas conexión para hacer cambios.')).toBeVisible();
    expect(
      screen.getByRole('checkbox', { name: 'Mantener un playset de esta carta' }),
    ).toBeDisabled();
    const first = within(legend(1));
    expect(first.getByRole('combobox', { name: 'Estado' })).toBeDisabled();
    expect(first.getByRole('switch', { name: 'En venta' })).toBeDisabled();
    expect(first.getByRole('button', { name: 'Eliminar' })).toBeDisabled();
    expect(first.getByRole('spinbutton', { name: 'Copias' })).toBeDisabled();
  });

  it('has no axe violations', async () => {
    await open();
    await act(async () => undefined);
    expect(await axe(document.body)).toHaveNoViolations();
  });

  it('ignores fireEvent noise on disabled controls', async () => {
    const sent = record();
    await open(aylaGroup, { offline: true });
    fireEvent.click(within(legend(1)).getByRole('switch', { name: 'En venta' }));
    expect(sent).toHaveLength(0);
  });
});
