import { describe, expect, it } from 'vitest';
import { HOME, safeNext } from './safeNext';

describe('safeNext (FAUTH-9)', () => {
  it('keeps a path under the SPA as a router navigation with the basename stripped', () => {
    expect(safeNext('/riftbound/app/collection')).toEqual({ kind: 'router', to: '/collection' });
  });

  it('keeps a legacy path as a full document navigation', () => {
    expect(safeNext('/riftbound/collection')).toEqual({
      kind: 'document',
      href: '/riftbound/collection',
    });
  });

  it('keeps the query string and the hash', () => {
    expect(safeNext('/riftbound/app/cards?set=OGN&page=2#top')).toEqual({
      kind: 'router',
      to: '/cards?set=OGN&page=2#top',
    });
    expect(safeNext('/riftbound/decks?x=1')).toEqual({
      kind: 'document',
      href: '/riftbound/decks?x=1',
    });
  });

  it('treats the SPA root, with or without the slash, as home', () => {
    expect(safeNext('/riftbound/app/')).toEqual({ kind: 'router', to: '/' });
    expect(safeNext('/riftbound/app')).toEqual({ kind: 'router', to: '/' });
    expect(safeNext('/riftbound/app?x=1')).toEqual({ kind: 'router', to: '/?x=1' });
  });

  it('accepts a percent-encoded query value that is harmless', () => {
    expect(safeNext('/riftbound/app/cards?q=a%26b')).toEqual({
      kind: 'router',
      to: '/cards?q=a%26b',
    });
  });

  it.each([
    ['an absolute URL', 'https://evil.example'],
    ['a protocol-relative URL', '//evil.example'],
    ['a backslash', '/\\evil'],
    ['a javascript URL', 'javascript:alert(1)'],
    ['a parent segment', '/riftbound/../etc'],
    ['a parent segment inside the SPA', '/riftbound/app/../../etc/passwd'],
    ['an encoded protocol-relative URL', '%2f%2fevil.example'],
    ['a double-encoded protocol-relative URL', '%252f%252fevil.example'],
    ['an encoded backslash', '/riftbound/app/%5cevil'],
    ['a double-encoded backslash', '/riftbound/app/%255cevil'],
    ['an encoded parent segment', '/riftbound/app/%2e%2e/x'],
    ['a double-encoded parent segment', '/riftbound/app/%252e%252e/x'],
    ['a path outside the product', '/other'],
    ['a look-alike prefix', '/riftboundx/app'],
    ['an encoded control character', '/riftbound/app/x%0d%0aSet-Cookie:a=b'],
    ['a raw control character', '/riftbound/app/x\ny'],
    ['a tab inside the prefix', '/riftbound/\tapp/x'],
    ['malformed percent-encoding', '/riftbound/app/%E0%A4%A'],
    ['an empty string', ''],
    ['null', null],
    ['undefined', undefined],
  ])('returns home for %s', (_label, raw) => {
    expect(safeNext(raw)).toEqual(HOME);
  });

  it('home is the router root', () => {
    expect(HOME).toEqual({ kind: 'router', to: '/' });
  });
});
