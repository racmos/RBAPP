# F14-e: Products UI — mobile core, owned products, nav entry

| Field | Value |
|---|---|
| Phase / unit | F14 / e — batch 1, unit 31 |
| Branch | `feat/f14e-products-ui-mobile` (from the F14-d branch) |
| Depends on | F14-b, F14-c, F14-d, F2-g (stack) |
| Size forecast | ~600 authored lines |
| Risk | `Risk: none` |
| TDD | ON (strict). Runner: `cd frontend && npx vitest run` |
| Sources | F14 phase spec (F14-R10, "UI"), `decisions-2026-10-25.md` (D-F14-14) |

## Objective

A "Productos" section where the user browses sealed products with prices, opens one with its price chart, and keeps
the list of the products they own with a total that is clearly separate from the card collection.

## Read first

- `src/catalog/` (F2-h list patterns, params ⇄ URL), `src/collection/` (F3-g steppers, sheets, undo),
  `src/components/charts/PriceChart` (F2-g), `src/shell/navRegistry.ts`, `src/components/ui/icons.ts`, `docs/api.md`

## Specs

S1. Nav: new `NavId` `products`, entry `{id: 'products', icon: 'gift', status: 'spa', to: '/products', placements:
    ['top', 'hub', 'more']}` after `collection`; `nav:items.products.label` / `description`.
S2. Route `/products` (`ProductsPage`) with two tabs (`role="tablist"`, URL `?tab=mine|catalog`, default `mine`
    when the user owns products, else `catalog`):
    - **Mis productos**: total band (`products:total.title`, value, lines, unpriced count with
      `products:total.unpriced`) and the hint `products:total.separate`; list of owned lines (image or kind
      placeholder, name, kind, quantity stepper, unit price, line value); tap → line sheet (quantity, purchase price,
      note, delete with confirm + undo 8 s).
    - **Catálogo**: search (`q`), kind chips (with counts), set `Select`, sort (`name`, `price`, `change_7d`,
      `change_30d`), grid of tiles (image/placeholder, name, kind, price with 7-day change, owned badge `×N`),
      `Pagination`.
S3. Route `/products/:id` (`ProductDetail`, full page on mobile): image, name, kind, set, price and changes,
    `PriceChart` with ranges 30 d / 90 d / 1 año / Todo (adapt the chart's input to `{date, value}` points;
    if `PriceChart` props are card-specific, add a small adapter, recorded as a deviation), owned lines and an
    "Añadir" form (quantity, purchase price, note) that merges per F14-c.
S4. Kind placeholder: a tile with the `gift` icon and the kind label when there is no image.
S5. States: skeletons, empty mine (`products:empty.mine` + button to the catalog tab), empty catalog with filters
    (`products:empty.catalog` + clear), unpriced (`products:unpriced` instead of a price), error, offline (online
    only in batch 1: cached TanStack data shown, edits disabled with `common:offline.editDisabled`). Axe clean;
    `useDocumentTitle`.

## UI strings

| Key | ES | EN |
|---|---|---|
| `nav:items.products.label` | Productos | Products |
| `nav:items.products.description` | Cajas, sobres y accesorios | Boxes, boosters and accessories |
| `products:title` | Productos | Products |
| `products:tabs.mine` | Mis productos | My products |
| `products:tabs.catalog` | Catálogo | Catalog |
| `products:total.title` | Valor de tus productos | Value of your products |
| `products:total.lines` | Líneas | Lines |
| `products:total.unpriced_one` | {{count}} sin precio | {{count}} without price |
| `products:total.unpriced_other` | {{count}} sin precio | {{count}} without price |
| `products:total.separate` | Este total no se suma al valor de tu colección de cartas. | This total is not added to the value of your card collection. |
| `products:search.label` | Buscar productos | Search products |
| `products:search.placeholder` | Nombre del producto | Product name |
| `products:filters.kind` | Tipo | Kind |
| `products:filters.set` | Set | Set |
| `products:filters.allSets` | Todos los sets | All sets |
| `products:sort.label` | Ordenar por | Sort by |
| `products:sort.name` | Nombre | Name |
| `products:sort.price` | Precio | Price |
| `products:sort.change_7d` | Cambio 7 d | 7-day change |
| `products:sort.change_30d` | Cambio 30 d | 30-day change |
| `products:owned` | Tienes {{count}} | You own {{count}} |
| `products:unpriced` | Sin precio | No price |
| `products:line.quantity` | Cantidad | Quantity |
| `products:line.purchasePrice` | Precio de compra (unidad) | Purchase price (each) |
| `products:line.note` | Nota | Note |
| `products:line.value` | Valor | Value |
| `products:line.delete` | Eliminar | Delete |
| `products:line.confirmDelete` | ¿Eliminar esta línea? | Delete this line? |
| `products:line.deleted` | Línea eliminada. | Line deleted. |
| `products:line.undo` | Deshacer | Undo |
| `products:add.title` | Añadir a mis productos | Add to my products |
| `products:add.submit` | Añadir | Add |
| `products:add.added` | Añadido a tus productos. | Added to your products. |
| `products:add.merged` | Sumado a una línea que ya tenías. | Added to a line you already had. |
| `products:detail.price` | Precio | Price |
| `products:detail.change7d` | 7 días | 7 days |
| `products:detail.change30d` | 30 días | 30 days |
| `products:detail.history` | Evolución del precio | Price history |
| `products:detail.yourLines` | Tus unidades | Your units |
| `products:empty.mine` | Todavía no has añadido productos. | You have not added any products yet. |
| `products:empty.goCatalog` | Ver el catálogo | Browse the catalog |
| `products:empty.catalog` | Ningún producto coincide con los filtros. | No product matches the filters. |
| `products:clearFilters` | Limpiar filtros | Clear filters |

## Acceptance criteria

- [ ] AC1 Nav entry and route; tab from the URL and default rule (S1, S2).
- [ ] AC2 `ProductsPage.test.tsx` at 390: mine tab total band and separation hint, stepper PATCH, line sheet edit/delete + undo; catalog tab search, kind chips, set, sort, pagination (S2).
- [ ] AC3 `ProductDetail.test.tsx`: chart ranges request, add with merge toast, owned lines (S3); placeholder (S4).
- [ ] AC4 States, offline, axe, parity; full lanes green; `docs/frontend.md`, `state.md` (S5).

## Delivery

PR title: `feat(products): products section with owned products and price chart (F14 unit e)`. Screenshots at 390 px.

## After merge

Deploy. Manual (owner, phone): add a booster box you own, check the separate total, open its chart.

## Open questions

none
