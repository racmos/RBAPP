import { describe, expect, it } from 'vitest';
import {
  MAX_BATCH_FILES,
  MAX_IMAGE_BYTES,
  lookupKey,
  matchFiles,
  type FileLike,
  type ImageTarget,
} from './matchFiles';

const file = (name: string, size = 1000, type = 'image/png'): FileLike => ({ name, size, type });

const ogn66: ImageTarget = { kind: 'card', key: 'OGN-66', name: 'Jinx' };
const plat: ImageTarget = { kind: 'card', key: 'PLAT-sfd189', name: 'Plated' };
const box: ImageTarget = { kind: 'product', key: '123', name: 'Booster Box' };
const CATALOG: Record<string, ImageTarget> = {
  'OGN-66': ogn66,
  'PLAT-sfd189': plat,
  '123': box,
};
const resolve = (key: string) => CATALOG[key] ?? null;

describe('lookupKey (F13-h S6: the file name stem, case-insensitive, - and _ alike)', () => {
  it.each([
    ['OGN-66.jpg', 'OGN-66'],
    ['ogn_66.png', 'OGN-66'],
    ['Ogn_66.WEBP', 'OGN-66'],
    ['ognx_66.png', 'OGNX-66'],
    ['plat_sfd189.png', 'PLAT-sfd189'],
    ['PLAT-SFD189.jpeg', 'PLAT-sfd189'],
  ])('card %j -> %j', (name, key) => {
    expect(lookupKey(name, 'cards')).toBe(key);
  });

  it.each(['66.png', 'ogn.png', 'ogn_66_extra.png', 'ogn 66.png', 'ogn_6.6.png', '.png'])(
    'card %j has no key',
    (name) => {
      expect(lookupKey(name, 'cards')).toBeNull();
    },
  );

  it('a product is its id', () => {
    expect(lookupKey('123.png', 'products')).toBe('123');
    expect(lookupKey('0123.jpg', 'products')).toBe('123');
    expect(lookupKey('box-123.png', 'products')).toBeNull();
    expect(lookupKey('0.png', 'products')).toBeNull();
  });
});

describe('matchFiles (F13-h S6, AC5)', () => {
  it('matches ogn_66.png and OGN-66.jpg to OGN-66, plat_sfd189.png and a product', () => {
    expect(
      matchFiles([file('ogn_66.png'), file('plat_sfd189.png')], 'cards', resolve).map((row) => [
        row.file.name,
        row.target?.key ?? null,
        row.status,
      ]),
    ).toEqual([
      ['ogn_66.png', 'OGN-66', 'ready'],
      ['plat_sfd189.png', 'PLAT-sfd189', 'ready'],
    ]);
    expect(matchFiles([file('OGN-66.jpg', 10, 'image/jpeg')], 'cards', resolve)[0]).toMatchObject({
      target: ogn66,
      status: 'ready',
    });
    expect(matchFiles([file('123.png')], 'products', resolve)[0]).toMatchObject({
      target: box,
      status: 'ready',
    });
  });

  it('two files for one card are both several matches', () => {
    const rows = matchFiles(
      [file('ogn_66.png'), file('ogn-66.jpg', 10, 'image/jpeg')],
      'cards',
      resolve,
    );
    expect(rows.map((row) => row.status)).toEqual(['several', 'several']);
  });

  it('no match, too large and not an image', () => {
    const rows = matchFiles(
      [
        file('ogn_999.png'),
        file('ogn_66.png', MAX_IMAGE_BYTES + 1),
        file('notes.txt', 10, 'text/plain'),
        file('anim.gif', 10, 'image/gif'),
        file('ogn_66.png', MAX_IMAGE_BYTES),
      ],
      'cards',
      resolve,
    );
    expect(rows.map((row) => row.status)).toEqual([
      'no_match',
      'too_large',
      'not_image',
      'not_image',
      'ready',
    ]);
  });

  it('a file without a type is judged by its extension', () => {
    expect(matchFiles([file('ogn_66.webp', 10, '')], 'cards', resolve)[0].status).toBe('ready');
    expect(matchFiles([file('ogn_66.bmp', 10, '')], 'cards', resolve)[0].status).toBe('not_image');
  });

  it('a target chosen by hand wins, and a duplicate by hand is several matches', () => {
    const files = [file('scan-001.png'), file('ogn_66.png')];
    expect(matchFiles(files, 'cards', resolve, { 0: plat }).map((row) => row.status)).toEqual([
      'ready',
      'ready',
    ]);
    const twice = matchFiles(files, 'cards', resolve, { 0: ogn66 });
    expect(twice.map((row) => [row.status, row.manual])).toEqual([
      ['several', true],
      ['several', false],
    ]);
  });

  it('a batch holds at most 50 files', () => {
    expect(MAX_BATCH_FILES).toBe(50);
  });
});
