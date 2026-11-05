import { beforeAll, describe, expect, it } from 'vitest';
import type { TFunction } from 'i18next';
import { createI18n } from '@/i18n';
import { HARD_RULES, ISSUE_CODES } from './rules';
import { hardLimitMessage, issueMessage, issueShort } from './issues';

/** Params of every issue code (F5-a S7): a sized one is tried both under and over. */
const SAMPLES: Record<string, Record<string, string | number>[]> = {
  legend_missing: [{ have: 0, need: 1, missing: 1 }],
  champion_missing: [{ have: 0, need: 1, missing: 1 }],
  champion_tag: [{ name: 'Riven, Broken Blade' }],
  main_size: [
    { have: 23, need: 39, missing: 16, over: 0 },
    { have: 41, need: 39, missing: 0, over: 2 },
  ],
  runes_count: [
    { have: 6, need: 12, missing: 6, over: 0 },
    { have: 13, need: 12, missing: 0, over: 1 },
  ],
  rune_off_identity: [{ name: 'Fury Rune' }],
  battlefields_count: [
    { have: 2, need: 3, missing: 1, over: 0 },
    { have: 4, need: 3, missing: 0, over: 1 },
  ],
  battlefields_duplicate: [{ name: 'Star Spring' }],
  sideboard_size: [
    { have: 8, need: 10, missing: 2, over: 0 },
    { have: 11, need: 10, missing: 0, over: 1 },
  ],
  copies_over: [{ name: 'Discipline', count: 4, max: 3 }],
  workbench_over: [{ count: 101, max: 100 }],
  card_off_identity: [
    { name: 'Star Spring', zone: 'main', reason: 'type' },
    { name: 'Ember Wisp', zone: 'sideboard', reason: 'domain' },
    { name: 'Blade of the Exile', zone: 'main', reason: 'tag' },
  ],
  token_in_deck: [{ name: 'Spark Token', zone: 'main' }],
  banned: [{ name: "Zhonya's Hourglass", mode: '2v2' }],
};

let t: TFunction<'decks'>;
beforeAll(async () => {
  const i18n = await createI18n();
  t = i18n.getFixedT('en', 'decks');
});

describe('issue messages (F5-R19)', () => {
  it('has samples for exactly the engine codes', () => {
    expect(Object.keys(SAMPLES).sort()).toEqual([...ISSUE_CODES].sort());
  });

  it.each(ISSUE_CODES.flatMap((code) => SAMPLES[code].map((params) => [code, params] as const)))(
    '%s says what is wrong with its params',
    (code, params) => {
      const text = issueMessage(t, { code, params });
      expect(text).not.toBe('');
      expect(text).not.toMatch(/\{\{|issue\.|undefined/);
      // a missing slot needs no numbers: "Choose a legend."
      const slot = code === 'legend_missing' || code === 'champion_missing';
      const keys = slot ? [] : (['name', 'mode', 'count', 'max', 'have', 'need'] as const);
      for (const key of keys) {
        if (params[key] !== undefined) expect(text).toContain(String(params[key]));
      }
      if (Number(params.missing) > 0 && params.over !== undefined) {
        expect(text).toContain(`${params.missing} missing`);
      }
      if (Number(params.over) > 0) expect(text).toContain(`${params.over} too many`);
    },
  );

  it('gives each reason of card_off_identity and each zone its own words', () => {
    const texts = SAMPLES.card_off_identity.map((params) =>
      issueMessage(t, { code: 'card_off_identity', params }),
    );
    expect(new Set(texts).size).toBe(3);
    expect(texts[0]).toBe('Star Spring cannot go in the main deck: wrong card type.');
    expect(texts[1]).toBe("Ember Wisp has a domain outside the legend's domains (the sideboard).");
    expect(texts[2]).toBe(
      'Blade of the Exile is a signature card that shares no tag with the legend (the main deck).',
    );
    expect(issueMessage(t, { code: 'copies_over', params: SAMPLES.copies_over[0] })).toBe(
      'Discipline has 4 copies (max 3).',
    );
    expect(issueMessage(t, { code: 'sideboard_size', params: SAMPLES.sideboard_size[0] })).toBe(
      'The sideboard has 8 of 10 cards (2 missing).',
    );
  });

  it('has a short reason for every code (the list knows only the codes)', () => {
    for (const code of ISSUE_CODES) {
      const text = issueShort(t, code);
      expect(text, code).not.toBe('');
      expect(text, code).not.toMatch(/\{\{|issue/);
    }
    expect(issueShort(t, 'banned')).toBe('A banned card');
  });

  it('falls back to the code for an unknown one', () => {
    expect(issueMessage(t, { code: 'new_rule', params: {} })).toBe('Rule not met: new_rule.');
    expect(issueShort(t, 'new_rule')).toBe('Rule not met: new_rule.');
  });

  it('explains every hard limit (deck_limit_exceeded params)', () => {
    for (const rule of HARD_RULES) {
      const text = hardLimitMessage(t, { rule, max: 3, name: 'Discipline' });
      expect(text, rule).not.toBe('');
      expect(text, rule).not.toMatch(/\{\{|limit\./);
    }
    expect(hardLimitMessage(t, { rule: 'copies', max: 3, name: 'Discipline' })).toBe(
      'Discipline: more than 3 copies.',
    );
    expect(hardLimitMessage(t, { rule: 'runes', max: 12 })).toBe('More than 12 runes.');
  });
});
