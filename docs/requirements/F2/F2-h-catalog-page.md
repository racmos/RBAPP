# F2-h: Catalog page (mobile-first core) and nav flip

| Field | Value |
|---|---|
| Phase / unit | F2 / h |
| Branch | `feat/f2h-catalog-page` (from up-to-date `main`) |
| Depends on | F2-c (list API) and F2-f (detail screen, `src/catalog/`) merged |
| Size forecast | ~650 authored lines (tests and docs included) |
| Risk | `Risk: none` |
| TDD | ON (strict). Runners: `venv/bin/pytest` (backend), `cd frontend && npx vitest run` (frontend) |
| Save as | `docs/requirements/F2/F2-h-catalog-page.md` (commit this document verbatim in the first commit if it is not in the repo yet) |

## Objective

"Cartas" in the app opens the new catalog instead of the Jinja page. On a phone the user can search by
name, tag or number, filter by every facet in a bottom sheet (with counts), sort, switch grid/list, page
through results and open a card; on tablets and desktop the card opens as a modal over the catalog and the
filters survive in the URL (shareable, back button works). Desktop sidebar, table and wide preview come in
F2-i.

## Read first

- `AGENTS.md`, `docs/knowledge/conventions.md`, `docs/frontend.md` (navigation registry, "Catalog")
- `docs/requirements/F2/README.md` (F2-R16, R20, R25, R26; D-F2-11, D-F2-13)
- `docs/api.md` → `GET /meta/game`, `GET /cards` (F2-b, F2-c)
- `openspec/design-handoff.md` §3.4 (catalog), §2.5 (chips, segmented), §2.6 (pagination, empty states), §7.5 R2
- `frontend/src/api/client.ts` (+ tests), `src/catalog/*` (F2-f: `CardsLayout`, `CardDetailRoute`, context),
  `src/components/ui/{Sheet,SegmentedControl,Select,Switch,Input,Checkbox,EmptyState,ErrorState,Skeleton,PageHeader}.tsx`,
  `src/components/card/*`, `src/shell/navRegistry.ts` (+ test), `src/shell/legacyRoutes.ts`, `src/lib/storage.ts`,
  `src/lib/breakpoints.ts`, `src/lib/useMediaQuery.ts`, `src/test/msw/handlers.ts`, `src/test/fixtures/cards.ts`

## Scope

In:
- `requestWithMeta` in `src/api/client.ts`; `getGameMeta`, `listCards`; their types.
- `src/catalog/params.ts` (URL ⇄ params), `useGameMeta`, `useCardList`.
- `CatalogPage` as the `/cards` layout (catalog + detail outlet), filter sheet, toolbar, active chips, grid,
  list, pagination, states.
- Generic primitives `src/components/ui/FilterChip.tsx` (+ `ChipGroup`) and `src/components/ui/Pagination.tsx`.
- Nav registry flip of `cards`; link to the classic catalog.

Out (do not do, even if tempting):
- Sidebar ≥ 1240, table view, page-size selector, wide preview (F2-i). Offline caching (F2-j). Global search (F2-k).
- Any change to `sets` (stays legacy, D-F2-11) or to the Jinja catalog.

## Specs

S1. `requestWithMeta<T, M>(path, options)` in `src/api/client.ts` resolves to `{data: T; meta: M | undefined}`
    with exactly the behaviour of `request` (errors, CSRF retry, 401 handler, timeout); both share one
    implementation; all existing client tests stay green.

S2. Types `GameMeta`, `CardListParams`, `CardListMeta` (`page, per_page, total, pages, facets, price_as_of`),
    `CardFacets`; `getGameMeta(signal?)` → `request('/meta/game')`; `listCards(params, signal?)` →
    `requestWithMeta('/cards?' + serialize(params))`.

S3. `src/catalog/params.ts`:
  - `parseCatalogSearch(search: URLSearchParams): CardListParams` reads exactly the API parameter names
    (F2-c S2), repeated keys as arrays; invalid values fall back to the default (unknown `sort` → `number`,
    `page` < 1 or not a number → 1, `per_page` not in `48 | 96 | 192` → 48, booleans only `true`).
  - `serializeCatalogParams(params): string` writes keys in a fixed order (the S2 table order of F2-c),
    arrays as repeated keys in the given order, and omits defaults and empty values, so equal params give
    equal strings. Round-trip test: `serialize(parse(x)) === x` for canonical strings.
  - `withChange(params, patch)`: any change other than `page` resets `page` to 1.

S4. Queries (`src/catalog/queries.ts`): `useGameMeta()` key `['meta', 'game']`, `staleTime` 1 h;
    `useCardList(params)` key `['cards', 'list', serializeCatalogParams(params)]`, `placeholderData:
    keepPreviousData`, `staleTime` 5 min.

S5. URL state (`useCatalogParams()`): the catalog reads its params from the current location's search string
    and writes them back with `navigate`: the text search is debounced 300 ms and uses `replace`; every other
    change pushes a history entry. The detail URL keeps the same search string
    (`/cards/OGN/79?domain=Fury&page=2`), so the catalog behind the modal keeps its filters.

S6. Routing: `/cards` uses `CatalogPage` as the layout (replacing F2-f's `CardsLayout`):
  - No child route active → the catalog.
  - Child `:setId/:cardId` active and viewport ≥ 860 px (`up('md')`) → the catalog **and** the detail with
    outlet context `{presentation: 'modal', siblings: <keys of the current page in display order>, onClose}`;
    `onClose` navigates to `/cards` + the current search string.
  - Child active and < 860 px → only the outlet with `{presentation: 'page'}` (the catalog is not rendered);
    coming back restores the results' scroll position (saved in `sessionStorage` key `rb_cards_scroll` per
    search string; storage errors ignored).
  - Tiles and rows link to `/cards/<set>/<id>` + the current search string.

S7. Layout below 1240 px (one column, content capped at `--maxw`):
  1. `PageHeader`: title `cards:catalog.title`, subtitle `cards:catalog.count` (plural, `meta.total`), and a
     small link `cards:catalog.classic` to `legacyHref('cards')` (plain `<a>`).
  2. Search: `Input type="search"` with visible-to-AT label `cards:catalog.search.label`, placeholder
     `cards:catalog.search.placeholder`, `enterkeyhint="search"`; writes `q`.
  3. Toolbar: button `cards:catalog.filters.open` with a count badge (accessible name adds
     `cards:catalog.filters.active` plural); `Select` `cards:catalog.sort.label` with the nine sort options
     (`cards:catalog.sort.<key>`); a direction toggle button (`aria-pressed` = descending, name
     `cards:catalog.sort.dirLabel`, icon rotates); `SegmentedControl` `cards:catalog.view.label` with grid
     and list.
  4. Active filters: one removable `FilterChip` per active value (label = translated value, e.g. `Furia`,
     `Coste ≥ 3`, `Baneadas en 1v1`, `"jinx"` for `q`), each with the accessible name
     `cards:catalog.filters.remove`; a "Limpiar filtros" button when any is active.
  5. Results region (`aria-busy` while fetching; heading `cards:catalog.results`, visually hidden).
  6. `Pagination` (S10) when `pages > 1`. Page size is 48 below 1240.

S8. Filter sheet (`Sheet`, title `cards:catalog.filters.title`), every group a `fieldset` + `legend`; options
    come from `GameMeta` (all known values) with the count from `meta.facets` shown as `(n)`; zero-count
    unselected options are dimmed but stay enabled. Groups in order: Set (checkbox list), Dominio
    (`ChipGroup` with domain colours + `SegmentedControl` for `domain_match`: Alguno/Todos/Solo estos), Tipo,
    Supertipo, Rareza (chips), Coste de energía / Poder / Fuerza (min/max number inputs 0-99), Precio
    (min/max, step 0.01), Colección (`SegmentedControl` any/owned/missing), Baneos (`Select`: none, 1v1, 2v2,
    any), Solo versión base (`Switch`), Texto de la carta (`text`, input), Etiquetas (top tags from
    `facets.tag` as chips). Changes apply immediately (debounced 300 ms for inputs); the footer has
    "Limpiar" and a primary button `cards:catalog.filters.show` (plural, live `meta.total`) that closes the
    sheet and moves focus to the results heading.

S9. Results:
  - Grid: `ul` with `repeat(auto-fill, minmax(118px, 1fr))` below 680 px and `minmax(150px, 1fr)` above. Tile
    = link with `CardImage size="tile" decorative`, owned badge `×N` top-left (`aria-hidden`, plus sr-only
    `cards:catalog.owned`), `BanBadge variant="compact"` top-right, then name (2 lines max), `set_id · #card_id`,
    `DomainPips size={16}`, `PriceTag size="sm"` (7 d trend). Hover lift −4 px and accent border, disabled
    under `prefers-reduced-motion`.
  - List: `ul` of links, each row `CardImage size="thumb" decorative` (40 px wide), name, `set_id · #card_id`,
    translated type line, `DomainPips`, `RarityDot`, `PriceTag` (7 d), owned count, compact ban badge.
  - View choice stored in `localStorage` key `rb_cards_view` (`grid` | `list`; F2-i adds `table`), default grid.

S10. `Pagination` (`src/components/ui/Pagination.tsx`): `nav` with `aria-label` `common:pagination.label`,
     buttons `common:pagination.prev` / `next` (disabled at the ends; the "previous" arrow points left) and the
     text `common:pagination.page`; props `page`, `pages`, `onChange`. After a change the catalog scrolls to
     the results heading and focuses it.

S11. `FilterChip` (`src/components/ui/FilterChip.tsx`): `button` with `aria-pressed`, optional `count`
     (rendered `(n)`), optional `color` (CSS variable for domain/rarity tint, text contrast ≥ 4.5:1), optional
     `onRemove` variant (shows ×, `aria-label` given by the caller). `ChipGroup` = `role="group"` +
     `aria-labelledby` its legend.

S12. States: first load → 12 skeleton tiles and the label `cards:catalog.loading`; refetch → previous
     results dimmed with `aria-busy`; empty → `EmptyState` `cards:catalog.empty.title` / `body` + "Limpiar
     filtros"; error → `ErrorState` (`translateError`) with retry. `useDocumentTitle(cards:catalog.title)`.

S13. Nav: `navRegistry.ts` entry `cards` becomes `{status: 'spa', to: '/cards'}` (same icon and placements).
     `legacy-routes.json` keeps `cards` (TestLegacyRoutes unchanged). The Home hub tile and the bottom nav
     open the SPA catalog.

## API / data contract

Consumes `GET /meta/game` and `GET /cards` (F2-b, F2-c). No backend change.

## UI

Route `/riftbound/app/cards` (+ child detail). Mobile < 860: S7-S9 one column, detail full screen.
860-1239: same catalog, detail as modal (2-column detail). ≥ 1240: this unit keeps the one-column catalog
capped at `--maxw`; F2-i replaces it with the sidebar layout.

Strings — `cards.json` (add under `catalog`) and `common.json` (add `pagination`):

| Key | es | en |
|---|---|---|
| `catalog.title` | Cartas | Cards |
| `catalog.count_one` / `_other` | {{count}} carta / {{count}} cartas | {{count}} card / {{count}} cards |
| `catalog.classic` | Versión clásica | Classic version |
| `catalog.search.label` / `placeholder` | Buscar cartas / Nombre, etiqueta o número | Search cards / Name, tag or number |
| `catalog.filters.open` / `title` | Filtros / Filtros | Filters / Filters |
| `catalog.filters.active_one` / `_other` | {{count}} filtro activo / {{count}} filtros activos | {{count}} active filter / {{count}} active filters |
| `catalog.filters.clear` / `clearAll` | Limpiar / Limpiar filtros | Clear / Clear filters |
| `catalog.filters.show_one` / `_other` | Ver {{count}} carta / Ver {{count}} cartas | Show {{count}} card / Show {{count}} cards |
| `catalog.filters.remove` | Quitar filtro {{label}} | Remove filter {{label}} |
| `catalog.facet.set` / `domain` / `type` / `supertype` / `rarity` | Set / Dominio / Tipo / Supertipo / Rareza | Set / Domain / Type / Supertype / Rarity |
| `catalog.facet.domainMatch` / `.any` / `.all` / `.subset` | Coincidencia / Alguno / Todos / Solo estos | Match / Any / All / Only these |
| `catalog.facet.energy` / `power` / `might` / `price` | Coste de energía / Poder / Fuerza / Precio (€) | Energy cost / Power / Might / Price (€) |
| `catalog.facet.min` / `max` | Mín. / Máx. | Min / Max |
| `catalog.facet.owned` / `.any` / `.owned` / `.missing` | Colección / Todas / Las tengo / Me faltan | Collection / All / Owned / Missing |
| `catalog.facet.banned` / `.none` / `.1v1` / `.2v2` / `.any` | Baneos / Todas / Baneadas en 1v1 / Baneadas en 2v2 / Baneadas en algún modo | Bans / All / Banned in 1v1 / Banned in 2v2 / Banned in any mode |
| `catalog.facet.baseOnly` / `text` / `tags` | Solo versión base / Texto de la carta / Etiquetas | Base printing only / Card text / Tags |
| `catalog.chip.min` / `max` | {{label}} ≥ {{value}} / {{label}} ≤ {{value}} | {{label}} ≥ {{value}} / {{label}} ≤ {{value}} |
| `catalog.sort.label` / `dirLabel` | Ordenar por / Orden descendente | Sort by / Descending order |
| `catalog.sort.number` / `name` / `price` / `trend_7d` / `trend_30d` / `rarity` / `energy` / `power` / `might` | Número / Nombre / Precio / Variación 7 d / Variación 30 d / Rareza / Energía / Poder / Fuerza | Number / Name / Price / 7-day change / 30-day change / Rarity / Energy / Power / Might |
| `catalog.view.label` / `grid` / `list` / `table` | Vista / Cuadrícula / Lista / Tabla | View / Grid / List / Table |
| `catalog.owned` | Tienes {{count}} | You have {{count}} |
| `catalog.results` / `loading` | Resultados / Cargando cartas | Results / Loading cards |
| `catalog.empty.title` / `body` | Ninguna carta coincide con los filtros / Prueba con menos filtros o con otra búsqueda. | No card matches the filters / Try fewer filters or another search. |
| `common:pagination.label` / `prev` / `next` | Paginación / Anterior / Siguiente | Pagination / Previous / Next |
| `common:pagination.page` | Página {{page}} de {{pages}} | Page {{page}} of {{pages}} |

## Acceptance criteria

- [ ] AC1 `src/api/client.test.ts`: `requestWithMeta` returns data and meta; error, 401 and CSRF-retry paths shared with `request` (S1).
- [ ] AC2 `src/catalog/params.test.ts`: parse defaults/invalid fallbacks, canonical serialization and round trip, page reset rule (S3).
- [ ] AC3 `src/catalog/CatalogPage.test.tsx` at 390 px: list from MSW; search debounce writes `q` with replace; sheet groups, counts and dimmed zero options, immediate apply, "Ver N cartas" closes and focuses results; chips removal and "Limpiar filtros"; sort and direction; view toggle persisted in `rb_cards_view`; pagination focus; S12 states (S5, S7-S9, S12).
- [ ] AC4 `src/catalog/CatalogPage.test.tsx` routing: tile href keeps the search string; at 390 px the detail replaces the catalog and back restores it; at 1024 px the detail is a modal over the catalog with siblings (←/→ moves through the page) and close returns to `/cards?…` (S6).
- [ ] AC5 `src/components/ui/Pagination.test.tsx`, `src/components/ui/FilterChip.test.tsx` (S10, S11).
- [ ] AC6 `src/shell/navRegistry.test.tsx`: `cards` is `spa` at `/cards`; HomeHub and bottom nav links point to the SPA route (S13).
- [ ] AC7 Axe: catalog at 390 px (sheet closed and open) and 1024 px with the modal open: no violations.
- [ ] AC8 Full lanes green: `venv/bin/pytest`; `cd frontend && npm run lint && npm run typecheck && npx vitest run && npm run build && npm run check:dist`
- [ ] AC9 `docs/knowledge/state.md` updated (what changed, PR number placeholder, new follow-ups)
- [ ] AC10 `docs/frontend.md` "Catalog" section updated (URL parameters, routing/presentation, nav flip); `AGENTS.md` mentions the catalog route.

## Delivery

- Conventional Commits; commit messages end with the attribution lines the session supplies.
- Suggested slices: (1) client + params + queries, (2) primitives + results + pagination, (3) sheet + chips + routing + nav flip.
- Push and PR only when the user says so. PR title: `feat(catalog): catalog page with filters and nav flip (F2 unit h)`.
  PR body: summary, specs → tests map (S# → test file::name), screenshots (390 px with the sheet, 1024 px with the
  modal), manual checks, rollback (revert restores the legacy nav entry).
- Never merge. The user merges.

## After merge (user asks gentle-shell, or does it)

- Deploy to dev with `docs/knowledge/ops-runbook.md` (frontend build only).
- Live checks: Home hub "Cartas" opens `/riftbound/app/cards`; filtering by a domain updates the URL; the
  "Versión clásica" link opens the Jinja catalog.
- Manual checks for the user (phone and desktop): search a card by name and by number, combine two domains
  with "Solo estos", filter "Me faltan", open a card and go back (filters and scroll kept), share a filtered
  URL and open it in another browser tab.

## Open questions

- CONFIRM D-F2-11: the `sets` nav entry stays legacy until F10.
- CONFIRM D-F2-13: grid by default, last view remembered per device, 48 per page below 1240 px, sort by number.
