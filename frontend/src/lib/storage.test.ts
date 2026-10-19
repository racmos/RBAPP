import { afterEach, describe, expect, it, vi } from 'vitest';
import { readStorage, removeStorage, writeStorage } from './storage';

afterEach(() => vi.restoreAllMocks());

describe('safe storage', () => {
  it('round-trips a value through localStorage', () => {
    writeStorage('rb_test', 'hello');
    expect(localStorage.getItem('rb_test')).toBe('hello');
    expect(readStorage('rb_test')).toBe('hello');
  });

  it('reads null for a missing key and after removal', () => {
    expect(readStorage('rb_missing')).toBeNull();
    writeStorage('rb_test', 'x');
    removeStorage('rb_test');
    expect(readStorage('rb_test')).toBeNull();
  });

  it('can use sessionStorage instead', () => {
    writeStorage('rb_test', 'tab', 'session');
    expect(sessionStorage.getItem('rb_test')).toBe('tab');
    expect(localStorage.getItem('rb_test')).toBeNull();
    expect(readStorage('rb_test', 'session')).toBe('tab');
  });

  it('never throws when the storage is blocked (private mode, quota)', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new DOMException('blocked', 'SecurityError');
    });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('full', 'QuotaExceededError');
    });
    vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => {
      throw new DOMException('blocked', 'SecurityError');
    });
    expect(readStorage('k')).toBeNull();
    expect(() => writeStorage('k', 'v')).not.toThrow();
    expect(() => removeStorage('k')).not.toThrow();
  });
});
