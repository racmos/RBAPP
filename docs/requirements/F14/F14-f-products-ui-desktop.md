# F14-f: Products UI — desktop table and wide detail panel

| Field | Value |
|---|---|
| Phase / unit | F14 / f — batch 1, unit 32 (last) |
| Branch | `feat/f14f-products-ui-desktop` (from the F14-e branch) |
| Depends on | F14-e (stack) |
| Size forecast | ~400 authored lines |
| Risk | `Risk: none` |
| TDD | ON (strict). Runner: `cd frontend && npx vitest run` |
| Sources | F14 phase spec ("UI"), `decisions-2026-10-25.md` (D-F14-7 and D-F14-12 deferred) |

## Objective

On a computer the products section shows more at once: a filter rail, a table with every price column and the
owned quantity, and on wide screens a detail panel with the chart of the selected product.

## Read first

- `src/products/` (F14-e), F2-i desktop pieces (sidebar, table view), F3-h table patterns

## Specs

S1. From 1240 px: left rail (240 px) with search, kind checkboxes with counts, set `Select`, "solo los míos"
    switch (`products:filters.onlyMine` → `owned=owned`); the two tabs stay above the content.
S2. Catalog tab table (`<caption>` `products:table.caption`): image (40 px), name, kind, set, price, 7 d, 30 d,
    owned (`×N` or `—`), listed (`products:table.notListed` badge when false); sortable headers map to the API
    sorts (`aria-sort`); page size 48/96.
S3. Mine tab table: image, name, kind, quantity (inline stepper), purchase price (inline), unit price, value,
    profit € and %, note (inline); the total band on top with value, lines, unpriced and the separation hint.
S4. Wide ≥ 1600: a right panel (380 px) shows the selected product (row click): image, price and changes,
    `PriceChart` (90 d), the user's lines and the add form; empty text `products:panel.empty`. Below 1600 a row
    click opens `/products/:id`.
S5. States as F14-e; axe clean (table names, inline inputs labelled with the product name).

## UI strings

| Key | ES | EN |
|---|---|---|
| `products:filters.onlyMine` | Solo los míos | Only mine |
| `products:filters.pageSize` | Por página | Per page |
| `products:table.caption` | Productos de Cardmarket | Cardmarket products |
| `products:table.mineCaption` | Tus productos | Your products |
| `products:table.columns.image` | Imagen | Image |
| `products:table.columns.name` | Nombre | Name |
| `products:table.columns.kind` | Tipo | Kind |
| `products:table.columns.set` | Set | Set |
| `products:table.columns.price` | Precio | Price |
| `products:table.columns.change7d` | 7 d | 7 d |
| `products:table.columns.change30d` | 30 d | 30 d |
| `products:table.columns.owned` | Tienes | Owned |
| `products:table.columns.listed` | En Cardmarket | On Cardmarket |
| `products:table.columns.quantity` | Cantidad | Quantity |
| `products:table.columns.purchase` | Compra | Purchase |
| `products:table.columns.value` | Valor | Value |
| `products:table.columns.plAbs` | Ganancia € | Profit € |
| `products:table.columns.plPct` | Ganancia % | Profit % |
| `products:table.columns.note` | Nota | Note |
| `products:table.notListed` | Ya no aparece | No longer listed |
| `products:panel.empty` | Elige un producto para ver su detalle. | Pick a product to see its details. |

## Acceptance criteria

- [ ] AC1 `ProductsDesktop.test.tsx` at 1280: rail filters in the URL, catalog table sort and page size, mine table inline edits (S1-S3).
- [ ] AC2 Wide panel at 1700 with chart and add form; row click navigates below 1600 (S4).
- [ ] AC3 Axe, parity, full lanes green; `docs/frontend.md`, `state.md` (F14 phase row "implemented in batch 1") (S5).

## Delivery

PR title: `feat(products): desktop table and wide detail panel (F14 unit f)`. Screenshots at 1280 and 1700 px.
This is the last unit of batch 1: after opening the PR, post the batch summary (BATCH-1 R8).

## After merge

Deploy. Manual (owner, computer): sort the catalog by 30-day change, edit a quantity inline, open the wide panel.

## Open questions

none

## Log

- L1 (implementer): two strings added that the tests need and the spec table lacks: `products:filters.title` (name of the rail) and `products:panel.title` (name of the panel).
- L2 (implementer): the rail has no "Limpiar filtros" button (the empty catalog already offers one); any rail change switches to the catalog tab because the filters only apply there.
- L3 (implementer): in the Mine table the stepper's own label is hidden visually (the column header names it); `collection/Stepper` is unchanged.
- L4 (parent): no screenshots (no browser run); the desktop layout was tested at 1280 and 1700 px with axe.
