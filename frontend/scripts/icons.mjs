// Regenerates the icons in public/ (task 6.7, D21). Run by hand, not in CI; commit the outputs.
//   npm run icons
// Uses the presets of pwa-assets.config.ts through the API of @vite-pwa/assets-generator, because its
// CLI writes next to the source image and the sources live in src/assets/brand/.
import { copyFile, mkdir, readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { generateAssets } from '@vite-pwa/assets-generator/api/generate-assets';
import { instructions } from '@vite-pwa/assets-generator/api/instructions';
import { MARK, MARK_SIMPLE, faviconPreset, preset } from '../pwa-assets.config.ts';

const root = fileURLToPath(new URL('../', import.meta.url));
const PUBLIC = root + 'public';
const log = (message, ignored) => console.log(ignored ? `skipped ${message}` : message);

async function generate(image, imagePreset) {
  const instruction = await instructions({
    imageResolver: () => readFile(root + image),
    imageName: root + image,
    originalName: image,
    preset: imagePreset,
    faviconPreset: undefined,
    htmlLinks: { xhtml: false, includeId: false },
    basePath: '/',
    resolveSvgName: (name) => name,
  });
  await generateAssets(instruction, true, PUBLIC, log);
}

await mkdir(PUBLIC, { recursive: true });
await generate(MARK, preset);
await generate(MARK_SIMPLE, faviconPreset);
// The SVG favicon is the simplified mark itself.
await copyFile(root + MARK_SIMPLE, PUBLIC + '/favicon.svg');
console.log('favicon.svg');
