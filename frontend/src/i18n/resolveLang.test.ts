import { describe, expect, it } from 'vitest';
import { clearStoredLang, initialLang, resolveLang, storeLang, storedLang } from './resolveLang';

describe('resolveLang (I18N-2)', () => {
  it('prefers the account language over the browser', () => {
    expect(resolveLang({ accountLang: 'en', storedLang: null, browserLanguages: ['es-ES'] })).toBe(
      'en',
    );
  });

  it('prefers the account language over rb_lang', () => {
    expect(resolveLang({ accountLang: 'es', storedLang: 'en', browserLanguages: ['en-US'] })).toBe(
      'es',
    );
  });

  it('uses rb_lang when there is no account language (anonymous, or before the session)', () => {
    expect(resolveLang({ accountLang: null, storedLang: 'en', browserLanguages: ['es-ES'] })).toBe(
      'en',
    );
    expect(
      resolveLang({ accountLang: undefined, storedLang: 'es', browserLanguages: ['en-US'] }),
    ).toBe('es');
  });

  it('takes the first supported browser language by primary subtag', () => {
    expect(
      resolveLang({ accountLang: null, storedLang: null, browserLanguages: ['fr-FR', 'en-US'] }),
    ).toBe('en');
    expect(
      resolveLang({ accountLang: null, storedLang: null, browserLanguages: ['EN-gb', 'es'] }),
    ).toBe('en');
  });

  it('falls back to es', () => {
    expect(resolveLang({ accountLang: null, storedLang: null, browserLanguages: ['fr-FR'] })).toBe(
      'es',
    );
    expect(resolveLang({ accountLang: null, storedLang: null, browserLanguages: [] })).toBe('es');
  });

  it('ignores unsupported stored and account values', () => {
    expect(resolveLang({ accountLang: 'de', storedLang: 'fr', browserLanguages: ['en-US'] })).toBe(
      'en',
    );
    expect(resolveLang({ accountLang: '', storedLang: '<script>', browserLanguages: [] })).toBe(
      'es',
    );
  });
});

describe('rb_lang storage and initialLang', () => {
  it('round-trips a supported language and ignores anything else', () => {
    storeLang('en');
    expect(localStorage.getItem('rb_lang')).toBe('en');
    expect(storedLang()).toBe('en');
    localStorage.setItem('rb_lang', 'klingon');
    expect(storedLang()).toBeNull();
  });

  it('reads rb_lang and navigator.languages without a session', () => {
    localStorage.setItem('rb_lang', 'en');
    expect(initialLang()).toBe('en');
    localStorage.clear();
    expect(initialLang(['fr', 'en-US'])).toBe('en');
    expect(initialLang(['fr'])).toBe('es');
  });
});

describe('clearStoredLang (Auto language, PREF-8)', () => {
  it('forgets the device choice so the browser language applies again', () => {
    storeLang('en');
    expect(storedLang()).toBe('en');
    clearStoredLang();
    expect(storedLang()).toBeNull();
    expect(initialLang(['es-ES'])).toBe('es');
  });
});
