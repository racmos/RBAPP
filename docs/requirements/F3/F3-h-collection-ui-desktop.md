# F3-h: Collection UI — desktop table with sub-lines, bulk edit, wide panel

| Field | Value |
|---|---|
| Phase / unit | F3 / h — batch 1, unit 25 |
| Branch | `feat/f3h-collection-ui-desktop` (from the F3-g branch) |
| Depends on | F3-g, F2-g, F2-i (stack) |
| Size forecast | ~650 authored lines |
| Risk | `Risk: none` |
| TDD | ON (strict). Runner: `cd frontend && npx vitest run` |
| Sources | F3 phase spec (F3-R16, R17, R22, "UI"), `decisions-2026-10-25.md` (D-F3-8) |

## Objective

On a computer the collection shows much more at once: a facet sidebar, a table grouped by card with expandable
sub-lines and every money column, a summary band, row selection with bulk edits, and on wide screens a panel
with the selected card's price chart and lines.

## Read first

- `src/collection/` (F3-g), `src/catalog/` desktop pieces (F2-i: facet sidebar, table view, page size),
  `src/components/charts/` (F2-g `PriceChart`), `docs/api.md` (bulk endpoint)

## Specs

S1. From 1240 px `CollectionPage` uses the desktop layout (F3-g stays below): left sticky facet sidebar (280 px,
    the F3-g filter groups with counts, reusing F2-i's sidebar component), toolbar (count
    `collection:desktop.groups` plural, sort, direction, page size 25/50/100/200, view grid/table — table default
    on desktop when prefs `collection_view` is Auto), summary band, then results.
S2. Summary band: value, cost, profit (€ and %), lines, unique, value on sale, % foil (F3-b `meta.totals`); profit
    coloured by sign **and** prefixed with `+`/`−`.
S3. Table (`<caption>` `collection:table.caption`): one row per group with an expand button
    (`aria-expanded`, name `collection:table.expand` + card name) when it has more than one line; sub-line rows
    indented below. Columns: select, image (40 px), set, #, name (with playset warning icon + text when short),
    foil, qty, to sell, on sale (switch), sale price, condition, language, purchase, market, profit €, profit %,
    7 d, updated. Group rows show totals; editable cells live on line rows (single-line groups edit on the group
    row): qty, to sell, on sale, sale price, condition, language, purchase — inline inputs saved like F3-g S6.
    Sortable headers (`aria-sort`) map to F3-b sorts; the others are not sortable. Header sticky below the topbar.
S4. Selection: checkbox per line (group checkbox = all its lines, indeterminate when partial); header checkbox =
    every line on the page; when the whole page is selected and `total_groups > page size`, a link
    `collection:bulk.selectAllFiltered` selects every line id of the filtered set by fetching the ids
    (`GET /collection` pages, max 1000 ids, D-F3-8; beyond that the link is disabled with
    `collection:bulk.tooMany`). Selection resets when filters change.
S5. Bulk bar (sticky bottom while something is selected): `collection:bulk.selected` (plural), controls condition,
    language, on sale (yes/no), copies to sell rule (`all` / `none` / keep N with a 1-9 input), sale price,
    purchase price, buttons apply and delete; apply/delete behind `ConfirmDialog`
    (`collection:bulk.confirm.apply` / `delete`, plural with the count); delete offers undo for 8 s (re-POSTs the
    deleted lines). Errors translated.
S6. Wide ≥ 1600: right panel (380 px) with the selected group (row click selects): card image, name, totals,
    `PriceChart` 30 d of the card (F2-g, foil series when the group is foil), the group's lines (read-only
    summary), decks using the card (`in_decks` from `GET /cards/{set}/{id}`), link to the card detail. Empty
    panel text `collection:panel.empty`.
S7. Grid view on desktop: F3-g tiles in 6-8 columns with the sidebar. States as F3-g; axe clean (table names,
    checkbox names `collection:table.selectLine` + card name).

## UI strings

| Key | ES | EN |
|---|---|---|
| `collection:desktop.groups_one` | {{count}} carta | {{count}} card |
| `collection:desktop.groups_other` | {{count}} cartas | {{count}} cards |
| `collection:desktop.pageSize` | Por página | Per page |
| `collection:view.table` | Tabla | Table |
| `collection:totals.value` | Valor | Value |
| `collection:totals.cost` | Coste | Cost |
| `collection:totals.pl` | Ganancia | Profit |
| `collection:totals.lines` | Líneas | Lines |
| `collection:totals.unique` | Únicas | Unique |
| `collection:totals.selling` | En venta | On sale |
| `collection:totals.foil` | Foil | Foil |
| `collection:table.caption` | Tu colección agrupada por carta | Your collection grouped by card |
| `collection:table.expand` | Ver las líneas de {{name}} | Show the lines of {{name}} |
| `collection:table.selectLine` | Seleccionar {{name}} | Select {{name}} |
| `collection:table.selectPage` | Seleccionar todo en esta página | Select all on this page |
| `collection:table.columns.image` | Imagen | Image |
| `collection:table.columns.set` | Set | Set |
| `collection:table.columns.number` | Nº | No. |
| `collection:table.columns.name` | Nombre | Name |
| `collection:table.columns.foil` | Foil | Foil |
| `collection:table.columns.qty` | Copias | Copies |
| `collection:table.columns.sellQty` | A vender | To sell |
| `collection:table.columns.selling` | En venta | On sale |
| `collection:table.columns.sellPrice` | Precio venta | Sale price |
| `collection:table.columns.condition` | Estado | Condition |
| `collection:table.columns.language` | Idioma | Language |
| `collection:table.columns.purchase` | Compra | Purchase |
| `collection:table.columns.market` | Mercado | Market |
| `collection:table.columns.plAbs` | Ganancia € | Profit € |
| `collection:table.columns.plPct` | Ganancia % | Profit % |
| `collection:table.columns.trend7d` | 7 d | 7 d |
| `collection:table.columns.updated` | Modificada | Updated |
| `collection:bulk.selected_one` | {{count}} línea seleccionada | {{count}} line selected |
| `collection:bulk.selected_other` | {{count}} líneas seleccionadas | {{count}} lines selected |
| `collection:bulk.selectAllFiltered` | Seleccionar las {{count}} líneas filtradas | Select all {{count}} filtered lines |
| `collection:bulk.tooMany` | Más de 1000 líneas: filtra un poco más. | More than 1000 lines: filter a bit more. |
| `collection:bulk.condition` | Estado | Condition |
| `collection:bulk.language` | Idioma | Language |
| `collection:bulk.selling` | En venta | On sale |
| `collection:bulk.sellRule` | Copias a vender | Copies to sell |
| `collection:bulk.sellRule.all` | Todas | All |
| `collection:bulk.sellRule.none` | Ninguna | None |
| `collection:bulk.sellRule.keep` | Conservar | Keep |
| `collection:bulk.sellPrice` | Precio de venta | Sale price |
| `collection:bulk.purchasePrice` | Precio de compra | Purchase price |
| `collection:bulk.apply` | Aplicar | Apply |
| `collection:bulk.delete` | Eliminar | Delete |
| `collection:bulk.clear` | Quitar selección | Clear selection |
| `collection:bulk.confirm.apply_one` | ¿Aplicar los cambios a {{count}} línea? | Apply the changes to {{count}} line? |
| `collection:bulk.confirm.apply_other` | ¿Aplicar los cambios a {{count}} líneas? | Apply the changes to {{count}} lines? |
| `collection:bulk.confirm.delete_one` | ¿Eliminar {{count}} línea? | Delete {{count}} line? |
| `collection:bulk.confirm.delete_other` | ¿Eliminar {{count}} líneas? | Delete {{count}} lines? |
| `collection:bulk.applied` | Cambios aplicados. | Changes applied. |
| `collection:bulk.deleted_one` | {{count}} línea eliminada. | {{count}} line deleted. |
| `collection:bulk.deleted_other` | {{count}} líneas eliminadas. | {{count}} lines deleted. |
| `collection:panel.empty` | Elige una carta para ver su detalle. | Pick a card to see its details. |
| `collection:panel.decks` | En tus mazos | In your decks |
| `collection:panel.noDecks` | No está en ningún mazo. | It is not in any deck. |
| `collection:panel.openDetail` | Ver ficha de la carta | Open the card page |

## Acceptance criteria

- [ ] AC1 `CollectionDesktop.test.tsx` at 1280: sidebar facets, toolbar, summary band values and signs, table default (S1-S3).
- [ ] AC2 Table: expand/collapse sub-lines, inline edits PATCH the right line, sortable headers with `aria-sort` (S3).
- [ ] AC3 Selection: group indeterminate, page select, select all filtered with the 1000 cap; bulk apply and delete with confirm and undo (S4, S5).
- [ ] AC4 Wide panel at 1700 with chart, lines, decks (S6); grid view on desktop (S7).
- [ ] AC5 Axe, parity, full lanes green; `docs/frontend.md`, `state.md`.

## Delivery

PR title: `feat(collection): desktop table with sub-lines, bulk edit and wide panel (F3 unit h)`. Screenshots at
1280 and 1700 px.

## After merge

Deploy. Manual (owner, computer): bulk-change the condition of several lines, set "keep 3" for a set, check the
summary band against your expectations.

## Open questions

none
