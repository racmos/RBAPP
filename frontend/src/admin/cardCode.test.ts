import { describe, expect, it } from 'vitest';
import { isCardNumber, readCardCode } from './cardCode';

const SETS = ['OGN', 'OGNX', 'OGS'];

describe('isCardNumber (the card_id rule of POST /admin/cards, CM-j)', () => {
  it.each(['197', '197a', 'r01', '066A', '1', 'abcdefghij', ' 197 '])('accepts %j', (value) => {
    expect(isCardNumber(value)).toBe(true);
  });

  it.each(['', '   ', 'OGN-197', 'OGNX 197', '06-6', '197_a', 'abcdefghijk', '19.7', 'ñ1'])(
    'refuses %j',
    (value) => {
      expect(isCardNumber(value)).toBe(false);
    },
  );
});

describe('readCardCode (a full card code typed in the number, CM-j)', () => {
  it.each([
    ['OGN-197', 'OGN', '197'],
    ['OGNX-197', 'OGNX', '197'],
    ['ognx-197', 'OGNX', '197'],
    ['OGNX 197', 'OGNX', '197'],
    ['OGN - 066A', 'OGN', '066a'],
    ['OGNX197', 'OGNX', '197'],
    ['ogn066a', 'OGN', '066a'],
    ['  OGS-010  ', 'OGS', '010'],
  ])('reads %j as set %s, number %s', (value, setId, number) => {
    expect(readCardCode(value, SETS)).toEqual({ code: value.trim(), setId, number });
  });

  it('keeps the set id as the set list writes it', () => {
    expect(readCardCode('OGN-1', ['ogn'])).toEqual({ code: 'OGN-1', setId: 'ogn', number: '1' });
  });

  it.each([
    ['a prefix that is no set', 'ZZZ-197'],
    ['a joined prefix that is no set', 'ZZZ197'],
    ['a plain number', '197'],
    ['a number with letters', 'r01'],
    ['letters only', 'OGN'],
    ['a code without a number', 'OGN-'],
    ['a number over 10 characters', 'OGN-12345678901'],
    ['two separators', 'OGN-1-2'],
    ['an empty value', ''],
  ])('does not guess %s (%j)', (_case, value) => {
    expect(readCardCode(value, SETS)).toBeNull();
  });

  it('reads nothing without sets', () => {
    expect(readCardCode('OGN-197', [])).toBeNull();
  });
});
