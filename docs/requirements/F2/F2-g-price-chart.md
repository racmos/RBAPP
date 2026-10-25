# F2-g: Price chart — real history in the card detail, sparkline

| Field | Value |
|---|---|
| Phase / unit | F2 / g |
| Branch | `feat/f2g-price-chart` (stacked on the previous unit's branch, `docs/requirements/BATCH-1.md` R1) |
| Depends on | F2-f merged (detail screen with the `price-chart` slot); F2-d API |
| Size forecast | ~500 authored lines (tests and docs included) |
| Risk | `Risk: none` |
| TDD | ON (strict). Runners: `venv/bin/pytest` (backend, untouched), `cd frontend && npx vitest run` (frontend) |
| Save as | `docs/requirements/F2/F2-g-price-chart.md` (commit this document verbatim in the first commit if it is not in the repo yet) |

## Objective

The card detail shows the card's real Cardmarket price history (instead of the prototype's synthetic
"14 wk" line) with dates on the axis, a grid, a tooltip that also works with the keyboard, a period
selector and a table alternative for screen readers. A small sparkline component is added for compact
places (the wide catalog preview in F2-i, later the dashboard).

## Read first

- `AGENTS.md`, `docs/knowledge/conventions.md`, `docs/frontend.md`
- `docs/requirements/F2/README.md` (F2-R9, R26; D-F2-6)
- `docs/api.md` → `GET /cards/{set}/{id}/prices`, `PricePoint` (F2-d)
- `openspec/design-handoff.md` §2.4 (Sparkline, PriceChart and their bugs L2/L3), §7.4 A13
- `frontend/src/catalog/CardDetailView.tsx` (slot `data-slot="price-chart"`), `src/catalog/queries.ts`,
  `src/components/ui/SegmentedControl.tsx`, `src/lib/format.ts`, `src/lib/storage.ts`, `src/components/card/*`

## Scope

In:
- `frontend/src/components/charts/`: `PriceChart`, `Sparkline`, `index.ts`.
- `frontend/src/lib/scale.ts` (`linearScale`, `niceTicks`).
- `getCardPrices` endpoint, `PricePoint` type, `useCardPrices`.
- `src/catalog/CardPriceHistory.tsx` placed in the detail slot.

Out (do not do, even if tempting):
- Collection value chart (F4/F6), any chart library dependency (hand-made SVG), donuts/bars (F6).

## Specs

S1. Data: `PricePoint` type and `getCardPrices(setId, cardId, range, signal?)` (`GET …/prices?range=`) in
    `src/api`; `useCardPrices(setId, cardId, range)` with key `['cards', 'prices', setId, cardId, range]`,
    `placeholderData: keepPreviousData`, `staleTime` 10 minutes.

S2. `linearScale([d0, d1], [r0, r1])` returns a function (and its inverse via `.invert`), handling `d0 === d1`
    (maps everything to the middle of the range). `niceTicks(min, max, count)` returns 2-6 round values
    covering `[min, max]` (steps 1, 2, 2.5 or 5 × 10^n). Examples: `niceTicks(0.83, 1.27, 4)` →
    `[0.8, 0.9, 1, 1.1, 1.2, 1.3]`; `niceTicks(5, 5, 4)` → `[5]`.

S3. `PriceChart` props: `points: PricePoint[]`, `series: ('market' | 'market_foil')[]`, `lang`, `height?`
    (default 200 below 860 px, 260 above), `title` (used in the table caption and summary).
  - SVG drawn at the measured container width (`ResizeObserver`, fallback width 600 when unavailable), never
    `preserveAspectRatio="none"`; strokes use `vector-effect: non-scaling-stroke`.
  - Y axis: `niceTicks` over all visible series, labels `formatMoney`; horizontal grid lines `--line-2`.
  - X axis: up to 6 date ticks; format day + short month for ranges ≤ 90 days, short month + year otherwise
    (`Intl.DateTimeFormat` with the app locale, UTC).
  - Series: `market` solid accent line with an area gradient (gradient id from `useId()`, so two charts on
    one page never share it); `market_foil` dashed `--gold` line; last point of each series marked. A legend
    names the visible series (`cards:chart.series.*`).
  - Null values break the line (no interpolation across gaps).
  - Interaction: pointer move shows a vertical crosshair and a tooltip with the date and each visible value;
    the plot is focusable (`tabIndex=0`, `role="group"`, `aria-label` = summary S4); ←/→ move the active point,
    Home/End jump to the ends, Esc hides the tooltip; the active point's text is written to an
    `aria-live="polite"` region (`cards:chart.point`).
  - 0 points → `cards:chart.empty`; 1 point → a single marker and its value, no line.

S4. Summary text (also the plot's accessible name): `cards:chart.summary` with the first and last dates, first and
    last market values, minimum and maximum. Example (en): `Market price from 22 Jul 2026 to 20 Oct 2026: €1.04 to €1.21 (low €0.98, high €1.25).`

S5. Table alternative: a button `cards:chart.showTable` / `hideTable` (`aria-expanded`) reveals a table with
    caption `cards:chart.table.caption`, columns date, market and (when shown) foil market, newest first.

S6. `CardPriceHistory` (in the detail slot): section title `cards:chart.title`, `SegmentedControl` labelled
    `cards:chart.range.label` with `30d`, `90d`, `1y`, `all` (`cards:chart.range.*`), default `90d`, last
    choice remembered per device in `localStorage` key `rb_price_range` (through `lib/storage.ts`, invalid
    value → default). Series: `market`, plus `market_foil` when the card is `foilable`. Loading → skeleton
    of the chart height (`cards:chart.loading`); error → `ErrorState` with retry; previous range stays
    visible (dimmed, `aria-busy`) while the next one loads. Placement follows F2-f S8 (column A at ≥ 1240).

S7. `Sparkline` props `values: (number | null)[]`, `label` (accessible name), `className?`. `viewBox="0 0 120 34"`,
    width 100 %, height 34 px, stroke 1.8; colour `--green-text` when the last non-null value ≥ the first,
    otherwise `--red-text`; `role="img"` with `aria-label={label}`. Fewer than 1 non-null value → renders
    nothing; exactly 1 → a flat line with a dot (no division by zero).

## API / data contract

Consumes `GET /riftbound/api/v1/cards/{set_id}/{card_id}/prices?range=` (F2-d). No backend change.

## UI

Placement: card detail (F2-f): mobile under the prices panel; 860-1239 in the right column under the
header; ≥ 1240 column A under the prices. Height S3. States S6.

Strings — `cards.json` (add under `chart`):

| Key | es | en |
|---|---|---|
| `chart.title` | Historial de precios | Price history |
| `chart.loading` | Cargando historial | Loading history |
| `chart.empty` | Sin historial de precios todavía. | No price history yet. |
| `chart.range.label` | Periodo | Period |
| `chart.range.30d` / `90d` / `1y` / `all` | 30 d / 90 d / 1 año / Todo | 30 d / 90 d / 1 year / All |
| `chart.series.market` / `market_foil` | Mercado / Mercado foil | Market / Foil market |
| `chart.summary` | Precio de mercado del {{from}} al {{to}}: de {{first}} a {{last}} (mín. {{min}}, máx. {{max}}). | Market price from {{from}} to {{to}}: {{first}} to {{last}} (low {{min}}, high {{max}}). |
| `chart.point` | {{date}}: {{values}} | {{date}}: {{values}} |
| `chart.showTable` / `chart.hideTable` | Ver como tabla / Ocultar tabla | Show as table / Hide table |
| `chart.table.caption` | Precios diarios de {{name}} | Daily prices of {{name}} |
| `chart.table.date` | Fecha | Date |

## Acceptance criteria

- [ ] AC1 `src/lib/scale.test.ts`: S2 examples, inverse, equal domain.
- [ ] AC2 `src/components/charts/PriceChart.test.tsx`: ticks rendered, two charts have different gradient ids, null gap, keyboard ←/→/Home/End/Esc update the live region, 0 and 1 point, foil series dashed, table toggle and caption, summary text in es and en (S3-S5).
- [ ] AC3 `src/components/charts/Sparkline.test.tsx`: colour rule, 0/1 values, accessible name (S7).
- [ ] AC4 `src/catalog/CardPriceHistory.test.tsx`: default 90d, range change refetches (MSW), remembered range and invalid stored value, foil series only when foilable, loading/error states (S6).
- [ ] AC5 Axe: detail page with the chart at 390 and 1280 px, table open, no violations.
- [ ] AC6 Full lanes green: `venv/bin/pytest`; `cd frontend && npm run lint && npm run typecheck && npx vitest run && npm run build && npm run check:dist`
- [ ] AC7 `docs/knowledge/state.md` updated (what changed, PR number placeholder, new follow-ups)
- [ ] AC8 `docs/frontend.md` "Charts" paragraph (components, no chart library, a11y pattern).

## Delivery

- Conventional Commits; commit messages end with the attribution lines the session supplies.
- Push and PR only when the user says so. PR title: `feat(catalog): price history chart and sparkline (F2 unit g)`.
  PR body: summary, specs → tests map (S# → test file::name), screenshots (390 px, 1440 px, keyboard
  tooltip, table open), manual checks, rollback (revert).
- Never merge. The user merges.

## After merge (user asks gentle-shell, or does it)

- Deploy to dev with `docs/knowledge/ops-runbook.md` (frontend build only).
- Live checks: a card with several loaded days shows a line with real dates; switching to "Todo" shows the
  whole series.
- Manual checks for the user: compare two or three points with Cardmarket's price history; use the chart with
  the keyboard (Tab to it, arrows) on desktop and with a finger on the phone.

## Open questions

none — the CONFIRM items of the draft (D-F2-6) are answered in
`docs/knowledge/decisions-2026-10-25.md`; batch rules in `docs/requirements/BATCH-1.md` (G1-G12) apply.
