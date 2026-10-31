import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { GameMeta } from '@/api/types';
import { renderWithI18n } from '@/test/i18n';
import { CollectionFilters } from './CollectionFilters';

/** `GET /meta/game` lists base values only (owner feedback S18 g). */
const META: GameMeta = {
  modes: ['1v1', '2v2'],
  domains: ['Fury', 'Calm', 'Mind', 'Body', 'Chaos', 'Order', 'Colorless'],
  types: ['Legend', 'Unit', 'Spell', 'Gear', 'Rune', 'Battlefield'],
  supertypes: ['Champion', 'Signature', 'Token', 'Basic'],
  rarities: ['Common', 'Uncommon', 'Rare', 'Epic', 'Showcase'],
  sets: [{ id: 'OGN', name: 'Origins', released_on: '2024-01-15', card_count: 6 }],
  price: { provider: 'cardmarket', currency: 'EUR', updated_on: null },
  rules: {},
  conditions: ['MT', 'NM'],
  languages: ['English'],
};

function renderSidebar(meta: GameMeta = META) {
  return renderWithI18n(
    <CollectionFilters
      variant="sidebar"
      params={{}}
      setParams={() => undefined}
      meta={meta}
      facets={{}}
      total={0}
      onClear={() => undefined}
    />,
  );
}

describe('CollectionFilters (owner feedback S18 g)', () => {
  it('shows each facet group heading once', async () => {
    await renderSidebar();
    for (const title of ['Set', 'Domain', 'Type', 'Rarity', 'Condition', 'Language']) {
      expect(screen.getAllByText(title, { exact: true }), title).toHaveLength(1);
      expect(screen.getByRole('group', { name: title })).toBeInTheDocument();
    }
  });

  it('shows what every tri-state filter filters (owner feedback S24)', async () => {
    await renderSidebar();
    for (const [name, option] of [
      ['Foil', 'Foil only'],
      ['On sale', 'Any'],
      ['With purchase price', 'Any'],
    ]) {
      const group = screen.getByRole('radiogroup', { name });
      const label = document.getElementById(group.getAttribute('aria-labelledby')!);
      expect(label, name).toHaveTextContent(name);
      expect(label, name).toBeVisible();
      expect(label!.closest('.sr-only'), name).toBeNull();
      expect(within(group).getByRole('radio', { name: option })).toBeInTheDocument();
    }
  });

  it('translates every base type and domain', async () => {
    await renderSidebar();
    const types = screen.getByRole('group', { name: 'Type' });
    for (const name of ['Legend', 'Unit', 'Spell', 'Gear', 'Rune', 'Battlefield']) {
      expect(within(types).getByRole('button', { name })).toBeInTheDocument();
    }
    const domains = screen.getByRole('group', { name: 'Domain' });
    for (const name of ['Fury', 'Calm', 'Mind', 'Body', 'Chaos', 'Order', 'Colorless']) {
      expect(within(domains).getByRole('button', { name })).toBeInTheDocument();
    }
  });
});

describe('CollectionFilters set order (owner feedback S19)', () => {
  it('lists the set chips newest first and the sets without a date last', async () => {
    await renderSidebar({
      ...META,
      sets: [
        { id: 'OLD', name: 'Old', released_on: '2024-01-15', card_count: 1 },
        { id: 'NOD', name: 'No date', released_on: null, card_count: 1 },
        { id: 'NEW', name: 'New', released_on: '2026-09-01', card_count: 1 },
        { id: 'MID', name: 'Mid', released_on: '2025-06-01', card_count: 1 },
      ],
    });
    const sets = screen.getByRole('group', { name: 'Set' });
    expect(
      within(sets)
        .getAllByRole('button')
        .map((chip) => chip.textContent),
    ).toEqual(['NEW', 'MID', 'OLD', 'NOD']);
  });
});
