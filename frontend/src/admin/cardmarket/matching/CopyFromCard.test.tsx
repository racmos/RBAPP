import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { axe } from 'vitest-axe';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { renderApp } from '@/test/renderApp';
import { clearToasts } from '@/components/ui/toastStore';
import {
  AHRI,
  CARDS_PATH,
  CATALOG_CARDS,
  EXPANSIONS,
  UNNAMED,
  callsTo,
  catalogCard,
  matchingApi,
  unmatchedList,
} from '@/test/fixtures/cardmarketMatching';

const LONG = { timeout: 10000 };
const PATH = '/admin/cardmarket/matching';
const SECTION = 'Copy from an existing card';

const RUNE = {
  ...AHRI,
  id_product: 9300,
  name: 'Fury Rune',
  expansion: { id: 6567, name: null, set_id: 'UNLX' },
  suggestions: [],
};

const api = (catalog = CATALOG_CARDS) =>
  matchingApi({
    unmatched: unmatchedList([RUNE]),
    expansions: [...EXPANSIONS, { ...UNNAMED, mapped_set_id: 'UNLX', mapped_set_name: null }],
    catalog,
  });

async function openCreate(user = userEvent.setup()) {
  await renderApp({ path: PATH, width: 1280 });
  const list = await screen.findByRole('list', { name: 'Products to link' }, LONG);
  await user.click(within(list).getByRole('button', { name: 'Create a card for Fury Rune' }));
  const dialog = await screen.findByRole('dialog', { name: 'Create a card for Fury Rune' });
  const section = within(dialog).getByRole('region', { name: SECTION });
  return { dialog, section, user };
}

const field = (dialog: HTMLElement, name: string) =>
  within(dialog).getByRole('textbox', { name: new RegExp(`^${name}`) });
const number = (dialog: HTMLElement, name: string) =>
  within(dialog).getByRole('spinbutton', { name: new RegExp(`^${name}`) });

const results = (section: HTMLElement) =>
  within(section).findByRole('list', { name: 'Cards to copy' }, LONG);

const lastCardsSearch = (calls: ReturnType<typeof matchingApi>) =>
  callsTo(calls, 'GET', CARDS_PATH).at(-1)!.search;

afterEach(() => {
  vi.restoreAllMocks();
  clearToasts();
});

describe('Copy the fields of an existing card (CM-i)', () => {
  it('searches the catalog with the Cardmarket name at once and lists the cards found', async () => {
    const calls = api();
    const { dialog, section } = await openCreate();
    // above the fields
    const name = field(dialog, 'Name');
    expect(section.compareDocumentPosition(name) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(within(section).getByRole('textbox', { name: 'Card to copy' })).toHaveValue('Fury Rune');
    expect(within(section).getByText('A name or a code such as OGN-007.')).toBeVisible();
    const list = await results(section);
    const items = within(list).getAllByRole('listitem');
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent('Fury Rune');
    expect(items[0]).toHaveTextContent('OGN-007');
    expect(items[0]).toHaveTextContent('Common · Rune');
    expect(within(items[0]!).getByRole('img', { name: 'Fury Rune' })).toHaveAttribute(
      'src',
      '/riftbound/media/cards/ogn/007.webp',
    );
    expect(items[1]).toHaveTextContent('UNLX-001');
    const search = lastCardsSearch(calls);
    expect(search.get('q')).toBe('Fury Rune');
    expect(search.getAll('set')).toEqual([]);
    expect(search.get('type')).toBeNull();
  });

  it('the Set and Type filters narrow the search; a code finds its card', async () => {
    const calls = api();
    const { section, user } = await openCreate();
    await results(section);
    const set = within(section).getByRole('combobox', { name: 'Filter by set' });
    expect(
      within(set)
        .getAllByRole('option')
        .map((option) => option.textContent),
    ).toEqual(['Any set', 'OGN · Origins', 'OGS · Proving Grounds']);
    await user.selectOptions(set, 'OGN · Origins');
    const type = within(section).getByRole('combobox', { name: 'Filter by type' });
    await vi.waitFor(() =>
      expect(
        within(type)
          .getAllByRole('option')
          .map((option) => option.textContent),
      ).toEqual(['Any type', 'Legend', 'Unit', 'Spell', 'Gear', 'Rune', 'Battlefield']),
    );
    await user.selectOptions(type, 'Rune');
    await vi.waitFor(() => {
      const search = lastCardsSearch(calls);
      expect(search.getAll('set')).toEqual(['OGN']);
      expect(search.get('type')).toBe('Rune');
    });
    const box = within(section).getByRole('textbox', { name: 'Card to copy' });
    await user.clear(box);
    await user.type(box, 'OGN-042');
    await vi.waitFor(() => expect(lastCardsSearch(calls).get('q')).toBe('OGN-042'));
    const list = await results(section);
    await vi.waitFor(() => expect(within(list).getAllByRole('listitem')).toHaveLength(1));
    expect(within(list).getByRole('listitem')).toHaveTextContent('Calm Rune');
  });

  it('Enter in the search searches at once and never submits the card form', async () => {
    const calls = api();
    const { dialog, section, user } = await openCreate();
    await results(section);
    // a complete form: a submit would create the card
    await user.type(field(dialog, 'Number'), '099');
    const box = within(section).getByRole('textbox', { name: 'Card to copy' });
    await user.clear(box);
    await user.type(box, 'Calm{Enter}');
    await vi.waitFor(() => expect(lastCardsSearch(calls).get('q')).toBe('Calm'));
    // a submit would have posted by now: give it the time a create takes
    await new Promise((resolve) => setTimeout(resolve, 300));
    expect(callsTo(calls, 'POST', CARDS_PATH)).toHaveLength(0);
    expect(screen.getByRole('dialog', { name: 'Create a card for Fury Rune' })).toBeVisible();
  });

  it('nothing found says so; an empty search without filters asks for one', async () => {
    api();
    const { section, user } = await openCreate();
    await results(section);
    const box = within(section).getByRole('textbox', { name: 'Card to copy' });
    await user.clear(box);
    await user.type(box, 'zzz');
    expect(await within(section).findByText('No cards found.', {}, LONG)).toBeVisible();
    await user.clear(box);
    expect(
      await within(section).findByText('Search a name or a code, or choose a set or a type.'),
    ).toBeVisible();
  });

  it('a long result list shows the first cards and asks to refine', async () => {
    const many = Array.from({ length: 12 }, (_, index) =>
      catalogCard('OGN', String(index + 1).padStart(3, '0'), 'Fury Rune', {
        type: 'Rune',
        rarity: 'Common',
      }),
    );
    api(many);
    const { section } = await openCreate();
    const list = await results(section);
    expect(within(list).getAllByRole('listitem')).toHaveLength(8);
    expect(within(section).getByText('Showing 8 of 12 cards: refine the search.')).toBeVisible();
  });

  it('Use this card fills the fields but the set, the number and the image, marking them', async () => {
    const calls = api();
    const { dialog, section, user } = await openCreate();
    const list = await results(section);
    const set = within(dialog).getByRole('combobox', { name: 'Set' });
    await vi.waitFor(() => expect(set).toHaveValue('UNLX'));
    await user.type(field(dialog, 'Number'), '007');
    await user.click(
      within(list).getByRole('button', { name: 'Use this card: OGN-007 Fury Rune' }),
    );

    expect(field(dialog, 'Name')).toHaveValue('Fury Rune');
    expect(field(dialog, 'Type')).toHaveValue('Rune');
    expect(field(dialog, 'Domain')).toHaveValue('Fury');
    expect(field(dialog, 'Rarity')).toHaveValue('Common');
    expect(field(dialog, 'Artist')).toHaveValue('Kudos Productions');
    expect(field(dialog, 'Ability')).toHaveValue('Exhaust: add 1 Fury power.');
    expect(field(dialog, 'Tags')).toHaveValue('');
    expect(number(dialog, 'Energy')).toHaveValue(null);
    // the set stays the mapped one, the number what was typed, the image is never copied
    expect(set).toHaveValue('UNLX');
    expect(field(dialog, 'Number')).toHaveValue('007');
    expect(field(dialog, 'Gallery image URL')).toHaveValue('');
    // every filled field says where it came from
    expect(within(dialog).getAllByText(/^Copied from OGN-007\./)).toHaveLength(6);
    expect(field(dialog, 'Type')).toHaveAccessibleDescription(
      expect.stringContaining('Copied from OGN-007.'),
    );
    expect(within(section).getByRole('status')).toHaveTextContent(
      'Copied from OGN-007 Fury Rune: edit any field before creating.',
    );

    await user.click(within(dialog).getByRole('button', { name: 'Create and link' }));
    await vi.waitFor(() => expect(callsTo(calls, 'POST', '/links')).toHaveLength(1));
    expect(callsTo(calls, 'POST', CARDS_PATH).map((call) => call.body)).toEqual([
      {
        set_id: 'UNLX',
        card_id: '007',
        name: 'Fury Rune',
        domain: 'Fury',
        type: 'Rune',
        tags: null,
        energy: null,
        power: null,
        might: null,
        ability: 'Exhaust: add 1 Fury power.',
        rarity: 'Common',
        artist: 'Kudos Productions',
        image_url: null,
      },
    ]);
    // a rune has one Cardmarket product: no slot
    expect(callsTo(calls, 'POST', '/links')[0]!.body).toEqual({
      id_product: 9300,
      card: { set_id: 'UNLX', card_id: '007' },
      foil: null,
    });
  });

  it('a card of the same set leaves the number empty with a hint', async () => {
    api();
    const { dialog, section, user } = await openCreate();
    const list = await results(section);
    await vi.waitFor(() =>
      expect(within(dialog).getByRole('combobox', { name: 'Set' })).toHaveValue('UNLX'),
    );
    await user.click(
      within(list).getByRole('button', { name: 'Use this card: UNLX-001 Fury Rune' }),
    );
    expect(field(dialog, 'Number')).toHaveValue('');
    expect(
      within(dialog).getByText('UNLX-001 is in this set: give the new card its own number.'),
    ).toBeVisible();
    expect(field(dialog, 'Rarity')).toHaveValue('Showcase');
  });

  it('an edited field loses its mark; Clear copied data puts the fields back', async () => {
    api();
    const { dialog, section, user } = await openCreate();
    const list = await results(section);
    await user.click(
      within(list).getByRole('button', { name: 'Use this card: OGN-007 Fury Rune' }),
    );
    expect(within(dialog).getAllByText(/^Copied from OGN-007\./)).toHaveLength(6);
    await user.clear(field(dialog, 'Artist'));
    await user.type(field(dialog, 'Artist'), 'Another');
    expect(within(dialog).getAllByText(/^Copied from OGN-007\./)).toHaveLength(5);

    await user.click(within(section).getByRole('button', { name: 'Clear copied data' }));
    expect(field(dialog, 'Name')).toHaveValue('Fury Rune');
    expect(field(dialog, 'Type')).toHaveValue('');
    expect(field(dialog, 'Domain')).toHaveValue('');
    expect(field(dialog, 'Rarity')).toHaveValue('');
    expect(field(dialog, 'Artist')).toHaveValue('');
    expect(field(dialog, 'Ability')).toHaveValue('');
    expect(within(dialog).queryByText(/^Copied from/)).toBeNull();
    expect(within(section).queryByRole('button', { name: 'Clear copied data' })).toBeNull();
  });

  it('offline: Use this card is disabled', async () => {
    api();
    const { section } = await openCreate();
    const list = await results(section);
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    window.dispatchEvent(new Event('offline'));
    await vi.waitFor(() =>
      expect(
        within(list).getByRole('button', { name: 'Use this card: OGN-007 Fury Rune' }),
      ).toBeDisabled(),
    );
    vi.restoreAllMocks();
    window.dispatchEvent(new Event('online'));
  });

  it('has no axe violations', async () => {
    api();
    const { dialog, section, user } = await openCreate();
    const list = await results(section);
    await user.click(
      within(list).getByRole('button', { name: 'Use this card: OGN-007 Fury Rune' }),
    );
    expect(await axe(dialog)).toHaveNoViolations();
  }, 20000);
});
