// One-off: derives the mobile background from assets-src/new_rift.webp (task 1.30).
// Run by hand with `node scripts/make-bg.mjs`; the outputs in src/assets/bg are committed.
import { copyFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';

const source = fileURLToPath(new URL('../assets-src/new_rift.webp', import.meta.url));
const out = (name) => fileURLToPath(new URL(`../src/assets/bg/${name}`, import.meta.url));

// Desktop: the original, byte for byte (1920 px wide, already WebP).
await copyFile(source, out('new_rift-1920.webp'));

// Phones below 860 px (R5): 1280 px wide. The layer is blurred and darkened at runtime,
// so a lower quality is invisible.
await sharp(source)
  .resize({ width: 1280 })
  .webp({ quality: 74, effort: 6 })
  .toFile(out('new_rift-1280.webp'));

// Portrait screens: the map turned 90 degrees (1079x1920 before resizing). The board is
// symmetric, so it still reads as the map, and a tall phone covers it with little zoom
// instead of blowing up a thin slice of the landscape image.
await sharp(source)
  .rotate(90)
  .resize({ height: 1600 })
  .webp({ quality: 74, effort: 6 })
  .toFile(out('new_rift-portrait.webp'));
