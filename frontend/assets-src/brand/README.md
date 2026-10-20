# Brand sources

| File                         | What it is                                                           |
| ---------------------------- | -------------------------------------------------------------------- |
| `rift-manager-mark.webp`     | The swirl mark, 1251x1293, transparent background.                   |
| `rift-manager-wordmark.webp` | Mark and the words "RIFT MANAGER", 2000x746, transparent background. |

Both were supplied by the project owner (2026-10-19) and are copied unchanged. They are
sources only: **never shipped**. The build uses the traced SVGs in `src/assets/brand/`.

## Regenerate

```bash
cd frontend
npm run brand:trace
```

`scripts/brand-trace.mjs` (not run in CI) does, per asset:

1. read the alpha channel of the WebP; the silhouette is `alpha >= 128` after a 2x Lanczos
   upscale, so edges are placed with sub-pixel precision;
2. trace the silhouette with `potrace` (parameters are the constants at the top of the script);
3. re-sample the brand gradient from the opaque pixels of the original: a least-squares plane
   fit of the green channel gives the direction, the average colour of the first and last 6 %
   of pixels along it gives the end colours;
4. write a single `<path>` filled with that `linearGradient`, crop the `viewBox` to the
   silhouette bounding box plus a 1 % margin, and clean the result with `svgo`.

Part 3 (unit f) builds `mark-simple.svg`, the favicon source, from the mark: the silhouette is
grown by 1 % of the larger side on every side (blur plus a low threshold, a round dilation of about
2 % across) and traced with a higher `turdSize`, so the thin swirl tips and slits do not turn to
noise at 16 to 48 px. It keeps the same gradient. To rebuild only that file run
`npm run brand:trace -- mark-simple` (the names after `--` filter the outputs).

Outputs: `src/assets/brand/mark.svg`, `src/assets/brand/wordmark.svg` and
`src/assets/brand/mark-simple.svg`. A human reviews them
(path count, swirl tips, gradient direction, no white fringe on `#06222c`) before they are
committed; the review renders are described in the unit-a pull request.
