// Traces the brand WebP sources to clean SVG (task 1.33/1.34, D20). Run by hand:
//   npm run brand:trace
// Not part of CI. See assets-src/brand/README.md.
import { mkdir, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';
import { optimize } from 'svgo';

const require = createRequire(import.meta.url);
const potrace = require('potrace');

const SOURCES = fileURLToPath(new URL('../assets-src/brand/', import.meta.url));
const OUT = fileURLToPath(new URL('../src/assets/brand/', import.meta.url));

// Trace parameters (documented in assets-src/brand/README.md).
const UPSCALE = 2; // Lanczos upscale before thresholding: sub-pixel edge placement
const ALPHA_THRESHOLD = 128; // silhouette = pixels at least this opaque
const POTRACE = { turdSize: 12, alphaMax: 0.9, optCurve: true, optTolerance: 0.2, threshold: 128 };
const MARGIN = 0.01; // viewBox margin, as a fraction of the larger side
const TAIL = 0.06; // share of pixels averaged for each gradient end colour
const INTERIOR_ALPHA = 250; // only fully opaque pixels are colour samples

const ASSETS = [
  { name: 'mark', file: 'rift-manager-mark.webp', gradient: 'plane' },
  { name: 'wordmark', file: 'rift-manager-wordmark.webp', gradient: 'vertical' },
];

const hex = (rgb) => '#' + rgb.map((c) => Math.round(c).toString(16).padStart(2, '0')).join('');

/** Black silhouette on white from the alpha channel, at UPSCALE x. */
async function silhouette(image, width, height) {
  return sharp(await image.clone().extractChannel('alpha').raw().toBuffer(), {
    raw: { width, height, channels: 1 },
  })
    .resize(width * UPSCALE, height * UPSCALE, { kernel: 'lanczos3' })
    .threshold(ALPHA_THRESHOLD)
    .negate()
    .png()
    .toBuffer();
}

function tracePath(png) {
  return new Promise((resolve, reject) => {
    potrace.trace(png, POTRACE, (error, svg) => {
      if (error) return reject(error);
      const d = /<path[^>]* d="([^"]+)"/.exec(svg)?.[1];
      return d ? resolve(d) : reject(new Error('potrace returned no path'));
    });
  });
}

/** Bounding box of the silhouette in original pixels. */
function boundingBox(rgba, width, height) {
  let [x0, y0, x1, y1] = [width, height, 0, 0];
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      if (rgba[(y * width + x) * 4 + 3] >= ALPHA_THRESHOLD) {
        x0 = Math.min(x0, x);
        y0 = Math.min(y0, y);
        x1 = Math.max(x1, x + 1);
        y1 = Math.max(y1, y + 1);
      }
    }
  }
  return { x0, y0, x1, y1 };
}

/**
 * Brand gradient re-sampled from the opaque pixels. Direction: least-squares plane fit of the
 * green channel (`plane`) or straight down (`vertical`); it points from the light end (high
 * green, yellow) to the dark end (low green, red). End colours are the mean of the first and
 * last TAIL of pixels along that direction.
 */
function sampleGradient(rgba, width, height, mode, box) {
  const samples = [];
  for (let y = box.y0; y < box.y1; y++) {
    for (let x = box.x0; x < box.x1; x++) {
      const i = (y * width + x) * 4;
      if (rgba[i + 3] >= INTERIOR_ALPHA)
        samples.push({ x, y, c: [rgba[i], rgba[i + 1], rgba[i + 2]] });
    }
  }
  const mean = (key) => samples.reduce((sum, s) => sum + key(s), 0) / samples.length;
  const [mx, my, mg] = [mean((s) => s.x), mean((s) => s.y), mean((s) => s.c[1])];
  let [sxx, sxy, syy, sxg, syg] = [0, 0, 0, 0, 0];
  for (const s of samples) {
    const [dx, dy, dg] = [s.x - mx, s.y - my, s.c[1] - mg];
    sxx += dx * dx;
    sxy += dx * dy;
    syy += dy * dy;
    sxg += dx * dg;
    syg += dy * dg;
  }
  const det = sxx * syy - sxy * sxy;
  let [gx, gy] =
    mode === 'vertical'
      ? [0, syg / syy]
      : [(sxg * syy - syg * sxy) / det, (syg * sxx - sxg * sxy) / det];
  const length = Math.hypot(gx, gy);
  const dir = [-gx / length, -gy / length]; // toward decreasing green
  const along = samples.map((s) => ({ ...s, p: (s.x - mx) * dir[0] + (s.y - my) * dir[1] }));
  along.sort((a, b) => a.p - b.p);
  const tail = Math.max(1, Math.floor(along.length * TAIL));
  const average = (list) =>
    [0, 1, 2].map((k) => list.reduce((sum, s) => sum + s.c[k], 0) / list.length);
  // Gradient line spans the silhouette extent along `dir`.
  const corners = [
    [box.x0, box.y0],
    [box.x1, box.y0],
    [box.x0, box.y1],
    [box.x1, box.y1],
  ].map(([x, y]) => (x - mx) * dir[0] + (y - my) * dir[1]);
  const [pMin, pMax] = [Math.min(...corners), Math.max(...corners)];
  const point = (p) => [mx + dir[0] * p, my + dir[1] * p];
  return {
    from: point(pMin),
    to: point(pMax),
    start: hex(average(along.slice(0, tail))),
    end: hex(average(along.slice(-tail))),
  };
}

function compose({ d, box, gradient }) {
  const margin = Math.max(box.x1 - box.x0, box.y1 - box.y0) * MARGIN;
  const view = [
    box.x0 - margin,
    box.y0 - margin,
    box.x1 - box.x0 + 2 * margin,
    box.y1 - box.y0 + 2 * margin,
  ];
  const s = UPSCALE;
  const n = (value) => +(value * s).toFixed(1);
  const viewBox = view.map(n).join(' ');
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${viewBox}">` +
    `<defs><linearGradient id="brand" gradientUnits="userSpaceOnUse" x1="${n(gradient.from[0])}" y1="${n(gradient.from[1])}" x2="${n(gradient.to[0])}" y2="${n(gradient.to[1])}">` +
    `<stop offset="0" stop-color="${gradient.start}"/><stop offset="1" stop-color="${gradient.end}"/></linearGradient></defs>` +
    `<path fill="url(#brand)" fill-rule="evenodd" d="${d}"/></svg>`;
  return optimize(svg, {
    multipass: true,
    floatPrecision: 1,
    plugins: ['preset-default'],
  }).data;
}

await mkdir(OUT, { recursive: true });
for (const { name, file, gradient: mode } of ASSETS) {
  const image = sharp(SOURCES + file).ensureAlpha();
  const { data, info } = await image.clone().raw().toBuffer({ resolveWithObject: true });
  const box = boundingBox(data, info.width, info.height);
  const d = await tracePath(await silhouette(image, info.width, info.height));
  const gradient = sampleGradient(data, info.width, info.height, mode, box);
  const svg = compose({ d, box, gradient });
  await writeFile(OUT + `${name}.svg`, svg + '\n');
  console.log(
    `${name}.svg  ${svg.length} bytes  paths: ${(d.match(/M/g) ?? []).length}  gradient ${gradient.start} -> ${gradient.end}`,
  );
}
