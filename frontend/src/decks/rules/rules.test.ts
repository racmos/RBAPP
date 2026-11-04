// F5-b: library behaviour the shared cases cannot express (errors, purity, rule values from
// the context, names). The rules themselves are in `cases.test.ts`.
import { globSync, readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import type { CardSummary, GameMeta } from '@/api/types';
import {
  CASES,
  caseById,
  cardsOf,
  readRepoFile,
  runCase,
  type RulesCase,
} from '@/test/deckRulesCases';
import {
  DEFAULT_RULES,
  UnknownCard,
  canAdd,
  canMove,
  compareNames,
  hardLimitViolations,
  makeCards,
  nameKey,
  rulesFromMeta,
  sortNames,
  validate,
  type DeckContent,
  type RulesContext,
} from './index';

const REAL = caseById('validate-real-deck-legal-1v1');
const REAL_DECK = REAL.deck as DeckContent;

function deepFreeze<T>(value: T): T {
  if (value !== null && typeof value === 'object') {
    Object.values(value).forEach(deepFreeze);
    Object.freeze(value);
  }
  return value;
}

/** Every object and array reachable from `value`. */
function objectsOf(value: unknown, out = new Set<unknown>()): Set<unknown> {
  if (value !== null && typeof value === 'object') {
    out.add(value);
    Object.values(value).forEach((item) => objectsOf(item, out));
  }
  return out;
}

describe('purity (F5-a S2)', () => {
  it('never mutates its inputs and never returns them', () => {
    for (const testCase of CASES) {
      const snapshot = structuredClone({ deck: testCase.deck, args: testCase.args });
      const cards = cardsOf(testCase);
      const cardsBefore = structuredClone([...cards]);
      // Frozen inputs: any write throws (modules are strict).
      const frozen: RulesCase = deepFreeze(structuredClone(testCase));
      for (const card of cards.values()) deepFreeze(card);
      const result = runCase(frozen, DEFAULT_RULES, cards);
      expect({ deck: frozen.deck, args: frozen.args }, testCase.id).toEqual(snapshot);
      expect([...cards], testCase.id).toEqual(cardsBefore);
      const inputs = objectsOf({ deck: frozen.deck, args: frozen.args });
      for (const item of objectsOf(result)) {
        expect(inputs.has(item), testCase.id).toBe(false);
      }
    }
  });
});

describe('errors (F5-a S2)', () => {
  it('rejects an unknown game mode', () => {
    expect(() => validate(REAL_DECK, cardsOf(REAL), {}, 'ffa', DEFAULT_RULES)).toThrow(
      new RangeError('unknown game mode: ffa'),
    );
  });

  it('reports an unknown card with its printing', () => {
    const deck = { ...REAL_DECK, main: [...REAL_DECK.main, { set: 'ZZZ', id: '1', qty: 1 }] };
    let raised: unknown = null;
    try {
      validate(deck, cardsOf(REAL), {}, '1v1', DEFAULT_RULES);
    } catch (error) {
      raised = error;
    }
    expect(raised).toBeInstanceOf(UnknownCard);
    expect((raised as UnknownCard).ref).toEqual(['ZZZ', '1']);
    expect(() =>
      canAdd(REAL_DECK, cardsOf(REAL), { set: 'ZZZ', id: '1' }, 'main', DEFAULT_RULES),
    ).toThrow(UnknownCard);
  });

  it('rejects an unknown zone or move', () => {
    const cards = cardsOf(REAL);
    const card = { set: 'OGN', id: '17' }; // Defy, in the main deck
    // @ts-expect-error legend is not an add zone.
    expect(() => canAdd(REAL_DECK, cards, card, 'legend', DEFAULT_RULES)).toThrow(
      new RangeError('unknown zone: legend'),
    );
    expect(() => canMove(REAL_DECK, cards, card, 'main', 'main', DEFAULT_RULES)).toThrow(
      /unknown move/,
    );
    // @ts-expect-error runes is not a move zone.
    expect(() => canMove(REAL_DECK, cards, card, 'main', 'runes', DEFAULT_RULES)).toThrow(
      /unknown move/,
    );
    expect(() => canMove(REAL_DECK, cards, card, 'sideboard', 'main', DEFAULT_RULES)).toThrow(
      new RangeError('card not in sideboard'),
    );
  });
});

describe('rule values (F5-a S1)', () => {
  it('reads every value from the context it is given', () => {
    const rules: RulesContext = { ...DEFAULT_RULES, deck: { ...DEFAULT_RULES.deck, sideboard: 9 } };
    expect(validate(REAL_DECK, cardsOf(REAL), {}, '1v1', rules).issues).toEqual([
      { code: 'sideboard_size', params: { have: 10, need: 9, missing: 0, over: 1 } },
    ]);
    expect(hardLimitViolations(REAL_DECK, cardsOf(REAL), rules)).toEqual([
      { rule: 'sideboard', max: 9 },
    ]);
  });

  it('keeps DEFAULT_RULES equal to the backend values', () => {
    const domain = readRepoFile('app/schemas/game_domain.py');
    const block = domain.match(/^DECK_RULES = \{([^}]*)\}/m)![1];
    const values = Object.fromEntries(
      [...block.matchAll(/'(\w+)':\s*(\d+)/g)].map((item) => [item[1], Number(item[2])]),
    );
    expect(Object.entries(DEFAULT_RULES.deck)).toEqual(Object.entries(values));
    const tuple = (name: string) =>
      [...domain.match(new RegExp(`^${name} = \\(([^)]*)\\)`, 'm'))![1].matchAll(/'([^']*)'/g)].map(
        (item) => item[1],
      );
    expect(DEFAULT_RULES.modes).toEqual(tuple('GAME_MODES'));
    expect(DEFAULT_RULES.domains).toEqual(tuple('DOMAINS'));
  });

  it('builds the context from GET /meta/game', () => {
    const meta = {
      modes: ['1v1', '2v2'],
      domains: ['Fury', 'Calm'],
      rules: { deck: { ...DEFAULT_RULES.deck, runes: 11 } },
    } satisfies Pick<GameMeta, 'modes' | 'domains' | 'rules'>;
    expect(rulesFromMeta(meta)).toEqual({
      deck: { ...DEFAULT_RULES.deck, runes: 11 },
      modes: ['1v1', '2v2'],
      domains: ['Fury', 'Calm'],
    });
    expect(rulesFromMeta({ ...meta, rules: {} })).toBeNull();
  });

  it('is imported only by tests: the app never hardcodes the defaults', () => {
    const offenders = globSync('src/**/*.{ts,tsx}', { cwd: process.cwd() }).filter(
      (file) =>
        !/\.test\.tsx?$/.test(file) &&
        !file.startsWith('src/decks/rules/') &&
        !file.startsWith('src/test/') &&
        readFileSync(file, 'utf8').includes('DEFAULT_RULES'),
    );
    expect(offenders).toEqual([]);
  });
});

describe('cards (F5-a S2)', () => {
  it('accepts CardSummary-shaped cards (extra keys are ignored)', () => {
    const cards = makeCards(
      [...cardsOf(REAL).values()].map((card) => {
        const { set, id } = card as unknown as { set: string; id: string };
        const summary = {
          ...(card as object),
          set_id: set,
          card_id: id,
          price: null,
          bans: {},
        } as unknown as CardSummary;
        return [{ set, id }, summary] as const;
      }),
    );
    expect(validate(REAL_DECK, cards, {}, '2v2', DEFAULT_RULES).legal).toBe(true);
  });
});

describe('names (F5-a S3, D-F5-7)', () => {
  it('folds whitespace like Python str.split()', () => {
    expect(nameKey('  Not\u00a0So\u2003Fast\x1c ')).toBe('not so fast');
    // U+FEFF is \s in JS but not whitespace for Python.
    expect(nameKey('a\ufeffb')).toBe('a\ufeffb');
    expect(nameKey('Zhonya’s ‘Hourglass')).toBe("zhonya's 'hourglass");
  });

  it('compares by code point, not by UTF-16 unit or locale', () => {
    // U+1F600 is above U+FFFD as a code point, below it as a UTF-16 unit.
    expect(sortNames(['\u{1F600}', '\ufffd'])).toEqual(['\ufffd', '\u{1F600}']);
    expect(sortNames(['Élan', 'Zed', 'zed'])).toEqual(['Zed', 'zed', 'Élan']);
    expect(compareNames('REBUKE', 'Rebuke')).toBeLessThan(0);
  });

  it('returns a new array and leaves its input alone', () => {
    const names = Object.freeze(['b', 'a']);
    const sorted = sortNames(names);
    expect(sorted).toEqual(['a', 'b']);
    expect(names).toEqual(['b', 'a']);
  });
});
