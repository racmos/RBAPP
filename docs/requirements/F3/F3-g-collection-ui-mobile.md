# F3-g: Collection UI — mobile and tablet core, add, edit, playset warning

| Field | Value |
|---|---|
| Phase / unit | F3 / g — batch 1, unit 24 |
| Branch | `feat/f3g-collection-ui-mobile` (from the F3-e branch) |
| Depends on | F3-b, F3-c, F2-e, F2-h, F2-k (stack) |
| Size forecast | ~650 authored lines |
| Risk | `Risk: none` |
| TDD | ON (strict). Runner: `cd frontend && npx vitest run` |
| Sources | F3 phase spec (F3-R14, R15, R22, R26-R28, "UI"), `decisions-2026-10-25.md` (D-F3-8, 9, 10) |

## Objective

On the phone (and up to 1239 px) the user sees the collection as a grid or a list, searches and filters it, adds
cards with the card search, edits every field of every line, splits and deletes with undo, marks the cards to
keep a playset and sees in red the ones below it. The "Colección" menu entry opens this screen.

## Read first

- `frontend/src/catalog/` (F2-f/h: `CatalogPage`, params ⇄ URL, filter sheet, chips, grid tiles),
  `frontend/src/components/card/` (F2-e), `CardCombobox` (F2-k), `frontend/src/prefs/` (`collection_view`),
  `frontend/src/account/InterfacePage.tsx`, `docs/api.md` (collection read/write)

## Specs

S1. Data layer `src/collection/`: types `CollectionGroup`, `CollectionLine`, `CollectionMeta`; params ⇄ URL like
    `src/catalog/params.ts` (F3-b parameter names; defaults `sort=number`, `per_page=50`); queries
    `['collection', 'list', <serialized params>]`; mutations for add, patch, delete, split, keep-playset; every
    mutation invalidates `['collection']` and `['cards']` (owned counts).
S2. Route `/collection` (`CollectionPage`), nav entry `collection` → `{status: 'spa', to: '/collection'}`;
    `legacy-routes.json` keeps `collection`; header link `collection:classic` to the Jinja page. The card detail
    (F2-f) "Mis copias" link goes to `/collection?q=<SET-ID>`.
S3. Layout below 1240 px: `PageHeader` (`collection:title`, subtitle `collection:summary.line` with qty,
    unique and value); summary strip with three figures (copias, únicas, valor; `formatMoney`); search
    (`collection:search.label`/`placeholder`, writes `q`); toolbar (filters button with count, sort `Select`
    with `collection:sort.<key>`, direction toggle, view `SegmentedControl` grid/list — default from prefs
    `collection_view`, Auto = grid); active filter chips; results; `Pagination`; floating button
    `collection:add.open` (bottom right, above the bottom nav).
S4. Filter sheet (same pattern as F2-h S8): set, domain, type, rarity (from `/meta/game` with facet counts),
    foil (`SegmentedControl` any/foil/nonfoil), selling (any/yes/no), condition, language (lists from
    `/meta/game`), with purchase price (any/yes/no).
S5. Grid tile (`CollectionTile`): `CardImage` tile, `×{{qty}}` badge, foil badge `collection:foil` when foil,
    selling tag `collection:selling.tag` with `sell_qty` when > 0 and selling, name, `SET · #id`, value
    (`PriceTag`); when `playset_short`: a 2 px `--danger` outline **and** the text
    `collection:playset.short` (kept/size) under the name (never colour alone). List row: same data in one line.
S6. `LineSheet` (tap on a tile/row; bottom `Sheet`, title = card name + foil): the group's lines, each a
    `fieldset` with: qty stepper (`collection:line.qty`, min 1), condition `Select`, language `Select`
    (`/meta/game` list + the line's own value when it is not in the list), purchase price (number, € suffix),
    selling `Switch` (`role="switch"`), copies to sell stepper (0..qty), sell price (number); every change is
    saved with `PATCH` sending `if_updated_at` (debounce 500 ms for numbers); `stale_line` → toast + refetch.
    Per line: "Separar copias" (`collection:line.split`) opens an inline form (qty 1..qty−1, condition,
    language, sell price) → `split`; "Eliminar" → `ConfirmDialog` (`collection:line.confirmDelete.*`) → delete →
    toast `collection:line.deleted` with action `collection:line.undo` for 8 s (re-POSTs the deleted line).
    At the top of the sheet: checkbox `collection:playset.keep` (calls keep-playset) and, when short, the
    warning `collection:playset.warning`.
S7. `AddSheet` (`collection:add.title`): `CardCombobox` (F2-k), foil switch (disabled with hint
    `collection:add.foilNotAvailable` when the card is not foilable), qty stepper, condition, language, purchase
    price, selling switch; submit `collection:add.submit`; success toast `collection:add.added` or
    `collection:add.merged`; the sheet stays open with the card search cleared ("add another").
S8. Playset size: in `/account/interface` a new `SettingsCard` `collection:settings.title` with a number input
    1-9 (`collection:settings.playsetSize`, hint `collection:settings.playsetHint`), saved through
    `PATCH /me/prefs` (`playset_size`, empty → null = 3).
S9. States: skeleton tiles; empty collection (`collection:empty.title`, `collection:empty.body`, buttons add
    and `collection:empty.import` → `/collection/import`, route added in F3-i: until then the button links to
    the classic page); empty filters (`collection:emptyFilters` + clear); error; offline (cached view, the FAB and
    every edit control disabled with `common:offline.editDisabled`). `useDocumentTitle(collection:title)`. Axe clean.

## UI strings

| Key | ES | EN |
|---|---|---|
| `collection:title` | Colección | Collection |
| `collection:classic` | Versión clásica | Classic version |
| `collection:summary.line` | Copias: {{qty}} · Únicas: {{unique}} · Valor: {{value}} | Copies: {{qty}} · Unique: {{unique}} · Value: {{value}} |
| `collection:summary.copies` | Copias | Copies |
| `collection:summary.unique` | Únicas | Unique |
| `collection:summary.value` | Valor | Value |
| `collection:search.label` | Buscar en tu colección | Search your collection |
| `collection:search.placeholder` | Nombre, número o etiqueta | Name, number or tag |
| `collection:filters.open` | Filtros | Filters |
| `collection:filters.title` | Filtrar colección | Filter collection |
| `collection:filters.foil` | Foil | Foil |
| `collection:filters.foilAny` | Todas | All |
| `collection:filters.foilOnly` | Solo foil | Foil only |
| `collection:filters.nonfoilOnly` | Sin foil | Non-foil |
| `collection:filters.selling` | En venta | On sale |
| `collection:filters.condition` | Estado | Condition |
| `collection:filters.language` | Idioma | Language |
| `collection:filters.hasPurchase` | Con precio de compra | With purchase price |
| `collection:filters.any` | Da igual | Any |
| `collection:filters.yes` | Sí | Yes |
| `collection:filters.no` | No | No |
| `collection:sort.label` | Ordenar por | Sort by |
| `collection:sort.number` | Número | Number |
| `collection:sort.name` | Nombre | Name |
| `collection:sort.price` | Precio | Price |
| `collection:sort.qty` | Copias | Copies |
| `collection:sort.value` | Valor | Value |
| `collection:sort.pl` | Ganancia | Profit |
| `collection:sort.trend_7d` | Cambio 7 d | 7-day change |
| `collection:sort.updated` | Última modificación | Last change |
| `collection:sort.rarity` | Rareza | Rarity |
| `collection:view.label` | Vista | View |
| `collection:view.grid` | Cuadrícula | Grid |
| `collection:view.list` | Lista | List |
| `collection:foil` | Foil | Foil |
| `collection:selling.tag` | En venta: {{count}} | On sale: {{count}} |
| `collection:playset.keep` | Mantener un playset de esta carta | Keep a playset of this card |
| `collection:playset.short` | Playset incompleto ({{kept}}/{{size}}) | Playset incomplete ({{kept}}/{{size}}) |
| `collection:playset.warning` | Copias sin vender: {{kept}} de {{size}}. | Unsold copies: {{kept}} of {{size}}. |
| `collection:line.title` | Copias de {{name}} | Copies of {{name}} |
| `collection:line.legend` | Línea {{index}} | Line {{index}} |
| `collection:line.qty` | Copias | Copies |
| `collection:line.condition` | Estado | Condition |
| `collection:line.language` | Idioma | Language |
| `collection:line.purchasePrice` | Precio de compra (unidad) | Purchase price (each) |
| `collection:line.selling` | En venta | On sale |
| `collection:line.sellQty` | Copias a vender | Copies to sell |
| `collection:line.sellPrice` | Precio de venta (unidad) | Sale price (each) |
| `collection:line.split` | Separar copias | Split copies |
| `collection:line.splitQty` | Copias a separar | Copies to split |
| `collection:line.splitSubmit` | Separar | Split |
| `collection:line.delete` | Eliminar | Delete |
| `collection:line.confirmDelete.title` | ¿Eliminar esta línea? | Delete this line? |
| `collection:line.confirmDelete.body_one` | Se quitará {{count}} copia de tu colección. | {{count}} copy will be removed from your collection. |
| `collection:line.confirmDelete.body_other` | Se quitarán {{count}} copias de tu colección. | {{count}} copies will be removed from your collection. |
| `collection:line.deleted` | Línea eliminada. | Line deleted. |
| `collection:line.undo` | Deshacer | Undo |
| `collection:line.saved` | Guardado. | Saved. |
| `collection:add.open` | Añadir carta | Add card |
| `collection:add.title` | Añadir a la colección | Add to collection |
| `collection:add.card` | Carta | Card |
| `collection:add.foil` | Foil | Foil |
| `collection:add.foilNotAvailable` | Esta carta no tiene versión foil. | This card has no foil version. |
| `collection:add.submit` | Añadir | Add |
| `collection:add.added` | Añadida a tu colección. | Added to your collection. |
| `collection:add.merged` | Sumada a una línea que ya tenías. | Added to a line you already had. |
| `collection:empty.title` | Tu colección está vacía | Your collection is empty |
| `collection:empty.body` | Añade cartas una a una o importa un fichero. | Add cards one by one or import a file. |
| `collection:empty.import` | Importar | Import |
| `collection:emptyFilters` | Ninguna carta de tu colección coincide con los filtros. | No card in your collection matches the filters. |
| `collection:clearFilters` | Limpiar filtros | Clear filters |
| `collection:settings.title` | Colección | Collection |
| `collection:settings.playsetSize` | Tamaño del playset | Playset size |
| `collection:settings.playsetHint` | Copias que quieres conservar de cada carta marcada. Por defecto, 3. | Copies you want to keep of each marked card. 3 by default. |
| `enums:condition.MT` | Mint (MT) | Mint (MT) |
| `enums:condition.NM` | Casi nueva (NM) | Near Mint (NM) |
| `enums:condition.EX` | Excelente (EX) | Excellent (EX) |
| `enums:condition.GD` | Buena (GD) | Good (GD) |
| `enums:condition.LP` | Algo jugada (LP) | Light Played (LP) |
| `enums:condition.PL` | Jugada (PL) | Played (PL) |
| `enums:condition.PO` | Deteriorada (PO) | Poor (PO) |
| `enums:language.English` | Inglés | English |
| `enums:language.French` | Francés | French |
| `enums:language.German` | Alemán | German |
| `enums:language.Spanish` | Español | Spanish |
| `enums:language.Italian` | Italiano | Italian |
| `enums:language.Simplified Chinese` | Chino simplificado | Simplified Chinese |
| `enums:language.Japanese` | Japonés | Japanese |
| `enums:language.Portuguese` | Portugués | Portuguese |
| `enums:language.Russian` | Ruso | Russian |
| `enums:language.Korean` | Coreano | Korean |
| `enums:language.Traditional Chinese` | Chino tradicional | Traditional Chinese |

(A language value outside the list is shown as stored. If i18next key separators make `Simplified Chinese`
awkward as a key, map values to keys `simplifiedChinese`/`traditionalChinese` in one helper; record it as a deviation.)

## Acceptance criteria

- [ ] AC1 Params ⇄ URL round trip and defaults; queries/mutations invalidate the right keys (S1).
- [ ] AC2 `CollectionPage.test.tsx` at 390 and 1000 px: header, summary, search, filters sheet, sort, view toggle from prefs, pagination, FAB; nav entry is SPA (S2-S4).
- [ ] AC3 Tile and row: badges, selling tag, value, playset short with outline and text (S5).
- [ ] AC4 `LineSheet.test.tsx`: every field PATCH (with `if_updated_at`), stale toast, split, delete + undo within 8 s (fake timers), keep-playset checkbox and warning (S6).
- [ ] AC5 `AddSheet.test.tsx`: combobox selection, foil disabled for non-foilable, add and merge toasts, stays open (S7).
- [ ] AC6 Interface page playset size saves `playset_size` and clears to null (S8).
- [ ] AC7 States, offline disabling, axe, parity; full lanes green; `docs/frontend.md`, `state.md` (S9).

## Delivery

PR title: `feat(collection): collection screen for mobile with add, edit and playset warning (F3 unit g)`.
Screenshots at 390 and 1000 px.

## After merge

Deploy. Manual (owner, phone): add a card, edit its condition and sale fields, mark "mantener playset" on a card
with 2 copies and see the red warning, delete and undo.

## Open questions

none

## Log

- L1 (implementer): `CollectionGroup` gains `kept` (copies not for sale of every printing of the name). The tile text "Playset incompleto (kept/size)" needs it and the group did not carry it; the change is additive (`docs/api.md`, `tests/test_api_collection_playset.py`).
- L2 (implementer): the group value is shown with `formatMoney` instead of `PriceTag` (a total is not a price object).
- L3 (implementer): the `collection_view` preference `table` starts the list view (this screen has grid and list only).
- L4 (implementer): above 1240 px the screen is still the mobile layout; F3-h adds the desktop one.
- L5 (implementer): the 8-second undo is checked by the toast's `duration` (8000) and by posting the line back, not with fake timers (the toast timer is the toast component's).
- L6 (implementer): condition and language filter chips take their values from `/meta/game`; domain and type have no counts because `GET /collection` has no facets for them. `condition`/`language` enum keys use the stored values as they are (`Simplified Chinese` works as an i18next key), so no key-mapping helper was needed.
