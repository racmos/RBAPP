import { describe, expect, it } from 'vitest';
import { parseAbility } from './parseAbility';

describe('parseAbility (F2-f S9)', () => {
  it('returns an empty array for null or empty text', () => {
    expect(parseAbility(null)).toEqual([]);
    expect(parseAbility('')).toEqual([]);
    expect(parseAbility('   ')).toEqual([]);
  });

  it('parses bracketed keywords', () => {
    expect(parseAbility('[Accelerate] When I attack, deal 2.')).toEqual([
      { kind: 'keyword', text: 'Accelerate' },
      { kind: 'text', text: ' When I attack, deal 2.' },
    ]);
  });

  it('parses energy symbols', () => {
    expect(parseAbility('Pay :rb_energy_2:.')).toEqual([
      { kind: 'text', text: 'Pay ' },
      { kind: 'energy', value: 2 },
      { kind: 'text', text: '.' },
    ]);
  });

  it('parses exhaust and might symbols', () => {
    expect(parseAbility(':rb_exhaust: and :rb_might:')).toEqual([
      { kind: 'exhaust' },
      { kind: 'text', text: ' and ' },
      { kind: 'might' },
    ]);
  });

  it('parses domain runes', () => {
    expect(parseAbility(':rb_rune_fury: or :rb_rune_calm:')).toEqual([
      { kind: 'rune', domain: 'Fury' },
      { kind: 'text', text: ' or ' },
      { kind: 'rune', domain: 'Calm' },
    ]);
  });

  it('parses the rainbow rune', () => {
    expect(parseAbility(':rb_rune_rainbow:')).toEqual([{ kind: 'rune', domain: 'rainbow' }]);
  });

  it('falls back to keyword for unknown rb symbols', () => {
    expect(parseAbility(':rb_power:')).toEqual([{ kind: 'keyword', text: 'power' }]);
    expect(parseAbility(':rb_unknown_thing:')).toEqual([
      { kind: 'keyword', text: 'unknown_thing' },
    ]);
  });

  it('treats parenthesised text as a reminder that is parsed recursively', () => {
    expect(parseAbility('Pay :rb_energy_2: (then :rb_exhaust:)')).toEqual([
      { kind: 'text', text: 'Pay ' },
      { kind: 'energy', value: 2 },
      { kind: 'text', text: ' ' },
      {
        kind: 'reminder',
        children: [{ kind: 'text', text: 'then ' }, { kind: 'exhaust' }],
      },
    ]);
  });

  it('keeps nested parentheses as plain text inside the reminder', () => {
    expect(parseAbility('(see rule 702)')).toEqual([
      { kind: 'reminder', children: [{ kind: 'text', text: 'see rule 702' }] },
    ]);
  });

  it('parses the S9 examples exactly', () => {
    expect(parseAbility('[Accelerate] When I attack, deal 2.')).toEqual([
      { kind: 'keyword', text: 'Accelerate' },
      { kind: 'text', text: ' When I attack, deal 2.' },
    ]);

    expect(parseAbility('Pay :rb_energy_2: (then :rb_exhaust:)')).toEqual([
      { kind: 'text', text: 'Pay ' },
      { kind: 'energy', value: 2 },
      { kind: 'text', text: ' ' },
      {
        kind: 'reminder',
        children: [{ kind: 'text', text: 'then ' }, { kind: 'exhaust' }],
      },
    ]);
  });

  it('preserves whitespace between symbols', () => {
    expect(parseAbility('  [X]   [Y]  ')).toEqual([
      { kind: 'text', text: '  ' },
      { kind: 'keyword', text: 'X' },
      { kind: 'text', text: '   ' },
      { kind: 'keyword', text: 'Y' },
      { kind: 'text', text: '  ' },
    ]);
  });

  it('handles unknown rune colours as keywords', () => {
    expect(parseAbility(':rb_rune_void:')).toEqual([{ kind: 'keyword', text: 'rune_void' }]);
  });
});
