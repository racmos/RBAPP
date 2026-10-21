// Icon presets for `npm run icons` (D21, PWA-2). The outputs in public/ are committed: CI never
// generates them, check-dist only verifies them. Sources: the brand mark for the PWA icons and the
// simplified mark (a legible silhouette at 16-48 px) for the favicon.
import { defineConfig, type Preset } from '@vite-pwa/assets-generator/config';

const BRAND = '#06222c';
const onBrand = { fit: 'contain', background: BRAND } as const;

export const MARK = 'src/assets/brand/mark.svg';
export const MARK_SIMPLE = 'src/assets/brand/mark-simple.svg';

/** From mark.svg: pwa-{64,192,512}x*.png, maskable-icon-512x512.png, apple-touch-icon-180x180.png. */
export const preset: Preset = {
  // Full colour: the generator's default `quality: 60` quantises to a 256-colour palette, and the
  // mark is a gradient that would band.
  png: { compressionLevel: 9 },
  // Purpose "any": the mark on the brand colour with 10 % padding on each side.
  transparent: { sizes: [64, 192, 512], padding: 0.1, resizeOptions: onBrand },
  // Purpose "maskable": full bleed, and 30 % padding keeps the mark inside the 80 % safe circle
  // (a mask may cut away everything outside a circle of 40 % of the side around the centre).
  maskable: { sizes: [512], padding: 0.3, resizeOptions: onBrand },
  // iOS draws no mask but rounds the corners: 20 % padding on the brand colour.
  apple: { sizes: [180], padding: 0.2, resizeOptions: onBrand },
};

/** From mark-simple.svg: favicon.ico at 48 px, transparent, almost no padding (every pixel counts). */
export const faviconPreset: Preset = {
  transparent: {
    sizes: [],
    favicons: [[48, 'favicon.ico']],
    padding: 0.04,
    resizeOptions: { fit: 'contain', background: { r: 0, g: 0, b: 0, alpha: 0 } },
  },
  maskable: { sizes: [] },
  apple: { sizes: [] },
};

// `npm run icons` runs scripts/icons.mjs, which uses the two presets above and writes to public/.
export default defineConfig({ preset, images: [MARK] });
