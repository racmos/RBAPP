import { describe, expect, it } from 'vitest';
import { clearSignedInHint, hasSignedInHint, setSignedInHint } from './hint';

describe('was-signed-in hint (FAUTH-1, PWA-7)', () => {
  it('is absent by default', () => {
    expect(hasSignedInHint()).toBe(false);
  });

  it('is set and cleared', () => {
    setSignedInHint();
    expect(hasSignedInHint()).toBe(true);
    clearSignedInHint();
    expect(hasSignedInHint()).toBe(false);
  });

  it('stores only a flag, never an identity', () => {
    setSignedInHint();
    expect(Object.values(localStorage)).toEqual(['1']);
  });
});
