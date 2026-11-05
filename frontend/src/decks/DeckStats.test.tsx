import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { axe } from 'vitest-axe';
import type { DeckCard, DeckContentV2 } from '@/api/types';
import { emptyContent } from '@/test/fixtures/decks';
import { renderWithI18n } from '@/test/i18n';
import { DeckStats } from './DeckStats';
import type { CardBook } from './editor';

const card = (card_id: string, overrides: Partial<DeckCard>): DeckCard => ({
  set_id: 'OGN',
  card_id,
  key: `OGN-${card_id}`,
  name: `Card ${card_id}`,
  domains: ['Calm'],
  type: 'Spell',
  supertype: null,
  rarity: 'Common',
  image_src: null,
  image_thumb_src: null,
  is_base: true,
  market: null,
  owned_total: 0,
  tags: [],
  energy: null,
  power: null,
  might: null,
  variants: 1,
  keywords: [],
  ...overrides,
});

const unit = card('1', { type: 'Unit', energy: 2, might: 3, power: 1, keywords: ['Hidden'] });
const champ = card('2', {
  type: 'Unit',
  supertype: 'Champion',
  domains: ['Chaos'],
  energy: 4,
  might: 5,
  keywords: ['Action', 'Hidden'],
});
const spell = card('3', { energy: 2, power: 2, domains: ['Calm', 'Chaos'] });
const gear = card('4', { type: 'Gear', energy: 11, domains: ['Chaos'] });
const calmRune = card('r1', { type: 'Rune', domains: ['Calm'] });
const chaosRune = card('r2', { type: 'Rune', domains: ['Chaos'] });
const book: CardBook = Object.fromEntries(
  [unit, champ, spell, gear, calmRune, chaosRune].map((c) => [c.key, c]),
);
const line = (c: DeckCard, qty: number) => ({ set: c.set_id, id: c.card_id, qty });
const content: DeckContentV2 = {
  ...emptyContent,
  main: [line(unit, 3), line(champ, 1), line(spell, 2), line(gear, 1)],
  runes: [line(calmRune, 5), line(chaosRune, 7)],
};

const tile = (name: string) =>
  screen.getByText(name, { selector: 'dt' }).parentElement?.querySelector('dd')?.textContent;
const items = (element: HTMLElement) =>
  within(element)
    .getAllByRole('listitem')
    .map((item) => item.textContent);

describe('DeckStats (F5-i step 4)', () => {
  it('shows the summary tiles', async () => {
    await renderWithI18n(<DeckStats content={content} book={book} />);
    expect(tile('Main deck')).toBe('7');
    // (2*3 + 4 + 2*2 + 11) / 7 = 3.57
    expect(tile('Avg energy')).toBe('3.6');
    // units only have might here: (3*3 + 5) / 4
    expect(tile('Avg might')).toBe('3.5');
    expect(tile('Power cards')).toBe('5');
  });

  it('gives the energy curve as text, each bar split by group, 10+ last', async () => {
    await renderWithI18n(<DeckStats content={content} book={book} />);
    const curve = screen.getByRole('figure', { name: 'Energy curve' });
    const values = items(within(curve).getByRole('list', { name: 'Energy curve values' }));
    expect(values).toHaveLength(11);
    expect(values[0]).toBe('Energy 0: 0 cards');
    expect(values[2]).toBe('Energy 2: 5 cards (Unit 3, Spell 2)');
    expect(values[4]).toBe('Energy 4: 1 card (Champion 1)');
    expect(values[10]).toBe('Energy 10+: 1 card (Gear 1)');
    // the legend names the four groups
    expect(
      items(within(curve).getByRole('list', { name: 'Card groups' })).map((text) => text?.trim()),
    ).toEqual(['Unit', 'Spell', 'Gear', 'Champion']);
  });

  it('gives power and runes per domain with their shares', async () => {
    await renderWithI18n(<DeckStats content={content} book={book} />);
    const figure = screen.getByRole('figure', { name: 'Power & runes by domain' });
    const calm = within(figure).getByRole('group', { name: 'Calm' });
    const chaos = within(figure).getByRole('group', { name: 'Chaos' });
    // Calm: unit ×3 (power 3) + spell ×2 (power 4); Chaos: champ, spell ×2 (power 4), gear
    expect(items(calm)).toEqual(['Cards 5 (56%)', 'Power 7 (64%)', 'Runes 5 (42%)']);
    expect(items(chaos)).toEqual(['Cards 4 (44%)', 'Power 4 (36%)', 'Runes 7 (58%)']);
    expect(within(figure).getByText(/counts in each of its domains/)).toBeVisible();
  });

  it('gives the unit might histogram as text', async () => {
    await renderWithI18n(<DeckStats content={content} book={book} />);
    const figure = screen.getByRole('figure', { name: 'Unit might' });
    const values = items(within(figure).getByRole('list', { name: 'Unit might values' }));
    expect(values).toHaveLength(13);
    expect(values[3]).toBe('Might 3: 3 units');
    expect(values[5]).toBe('Might 5: 1 unit');
    expect(values[12]).toBe('Might 12+: 0 units');
  });

  it('lists the keywords by copies and says they are approximate', async () => {
    await renderWithI18n(<DeckStats content={content} book={book} />);
    const block = screen.getByRole('region', { name: 'Keywords' });
    expect(items(block)).toEqual(['Hidden4', 'Action1']);
    expect(within(block).getByText(/approximate/)).toBeVisible();
  });

  it('says when no main card has a keyword', async () => {
    const plain = { ...content, main: [line(gear, 1)] };
    await renderWithI18n(<DeckStats content={plain} book={book} />);
    const block = screen.getByRole('region', { name: 'Keywords' });
    expect(within(block).getByText('No keywords found.')).toBeVisible();
    expect(tile('Avg might')).toBe('—No value');
  });

  it('an empty main deck shows a short message instead of the charts', async () => {
    await renderWithI18n(<DeckStats content={emptyContent} book={{}} />);
    expect(screen.getByText('Add cards to the main deck to see its stats.')).toBeVisible();
    expect(screen.queryByRole('figure')).toBeNull();
  });

  it('is axe clean', async () => {
    const { container } = await renderWithI18n(<DeckStats content={content} book={book} />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
