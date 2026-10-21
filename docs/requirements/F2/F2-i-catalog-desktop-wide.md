# F2-i: Catalog desktop and wide — facet sidebar, table view, preview panel

| Field | Value |
|---|---|
| Phase / unit | F2 / i |
| Branch | `feat/f2i-catalog-desktop-wide` (from up-to-date `main`) |
| Depends on | F2-g (Sparkline, `useCardPrices`) and F2-h (catalog page) merged |
| Size forecast | ~550 authored lines (tests and docs included) |
| Risk | `Risk: none` |
| TDD | ON (strict). Runners: `venv/bin/pytest` (backend, untouched), `cd frontend && npx vitest run` (frontend) |
| Save as | `docs/requirements/F2/F2-i-catalog-desktop-wide.md` (commit this document verbatim in the first commit if it is not in the repo yet) |

## Objective

On a desktop screen the catalog uses the width to show more data instead of stretching: the filters become a
permanent sidebar with counts, a dense sortable table shows energy, power, might, tags, foil price, 7- and
30-day changes, owned copies and bans, the page size can grow to 192, and on wide screens (≥ 1600 px) a
preview panel shows the selected card next to the results.

## Read first

- `AGENTS.md`, `docs/knowledge/conventions.md`, `docs/frontend.md` ("Catalog")
- `docs/requirements/F2/README.md` (F2-R18, R19, R26; D-F2-13)
- `openspec/design-handoff.md` §3.0 (desktop principles), §3.4 "Desktop: más datos", §2.6 (DataTable), §3.13, §7.5 R6
- `frontend/src/catalog/*` (F2-h: `CatalogPage`, filter sheet content, params, queries), `src/components/charts/Sparkline.tsx`,
  `src/catalog/queries.ts::useCardPrices` (F2-g), `src/shell/AppShell.module.css` (`--maxw`, `--maxw-wide`),
  `src/lib/breakpoints.ts`, `src/lib/storage.ts`, `src/test/viewport.ts`

## Scope

In:
- Shared `CatalogFilters` content rendered in the sheet (< 1240) or in a sticky sidebar (≥ 1240).
- Desktop toolbar (page size, view with table).
- Table view (≥ 860) with sortable headers.
- Wide (≥ 1600) three-column layout with `CatalogPreview`.

Out (do not do, even if tempting):
- Column chooser, virtual scrolling, keyboard grid navigation, bulk actions (later phases if needed).
- Any backend change.

## Specs

S1. `CatalogFilters` holds the filter groups of F2-h S8. Below 1240 px it renders inside the sheet as today;
    at ≥ 1240 (`up('xl')`) it renders in a sidebar and the toolbar's "Filtros" button is not rendered. In the
    sidebar each group header is a button with `aria-expanded` that collapses the group; the open/closed
    state is remembered per device in `localStorage` key `rb_cards_facets` (JSON array of open group ids;
    invalid → all open). The sidebar has no footer buttons; "Limpiar filtros" sits at its top when filters
    are active.

S2. Layout ≥ 1240 (main content capped at `--maxw`, `--maxw-wide` from 1600 as the shell already does): grid
    `280px minmax(0, 1fr)`; the sidebar is `position: sticky` below the topbar (`top: calc(64px + var(--gap))`)
    with its own scroll (`max-height: calc(100dvh - 64px - 2 * var(--gap))`). Results grid uses the same
    `minmax(150px, 1fr)` tiles (6-8 columns).

S3. Toolbar ≥ 1240: count (`cards:catalog.count`), sort `Select` + direction, page size `Select`
    (`cards:catalog.perPage`: 48, 96, 192 → `per_page` in the URL, page reset to 1) and view
    `SegmentedControl` grid / list / table.

S4. Table view (offered from 860 px; below 860 a stored `table` falls back to list; `rb_cards_view` accepts
    `table`):
  - `<table>` with a visually hidden `caption` `cards:catalog.table.caption`; `th scope="col"`.
  - Columns 860-1239: image (thumb 40 px, decorative), set, number, name (link to the detail, with
    `DomainPips`), type, rarity (dot + text), energy, power, might, price, 7 d, owned, bans (compact badge).
    ≥ 1240 adds: tags (first 3, `+n`), foil price (`price.market_foil` or `—`), 30 d.
  - Sortable headers (number, name, rarity, energy, power, might, price, 7 d, 30 d) contain a button; the
    active column's `th` has `aria-sort="ascending" | "descending"`. Clicking the active column toggles the
    direction; another column starts ascending, except price and 7 d / 30 d which start descending.
  - 860-1239: wrapper with horizontal scroll, `min-width: 920px`. ≥ 1240: no overflow wrapper and the header
    is sticky below the topbar (`top: 64px`).
  - Numbers right-aligned with `font-variant-numeric: tabular-nums`; trends with sign and colour plus their
    accessible text (as `PriceTag`).

S5. Wide ≥ 1600 (`up('2xl')`) in grid or list view: grid `280px minmax(0, 1fr) 380px`; the third column is
    `CatalogPreview` (sticky like the sidebar). In table view there is no preview column (the table takes the
    width).
  - Tiles/rows become `button`s with `aria-pressed` (selected) and the accessible name
    `cards:catalog.tile.select`; activating one selects it (URL param `selected=<SET>-<ID>`, `replace`) instead
    of opening the detail. Default selection when the param is missing or not on the current page: the first
    result.
  - `CatalogPreview` (heading `cards:catalog.preview.title`): `CardImage size="full"`, name, `set · #id`,
    `RarityDot showLabel`, `DomainPips`, type line, `BanBadge`, `PriceTag size="lg"` (market) and, when
    foilable, the foil price, both trends, a `Sparkline` of the last 30 days (`useCardPrices(…, '30d')`,
    label `cards:catalog.preview.trend`), owned (`cards:catalog.owned`), and a link
    `cards:catalog.preview.open` to the detail route (opens the modal). No results → `cards:catalog.preview.empty`.
  - Below 1600 nothing changes from F2-h (tiles are links).

S6. `meta.facets` counts are shown in the sidebar exactly as in the sheet; the sidebar never shows a stale
    count while a request is in flight longer than 300 ms (counts dimmed with `aria-busy`).

## API / data contract

Consumes `GET /cards` and `GET /cards/{set}/{id}/prices?range=30d`. No backend change.

## UI

| Width | Layout |
|---|---|
| < 860 | Unchanged (F2-h). |
| 860-1239 | Unchanged plus the table view (scrolling wrapper, 13 columns). |
| ≥ 1240 | Sidebar 280 px + results; toolbar with page size and table view; full table (16 columns). |
| ≥ 1600 | Sidebar + results + preview 380 px (grid/list); table view without preview. |

Strings — `cards.json`:

| Key | es | en |
|---|---|---|
| `catalog.perPage` | Por página | Per page |
| `catalog.table.caption` | Cartas del catálogo | Catalog cards |
| `catalog.table.image` / `set` / `number` / `name` / `type` / `rarity` | Imagen / Set / Nº / Nombre / Tipo / Rareza | Image / Set / No. / Name / Type / Rarity |
| `catalog.table.energy` / `power` / `might` / `tags` | Energía / Poder / Fuerza / Etiquetas | Energy / Power / Might / Tags |
| `catalog.table.price` / `foil` / `trend7` / `trend30` / `owned` / `bans` | Precio / Foil / 7 d / 30 d / Tengo / Baneos | Price / Foil / 7 d / 30 d / Owned / Bans |
| `catalog.table.moreTags` | +{{count}} | +{{count}} |
| `catalog.tile.select` | Mostrar {{name}} en la vista previa | Show {{name}} in the preview |
| `catalog.preview.title` | Vista previa | Preview |
| `catalog.preview.open` | Ver ficha completa | Open full card |
| `catalog.preview.empty` | Selecciona una carta para verla aquí. | Select a card to preview it here. |
| `catalog.preview.trend` | Precio de los últimos 30 días | Price over the last 30 days |

## Acceptance criteria

- [ ] AC1 `src/catalog/CatalogFilters.test.tsx`: sheet below 1240 and sidebar at 1280; collapsible groups with `aria-expanded`; remembered/invalid `rb_cards_facets` (S1).
- [ ] AC2 `src/catalog/CatalogPage.desktop.test.tsx` at 1280 px: two-column layout class, no "Filtros" button, page size writes `per_page` and resets page (S2, S3).
- [ ] AC3 `src/catalog/CatalogTable.test.tsx`: 13 columns at 1024, 16 at 1280; `aria-sort`; header click rules (toggle, price starts descending); name link href; fallback to list below 860 (S4).
- [ ] AC4 `src/catalog/CatalogPreview.test.tsx` at 1680 px: default first selection, `selected` param with replace, `aria-pressed`, preview content (prices, foil only when foilable, sparkline from MSW 30d), open link, table view has no preview (S5).
- [ ] AC5 Axe at 1280 (grid, table) and 1680 (grid with preview): no violations.
- [ ] AC6 Full lanes green: `venv/bin/pytest`; `cd frontend && npm run lint && npm run typecheck && npx vitest run && npm run build && npm run check:dist`
- [ ] AC7 `docs/knowledge/state.md` updated (what changed, PR number placeholder, new follow-ups)
- [ ] AC8 `docs/frontend.md` "Catalog" section: layouts per width, storage keys (`rb_cards_view`, `rb_cards_facets`, `rb_price_range`, `rb_cards_scroll`).

## Delivery

- Conventional Commits; commit messages end with the attribution lines the session supplies.
- Push and PR only when the user says so. PR title: `feat(catalog): desktop sidebar, table view and wide preview (F2 unit i)`.
  PR body: summary, specs → tests map (S# → test file::name), screenshots at 1024, 1280, 1440 and 1920 px,
  manual checks, rollback (revert).
- Never merge. The user merges.

## After merge (user asks gentle-shell, or does it)

- Deploy to dev with `docs/knowledge/ops-runbook.md` (frontend build only).
- Live checks: at 1280 px the sidebar is visible and sticky; at 1920 px the preview panel follows the selected tile.
- Manual checks for the user (desktop): sort the table by price and by 7-day change, switch to 192 per page,
  collapse filter groups and reload (state kept), check the preview on a wide monitor.

## Open questions

- CONFIRM D-F2-13: page sizes 48/96/192 on desktop; table view from 860 px; preview panel only in grid/list views.
