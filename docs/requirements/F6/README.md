# F6: Stats — phase spec
Status: planned · Depends on: F3 (collection read model, purchase price), F4 (value snapshots, `ValueChart`, `KpiCard`), F5 (`Donut`, `MiniCurve`) · Order (`docs/knowledge/roadmap.md`): medium priority, before production · Source: roadmap §5 (F6), design-handoff §2.4 (Donut, Bars), §3.10, §3.13, §6-6, §7.6 L1/L2/L6, §9 (F6), `docs/knowledge/product.md` "Scope by phase"

## Goal

Each user understands their collection at a glance: how it is distributed by domain, rarity, type and set
(by number of copies or by value), how complete each set is, which cards are worth the most, which ones
gained or lost the most against the purchase price, and how the value evolved over time. Phones get a
single readable column; desktop shows a 2×2 grid of charts with the value chart full width; wide screens
show four distribution columns.

## Current state

| Area | What exists today |
|---|---|
| Data | `rbcollection` + F3 columns (`purchase_price`, `sell_qty`); F2 card normalization (`domains`, `type`, `rarity`) and `price_summaries`; F4 `rbvaluesnaps` and `GET /collection/value-history`. |
| UI | No stats screen (Jinja has none). Nav entry `stats` is `planned` (not rendered). Prototype `Stats` (`sections-b.jsx:77-169`) with synthetic value series (bug L1), Donut without the single-segment case (L2), "value by set" promised but absent. |
| Charts | F2 `PriceChart`/`Sparkline`, F4 `ValueChart`/`KpiCard`, F5 `Donut`/`MiniCurve`. |

## Scope

In: stats API (distributions by quantity and value, completion by set and set × rarity, top value, top/bottom
P/L, foil ratio, value on sale, value history reuse); `BarList`, `CompletionMatrix`, legend/table
alternatives; stats page with toggle quantity/value; nav entry `stats` → `spa`; offline read.

Out: deck statistics and event performance (F8), price analytics of cards not owned (F4 movers), export of
stats.

## Decisions already taken

- Distribution by domain, rarity, type, set; top cards by value (product.md F6).
- Value history comes only from daily snapshots (F4); no synthetic series, no comparison with fake data (L1).
- Charts need a text alternative and never rely on colour alone (design-handoff §7.4 A13).
- Prices: PRC-1 market unit price × quantity, EUR.
- New tables, if any, reference `rbusers.id`; migrations take the next free revision numbers (none expected).
- Products (owner, 2026-10-22): sealed products (F14) have their own "products" total, never added to the
  cards' collection value; every figure here covers cards only.
- Tests (owner, 2026-10-22, unit M-a): each F6 unit writes its own tests (ES/EN parity for the new strings).

## Requirements

### API
- **F6-R1** `GET /stats/collection` (U) with `scope=all|set` and `set_id` (when scope=set) returns:
  `{totals: {qty, unique, value, cost, pl, foil_qty, foil_pct, selling_value}, by_domain[{key, qty, value}]`
  (a multi-domain card counts in each of its domains; `qty` sums copies), `by_rarity[]`, `by_type[]`,
  `by_set[{set_id, name, owned_unique, total, qty, value, cost}]`, `completion_by_set_rarity[{set_id,
  rarity, owned_unique, total}]`, `top_value[{card: CardMini, qty, value}]` (10), `top_pl[]` and `bottom_pl[]`
  (10 each, lines with purchase price only), `price_as_of}`. (F6-a)
- **F6-R2** Completion counts printings of the set by `card_id` (owned = at least one copy, any foil);
  tokens excluded from totals (D-F6-2). (F6-a)
- **F6-R3** Value history reuses `GET /collection/value-history` (F4); no new endpoint. (F6-c)
- **F6-R4** ≤ 8 SQL statements and p95 < 300 ms for 5 000 lines (reuse F3's grouped query and F2's batch prices). (F6-a)

### UI
- **F6-R5** `/stats` (nav `stats` → `spa`, placements top + hub + "Más"): header with KPIs (value, P/L, unique, foil %), a `SegmentedControl` "Cantidad / Valor" that switches every distribution, scope selector (all sets / one set). (F6-c)
- **F6-R6** Mobile < 860: one column — value chart (12 m), Donut by domain, Donut by rarity, bars by type, completion by set (progress bars), top value, top/bottom P/L (tabs). (F6-c)
- **F6-R7** Desktop ≥ 1240: value chart full width; 2×2 grid (domain, rarity, type, set); completion matrix set × rarity; top lists in 2 columns. Wide ≥ 1600: 4 distribution columns in one row and the matrix next to the top lists. (F6-c)
- **F6-R8** Every chart has a legend with values and a "Ver como tabla" alternative; Donut handles the 100 % single segment; segment colours from the domain/rarity tokens with labels. (F6-b)
- **F6-R9** Clicking a segment/bar opens the collection filtered by that value (`/collection?domain=Fury`). (F6-c)

### Offline / i18n / a11y
- **F6-R10** `GET /stats/collection` in a `rb-api-stats` read cache (NetworkFirst) purged with the user caches. (F6-c)
- **F6-R11** Namespace `stats`; enum labels from `enums`; numbers and money by app locale. (F6-b, F6-c)

## Data model changes

None.

## API

| Method | Path | Auth | Purpose | Unit |
|---|---|---|---|---|
| GET | `/stats/collection` | U | Distributions, completion, tops | F6-a |

New error codes: none (invalid `scope`/`set_id` → `validation_error`).

## UI

| Route | Mobile < 860 | Desktop ≥ 1240 | Wide ≥ 1600 |
|---|---|---|---|
| `/stats` | single column (R6) | value full width + 2×2 + matrix + tops in 2 cols | 4 distribution columns + matrix beside tops |

New components: `BarList`, `CompletionMatrix` (heatmap table with numbers), `ChartLegend`, `ChartTable`
(shared table alternative). Reused: `Donut`, `MiniCurve` (F5), `ValueChart`, `KpiCard` (F4). States: loading,
empty ("Añade cartas a tu colección para ver estadísticas"), no snapshots yet ("Recopilando datos"), error, offline.

## Units

| ID | Title | Depends on | Size | Risk | Summary |
|---|---|---|---|---|---|
| F6-a | Stats API | F3-b, F4-c | ~450 | item 3 | `GET /stats/collection`, statement budget, docs |
| F6-b | Stats chart components | F5-i | ~450 | none | `BarList`, `CompletionMatrix`, `ChartLegend`, `ChartTable`, Donut single-segment fix if missing |
| F6-c | Stats page + nav flip + offline | F6-a, F6-b | ~600 | none | `/stats` mobile/desktop/wide, quantity/value toggle, links to filtered collection, read cache |

## Open decisions

| ID | Question | Options | Recommendation | Blocks |
|---|---|---|---|---|
| D-F6-1 | "Value" of a line without price | 0 / excluded / estimated | Excluded from value totals and counted in `unpriced` (shown as a footnote) | F6-a |
| D-F6-2 | Tokens and Basic Runes in completion | include / exclude | Exclude tokens; include Basic Runes | F6-a |
| D-F6-3 | Promo sets in completion | separate rows / merged into the base set | Separate rows (set ids as in the catalog), sorted by release | F6-a |
| D-F6-4 | P/L reference | purchase price vs current market | Current market (PRC-1) − purchase price, per unit × qty; lines without purchase price excluded from P/L | F6-a |
| D-F6-5 | Can F6 swap with F7? | — | Yes (roadmap); F6 only needs F3/F4/F5 components | — |

## Risks and notes

- If F6 runs before F5, `Donut`/`MiniCurve` move into F6-b (then F5 reuses them); the component list stays the same.
- Multi-domain cards make domain totals exceed the collection total; the UI says so in the chart note.
- Large collections: reuse F3's grouped query; never load per-card prices one by one.
