import type { DeckCard, DeckContentV2, DeckRefLine } from '@/api/types';
import { DOMAIN_COLORS } from '@/lib/domains';
import type { CardBook } from './editor';
import { refKey } from './labels';
import { COLORLESS } from './rules';

/**
 * The numbers of the workspace Stats tab (F5-i step 4), pure. Everything is counted over the
 * MAIN deck by copies (`qty`); the sideboard and the workbench never count, and a printing the
 * book does not know is skipped. Definitions:
 * - Averages (energy, might) are over the copies that have the value; `null` when none has it.
 * - Power cards = copies with a power cost greater than 0 (owner decision 3).
 * - Energy curve: buckets 0..9 and `10+`, each split into Unit, Spell, Gear and Champion
 *   (Champion = supertype `Champion`, whatever the type). A card without an energy cost, or of
 *   another type (a misplaced legend or rune, which the legality reports), is in no bucket.
 * - Unit might: units only (champion units included), buckets 0..11 and `12+`.
 * - Power & runes by domain: a multi-domain card counts fully in each of its domains (cards and
 *   power), the simplest reading of "this card needs this domain"; a card with no domain but
 *   Colorless counts under Colorless. Runes come from the runes zone, by their domains. Each share
 *   is the row's part of that column's sum over the rows, so every column adds up to 100%.
 * - Keywords (derived from the ability text, approximate): copies per keyword, a keyword once per
 *   card, most used first, then by name.
 */

export const ENERGY_TOP = 10;
export const MIGHT_TOP = 12;
export const STAT_GROUPS = ['unit', 'spell', 'gear', 'champion'] as const;
export type StatGroup = (typeof STAT_GROUPS)[number];

export type EnergyBucket = {
  value: number;
  /** The last bucket: this value and above. */
  top: boolean;
  total: number;
  groups: Record<StatGroup, number>;
};
export type MightBucket = { value: number; top: boolean; count: number };
export type DomainRow = {
  domain: string;
  cards: number;
  power: number;
  runes: number;
  cardShare: number;
  powerShare: number;
  runeShare: number;
};
export type KeywordCount = { name: string; count: number };

export type DeckStats = {
  mainCount: number;
  avgEnergy: number | null;
  avgMight: number | null;
  powerCards: number;
  energyCurve: EnergyBucket[];
  powerByDomain: DomainRow[];
  mightHistogram: MightBucket[];
  keywords: KeywordCount[];
};

const GAME_ORDER: readonly string[] = Object.keys(DOMAIN_COLORS);

const bucketOf = (value: number, top: number) => Math.min(Math.max(0, Math.floor(value)), top);

function groupOf(card: DeckCard): StatGroup | null {
  if (card.supertype === 'Champion') return 'champion';
  if (card.type === 'Unit') return 'unit';
  if (card.type === 'Spell') return 'spell';
  if (card.type === 'Gear') return 'gear';
  return null;
}

function domainsOf(card: DeckCard): string[] {
  const colours = card.domains.filter((domain) => domain !== COLORLESS);
  return colours.length > 0 ? [...new Set(colours)] : [COLORLESS];
}

const average = (sum: number, count: number) => (count > 0 ? sum / count : null);
const share = (part: number, whole: number) => (whole > 0 ? part / whole : 0);

/** Every known card of a zone with its copies. */
function known(lines: DeckRefLine[], book: CardBook) {
  return lines.flatMap((line) => {
    const card = book[refKey(line)];
    return card ? [{ card, qty: line.qty }] : [];
  });
}

export function deckStats(content: DeckContentV2, book: CardBook): DeckStats {
  const main = known(content.main, book);
  const energyCurve: EnergyBucket[] = Array.from({ length: ENERGY_TOP + 1 }, (_, value) => ({
    value,
    top: value === ENERGY_TOP,
    total: 0,
    groups: { unit: 0, spell: 0, gear: 0, champion: 0 },
  }));
  const mightHistogram: MightBucket[] = Array.from({ length: MIGHT_TOP + 1 }, (_, value) => ({
    value,
    top: value === MIGHT_TOP,
    count: 0,
  }));
  const domains = new Map<string, { cards: number; power: number; runes: number }>();
  const domainRow = (domain: string) => {
    let row = domains.get(domain);
    if (!row) {
      row = { cards: 0, power: 0, runes: 0 };
      domains.set(domain, row);
    }
    return row;
  };
  const keywords = new Map<string, number>();
  let mainCount = 0;
  let powerCards = 0;
  const energy = { sum: 0, count: 0 };
  const might = { sum: 0, count: 0 };

  for (const { card, qty } of main) {
    mainCount += qty;
    if (card.power !== null && card.power > 0) powerCards += qty;
    if (card.energy !== null) {
      energy.sum += card.energy * qty;
      energy.count += qty;
      const group = groupOf(card);
      if (group) {
        const bucket = energyCurve[bucketOf(card.energy, ENERGY_TOP)];
        bucket.total += qty;
        bucket.groups[group] += qty;
      }
    }
    if (card.might !== null) {
      might.sum += card.might * qty;
      might.count += qty;
      if (card.type === 'Unit') mightHistogram[bucketOf(card.might, MIGHT_TOP)].count += qty;
    }
    for (const domain of domainsOf(card)) {
      const row = domainRow(domain);
      row.cards += qty;
      row.power += (card.power ?? 0) * qty;
    }
    for (const keyword of new Set(card.keywords)) {
      keywords.set(keyword, (keywords.get(keyword) ?? 0) + qty);
    }
  }
  for (const { card, qty } of known(content.runes, book)) {
    for (const domain of domainsOf(card)) domainRow(domain).runes += qty;
  }

  const rank = (domain: string) => {
    const index = GAME_ORDER.indexOf(domain);
    return index === -1 ? GAME_ORDER.length : index;
  };
  const rows = [...domains.entries()].sort(
    ([a], [b]) => rank(a) - rank(b) || a.localeCompare(b, 'en'),
  );
  const sum = (key: 'cards' | 'power' | 'runes') =>
    rows.reduce((total, [, row]) => total + row[key], 0);
  const totals = { cards: sum('cards'), power: sum('power'), runes: sum('runes') };

  return {
    mainCount,
    avgEnergy: average(energy.sum, energy.count),
    avgMight: average(might.sum, might.count),
    powerCards,
    energyCurve,
    powerByDomain: rows.map(([domain, row]) => ({
      domain,
      ...row,
      cardShare: share(row.cards, totals.cards),
      powerShare: share(row.power, totals.power),
      runeShare: share(row.runes, totals.runes),
    })),
    mightHistogram,
    keywords: [...keywords.entries()]
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name, 'en')),
  };
}
