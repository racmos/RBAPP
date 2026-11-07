import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { axe } from 'vitest-axe';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { API, failure, ok } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';
import { clearToasts } from '@/components/ui/toastStore';
import {
  AHRI,
  BOX,
  CANDIDATES,
  CARDS_PATH,
  MYSTERY,
  callsTo,
  matchingApi,
  reviewList,
  unmatchedList,
} from '@/test/fixtures/cardmarketMatching';

const LONG = { timeout: 10000 };
const PATH = '/admin/cardmarket/matching';
const EMPTY_CARD = {
  domain: null,
  type: null,
  tags: null,
  energy: null,
  power: null,
  might: null,
  ability: null,
  rarity: null,
  artist: null,
  image_url: null,
};
const SPIRITFORGED = { id: 7001, name: 'Spiritforged', set_id: null };

const rowOf = (list: HTMLElement, name: string) =>
  within(list)
    .getAllByRole('listitem')
    .find((item) => within(item).queryByRole('heading', { name }) !== null)!;

/** Opens the create-card form from the To link row of `name`. */
async function openCreate(name = 'Ahri, Alluring', user = userEvent.setup()) {
  const rendered = await renderApp({ path: PATH, width: 1280 });
  const list = await screen.findByRole('list', { name: 'Products to link' }, LONG);
  await user.click(
    within(rowOf(list, name)).getByRole('button', { name: `Create a card for ${name}` }),
  );
  const dialog = await screen.findByRole('dialog', { name: `Create a card for ${name}` });
  return { ...rendered, list, dialog, user };
}

const field = (dialog: HTMLElement, name: string) =>
  within(dialog).getByRole('textbox', { name: new RegExp(`^${name}`) });

afterEach(() => {
  vi.restoreAllMocks();
  // the toast store outlives a render: an Undo left by one test must not reach the next
  clearToasts();
});

describe('Create a card from a Cardmarket item (CM-c)', () => {
  it('a single row offers Create card; a sealed row says the product is created for it', async () => {
    matchingApi();
    await renderApp({ path: PATH, width: 1280 });
    const list = await screen.findByRole('list', { name: 'Products to link' }, LONG);
    expect(
      within(rowOf(list, 'Ahri, Alluring')).getByRole('button', {
        name: 'Create a card for Ahri, Alluring',
      }),
    ).toHaveTextContent('Create card');
    const box = rowOf(list, 'Origins Booster Box');
    expect(within(box).queryByRole('button')).toBeNull();
    expect(
      within(box).getByText(/the daily load creates the product with the same id/),
    ).toBeVisible();
    expect(within(box).getByRole('link', { name: 'Products' })).toHaveAttribute(
      'href',
      '/riftbound/app/admin/products',
    );
  });

  it('prefills from the item with a mapped expansion, creates the card and links it', async () => {
    const calls = matchingApi();
    const { dialog, user, queryClient } = await openCreate();
    queryClient.setQueryData(['admin', 'cards', ''], { items: [], meta: {} });
    expect(field(dialog, 'Name')).toHaveValue('Ahri, Alluring');
    const set = within(dialog).getByRole('combobox', { name: 'Set' });
    await vi.waitFor(() => expect(set).toHaveValue('OGN'));
    expect(within(dialog).getByText('From the Cardmarket expansion Origins.')).toBeVisible();
    expect(field(dialog, 'Number')).toHaveValue('');
    expect(within(dialog).getByText('Card number inside the set, e.g. 066 or 066a.')).toBeVisible();
    expect(field(dialog, 'Type')).toHaveValue('');
    expect(field(dialog, 'Rarity')).toHaveValue('');
    expect(within(dialog).getByText(/Undo removes the link only; the card stays/)).toBeVisible();
    const slot = within(dialog).getByRole('combobox', { name: 'Slot' });
    // no rarity yet: one slot; a common gets the normal slot
    expect(slot).toHaveValue('');
    await user.type(field(dialog, 'Number'), '066A');
    await user.type(field(dialog, 'Rarity'), 'Common');
    expect(slot).toHaveValue('N');

    await user.click(within(dialog).getByRole('button', { name: 'Create and link' }));
    await vi.waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(callsTo(calls, 'POST', CARDS_PATH).map((call) => call.body)).toEqual([
      { ...EMPTY_CARD, set_id: 'OGN', card_id: '066A', name: 'Ahri, Alluring', rarity: 'Common' },
    ]);
    // the link uses the card the API created (its id lower-cased)
    expect(callsTo(calls, 'POST', '/links').map((call) => call.body)).toEqual([
      { id_product: 501, card: { set_id: 'OGN', card_id: '066a' }, foil: 'N' },
    ]);
    expect((await screen.findAllByText('Card created and linked.')).length).toBeGreaterThan(0);
    // every Cardmarket list, the counters and the admin cards reload
    await vi.waitFor(() => {
      expect(callsTo(calls, 'GET', '/unmatched').length).toBeGreaterThan(1);
      expect(callsTo(calls, 'GET', '/status').length).toBeGreaterThan(1);
    });
    expect(queryClient.getQueryState(['admin', 'cards', ''])?.isInvalidated).toBe(true);
  });

  it('Undo deletes the link only, never the card', async () => {
    const calls = matchingApi();
    const { dialog, user } = await openCreate();
    await vi.waitFor(() =>
      expect(within(dialog).getByRole('combobox', { name: 'Set' })).toHaveValue('OGN'),
    );
    await user.type(field(dialog, 'Number'), '066a');
    await user.click(within(dialog).getByRole('button', { name: 'Create and link' }));
    await screen.findAllByText('Card created and linked.');
    await user.click(screen.getByRole('button', { name: 'Undo' }));
    await vi.waitFor(() => expect(callsTo(calls, 'DELETE', '/links/501')).toHaveLength(1));
    expect(calls.filter((call) => call.method === 'DELETE')).toHaveLength(1);
  });

  it('an unmapped expansion asks for the set from the admin sets', async () => {
    const calls = matchingApi({
      unmatched: unmatchedList([{ ...MYSTERY, expansion: SPIRITFORGED }]),
    });
    const { dialog, user } = await openCreate('Mystery Card');
    expect(
      within(dialog).getByText(
        'The Cardmarket expansion Spiritforged is not mapped to a set: choose one.',
      ),
    ).toBeVisible();
    const set = within(dialog).getByRole('combobox', { name: 'Set' });
    expect(set).toHaveValue('');
    // newest first, as in the cards admin
    await vi.waitFor(() =>
      expect(
        within(set)
          .getAllByRole('option')
          .map((option) => option.textContent),
      ).toEqual(['Choose a set', 'OGN · Origins', 'OGS · Proving Grounds']),
    );
    await user.selectOptions(set, 'OGS · Proving Grounds');
    await user.type(field(dialog, 'Number'), '010');
    await user.click(within(dialog).getByRole('button', { name: 'Create and link' }));
    await vi.waitFor(() => expect(callsTo(calls, 'POST', '/links')).toHaveLength(1));
    expect(callsTo(calls, 'POST', CARDS_PATH)[0]!.body).toEqual({
      ...EMPTY_CARD,
      set_id: 'OGS',
      card_id: '010',
      name: 'Mystery Card',
    });
    expect(callsTo(calls, 'POST', '/links')[0]!.body).toEqual({
      id_product: 502,
      card: { set_id: 'OGS', card_id: '010' },
      foil: null,
    });
  });

  it('validation errors stay on their fields and nothing is linked', async () => {
    const calls = matchingApi();
    server.use(
      http.post(`${API}/admin/cards`, () =>
        failure(400, {
          error: 'Validation Error',
          message: 'Invalid request data',
          code: 'validation_error',
          details: [
            {
              field: 'card_id',
              message: 'bad',
              type: 'string_pattern_mismatch',
              code: 'invalid_format',
            },
            { field: 'energy', message: 'big', type: 'less_than_equal', code: 'out_of_range' },
          ],
        }),
      ),
    );
    const { dialog, user } = await openCreate();
    await user.type(field(dialog, 'Number'), '06-6');
    await user.click(within(dialog).getByRole('button', { name: 'Create and link' }));
    await vi.waitFor(() => expect(field(dialog, 'Number')).toHaveAttribute('aria-invalid', 'true'));
    expect(within(dialog).getByText('The format is not valid.')).toBeVisible();
    expect(within(dialog).getByText('The value is out of range.')).toBeVisible();
    expect(callsTo(calls, 'POST', '/links')).toHaveLength(0);
    expect(screen.getByRole('dialog', { name: 'Create a card for Ahri, Alluring' })).toBeVisible();
  });

  it('a card that exists already offers to use it: the search opens with its id', async () => {
    const calls = matchingApi();
    server.use(
      http.post(`${API}/admin/cards`, () =>
        failure(409, {
          error: 'Conflict',
          message: 'Card OGN-066 already exists.',
          code: 'already_exists',
          params: { field: 'card_id' },
        }),
      ),
    );
    const { dialog, user } = await openCreate();
    await vi.waitFor(() =>
      expect(within(dialog).getByRole('combobox', { name: 'Set' })).toHaveValue('OGN'),
    );
    await user.type(field(dialog, 'Number'), '066');
    await user.click(within(dialog).getByRole('button', { name: 'Create and link' }));
    expect(await within(dialog).findByText('OGN-066 already exists in the catalog.')).toBeVisible();
    expect(field(dialog, 'Number')).toHaveAttribute('aria-invalid', 'true');
    expect(callsTo(calls, 'POST', '/links')).toHaveLength(0);
    await user.click(within(dialog).getByRole('button', { name: 'Use the existing card instead' }));
    const search = await screen.findByRole('dialog', { name: 'Link Ahri, Alluring' });
    expect(within(search).getByRole('textbox', { name: 'Search cards' })).toHaveValue('OGN-066');
    await vi.waitFor(() =>
      expect(callsTo(calls, 'GET', '/unmatched/501/candidates').at(-1)!.search.get('q')).toBe(
        'OGN-066',
      ),
    );
  });

  it('created but not linked: the dialog stays open and Link again links without creating', async () => {
    const calls = matchingApi();
    let linkCalls = 0;
    server.use(
      http.post(`${API}/admin/cardmarket/links`, async ({ request }) => {
        linkCalls += 1;
        const body = (await request.json()) as { id_product: number };
        if (linkCalls === 1) {
          return failure(409, {
            message: 'That card slot is linked to another product.',
            code: 'already_exists',
            params: { field: 'card', linked_id_product: 900 },
          });
        }
        return ok(
          {
            id_product: body.id_product,
            product_name: 'Ahri, Alluring',
            product_type: 'single',
            in_latest_load: true,
            set_id: 'OGN',
            card_id: '066a',
            card_name: 'Ahri, Alluring',
            foil: 'S',
            match_type: 'manual',
            confidence: null,
            low_price: null,
            price_date: null,
          },
          201,
        );
      }),
    );
    const { dialog, user } = await openCreate();
    await vi.waitFor(() =>
      expect(within(dialog).getByRole('combobox', { name: 'Set' })).toHaveValue('OGN'),
    );
    await user.type(field(dialog, 'Number'), '066a');
    await user.type(field(dialog, 'Rarity'), 'Common');
    await user.click(within(dialog).getByRole('button', { name: 'Create and link' }));
    const alert = await within(dialog).findByRole('alert');
    expect(alert).toHaveTextContent(
      'Card created, link failed: That card slot is linked to another product. Cardmarket product #900 holds OGN-066a, slot N.',
    );
    // the card exists now: its fields are locked and it is never created twice
    expect(field(dialog, 'Number')).toBeDisabled();
    expect(within(dialog).queryByRole('button', { name: 'Create and link' })).toBeNull();
    await user.selectOptions(within(dialog).getByRole('combobox', { name: 'Slot' }), 'S (foil)');
    await user.click(within(alert).getByRole('button', { name: 'Link again' }));
    await vi.waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(linkCalls).toBe(2);
    expect(callsTo(calls, 'POST', CARDS_PATH)).toHaveLength(1);
    expect((await screen.findAllByText('Card created and linked.')).length).toBeGreaterThan(0);
  });

  it('the link dialog switches to the form and back to the search', async () => {
    matchingApi();
    const user = userEvent.setup();
    await renderApp({ path: PATH, width: 1280 });
    const list = await screen.findByRole('list', { name: 'Products to link' }, LONG);
    await user.click(
      within(rowOf(list, 'Ahri, Alluring')).getByRole('button', {
        name: 'Choose a card for Ahri, Alluring',
      }),
    );
    const search = await screen.findByRole('dialog', { name: 'Link Ahri, Alluring' });
    await within(search).findByRole('list', { name: 'Cards' }, LONG);
    await user.click(within(search).getByRole('button', { name: 'Create card' }));
    const form = await screen.findByRole('dialog', { name: 'Create a card for Ahri, Alluring' });
    expect(field(form, 'Name')).toHaveValue('Ahri, Alluring');
    await user.click(within(form).getByRole('button', { name: 'Search cards instead' }));
    expect(await screen.findByRole('dialog', { name: 'Link Ahri, Alluring' })).toBeVisible();
  });

  it('a review item without candidates opens the form with the facts of the product', async () => {
    const calls = matchingApi({
      review: reviewList([
        {
          product_id: 502,
          name: 'Mystery Card',
          expansion_id: null,
          reason: 'no_candidates',
          candidates: [],
        },
      ]),
    });
    server.use(
      http.get(`${API}/admin/cardmarket/unmatched/:id/candidates`, () =>
        ok({
          ...CANDIDATES,
          product: { ...CANDIDATES.product, id_product: 502, name: 'Mystery Card' },
          cards: [],
        }),
      ),
    );
    const user = userEvent.setup();
    await renderApp({ path: `${PATH}?tab=auto`, width: 1280 });
    const list = await screen.findByRole('list', { name: 'Products to review' }, LONG);
    await user.click(
      within(rowOf(list, 'Mystery Card')).getByRole('button', {
        name: 'Create a card for Mystery Card',
      }),
    );
    const dialog = await screen.findByRole('dialog', { name: 'Create a card for Mystery Card' });
    await vi.waitFor(() =>
      expect(within(dialog).getByRole('combobox', { name: 'Set' })).toHaveValue('OGN'),
    );
    await user.type(field(dialog, 'Number'), '300');
    await user.click(within(dialog).getByRole('button', { name: 'Create and link' }));
    await vi.waitFor(() =>
      expect(callsTo(calls, 'POST', '/links').map((call) => call.body)).toEqual([
        { id_product: 502, card: { set_id: 'OGN', card_id: '300' }, foil: null },
      ]),
    );
  });

  it('a review item with candidates has no Create card', async () => {
    matchingApi();
    await renderApp({ path: `${PATH}?tab=auto`, width: 1280 });
    const list = await screen.findByRole('list', { name: 'Products to review' }, LONG);
    expect(
      within(rowOf(list, 'Ahri, Alluring')).queryByRole('button', {
        name: 'Create a card for Ahri, Alluring',
      }),
    ).toBeNull();
  });

  it('offline: Create card is disabled', async () => {
    matchingApi({ unmatched: unmatchedList([AHRI, BOX]) });
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    await renderApp({ path: PATH, width: 1280 });
    const list = await screen.findByRole('list', { name: 'Products to link' }, LONG);
    expect(
      within(rowOf(list, 'Ahri, Alluring')).getByRole('button', {
        name: 'Create a card for Ahri, Alluring',
      }),
    ).toBeDisabled();
  });

  it('offline in the form: Create and link is disabled', async () => {
    matchingApi();
    const { dialog } = await openCreate();
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    window.dispatchEvent(new Event('offline'));
    await vi.waitFor(() =>
      expect(within(dialog).getByRole('button', { name: 'Create and link' })).toBeDisabled(),
    );
    // the query client listens to these events too: back online for the next test
    vi.restoreAllMocks();
    window.dispatchEvent(new Event('online'));
  });

  it('has no axe violations', async () => {
    matchingApi();
    const { dialog } = await openCreate();
    await vi.waitFor(() =>
      expect(within(dialog).getByRole('combobox', { name: 'Set' })).toHaveValue('OGN'),
    );
    expect(await axe(dialog)).toHaveNoViolations();
  }, 20000);
});
