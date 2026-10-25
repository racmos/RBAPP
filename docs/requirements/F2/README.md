# F2: Catalog — phase spec
Status: planned · Depends on: F1 (units a-f merged; F1-close recommended first) · Order (`docs/knowledge/roadmap.md`): F2-a runs right after F4-a/F4-b and before M-d; F2-b..l run after F13 (Riot sync + catalog admin) · Source: roadmap §5 (F2), design-handoff §2.1-2.4, §3.1, §3.4, §3.5, §3.13, §6 (2, 4, 5, 8, 9, 33), §7 (R2, R5, S3, S5, A5, A13), §9 (F2), §10 (8, 10, 12), `docs/knowledge/product.md`

## Goal

Every signed-in user can browse the whole Riftbound card catalog in the React app: search, filter by facets
with counts, sort, page, switch grid/table, open a card detail with real Cardmarket price history, see their
own copies, other printings, related cards and in which game mode (1v1/2v2) the card is banned. The catalog
and the cards already viewed stay readable offline. On desktop the extra width shows more data (facet
sidebar, more columns, a preview panel on wide screens), never a stretched layout. F2 also creates the
backend pieces later phases build on: the per-mode ban table, the game meta endpoint, the card DTO and the
service-worker read cache.

## Current state

| Area | What exists today |
|---|---|
| Models | `RbSet` (`rbset`: `rbset_id`, `rbset_name`, `rbset_ncard`, `rbset_outdat`), `RbCard` (`rbcards`, PK `rbcar_rbset_id`+`rbcar_id`; text columns `rbcar_domain` = space-separated labels such as `Fury Chaos`, `rbcar_type` = supertype + type such as `Champion Unit`, `Signature Spell`, `Token Unit`, `Basic Rune`, `Legend`; `rbcar_tags` = comma-separated; `rbcar_energy/power/might` smallint; `rbcar_rarity`; `rbcar_artist`; `rbcar_banned` 'S'/'N'; `image`, `image_url`; property `image_src`) — `app/models/card.py`, `set.py`. Card ids are text: `1`, `79a`, `227s` (showcase), `t03` (token). |
| Prices | Loaded every day by the F4-b job (06:30 Europe/Madrid, retry 08:00), which lands before F2. `rbcm_price` (daily rows per Cardmarket `idProduct`, date text `YYYYMMDD`, `rbprc_low/avg1/avg7/avg30/trend` and `_foil` variants, `rbprc_low_ex`), `rbcm_product_card_map` (product → card + foil `N`/`S`/NULL) — `app/models/cardmarket.py`. PK of `rbcm_price` is (`rbprc_date`, `rbprc_id_product`); no index starts with the product. |
| Pricing service | `app/services/pricing.py`: `resolve_price` (chain PRC-1: premium rarity or foil → `avg7_foil → avg7 → low_foil → low`; otherwise `avg7 → avg7_foil → low → low_foil`; 0/NULL = missing), `canonical_product_id`, `latest_price_for_card`. Contract: `openspec/specs/price-resolution/spec.md`. |
| Foil rules | Collection add refuses foil for Rare/Epic/Showcase (`app/routes/domains/collection.py`); the matcher gives Basic Runes one slot and never foil, common/uncommon two slots N/S (`app/services/cardmarket_matcher.py`). |
| Images | `RbCard.image_src` → `/riftbound/static/images/cards/<prefix folder>/<image>` (IMG-1, `openspec/specs/card-images/spec.md`); PNG 352×492, about 205 KB each No thumbnails. Since M-d they live outside git in the `CARD_IMAGES_DIR` data directory and `card_images.serve` serves them at the same URLs. |
| Routes | Jinja catalog `GET /riftbound/card` (`cards.cards`, U; filters by name/set/id/domain/type/tags/rarity/ability/banned/energy/power/might; sorts with `regexp_replace`, which SQLite only has through a test shim registered in `app/__init__.py`; the id filter uses the PostgreSQL `~` operator), admin `POST /riftbound/card/add`, `/update/<set>/<card>`, `/upload_image`; Jinja sets page `GET /riftbound/set` (U) + admin add/update; `GET /riftbound/collection/api/cards` (U, picker search, flat JSON). No catalog endpoint in API v1. |
| API v1 | `app/api/v1/{auth,me,meta}.py`: `GET /health`, `GET /meta/config`, auth, `GET/PATCH /me/prefs`. Envelope `ok()/fail()`, error codes `app/api/error_codes.py`. `app/schemas/validation.py` has an unused `validate_query` (no list params, no error codes). |
| Bans | Only `rbcar_banned` (single flag). The Riot scraper rewrites every field of an existing card, so it resets `rbcar_banned` to `'N'` on every run (`app/services/riot_scraper.py`, step 5). The Jinja admin form edits the flag. |
| CLI | `flask schema ...`, `flask users ...` (`app/cli/`). |
| Frontend | Nav registry `frontend/src/shell/navRegistry.ts`: `cards` and `sets` are `legacy`. Primitives in `src/components/ui/` (Badge, Button, Checkbox, ConfirmDialog, EmptyState, ErrorState, Field, Icon, Input, Modal/Sheet (no size variants), OfflineBanner, PageHeader, Panel, SegmentedControl, Select, Skeleton, Slider, Switch, Toast). No DomainPips, RarityDot, CardImage, Pagination, DataTable, chips, charts. `src/lib/format.ts` (`formatMoney`, `formatDate`, `formatNumber`). Breakpoints `src/lib/breakpoints.ts`: `sm 680, md 860, lg 960, xl 1240, 2xl 1600`. |
| PWA | `frontend/pwa-options.ts`: precache of the shell only, **no runtime caching**; `scripts/check-dist.mjs` fails the build if any `registerRoute` other than the navigation route exists or the precache lists an API URL. F1 spec PWA-1 says "MUST NOT register any runtime caching" — F2 supersedes that clause. TanStack Query uses the default `networkMode: 'online'` (queries pause while offline). |
| Tests | Since M-a only `tests/test_authz_matrix.py` (every rule P/U/A) and the startup smoke tests (`tests/test_smoke.py`, `frontend/src/app/smoke.test.tsx`) remain; a unit re-creates the guard of the area it touches in its smallest form (migration round-trip + drift test with `tests/migration_helpers.py`, ES/EN parity, error-code catalog test, legacy-routes check). |

## Scope

In:
- Per-mode ban table + migration + initial data from the official ban list + `flask bans` CLI + read API;
  bans exposed on cards.
- `GET /meta/game` (enums, sets, price freshness, empty `rules` object for F5).
- Card DTO (`CardSummary`, `CardDetail`), catalog list with filters, facets, sort, pagination; card detail;
  price history; my copies (read-only); printings; related; in my decks (read-only).
- React catalog `/cards`, card detail `/cards/:setId/:cardId`, card UI kit, `PriceChart`, `Sparkline`,
  `CardCombobox` + desktop global search.
- Service-worker read cache for catalog API GETs and card images; offline states.
- Optional: card thumbnails (WebP derivatives) — see D-F2-10.
- Nav: `cards` flips to `spa`; the Jinja catalog stays reachable.

Out:
- Editing collection lines from the card detail (F3: the detail links to the collection instead).
- Wishlist / watchlist buttons (F3 / F4). Deck legality (F5). Ban admin UI (F10). Card/set editing and the
  Riot sync (F13).
- Full offline catalog snapshot in IndexedDB (D-F2-8). Translating card names/abilities (they are data).
- Removing `rbcar_banned` (F11, with Jinja).

## Decisions already taken

- Bans are per mode (`1v1`, `2v2`) and apply to the card **name** (all printings); the UI names the mode;
  the single `rbcar_banned` column is not enough (product.md "Game rules"; design-handoff §6-2).
- **D-F2-2** (owner, 2026-10-22): bans per card name (all printings), two modes 1v1 and 2v2. The legacy
  `rbcar_banned` flag is **not** used as a source (the scraper resets it); the initial data comes from the
  official ban list the owner provides (cards and mode; owner input pending, needed for F2-a).
- **D-F2-1** (owner, 2026-10-22): the implementer queries the dev PostgreSQL database read-only to get the
  real values of `rbcar_domain`, `rbcar_type` and `rbcar_rarity` (the data there is real); the F2-b
  constants follow the result.
- **D-F2-12** (owner, 2026-10-22): the Spanish names of the enum values are taken by the implementer from
  the official Spanish card gallery (`es-es`); the owner is asked only for a value that is not there. The
  dev database holds the English values (the scraper reads `en-us`). Card names and abilities are data and
  stay untranslated.
- Order (owner, 2026-10-22): F2-a (bans) runs right after F4-a/F4-b; M-d (card images out of git) and F13
  (Riot sync + catalog admin) come next; the rest of F2 follows F13.
- Tests (owner, 2026-10-22, unit M-a): the old suites were removed; each F2 unit writes its own tests and
  re-creates the removed guard of the area it touches (see "Current state" → Tests).
- Rule values and enumerations live in the backend and the frontend reads them from the API (product.md).
- Prices: Cardmarket only, EUR only; chain PRC-1 is the single implementation (product.md; price-resolution
  spec). Note: product.md summarises the chain as `avg7_foil → avg7 → low_foil → low`; the code and PRC-1
  apply that order to premium rarities and foil, and `avg7 → avg7_foil → low → low_foil` to non-foil
  common/uncommon. PRC-1 is the contract.
- The catalog comes from the Riot gallery scraper; the prototype CSV is not imported (product.md "Data").
- Images by filename-prefix folder (IMG-1); the card art ratio is 352/492, not 3/4 (design-handoff §0.1-8).
- Offline is read-only from F2; edits need a connection (product.md).
- Coexistence: the PWA takes over one module per phase; the Jinja page stays linked until F11.
- Desktop shows more data: sidebar facets ≥ 1240, preview panel ≥ 1600 (design-handoff §3.0, §3.4).
- Remove the prototype's estimated prices, "recommended (est.)" and fixed "14 wk" label (design-handoff §3.5).

## Requirements

### Data
- **F2-R1** MUST add table `rbcardbans` (one row per normalized card name and mode) with migration `00NN_card_bans` (next free revision; F4-a's `rbjobs` lands first); reversible. (F2-a)
- **F2-R2** The migration MUST NOT read `rbcar_banned` (owner decision of 2026-10-22, see "Decisions already taken"); the table starts empty and the initial rows come from the official ban list the owner provides, loaded through `flask bans add` (F2-R14) or a one-off import that the F2-a requirement defines. (F2-a)
- **F2-R3** Card name matching for bans and printings MUST use one normalization function (`name_key`). (F2-a)
- **F2-R4** MUST add index `idx_rbcm_price_product_date` on `rbcm_price (rbprc_id_product, rbprc_date)` with migration `00NN_price_product_date_idx` (next free revision). (F2-b)
- **F2-R5** Game enumerations (modes, domains, types, supertypes, rarity order) MUST live in `app/schemas/game_domain.py` only. (F2-a creates it with the modes, F2-b completes it)

### API
- **F2-R6** `GET /meta/game` (P) MUST return modes, domains, types, supertypes, rarities, sets, price freshness and a `rules` object (empty until F5). (F2-b)
- **F2-R7** `GET /cards` (U) MUST support the query parameters of the API table below, disjunctive facet counts, sort and pagination in `meta`. (F2-c)
- **F2-R8** `GET /cards/{set_id}/{card_id}` (U) MUST return `CardDetail`; 404 envelope when missing. (F2-d)
- **F2-R9** `GET /cards/{set_id}/{card_id}/prices?range=` (U) MUST return the daily series of the canonical product(s). (F2-d)
- **F2-R10** `GET /bans` (U) MUST list bans, optionally by mode. (F2-a)
- **F2-R11** Every price in the API MUST come from the pricing service (PRC-2); `market_source` names the column used. (F2-b)
- **F2-R12** Query parameters MUST be validated with an upgraded `validate_query` (repeated params, the same error body and codes as `validate_json`). (F2-c)
- **F2-R13** `owned`, `my_lines` and `in_decks` MUST be computed for the current user only. (F2-c, F2-d)

### CLI
- **F2-R14** `flask bans list|add|remove` MUST manage bans until the F10 admin UI; idempotent; names validated against the catalog unless `--force`. (F2-a)
- **F2-R15** (optional, D-F2-10) `flask images thumbs` MUST generate WebP thumbnails; the scraper generates them for new images. (F2-l)

### UI mobile (< 860 px)
- **F2-R16** `/cards`: search, filter sheet, active-filter chips, sort, grid (min 118 px tiles) or list, pagination; filters in the URL. (F2-h)
- **F2-R17** Card detail is a full-screen route with back navigation. (F2-f)

### UI desktop (≥ 1240 px) and wide (≥ 1600 px)
- **F2-R18** ≥ 1240: sticky 280 px facet sidebar with counts; grid of 6-8 columns or a table with energy/power/might, tags, foil price, 7 d / 30 d trend, owned and bans columns; page sizes 48/96/192. (F2-i)
- **F2-R19** ≥ 1600: three columns (facets | results | 380 px preview panel of the selected card). (F2-i)
- **F2-R20** From the catalog at ≥ 860 the detail opens as a large modal over the catalog (3 columns at ≥ 1240) with ←/→ to move through the current page. (F2-f)
- **F2-R21** ≥ 1240: global card search (combobox) in the topbar. (F2-k)

### Offline
- **F2-R22** The service worker MUST cache catalog API GET responses (strategy: D-F2-7) and card images (cache-first, LRU limits: D-F2-9); `check:dist` allows exactly these routes. (F2-j)
- **F2-R23** Catalog queries MUST run with `networkMode: 'offlineFirst'` so cached answers are served offline; uncached views show an offline empty state. (F2-j)
- **F2-R24** User-specific cached API responses MUST be deleted on logout and when another user signs in. (F2-j)

### i18n
- **F2-R25** New namespaces `cards` and `enums`; every enum value shown in the UI comes from `enums` (domains, types, supertypes, rarities, modes); card names and abilities are data and are not translated. (F2-e `enums` and `cards`, extended by f-k)

### a11y
- **F2-R26** Filter chips use `aria-pressed`; the combobox follows the ARIA 1.2 pattern; charts have a text alternative; tiles are links or buttons with accessible names; colour is never the only signal (pips, rarity, trend). Axe clean on every new screen. (F2-e..k)

### Security / authz
- **F2-R27** New rules classified in `tests/test_authz_matrix.py`: `api_v1.meta_game` P; `api_v1.list_cards`, `api_v1.get_card`, `api_v1.get_card_prices`, `api_v1.list_bans` U (CONFIRM D-F2-3). No endpoint accepts a user id. (F2-a..d)

### Performance
- **F2-R28** `GET /cards` p95 < 300 ms and detail < 200 ms on the dev data (all sets, ≥ 1 year of daily prices), measured with `flask shell` timing in the PR. Tile images lazy-load with explicit dimensions (no layout shift). (F2-b, F2-c, F2-e)

## Data model changes

| Change | Detail | Migration | Backfill / downgrade | Risk |
|---|---|---|---|---|
| New table `riftbound.rbcardbans` | `rbban_id` int PK; `rbban_name_key` varchar(200) NOT NULL; `rbban_name` varchar(200) NOT NULL; `rbban_mode` varchar(3) NOT NULL CHECK `IN ('1v1','2v2')` (`rbcardbans_mode_chk`); `rbban_since` date NOT NULL; `rbban_reason` varchar(500) NULL; `rbban_created_at` timestamp NOT NULL default now; UNIQUE (`rbban_name_key`, `rbban_mode`) `rbcardbans_name_mode_key` | `00NN_card_bans` | No backfill: `rbcar_banned` is not a source; the initial rows come from the official ban list after the upgrade (F2-R2); downgrade drops the table (bans added since are lost; `rbcar_banned` is untouched) | Low: new table only |
| Index on `rbcm_price` | `idx_rbcm_price_product_date (rbprc_id_product, rbprc_date)` | `00NN_price_product_date_idx` | Downgrade drops it | Low: build takes seconds; write lock during build (no load runs at deploy time) |
| `rbcar_banned` | Kept, deprecated (code comment). The API ignores it. Removed in F11. | none | — | — |
| Thumbnails (optional) | Files only: `<folder>/<stem>.webp` in the card-image data directory that M-d sets up outside the code tree, never in git | none | — | Low |

## API

All under `/riftbound/api/v1`, envelope `{success, data, meta}`.

| Method | Path | Auth | Purpose | Unit |
|---|---|---|---|---|
| GET | `/meta/game` | P | Modes, domains, types, supertypes, rarities (ordered), sets (ordered by release), price `{currency, provider, updated_on}`, `rules: {}` | F2-b |
| GET | `/cards` | U | Catalog list: `q`, `text`, `set[]`, `domain[]` + `domain_match=any\|all\|subset`, `type[]`, `supertype[]`, `exclude_supertype[]`, `rarity[]`, `tag[]`, `energy_min/max`, `power_min/max`, `might_min/max`, `price_min/max`, `owned=any\|owned\|missing`, `banned_in=1v1\|2v2\|any`, `base_only`, `sort=number\|name\|price\|trend_7d\|trend_30d\|rarity\|energy\|power\|might`, `dir=asc\|desc`, `page`, `per_page` (1-192, default 48). `data.items[]` = `CardSummary`; `meta` = `{page, per_page, total, pages, facets{set, domain, type, supertype, rarity, tag[]}, price_as_of}` | F2-c |
| GET | `/cards/{set_id}/{card_id}` | U | `CardDetail`: summary + ability, artist, set, price detail (raw columns), printings, related (≤ 12), `ban_info[]`, `my_lines[]`, `in_decks[]` | F2-d |
| GET | `/cards/{set_id}/{card_id}/prices` | U | `range=30d\|90d\|1y\|all` (default 90d) → `{range, currency, foilable, points[{date, market, market_foil, low, avg7, avg30}]}` | F2-d |
| GET | `/bans` | U | `mode=1v1\|2v2` optional → `{items[{name, mode, since, reason, printings[{set_id, card_id}]}]}` | F2-a |

`CardSummary` (contract consumed by F3-F6; additive changes only):
`{set_id, card_id, key, number, name, domains[], type, supertype, type_raw, tags[], energy, power, might,
rarity, image_src, image_thumb_src, foilable, is_base, price{market, market_source, market_foil,
market_foil_source, trend_7d_pct, trend_30d_pct, as_of} | null, bans{"1v1": bool, "2v2": bool},
owned{total, foil}}`.

New error codes: **none**. Validation uses `validation_error` with detail codes `out_of_range` /
`invalid_value`; a missing card is the existing 404 envelope (`error: "Not Found"`).

## UI

| Route (basename `/riftbound/app`) | Screen | Mobile < 860 | Tablet 860-1239 | Desktop ≥ 1240 | Wide ≥ 1600 |
|---|---|---|---|---|---|
| `/cards` | Catalog | Header + search + "Filtros" sheet + active chips + sort + grid (min 118 px) / list; pagination; page size 48 | Same, grid min 150 px, table available (fewer columns) | Sticky facet sidebar 280 px + toolbar (count, sort, page size 48/96/192, view) + grid 6-8 cols or full table | Facets \| results (8-10 cols) \| preview panel 380 px of the selected card |
| `/cards/:setId/:cardId` | Card detail | Full-screen page | Modal (2 cols) when opened from the catalog; page on direct load | Modal ≈ 1200 px, 3 cols; ←/→ through the page | Same as desktop |

States for every screen: loading (skeleton tiles/rows), empty ("Ninguna carta coincide…" + clear filters),
error (`ErrorState` + retry), offline-not-cached (`EmptyState` with the offline icon). Components to build
(design-handoff §2, §9-F2): `CardImage` + `CardArtPlaceholder` (§2.2, ratio 352/492), `DomainPips`,
`RarityDot`, `BanBadge`, `PriceTag` (F2-e); `AbilityText`/`parseAbility` (§2.3 grammar, F2-f);
`Sparkline` and `PriceChart` (§2.4: real axes, grid, keyboard tooltip, range selector, `useId` gradient,
F2-g); `FilterChip`/`ChipGroup`, `Pagination` (F2-h); `CardCombobox` (ARIA 1.2, server search, F2-k).
`Modal` gains `size` (F2-f).
Nav: `cards` → `{status: 'spa', to: '/cards'}`; `legacy-routes.json` keeps `cards`; the catalog header
links to the classic page ("Versión clásica"). `sets` stays `legacy` (D-F2-11).

## Units

| ID | Title | Depends on | Size | Risk | Summary |
|---|---|---|---|---|---|
| F2-a | Per-mode card bans | F1 merged, F4-a/F4-b (order), official ban list (owner) | ~550 | items 1, 3 | `rbcardbans` + migration (no backfill) + initial data from the official ban list, `name_key`, `app/services/bans.py`, `flask bans`, `GET /bans`, Jinja catalog reads the ban table |
| F2-b | Game meta, card DTO and price summary | F2-a, M-d, F13 (order) | ~550 | items 1, 3 | `game_domain.py` (values from the read-only dev DB query, Spanish names from `es-es`), card normalization (`app/services/catalog.py`), `resolve_price_with_source`, batch price summaries with 7/30 d trend, index migration, `GET /meta/game`, `docs/api.md` |
| F2-c | Cards list API | F2-b | ~550 | item 3 | `validate_query` upgrade, `GET /cards` filters/facets/sort/pagination, owned, bans |
| F2-d | Card detail and price history API | F2-b (F2-c first) | ~450 | item 3 | `GET /cards/{set}/{id}`, `GET /cards/{set}/{id}/prices` |
| F2-e | Card UI atoms | F2-b (contract) | ~500 | none | `src/components/card/`: `CardImage` + `CardArtPlaceholder`, `DomainPips`, `RarityDot`, `BanBadge`, `PriceTag`; `CardSummary` TS type; `enums` namespace; ESLint boundary |
| F2-f | Card detail screen | F2-d, F2-e | ~650 | none | `src/catalog/`: `/cards/:setId/:cardId` full page (mobile, direct load) and modal over a background route (≥ 860), `AbilityText`, prices block, printings, related, my copies, decks, bans, ←/→, `Modal` size |
| F2-g | Price chart | F2-f | ~500 | none | `src/components/charts/`: `PriceChart` (axes, grid, keyboard tooltip, table alternative), range selector wired to `/prices`, `Sparkline` |
| F2-h | Catalog page (mobile-first core) | F2-c, F2-f | ~650 | none | `/cards` route (catalog in `CardsLayout`, detail as modal over it), `requestWithMeta`, list/meta endpoints, URL state, search, filter sheet with chips, grid/list, sort, pagination, states, nav flip `cards` → `spa` |
| F2-i | Catalog desktop and wide | F2-g, F2-h | ~550 | none | Facet sidebar with counts ≥ 1240, table view with extra columns, page size, remembered view, preview panel ≥ 1600 (with `Sparkline`) |
| F2-j | Offline catalog | F2-i | ~350 | items 5, 6 | Workbox runtime caching, `check:dist`, cache purge on logout/user switch, `offlineFirst` queries, offline states |
| F2-k | Card combobox and global search | F2-c, F2-e, F2-h | ~450 | none | `CardCombobox` (ARIA 1.2, reused by F3/F5), topbar search ≥ 1240, "/" shortcut |
| F2-l | Card thumbnails (optional) | F2-b | ~350 | item 5 | Pillow, `flask images thumbs` (writes to the M-d data directory), scraper hook, `image_thumb_src` |

Order: a runs early (after F4-a/F4-b, before M-d and F13); then, after F13: b → c → d → e → f → g → h → i → j → k. The detail screen (f) lands before the catalog (h) so the
catalog's tiles never link to a missing route; until h flips the nav entry, the detail is reachable only by
URL. l can land any time after b (best before j, so the offline image cache starts with thumbnails). e can
start as soon as b is merged (it codes against the `CardSummary` contract in `docs/api.md` with fixtures).

## Open decisions

| ID | Question | Options | Recommendation | Blocks |
|---|---|---|---|---|
| D-F2-3 | Is the catalog API public or for signed-in users? | P / U | U (as the Jinja catalog). `/meta/game` P (no user data; F5 public deck links need it) | F2-c, F2-d |
| D-F2-4 | Base printing and tokens (design-handoff §10-8) | — | `is_base`: among the printings of a name, those with a purely numeric `card_id`; earliest set release (`rbset_outdat`, NULL last), then set id, then lowest number; if none is numeric, the first by the same order. Tokens (`supertype` Token) are shown and filterable; `exclude_supertype=Token` lets F3/F5 hide them | F2-b |
| D-F2-5 | Which prices does the detail show (design-handoff §10-12)? | Low/Market/High (prototype) vs real columns | "Mercado" (resolved PRC-1 price, with its source), "Mín." (`low`), "Media 30 d" (`avg30`), "Mercado foil" when foilable; trend 7 d and 30 d of the market price. No "High" (Cardmarket has none) | F2-b, F2-f |
| D-F2-6 | Price history ranges | — | `30d`, `90d` (default), `1y`, `all`; the series starts at the first loaded day | F2-d, F2-g |
| D-F2-7 | Service-worker strategy for API GETs. The cross-phase contract says stale-while-revalidate; SWR answers from the cache first, so a refetch right after an edit (F3/F5) shows the old data | SWR / NetworkFirst with timeout | **NetworkFirst, 4 s timeout, fall back to the cache**. Same offline result, no stale reads online. Needs the orchestrator/owner to amend the contract | F2-j (and F3/F5 extensions) |
| D-F2-8 | Offline depth | (a) cache what was viewed; (b) full catalog snapshot in IndexedDB with client-side filtering | (a) in F2; (b) only if the owner needs search offline (it duplicates the filter logic in TS) | F2-j |
| D-F2-9 | Cache budgets (design-handoff §10-10) | — | API 300 entries / 14 days; thumbnails 2 500 / 60 days; full images 300 / 60 days; `purgeOnQuotaError` | F2-j |
| D-F2-10 | Generate WebP thumbnails (adds Pillow)? | yes / no | Yes: a 48-tile page drops from ≈ 10 MB to < 1 MB and offline image caching becomes realistic | F2-l |
| D-F2-11 | Sets nav entry | keep legacy / fold into the catalog | Keep `sets` legacy until the F13 catalog admin (it is mostly the admin editor); the catalog has the set facet | F2-h |
| D-F2-13 | Catalog defaults | — | Grid view by default, last choice remembered per device (`rb_cards_view`); 48 per page (mobile fixed 48); sort `number` asc (set release order, then number) | F2-c, F2-h, F2-i |
| D-F2-14 | Global search in the topbar | F2 / later | F2-k, visible ≥ 1240; "/" focuses it | F2-k |

## Risks and notes

- **Contract change**: F2-j amends F1 PWA-1 ("no runtime caching") and `check:dist`; `docs/frontend.md`
  must be updated in the same PR. F1-close archives PWA-1 as written; F2-j's PR records the amendment.
- **Cache leaks between users**: API responses contain `owned` and `my_lines`; F2-j purges the API cache on
  logout and on a user change. Images are not user data and stay.
- **SQLite vs PostgreSQL**: no `regexp_replace`, `~` or other PostgreSQL-only SQL in the new code (the
  SQLite shim in `app/__init__.py` is for legacy routes only); natural sort is computed in Python (the
  catalog is a few thousand rows). Index migration tested on both.
- **Scraper**: after F2-a the scraper may keep writing `rbcar_banned = 'N'`; harmless because nothing reads
  it. Do not "fix" it by reading the ban table into the column.
- **Jinja coexistence**: the Jinja catalog stays U and working; its banned column switches to the ban table
  (F2-a). The collection add-picker (`/riftbound/collection/api/cards`) is untouched until F3.
- **Price freshness**: the F4-b daily load runs before F2-b, so prices are fresh every day; `price_as_of` /
  `updated_on` let the UI show "Precios a dd/mm"; trends are `null` when there is no row 7/30 days back.
- **Image weight**: without F2-l the grid downloads 352×492 PNGs; tiles must lazy-load and set width/height.
- **`in_decks`** reads the current deck JSON (`main` + `sideboard`, latest `seq` per name); F5 replaces the
  source when decks move to v2 (the field shape stays).
