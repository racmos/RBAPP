# Asset sources

Sources for files the build derives; nothing in this folder is shipped.

| File            | Used for                                                                                                                   |
| --------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `new_rift.webp` | The Summoner's Rift map (1920x1079) from the design handoff. Riot Games artwork, used for this non-commercial fan project. |
| `brand/`        | The logo sources and how they are traced, see `brand/README.md`.                                                           |

## Background images

`src/assets/bg/new_rift-1920.webp` is `new_rift.webp` copied unchanged; `new_rift-1280.webp`
(shown below 860 px, R5) is derived from it. Regenerate both, and commit the outputs, with:

```bash
cd frontend
node scripts/make-bg.mjs
```

The map is blurred and darkened at runtime by the CSS filter (`src/lib/background.ts`), so these
files are plain resized copies.
