import { screen, waitFor, within } from '@testing-library/react';
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
    name: 'Origins',
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
    expect(await screen.findByRole('table', { name: 'Catalog cards' })).toBeVisible();
    expect(container.querySelector('img[src*="ogn_1.png"]')).not.toBeNull();
    expect(screen.getByText('No image')).toBeVisible();
    expect(screen.getByRole('navigation', { name: 'Pagination' })).toBeVisible();
    expect(await axe(container)).toHaveNoViolations();
  });

  it('list rows on phones open the editor in a bottom sheet', async () => {
    cardsApi();
    await renderApp({ path: '/admin/cards', width: 390 });
    await userEvent.click(await screen.findByRole('button', { name: /Alpha Unit/ }));
    expect(await screen.findByLabelText('Name')).toBeVisible();
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
    await userEvent.click(await screen.findByRole('button', { name: 'New card' }));
    await userEvent.type(screen.getByLabelText('Set'), 'OGN');
    await userEvent.type(screen.getByLabelText('Number'), '9');
    await userEvent.type(screen.getByLabelText('Name'), 'New Card');
    await userEvent.click(screen.getByRole('button', { name: 'Save' }));
    expect((await screen.findAllByText('Card saved.')).length).toBeGreaterThan(0);
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
    await userEvent.click((await screen.findAllByRole('button', { name: 'Edit Alpha Unit' }))[0]);
    const file = new File(['png'], 'ogn_1.png', { type: 'image/png' });
    await userEvent.upload(screen.getByLabelText('Upload image'), file);
    expect((await screen.findAllByText('Image updated.')).length).toBeGreaterThan(0);
    expect(uploaded).toBe(true);
  });
});

const NEW_CARD = { ...CARDS.items[1]!, card_id: '9', key: 'OGN-9', name: 'New Card' };

/** Admin API with a mutable card list, so a write shows up on the next GET. */
function writableApi() {
  const state = { items: [...CARDS.items], posted: [] as unknown[], patched: [] as unknown[] };
  const list = () =>
    ok({ ...CARDS, items: state.items, meta: { ...CARDS.meta, total: state.items.length } });
  server.use(
    http.get(`${API}/auth/session`, () => adminSession()),
    http.get(`${API}/admin/cards`, list),
    http.get(`${API}/admin/sets`, () => ok(SETS)),
    http.post(`${API}/admin/cards`, async ({ request }) => {
      state.posted.push(await request.json());
      state.items = [...state.items, NEW_CARD];
      return ok(NEW_CARD, 201);
    }),
    http.patch(`${API}/admin/cards/OGN/1`, async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      state.patched.push(body);
      state.items = state.items.map((item) =>
        item.key === 'OGN-1' ? { ...item, name: String(body.name) } : item,
      );
      return ok(state.items[0]);
    }),
  );
  return state;
}

/** The editor: a side dialog below 1600 px, the persistent panel at 1600 px and up. */
const editorRole = (width: number) => (width >= 1600 ? 'complementary' : 'dialog');

describe('CardsAdminPage editor and row actions (owner feedback S20)', () => {
  it.each([1280, 1700])(
    '"New card" opens the editor and creates the card at %i px',
    async (width) => {
      const state = writableApi();
      await renderApp({ path: '/admin/cards', width });
      await userEvent.click(await screen.findByRole('button', { name: 'New card' }));
      const editor = await screen.findByRole(editorRole(width), { name: 'New card' });
      await userEvent.type(within(editor).getByLabelText('Set'), 'OGN');
      await userEvent.type(within(editor).getByLabelText('Number'), '9');
      await userEvent.type(within(editor).getByLabelText('Name'), 'New Card');
      await userEvent.click(within(editor).getByRole('button', { name: 'Save' }));
      expect((await screen.findAllByText('Card saved.')).length).toBeGreaterThan(0);
      expect(state.posted).toEqual([
        expect.objectContaining({ set_id: 'OGN', card_id: '9', name: 'New Card' }),
      ]);
      expect(await screen.findByRole('cell', { name: 'New Card' })).toBeVisible();
      await waitFor(() => expect(screen.queryByLabelText('Number')).not.toBeInTheDocument());
    },
  );

  it.each([1280, 1700])(
    '"Edit" opens the card in the editor and saves it at %i px',
    async (width) => {
      const state = writableApi();
      await renderApp({ path: '/admin/cards', width });
      await userEvent.click(await screen.findByRole('button', { name: 'Edit Alpha Unit' }));
      const editor = await screen.findByRole(editorRole(width), { name: 'Alpha Unit' });
      const name = within(editor).getByLabelText('Name');
      expect(name).toHaveValue('Alpha Unit');
      await userEvent.clear(name);
      await userEvent.type(name, 'Alpha Prime');
      await userEvent.click(within(editor).getByRole('button', { name: 'Save' }));
      expect((await screen.findAllByText('Card saved.')).length).toBeGreaterThan(0);
      expect(state.patched).toEqual([expect.objectContaining({ name: 'Alpha Prime' })]);
      expect(await screen.findByRole('cell', { name: 'Alpha Prime' })).toBeVisible();
    },
  );

  it('at 1600 px and up the editor is a column next to the table, not below it', async () => {
    writableApi();
    await renderApp({ path: '/admin/cards', width: 1700 });
    await userEvent.click(await screen.findByRole('button', { name: 'Edit Alpha Unit' }));
    const panel = await screen.findByRole('complementary', { name: 'Alpha Unit' });
    // Two columns: the table with its pagination, then the editor.
    expect(panel.parentElement!.children).toHaveLength(2);
    const main = panel.previousElementSibling as HTMLElement;
    expect(main).toContainElement(screen.getByRole('table', { name: 'Catalog cards' }));
    expect(main).toContainElement(screen.getByRole('navigation', { name: 'Pagination' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it.each([1280, 1700])(
    '"Delete" asks first, then deletes and refreshes at %i px',
    async (width) => {
      const state = writableApi();
      let deleted = 0;
      server.use(
        http.delete(`${API}/admin/cards/OGN/1`, () => {
          deleted += 1;
          state.items = state.items.filter((item) => item.key !== 'OGN-1');
          return ok({ deleted: 'OGN-1' });
        }),
      );
      await renderApp({ path: '/admin/cards', width });
      await userEvent.click(await screen.findByRole('button', { name: 'Delete Alpha Unit' }));
      const confirm = await screen.findByRole('dialog', { name: 'Delete Alpha Unit?' });
      expect(deleted).toBe(0);
      await userEvent.click(within(confirm).getByRole('button', { name: 'Delete' }));
      expect((await screen.findAllByText('Card deleted.')).length).toBeGreaterThan(0);
      expect(deleted).toBe(1);
      await waitFor(() =>
        expect(screen.queryByRole('cell', { name: 'Alpha Unit' })).not.toBeInTheDocument(),
      );
      expect(screen.queryByRole('dialog', { name: 'Delete Alpha Unit?' })).not.toBeInTheDocument();
    },
  );

  it.each([1280, 1700])(
    'a card in use: the question closes and a toast says why, translated, at %i px',
    async (width) => {
      writableApi();
      server.use(
        http.delete(`${API}/admin/cards/OGN/1`, () =>
          failure(409, {
            error: 'Conflict',
            message: "Card 'OGN-1' is used and cannot be deleted.",
            code: 'card_in_use',
            params: { collection_lines: 2, decks: 0 },
          }),
        ),
      );
      await renderApp({ path: '/admin/cards', width });
      await userEvent.click(await screen.findByRole('button', { name: 'Delete Alpha Unit' }));
      const confirm = await screen.findByRole('dialog', { name: 'Delete Alpha Unit?' });
      await userEvent.click(within(confirm).getByRole('button', { name: 'Delete' }));
      expect(
        (
          await screen.findAllByText(
            'Could not delete Alpha Unit: The card is used in collections or decks; it cannot be deleted.',
          )
        ).length,
      ).toBeGreaterThan(0);
      await waitFor(() =>
        expect(
          screen.queryByRole('dialog', { name: 'Delete Alpha Unit?' }),
        ).not.toBeInTheDocument(),
      );
      expect(screen.getByRole('cell', { name: 'Alpha Unit' })).toBeVisible();
    },
  );

  it('an error without a known code shows the message of the API', async () => {
    writableApi();
    server.use(
      http.delete(`${API}/admin/cards/OGN/1`, () =>
        failure(409, { error: 'Conflict', message: "Card 'OGN-1' is used and cannot be deleted." }),
      ),
    );
    await renderApp({ path: '/admin/cards', width: 1280 });
    await userEvent.click(await screen.findByRole('button', { name: 'Delete Alpha Unit' }));
    await userEvent.click(
      within(await screen.findByRole('dialog', { name: 'Delete Alpha Unit?' })).getByRole(
        'button',
        { name: 'Delete' },
      ),
    );
    expect(
      (
        await screen.findAllByText(
          "Could not delete Alpha Unit: Card 'OGN-1' is used and cannot be deleted.",
        )
      ).length,
    ).toBeGreaterThan(0);
  });

  it.each([1280, 1700])(
    '"Delete" inside the editor deletes the card and closes the editor at %i px',
    async (width) => {
      const state = writableApi();
      server.use(
        http.delete(`${API}/admin/cards/OGN/1`, () => {
          state.items = state.items.filter((item) => item.key !== 'OGN-1');
          return ok({ deleted: 'OGN-1' });
        }),
      );
      await renderApp({ path: '/admin/cards', width });
      await userEvent.click(await screen.findByRole('button', { name: 'Edit Alpha Unit' }));
      const editor = await screen.findByRole(editorRole(width), { name: 'Alpha Unit' });
      await userEvent.click(within(editor).getByRole('button', { name: 'Delete' }));
      const confirm = await screen.findByRole('dialog', { name: 'Delete Alpha Unit?' });
      await userEvent.click(within(confirm).getByRole('button', { name: 'Delete' }));
      expect((await screen.findAllByText('Card deleted.')).length).toBeGreaterThan(0);
      await waitFor(() => expect(screen.queryByLabelText('Name')).not.toBeInTheDocument());
    },
  );

  it('row actions are the shared Button with an icon, like the header button', async () => {
    writableApi();
    await renderApp({ path: '/admin/cards', width: 1280 });
    const edit = await screen.findByRole('button', { name: 'Edit Alpha Unit' });
    const remove = screen.getByRole('button', { name: 'Delete Alpha Unit' });
    const buttonClass = screen.getByRole('button', { name: 'New card' }).classList[0]!;
    for (const action of [edit, remove]) {
      expect(action).toHaveClass(buttonClass);
      expect(action.querySelector('svg')).not.toBeNull();
      expect(action.textContent).toBe('');
    }
  });
});

describe('CardsAdminPage set order (owner feedback S19)', () => {
  it('the set filter lists the sets newest first and the undated ones last', async () => {
    const base = SETS[0]!;
    server.use(
      http.get(`${API}/auth/session`, () => adminSession()),
      http.get(`${API}/admin/cards`, () => ok(CARDS)),
      http.get(`${API}/admin/sets`, () =>
        ok([
          { ...base, id: 'NOD', release_date: null },
          { ...base, id: 'VEN', release_date: '2026-08-01' },
          { ...base, id: 'OGN', release_date: '2025-10-31' },
          { ...base, id: 'OGS', release_date: '2025-11-07' },
        ]),
      ),
    );
    await renderApp({ path: '/admin/cards', width: 1280 });
    const select = await screen.findByRole('combobox', { name: 'All sets' });
    await within(select).findByRole('option', { name: 'VEN' });
    expect(
      within(select)
        .getAllByRole('option')
        .map((option) => option.getAttribute('value')),
    ).toEqual(['', 'VEN', 'OGS', 'OGN', 'NOD']);
  });
});
