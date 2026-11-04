// The shared deck rules cases (F5-R3, D-F5-8): `tests/fixtures/deck_rules_cases.json`, read
// with `fs` (never bundled), and the TypeScript twin of `_run` in
// `tests/test_deck_rules_cases.py` (same card resolution, same call per op).
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import {
  DEFAULT_RULES,
  applyChampion,
  applyLegend,
  autoRunes,
  canAdd,
  canMove,
  deckDomains,
  hardLimitViolations,
  makeCards,
  sortNames,
  validate,
  type AddZone,
  type Bans,
  type Card,
  type CardRef,
  type Cards,
  type DeckContent,
  type MoveZone,
  type RulesContext,
} from '@/decks/rules';

/** A file of the repository (vitest runs from frontend/, like the other fs-based tests). */
export const repoFile = (path: string) => resolve(process.cwd(), '..', path);

export type CatalogCard = Card & { set: string; id: string };
export type RulesCase = {
  id: string;
  description: string;
  op: string;
  mode?: string;
  deck: DeckContent | null;
  catalog: string[];
  bans?: Bans;
  args: Record<string, unknown>;
  expected: unknown;
};

const DATA = JSON.parse(readFileSync(repoFile('tests/fixtures/deck_rules_cases.json'), 'utf8')) as {
  catalog: CatalogCard[];
  cases: RulesCase[];
};
export const CATALOG = new Map(DATA.catalog.map((card) => [`${card.set}-${card.id}`, card]));
export const CASES = DATA.cases;

/** The ops the runner handles (`OPS` of the Python runner). */
export const OPS = [
  'validate',
  'can_add',
  'can_move',
  'auto_runes',
  'apply_legend',
  'apply_champion',
  'deck_domains',
  'hard_limits',
  'sort_names',
] as const;

/** Same as the Python `_cards`: the case's catalog keys, in their order. */
export function cardsOf(testCase: RulesCase): Cards {
  return makeCards(
    testCase.catalog.map((key) => {
      const card = CATALOG.get(key)!;
      return [{ set: card.set, id: card.id }, card] as const;
    }),
  );
}

export function caseById(id: string): RulesCase {
  const found = CASES.find((testCase) => testCase.id === id);
  if (!found) throw new Error(`no case ${id}`);
  return found;
}

/** Runs one case the way `_run` does; `cards` defaults to the case's catalog. */
export function runCase(
  testCase: RulesCase,
  rules: RulesContext = DEFAULT_RULES,
  cards: Cards = cardsOf(testCase),
): unknown {
  const deck = testCase.deck as DeckContent;
  const args = testCase.args;
  switch (testCase.op) {
    case 'validate':
      return validate(deck, cards, testCase.bans!, testCase.mode!, rules);
    case 'can_add':
      return canAdd(deck, cards, args.card as CardRef, args.zone as AddZone, rules);
    case 'can_move':
      return canMove(
        deck,
        cards,
        args.card as CardRef,
        args.from as MoveZone,
        args.to as MoveZone,
        rules,
      );
    case 'auto_runes':
      return autoRunes(deck, cards, rules);
    case 'apply_legend':
      return applyLegend(deck, cards, args.legend as CardRef | null);
    case 'apply_champion':
      return applyChampion(deck, cards, args.champion as CardRef | null, rules);
    case 'deck_domains':
      return deckDomains(deck, cards, rules);
    case 'hard_limits':
      return hardLimitViolations(deck, cards, rules);
    case 'sort_names':
      return sortNames(args.names as string[]);
    default:
      throw new Error(`unknown op ${testCase.op}`);
  }
}

/** The quoted strings of a Python tuple assignment `NAME = (...)`. */
export function pythonTuple(source: string, name: string): string[] {
  const match = source.match(new RegExp(`^${name} = \\(([^)]*)\\)`, 'm'));
  if (!match) throw new Error(`${name} not found`);
  return [...match[1].matchAll(/'([^']*)'/g)].map((item) => item[1]);
}

export const readRepoFile = (path: string) => readFileSync(repoFile(path), 'utf8');
