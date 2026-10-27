import { describe, expect, it } from 'vitest';
import { shadeHex } from './color';

describe('shadeHex', () => {
  it('returns the same hex when amount is 0', () => {
    expect(shadeHex('#e7504a', 0)).toBe('#e7504a');
  });

  it('clamps white when lightening black by 100', () => {
    expect(shadeHex('#000000', 100)).toBe('#ffffff');
  });

  it('clamps black when darkening white by 100', () => {
    expect(shadeHex('#ffffff', -100)).toBe('#000000');
  });

  it('rounds each channel and returns lower-case hex', () => {
    expect(shadeHex('#808080', 10)).toBe('#9a9a9a');
  });

  it('throws for shorthand hex', () => {
    expect(() => shadeHex('#000', 0)).toThrow('Expected #rrggbb');
  });

  it('throws for rgb strings', () => {
    expect(() => shadeHex('rgb(0,0,0)', 0)).toThrow('Expected #rrggbb');
  });

  it('throws for missing hash', () => {
    expect(() => shadeHex('000000', 0)).toThrow('Expected #rrggbb');
  });
});
