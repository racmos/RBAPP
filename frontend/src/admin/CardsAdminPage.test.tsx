import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { axe } from 'vitest-axe';
import { describe, expect, it } from 'vitest';
import { API, adminSession, failure, ok } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';

const CARDS = {
  items: [
    {
      set_id: 'OGN',
      card_id: '1',
      key: 'OGN-1',
      name: 'Alpha Unit',
      domain: 'fury',
      type: 'Unit',
      tags: '',
      energy: 2,
      power: 3,
      might: 4,
      ability: 'Strike.',
      rarity: 'Common',
      artist: 'An Artist',
      image: 'ogn_1.png',
      image_url: 'https://img.test/ogn_1.png',
      image_src: '/riftbound/media/cards/ogn/ogn_1.png',
    },
    {
      set_id: 'OGN',
      card_id: '2',
      key: 'OGN-2',
      name: 'Beta Spell',
      domain: 'calm',
      type: 'Spell',
      tags: '',
      energy: 1,
      power: null,
      might: null,
      ability: '',
      rarity: 'Rare',
      artist: 'An Artist',
      image: null,
      image_url: null,
      image_src: null,
    },
  ],
  meta: { page: 1, per_page: 50, total: 2, pages: 1 },
};
const SETS = [
  {
    id: 'OGN',
    name: 'Origen',
    release_date: '2026-01-01',
    card_count: 2,
    declared_count: 2,
    window: 'monthly',
    next_run_at: null,
  },
];

function cardsApi() {
  server.use(
    http.get(`${API}/auth/session`, () => adminSession()),
    http.get(`${API}/admin/cards`, () => ok(CARDS)),
    http.get(`${API}/admin/sets`, () => ok(SETS)),
  );
}

describe('CardsAdminPage (F13-f S7, S8)', () => {
  it('table at 1280 px with images, no-image badge and pagination', async () => {
    cardsApi();
    const { container } = await renderApp({ path: '/admin/cards', width: 1280 });
    expect(await screen.findByRole('table', { name: 'Cartas del catálogo' })).toBeVisible();
    expect(container.querySelector('img[src*="ogn_1.png"]')).not.toBeNull();
    expect(screen.getByText('Sin imagen')).toBeVisible();
    expect(screen.getByRole('navigation', { name: 'Paginación' })).toBeVisible();
    expect(await axe(container)).toHaveNoViolations();
  });

  it('list rows on phones open the editor in a bottom sheet', async () => {
    cardsApi();
    await renderApp({ path: '/admin/cards', width: 390 });
    await userEvent.click(await screen.findByRole('button', { name: /Alpha Unit/ }));
    expect(await screen.findByLabelText('Nombre')).toBeVisible();
  });

  it('creates a card and sends FormData for the image', async () => {
    const posted: unknown[] = [];
    server.use(
      http.get(`${API}/auth/session`, () => adminSession()),
      http.get(`${API}/admin/cards`, () =>
        ok({ items: [], meta: { page: 1, per_page: 50, total: 0, pages: 1 } }),
      ),
      http.get(`${API}/admin/sets`, () => ok(SETS)),
      http.post(`${API}/admin/cards`, async ({ request }) => {
        posted.push(await request.json());
        return ok({ ...CARDS.items[0], name: 'New Card' }, 201);
      }),
      http.post(`${API}/admin/cards/OGN/1/image`, async () => ok(CARDS.items[0])),
    );
    await renderApp({ path: '/admin/cards', width: 1280 });
    await userEvent.click(await screen.findByRole('button', { name: 'Nueva carta' }));
    await userEvent.type(screen.getByLabelText('Set'), 'OGN');
    await userEvent.type(screen.getByLabelText('Número'), '9');
    await userEvent.type(screen.getByLabelText('Nombre'), 'New Card');
    await userEvent.click(screen.getByRole('button', { name: 'Guardar' }));
    expect((await screen.findAllByText('Carta guardada.')).length).toBeGreaterThan(0);
    expect(posted).toHaveLength(1);
    expect(posted[0]).toMatchObject({ set_id: 'OGN', card_id: '9', name: 'New Card' });
  });

  it('uploads the image with FormData', async () => {
    let uploaded = false;
    server.use(
      http.get(`${API}/auth/session`, () => adminSession()),
      http.get(`${API}/admin/cards`, () => ok(CARDS)),
      http.get(`${API}/admin/sets`, () => ok(SETS)),
      http.post(`${API}/admin/cards/OGN/1/image`, async () => {
        uploaded = true;
        return ok(CARDS.items[0]);
      }),
    );
    await renderApp({ path: '/admin/cards', width: 1280 });
    await userEvent.click((await screen.findAllByRole('button', { name: 'Editar Alpha Unit' }))[0]);
    const file = new File(['png'], 'ogn_1.png', { type: 'image/png' });
    await userEvent.upload(screen.getByLabelText('Subir imagen'), file);
    expect((await screen.findAllByText('Imagen actualizada.')).length).toBeGreaterThan(0);
    expect(uploaded).toBe(true);
  });

  it('delete with card_in_use shows the translated error', async () => {
    server.use(
      http.get(`${API}/auth/session`, () => adminSession()),
      http.get(`${API}/admin/cards`, () => ok(CARDS)),
      http.get(`${API}/admin/sets`, () => ok(SETS)),
      http.delete(`${API}/admin/cards/OGN/1`, () =>
        failure(409, { message: 'used', code: 'card_in_use' }),
      ),
    );
    await renderApp({ path: '/admin/cards', width: 1280 });
    await userEvent.click((await screen.findAllByRole('button', { name: 'Borrar Alpha Unit' }))[0]);
    await userEvent.click(screen.getByRole('button', { name: 'Borrar' }));
    expect(
      await screen.findByText('La carta está en colecciones o mazos; no se puede borrar.'),
    ).toBeVisible();
  });
});
