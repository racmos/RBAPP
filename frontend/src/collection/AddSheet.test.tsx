import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { I18nextProvider } from 'react-i18next';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { axe } from 'vitest-axe';
import { ToastStack } from '@/components/ui/Toast';
import { clearToasts } from '@/components/ui/toastStore';
import { createI18n } from '@/i18n';
import { aylaLines, withCard } from '@/test/fixtures/collection';
import { cardList, foilCommon } from '@/test/fixtures/cards';
import { API, failure, ok } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { AddSheet } from './AddSheet';
import { QUICK_ADD_KEY } from './quickAdd';

const META = {
  conditions: ['MT', 'NM', 'EX', 'GD', 'LP', 'PL', 'PO'],
  languages: ['English', 'French', 'German', 'Spanish', 'Italian'],
  sets: [
    { id: 'OGN', name: 'Origen', released_on: '2024-01-15', card_count: 6 },
    { id: 'OGS', name: 'Proving Grounds', released_on: '2024-03-01', card_count: 24 },
  ],
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

type Sent = { method: string; path: string; url: URL; body: Record<string, unknown> | null };
const sent: Sent[] = [];
const posts = () => sent.filter((r) => r.method === 'POST').map((r) => r.body);
beforeEach(() => {
  clearToasts();
  sent.length = 0;
  server.events.on('request:start', async ({ request }) => {
    const url = new URL(request.url);
    if (!url.pathname.startsWith(`${API}/collection`) && url.pathname !== `${API}/cards`) return;
    const body =
      request.method === 'GET' || request.method === 'DELETE'
        ? null
        : ((await request.clone().json()) as Record<string, unknown>);
    sent.push({ method: request.method, path: url.pathname, url, body });
  });
});
afterEach(() => server.events.removeAllListeners());

const search = () => screen.getByRole('combobox', { name: 'Carta' });
const foilSwitch = () => screen.getByRole('switch', { name: 'Foil' });
const addButton = () => screen.getByRole('button', { name: 'Añadir' });

async function choose(name: RegExp, text = 'em') {
  await userEvent.type(search(), text);
  await userEvent.click(await screen.findByRole('option', { name }));
}

describe('AddSheet (F3-g S7)', () => {
  it('cannot add until a card is chosen', async () => {
    await open();
    expect(screen.getByRole('dialog', { name: 'Añadir a la colección' })).toBeVisible();
    expect(addButton()).toBeDisabled();
    expect(screen.getByText('Elige primero una carta.')).toBeVisible();
  });

  it('adds a foil copy with the typed values and stays open for the next card', async () => {
    await open();
    await choose(/Ember Wisp/);
    expect(foilSwitch()).toBeEnabled();
    await userEvent.click(foilSwitch());
    await userEvent.click(screen.getByRole('button', { name: 'Más copias: Copias' }));
    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: 'Estado' }),
      'Excelente (EX)',
    );
    await userEvent.click(screen.getByRole('switch', { name: 'En venta' }));
    await userEvent.click(addButton());

    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(posts()[0]).toMatchObject({
      set_id: 'OGN',
      card_id: '12',
      foil: true,
      qty: 2,
      condition: 'EX',
      selling: true,
    });
    expect(await screen.findByText('Añadida a tu colección.')).toBeVisible();
    // the sheet is still there, the card search is clear and focused
    expect(screen.getByRole('dialog', { name: 'Añadir a la colección' })).toBeVisible();
    expect(search()).toHaveValue('');
    await waitFor(() => expect(search()).toHaveFocus());
    expect(screen.getByText('Elige primero una carta.')).toBeVisible();
    expect(addButton()).toBeDisabled();
  });

  it('says so when the copies were added to an existing line', async () => {
    server.use(
      http.post(`${API}/collection`, () =>
        ok({ line: { ...withCard(aylaLines[0]) }, merged: true }, 201),
      ),
    );
    await open();
    await choose(/Ember Wisp/);
    await userEvent.click(addButton());
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
    await userEvent.click(addButton());
    expect(await screen.findByText('Esta carta no existe en versión foil.')).toBeVisible();
    expect(screen.getByText('Carta elegida: Ember Wisp')).toBeVisible();
    expect(addButton()).toBeEnabled();
  });

  it('disables everything offline and says why', async () => {
    await open({ offline: true });
    expect(screen.getByText('Necesitas conexión para hacer cambios.')).toBeVisible();
    expect(screen.getByRole('combobox', { name: 'Estado' })).toBeDisabled();
    expect(foilSwitch()).toBeDisabled();
    expect(addButton()).toBeDisabled();
  });

  it('has no axe violations', async () => {
    await open();
    expect(await axe(document.body)).toHaveNoViolations();
  });
});

describe('AddSheet quick add (owner feedback S9)', () => {
  it('narrows the card search to the chosen set', async () => {
    await open();
    const set = screen.getByRole('combobox', { name: 'Set' });
    expect(set).toHaveValue('');
    expect(within(set).getByRole('option', { name: 'Todos los sets' })).toBeInTheDocument();
    await userEvent.selectOptions(set, 'Proving Grounds (OGS)');
    await userEvent.type(search(), 'em');
    await waitFor(() => expect(sent.some((r) => r.path === `${API}/cards`)).toBe(true));
    const cards = sent.filter((r) => r.path === `${API}/cards`).at(-1)!;
    expect(cards.url.searchParams.getAll('set')).toEqual(['OGS']);
    expect(cards.url.searchParams.get('q')).toBe('em');
  });

  it('searches every set when no set is chosen', async () => {
    await open();
    await userEvent.type(search(), 'em');
    await screen.findByRole('option', { name: /Ember Wisp/ });
    const cards = sent.filter((r) => r.path === `${API}/cards`).at(-1)!;
    expect(cards.url.searchParams.getAll('set')).toEqual([]);
  });

  it('Enter in the search adds the highlighted card with the current choices', async () => {
    await open();
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Idioma' }), 'Español');
    await userEvent.click(screen.getByRole('button', { name: 'Más copias: Copias' }));
    await userEvent.type(search(), 'em');
    await screen.findByRole('option', { name: /Ember Wisp/ });
    await userEvent.keyboard('{Enter}');

    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(posts()[0]).toMatchObject({
      set_id: 'OGN',
      card_id: '12',
      foil: false,
      qty: 2,
      language: 'Spanish',
    });
    expect(await screen.findByText('Añadida a tu colección.')).toBeVisible();
    expect(search()).toHaveValue('');
    await waitFor(() => expect(search()).toHaveFocus());
  });

  it('Enter adds the name match, not a card the search found only by its text', async () => {
    const storm = { ...foilCommon, card_id: '1', key: 'OGN-1', name: 'Relentless Storm' };
    const garen = { ...foilCommon, card_id: '4', key: 'OGN-4', name: 'Garen, Rugged' };
    server.use(
      http.get(`${API}/cards`, () =>
        HttpResponse.json({
          success: true,
          data: { items: [storm, garen] },
          meta: { ...cardList.meta, per_page: 20, total: 2, pages: 1 },
        }),
      ),
    );
    await open();
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Set' }), 'Origen (OGN)');
    await userEvent.type(search(), 'Garen');
    await screen.findByRole('option', { name: /Garen, Rugged/ });
    await userEvent.keyboard('{Enter}');

    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(posts()[0]).toMatchObject({ set_id: 'OGN', card_id: '4' });
  });

  it('keeps set, foil, quantity, condition and language for the next card', async () => {
    await open();
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Set' }), 'Origen (OGN)');
    await userEvent.click(foilSwitch());
    await userEvent.click(screen.getByRole('button', { name: 'Más copias: Copias' }));
    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: 'Estado' }),
      'Casi nueva (NM)',
    );
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Idioma' }), 'Francés');
    await choose(/Ember Wisp/);
    await userEvent.click(addButton());
    await screen.findByText('Añadida a tu colección.');

    expect(screen.getByRole('combobox', { name: 'Set' })).toHaveValue('OGN');
    expect(foilSwitch()).toHaveAttribute('aria-checked', 'true');
    expect(screen.getByRole('spinbutton', { name: 'Copias' })).toHaveValue(2);
    expect(screen.getByRole('combobox', { name: 'Estado' })).toHaveValue('NM');
    expect(screen.getByRole('combobox', { name: 'Idioma' })).toHaveValue('French');
  });

  it('remembers the choices for the session and restores them when it opens again', async () => {
    const first = await open();
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Set' }), 'Origen (OGN)');
    await userEvent.click(foilSwitch());
    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: 'Estado' }),
      'Excelente (EX)',
    );
    await waitFor(() =>
      expect(JSON.parse(sessionStorage.getItem(QUICK_ADD_KEY) ?? '{}')).toMatchObject({
        set: 'OGN',
        foil: true,
        qty: 1,
        condition: 'EX',
        language: null,
      }),
    );
    expect(localStorage.getItem(QUICK_ADD_KEY)).toBeNull();
    first.unmount();

    await open();
    expect(screen.getByRole('combobox', { name: 'Set' })).toHaveValue('OGN');
    expect(foilSwitch()).toHaveAttribute('aria-checked', 'true');
    expect(screen.getByRole('combobox', { name: 'Estado' })).toHaveValue('EX');
  });

  it('ignores a stored value it cannot read', async () => {
    sessionStorage.setItem(QUICK_ADD_KEY, '{"set": 3, "qty": -4, "foil": "yes"');
    await open();
    expect(screen.getByRole('combobox', { name: 'Set' })).toHaveValue('');
    expect(screen.getByRole('spinbutton', { name: 'Copias' })).toHaveValue(1);
    expect(foilSwitch()).toHaveAttribute('aria-checked', 'false');
  });

  it('drops stored values that are out of range, keeping the rest', async () => {
    sessionStorage.setItem(
      QUICK_ADD_KEY,
      JSON.stringify({ set: 'OGS', qty: 0, foil: true, condition: 7, language: 'Spanish' }),
    );
    await open();
    expect(screen.getByRole('combobox', { name: 'Set' })).toHaveValue('OGS');
    expect(screen.getByRole('spinbutton', { name: 'Copias' })).toHaveValue(1);
    expect(foilSwitch()).toHaveAttribute('aria-checked', 'true');
    expect(screen.getByRole('combobox', { name: 'Estado' })).toHaveValue('');
    expect(screen.getByRole('combobox', { name: 'Idioma' })).toHaveValue('Spanish');
  });

  it('does not post a foil copy of a card without a foil version, and stays usable', async () => {
    await open();
    await userEvent.click(foilSwitch());
    await choose(/Fury Rune/, 'rune');
    expect(screen.getByText('Carta elegida: Fury Rune')).toBeVisible();
    expect(screen.getByText('Esta carta no tiene versión foil.')).toBeVisible();
    await userEvent.click(addButton());
    expect(await screen.findByText('Esta carta no existe en versión foil.')).toBeVisible();
    expect(posts()).toHaveLength(0);

    // turning foil off adds it
    await userEvent.click(foilSwitch());
    await userEvent.click(addButton());
    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(posts()[0]).toMatchObject({ card_id: 'r01', foil: false });
  });

  it('lists the cards added in this session, newest first', async () => {
    let id = 9000;
    server.use(
      http.post(`${API}/collection`, async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        id += 1;
        return ok({ line: { ...withCard(aylaLines[0]), ...body, id }, merged: false }, 201);
      }),
    );
    await open();
    expect(screen.queryByRole('list', { name: 'Añadidas en esta sesión' })).toBeNull();
    await choose(/Ember Wisp/);
    await userEvent.click(addButton());
    await screen.findByText('Añadida a tu colección.');
    await choose(/Ayla/, 'ay');
    await userEvent.click(screen.getByRole('button', { name: 'Más copias: Copias' }));
    await userEvent.click(addButton());

    const session = await screen.findByRole('list', { name: 'Añadidas en esta sesión' });
    await waitFor(() => expect(within(session).getAllByRole('listitem')).toHaveLength(2));
    const [newest, oldest] = within(session).getAllByRole('listitem');
    expect(newest).toHaveTextContent("Ayla, Fury's Champion");
    expect(newest).toHaveTextContent('OGN #79');
    expect(newest).toHaveTextContent('2 copias');
    expect(oldest).toHaveTextContent('Ember Wisp');
    expect(oldest).toHaveTextContent('1 copia');
  });

  it('undoes a new line with DELETE and offers to put it back', async () => {
    await open();
    await choose(/Ember Wisp/);
    await userEvent.click(addButton());
    await userEvent.click(await screen.findByRole('button', { name: 'Deshacer: Ember Wisp' }));

    await waitFor(() =>
      expect(sent.some((r) => r.method === 'DELETE' && r.path === `${API}/collection/9001`)).toBe(
        true,
      ),
    );
    expect(await screen.findByText('Entrada deshecha.')).toBeVisible();
    expect(screen.queryByRole('list', { name: 'Añadidas en esta sesión' })).toBeNull();

    // the toast puts the deleted line back
    await userEvent.click(screen.getByRole('button', { name: 'Deshacer' }));
    await waitFor(() => expect(posts()).toHaveLength(2));
    expect(await screen.findByText('Línea restaurada.')).toBeVisible();
  });

  it('undoes copies merged into an existing line by lowering its quantity', async () => {
    server.use(
      http.post(`${API}/collection`, async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        return ok(
          {
            line: {
              ...withCard(aylaLines[0], foilCommon),
              ...body,
              id: 1201,
              qty: 5,
              updated_at: '2026-10-29T10:00:00Z',
            },
            merged: true,
          },
          201,
        );
      }),
    );
    await open();
    await choose(/Ember Wisp/);
    await userEvent.click(screen.getByRole('button', { name: 'Más copias: Copias' }));
    await userEvent.click(addButton());
    await userEvent.click(await screen.findByRole('button', { name: 'Deshacer: Ember Wisp' }));

    await waitFor(() => expect(sent.some((r) => r.method === 'PATCH')).toBe(true));
    const patch = sent.find((r) => r.method === 'PATCH')!;
    expect(patch.path).toBe(`${API}/collection/1201`);
    expect(patch.body).toEqual({ qty: 3, if_updated_at: '2026-10-29T10:00:00Z' });
    expect(sent.some((r) => r.method === 'DELETE')).toBe(false);
    expect(await screen.findByText('Entrada deshecha.')).toBeVisible();
  });

  it('sums repeated adds that merge into a line of this session into one row', async () => {
    let calls = 0;
    server.use(
      http.post(`${API}/collection`, async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        calls += 1;
        return ok(
          {
            line: { ...withCard(aylaLines[0], foilCommon), ...body, id: 9001, qty: calls },
            merged: calls > 1,
          },
          201,
        );
      }),
    );
    await open();
    await choose(/Ember Wisp/);
    await userEvent.click(addButton());
    await screen.findByText('Añadida a tu colección.');
    await choose(/Ember Wisp/);
    await userEvent.click(addButton());
    await screen.findByText('Sumada a una línea que ya tenías.');

    const session = screen.getByRole('list', { name: 'Añadidas en esta sesión' });
    await waitFor(() =>
      expect(within(session).getByRole('listitem')).toHaveTextContent('2 copias'),
    );
    // the line was created in this session, so undo deletes it
    await userEvent.click(screen.getByRole('button', { name: 'Deshacer: Ember Wisp' }));
    await waitFor(() =>
      expect(sent.some((r) => r.method === 'DELETE' && r.path === `${API}/collection/9001`)).toBe(
        true,
      ),
    );
  });

  it('keeps the row and says why when the undo fails', async () => {
    server.use(
      http.delete(`${API}/collection/:id`, () =>
        failure(409, { error: 'Conflict', message: 'x', code: 'stale_line' }),
      ),
    );
    await open();
    await choose(/Ember Wisp/);
    await userEvent.click(addButton());
    await userEvent.click(await screen.findByRole('button', { name: 'Deshacer: Ember Wisp' }));
    expect(
      await screen.findByText(
        'Esta línea ha cambiado en otra ventana. Recarga y vuelve a intentarlo.',
      ),
    ).toBeVisible();
    expect(screen.getByRole('button', { name: 'Deshacer: Ember Wisp' })).toBeVisible();
  });

  it('has no axe violations with cards added in this session', async () => {
    await open();
    await choose(/Ember Wisp/);
    await userEvent.click(addButton());
    await screen.findByRole('list', { name: 'Añadidas en esta sesión' });
    expect(await axe(document.body)).toHaveNoViolations();
  });
});

describe('AddSheet in English', () => {
  it('names the set filter and the session list', async () => {
    const i18n = await createI18n('en');
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <I18nextProvider i18n={i18n}>
        <QueryClientProvider client={client}>
          <AddSheet open onClose={() => undefined} meta={META} offline={false} />
        </QueryClientProvider>
      </I18nextProvider>,
    );
    const set = screen.getByRole('combobox', { name: 'Set' });
    expect(within(set).getByRole('option', { name: 'All sets' })).toBeInTheDocument();
    expect(screen.getByText('Enter adds the highlighted card with these choices.')).toBeVisible();
  });
});
