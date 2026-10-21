// @vitest-environment node
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';
import { describe, expect, it } from 'vitest';

const frontend = fileURLToPath(new URL('../', import.meta.url));
const file = (name: string) => readFileSync(frontend + name);

describe('committed icons (PWA-2, D21)', () => {
  it.each([
    ['public/pwa-64x64.png', 64],
    ['public/pwa-192x192.png', 192],
    ['public/pwa-512x512.png', 512],
    ['public/maskable-icon-512x512.png', 512],
    ['public/apple-touch-icon-180x180.png', 180],
  ])('%s is a %i px square PNG', async (name, size) => {
    const meta = await sharp(file(name)).metadata();
    expect([meta.format, meta.width, meta.height]).toEqual(['png', size, size]);
  });

  it('keeps the maskable mark inside the central 80 % circle (the safe zone)', async () => {
    const { data, info } = await sharp(file('public/maskable-icon-512x512.png'))
      .raw()
      .toBuffer({ resolveWithObject: true });
    const background = [data[0], data[1], data[2]];
    let farthest = 0;
    for (let y = 0; y < info.height; y++) {
      for (let x = 0; x < info.width; x++) {
        const i = (y * info.width + x) * info.channels;
        const away =
          Math.abs(data[i] - background[0]) +
          Math.abs(data[i + 1] - background[1]) +
          Math.abs(data[i + 2] - background[2]);
        if (away > 40) farthest = Math.max(farthest, Math.hypot(x - 255.5, y - 255.5));
      }
    }
    expect(farthest).toBeGreaterThan(100); // the mark is there at all
    expect(farthest).toBeLessThanOrEqual(0.4 * 512);
  });

  it('paints the maskable icon full bleed on the brand colour', async () => {
    const { data } = await sharp(file('public/maskable-icon-512x512.png'))
      .raw()
      .toBuffer({ resolveWithObject: true });
    expect([data[0], data[1], data[2]]).toEqual([0x06, 0x22, 0x2c]); // the top-left corner
  });

  it('has a 48 px favicon.ico holding a PNG, and the SVG favicon is the simplified mark', () => {
    const ico = file('public/favicon.ico');
    expect([ico.readUInt16LE(0), ico.readUInt16LE(2), ico.readUInt16LE(4)]).toEqual([0, 1, 1]);
    expect(ico[6]).toBe(48); // width of the first image
    expect(ico[7]).toBe(48);
    expect(file('public/favicon.svg').equals(file('src/assets/brand/mark-simple.svg'))).toBe(true);
  });
});
