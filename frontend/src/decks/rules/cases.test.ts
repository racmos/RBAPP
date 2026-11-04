// F5-b (F5-R3, D-F5-8): every shared case of `tests/fixtures/deck_rules_cases.json` runs
// against the TypeScript library, with the same card resolution as the Python runner
// (`tests/test_deck_rules_cases.py`). The cases are the contract; the server stays authoritative.
import { describe, expect, it } from 'vitest';
import { CASES, CATALOG, OPS, pythonTuple, readRepoFile, runCase } from '@/test/deckRulesCases';
import { HARD_RULES, ISSUE_CODES } from './index';

let ran = 0;

describe('shared deck rules cases (F5-R3)', () => {
  it.each(CASES.map((testCase) => [testCase.id, testCase] as const))('%s', (_id, testCase) => {
    ran += 1;
    expect(runCase(testCase)).toStrictEqual(testCase.expected);
  });

  // Runs after the cases (vitest keeps declaration order): every case of the file ran, the
  // same list pytest parametrizes.
  it('ran every case of the file', () => {
    expect(CASES.length).toBeGreaterThan(0);
    expect(ran).toBe(CASES.length);
  });
});

describe('the cases file itself', () => {
  it('has unique ids and well-formed cases', () => {
    const ids = CASES.map((testCase) => testCase.id);
    expect(new Set(ids).size).toBe(ids.length);
    const keys = new Set([
      'id',
      'description',
      'op',
      'mode',
      'deck',
      'catalog',
      'bans',
      'args',
      'expected',
    ]);
    for (const testCase of CASES) {
      expect(
        Object.keys(testCase).every((key) => keys.has(key)),
        testCase.id,
      ).toBe(true);
      expect(testCase.description.trim(), testCase.id).not.toBe('');
      expect(
        testCase.catalog.every((key) => CATALOG.has(key)),
        testCase.id,
      ).toBe(true);
    }
  });

  it('handles exactly the ops of the Python runner, each with cases', () => {
    const python = pythonTuple(readRepoFile('tests/test_deck_rules_cases.py'), 'OPS');
    expect([...OPS].sort()).toEqual(python.sort());
    expect(new Set(CASES.map((testCase) => testCase.op))).toEqual(new Set(OPS));
  });

  it('uses the issue codes and hard rules of the Python engine, in its order', () => {
    const engine = readRepoFile('app/services/deck_rules.py');
    expect([...ISSUE_CODES]).toEqual(pythonTuple(engine, 'ISSUE_CODES'));
    expect([...HARD_RULES]).toEqual(pythonTuple(engine, 'HARD_RULES'));
  });

  it('expects every issue code and every hard rule at least once', () => {
    const codes = new Set(
      CASES.filter((testCase) => testCase.op === 'validate').flatMap((testCase) =>
        (testCase.expected as { issues: { code: string }[] }).issues.map((issue) => issue.code),
      ),
    );
    expect(codes).toEqual(new Set(ISSUE_CODES));
    const rules = new Set(
      CASES.filter((testCase) => testCase.op === 'hard_limits').flatMap((testCase) =>
        (testCase.expected as { rule: string }[]).map((item) => item.rule),
      ),
    );
    expect(rules).toEqual(new Set(HARD_RULES));
  });
});
