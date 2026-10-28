import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { I18nextProvider } from 'react-i18next';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { axe } from 'vitest-axe';
import { ToastStack } from '@/components/ui/Toast';
import { clearToasts } from '@/components/ui/toastStore';
import { createI18n } from '@/i18n';
import { aylaLines, withCard } from '@/test/fixtures/collection';
import { API, failure, ok } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { AddSheet } from './AddSheet';

const META = {
  conditions: ['MT', 'NM', 'EX', 'GD', 'LP', 'PL', 'PO'],
  languages: ['English', 'French', 'German', 'Spanish', 'Italian'],
};

async function open({ offline = false } = {}) {
  const i18n = await createI18n('es');
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <I18nextProvider i18n={i18n}>
      <QueryClientProvider client={client}>
        <AddSheet open onClose={() => undefined} meta={META} offline={offline} />
        <ToastStack />
      </QueryClientProvider>
    </I18nextProvider>,
  );
}

const sent: Array<Record<string, unknown>> = [];
beforeEach(() => {
  clearToasts();
  sent.length = 0;
  server.events.on('request:start', async ({ request }) => {
    if (request.method === 'POST' && new URL(request.url).pathname === `${API}/collection`) {
      sent.push((await request.clone().json()) as Record<string, unknown>);
    }
  });
});
afterEach(() => server.events.removeAllListeners());

async function choose(name: RegExp) {
  await userEvent.type(screen.getByRole('combobox', { name: 'Carta' }), 'em');
  await userEvent.click(await screen.findByRole('option', { name }));
}

describe('AddSheet (F3-g S7)', () => {
  it('cannot add until a card is chosen', async () => {
    await open();
    expect(screen.getByRole('dialog', { name: 'Añadir a la colección' })).toBeVisible();
    expect(screen.getByRole('button', { name: 'Añadir' })).toBeDisabled();
    expect(screen.getByText('Elige primero una carta.')).toBeVisible();
    expect(screen.getByRole('switch', { name: 'Foil' })).toBeDisabled();
  });

  it('keeps foil off, with a reason, for a card without a foil version', async () => {
    await open();
    await userEvent.type(screen.getByRole('combobox', { name: 'Carta' }), 'rune');
    await userEvent.click(await screen.findByRole('option', { name: /Fury Rune/ }));
    expect(screen.getByText('Carta elegida: Fury Rune')).toBeVisible();
    expect(screen.getByRole('switch', { name: 'Foil' })).toBeDisabled();
    expect(screen.getByText('Esta carta no tiene versión foil.')).toBeVisible();
  });

  it('adds a foil copy with the typed values and stays open for the next card', async () => {
    await open();
    await choose(/Ember Wisp/);
    expect(screen.getByRole('switch', { name: 'Foil' })).toBeEnabled();
    await userEvent.click(screen.getByRole('switch', { name: 'Foil' }));
    await userEvent.click(screen.getByRole('button', { name: 'Más copias: Copias' }));
    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: 'Estado' }),
      'Excelente (EX)',
    );
    await userEvent.click(screen.getByRole('switch', { name: 'En venta' }));
    await userEvent.click(screen.getByRole('button', { name: 'Añadir' }));

    await waitFor(() => expect(sent).toHaveLength(1));
    expect(sent[0]).toMatchObject({
      set_id: 'OGN',
      card_id: '12',
      foil: true,
      qty: 2,
      condition: 'EX',
      selling: true,
    });
    expect(await screen.findByText('Añadida a tu colección.')).toBeVisible();
    // the sheet is still there and the card search is clear
    expect(screen.getByRole('dialog', { name: 'Añadir a la colección' })).toBeVisible();
    expect(screen.getByRole('combobox', { name: 'Carta' })).toHaveValue('');
    expect(screen.getByText('Elige primero una carta.')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Añadir' })).toBeDisabled();
  });

  it('says so when the copies were added to an existing line', async () => {
    server.use(
      http.post(`${API}/collection`, () =>
        ok({ line: { ...withCard(aylaLines[0]) }, merged: true }, 201),
      ),
    );
    await open();
    await choose(/Ember Wisp/);
    await userEvent.click(screen.getByRole('button', { name: 'Añadir' }));
    expect(await screen.findByText('Sumada a una línea que ya tenías.')).toBeVisible();
  });

  it('shows the server error translated and keeps the card chosen', async () => {
    server.use(
      http.post(`${API}/collection`, () =>
        failure(400, { error: 'Bad Request', message: 'x', code: 'foil_not_allowed' }),
      ),
    );
    await open();
    await choose(/Ember Wisp/);
    await userEvent.click(screen.getByRole('button', { name: 'Añadir' }));
    expect(await screen.findByText('Esta carta no existe en versión foil.')).toBeVisible();
    expect(screen.getByText('Carta elegida: Ember Wisp')).toBeVisible();
  });

  it('disables everything offline and says why', async () => {
    await open({ offline: true });
    expect(screen.getByText('Necesitas conexión para hacer cambios.')).toBeVisible();
    expect(screen.getByRole('combobox', { name: 'Estado' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Añadir' })).toBeDisabled();
  });

  it('has no axe violations', async () => {
    await open();
    expect(await axe(document.body)).toHaveNoViolations();
  });
});
