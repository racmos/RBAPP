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

describe('readCardCode of a plated card (PLAT-<origin set>-<number>, CM-k)', () => {
  const WITH_PLAT = ['OGN', 'OGNX', 'SFD', 'PLAT', 'SET1'];

  it.each([
    ['PLAT-SFD-189', 'sfd189'],
    ['PLAT SFD 189', 'sfd189'],
    ['PLAT-sfd189', 'sfd189'],
    ['plat sfd189', 'sfd189'],
    ['PLAT - SFD - 189', 'sfd189'],
    ['PLAT-SFD189', 'sfd189'],
    ['PLAT-OGN-066A', 'ogn066a'],
    ['PLAT-ognx-7', 'ognx7'],
    ['  PLAT-SFD-189  ', 'sfd189'],
  ])('reads %j as set PLAT, number %s', (value, number) => {
    expect(readCardCode(value, WITH_PLAT)).toEqual({ code: value.trim(), setId: 'PLAT', number });
  });

  it('keeps the PLAT id as the set list writes it', () => {
    expect(readCardCode('PLAT-SFD-189', ['plat', 'sfd'])).toEqual({
      code: 'PLAT-SFD-189',
      setId: 'plat',
      number: 'sfd189',
    });
  });

  it.each([
    ['an origin set that is no set', 'PLAT-ZZZ-189'],
    ['a joined origin that is no set', 'PLAT-zzz189'],
    ['an origin that is PLAT itself', 'PLAT-PLAT-189'],
    ['an origin without a number', 'PLAT-SFD'],
    ['a number over 10 characters once joined', 'PLAT-OGNX-1234567'],
    ['three separators', 'PLAT-SFD-1-2'],
  ])('does not guess %s (%j)', (_case, value) => {
    expect(readCardCode(value, WITH_PLAT)).toBeNull();
  });

  it.each(['sfd189', 'SFD189', 'ognx7', '189'])(
    'with PLAT chosen, the plated number %j stays as typed (not read as a joined code)',
    (value) => {
      expect(readCardCode(value, WITH_PLAT, 'PLAT')).toBeNull();
      expect(readCardCode(value, WITH_PLAT, 'plat')).toBeNull();
    },
  );

  it('with another set chosen, sfd189 is still read as set SFD, number 189', () => {
    expect(readCardCode('sfd189', WITH_PLAT, 'OGN')).toEqual({
      code: 'sfd189',
      setId: 'SFD',
      number: '189',
    });
    expect(readCardCode('PLAT-SFD-189', WITH_PLAT, 'PLAT')?.number).toBe('sfd189');
    expect(readCardCode('OGN-5', WITH_PLAT, 'PLAT')?.setId).toBe('OGN');
  });

  it('without the PLAT set an origin code is not read', () => {
    expect(readCardCode('PLAT-SFD-189', ['SFD'])).toBeNull();
  });

  it('keeps the reading of every other code', () => {
    expect(readCardCode('PLAT-189', WITH_PLAT)).toEqual({
      code: 'PLAT-189',
      setId: 'PLAT',
      number: '189',
    });
    expect(readCardCode('SFD-189', WITH_PLAT)).toEqual({
      code: 'SFD-189',
      setId: 'SFD',
      number: '189',
    });
    expect(readCardCode('OGN 066a', WITH_PLAT)?.number).toBe('066a');
    // a set id ending with digits keeps the old reading (letters prefix only)
    expect(readCardCode('SET1-5', WITH_PLAT)).toBeNull();
  });
});
