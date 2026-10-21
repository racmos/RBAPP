# F3: Collection — phase spec
Status: planned · Depends on: F2 (CardSummary, `/meta/game`, `CardCombobox`, offline read cache, catalog detail "Mis copias") · Source: roadmap §5 (F3), design-handoff §3.6, §3.13, §5.7, §6 (20, 21, 32, 34), §7.2 V1-V2, §7.3 D1, §7.4 A19, §7.5 R3/R6, §9 (F3), §10 (1, 11), `docs/knowledge/product.md` "Scope by phase"

## Goal

Every user manages their collection in the React app on phone and desktop: a grouped table/grid of what
they own, fast add with the card search, inline and bulk edits, an optional purchase price per line, the
selling model (how many copies of a line are for sale, a selling switch, sub-lines with their own price,
condition and language), server-side CSV export (own format and Cardmarket), a CSV import wizard and a
wishlist. Desktop shows purchase price, P/L, 7-day change and a summary band; the collection stays readable
offline. F7 (sales) and F5 (deck vs collection) build on the data defined here.

## Current state

| Area | What exists today |
|---|---|
| Model | `RbCollection` (`rbcollection`, `app/models/collection.py`): synthetic PK `rbcol_id` (BIGINT), `rbcol_rbset_id`, `rbcol_rbcar_id` (FK to `rbcards`), `rbcol_foil` 'S'/'N', `rbcol_user` (**username**, FK to `rbusers.username`, ON UPDATE CASCADE), `rbcol_quantity` INT ≥ 1, `rbcol_selling` CHECK IN ('Y','N','S'), `rbcol_playset` NULL or 1-3 (copies kept), `rbcol_sell_price` NUMERIC NULL, `rbcol_condition` (MT, NM, EX, GD, LP, PL, PO), `rbcol_language` free text ≤ 40, `rbcol_chadat`. Indexes `idx_rbcollection_selling`, `idx_rbcollection_user_card_foil`. Several rows per (user, card, foil) are allowed (differ in condition/language/price). |
| Rules in code | Add merges into an exact duplicate (8 fields NULL-safe, atomic `quantity + n`, QTY-3); foil refused for Rare/Epic/Showcase; `update_playset` and `bulk_apply` set `selling='Y'` when `qty > playset` (foil rows get the playset first); export quantity = `qty − playset`. Contract: `openspec/specs/collection-quantity/spec.md` (QTY-1..4). |
| Routes (Jinja + flat JSON, all U) | `GET /riftbound/collection` (page), `POST …/add`, `/update_quantity`, `/delete`, `/update_selling`, `/update_playset`, `/update_sell_price`, `/update_condition`, `/update_language`, `/bulk_apply`, `/bulk_delete`, `GET …/api/sets`, `GET …/api/cards` (picker), `POST …/import_csv` (`set;card;foil;qty`, overwrites qty), `POST …/export_csv` (Cardmarket `name,language,quantity,price`, QUOTE_ALL, BOM, only `selling='Y'`, one set + rarity). |
| Prices | `_collection_query()` joins the canonical product and latest `rbcm_price`; `resolve_price` (PRC-1). F2-b adds `price_summaries` (batch, trends). |
| Frontend | Nav entry `collection` is `legacy`. F2 provides card atoms, `CardCombobox`, `/cards` detail with read-only "Mis copias" linking to the Jinja collection, read cache `rb-api-catalog`. Prefs `collection_view` (`table`/`grid`, Auto = grid < 860, table above). |
| Tests | `tests/test_collection_*.py` (merge, foil, quantity), `tests/test_authz_matrix.py` (`collection.*` U). |

## Scope

In: data changes (purchase price, sell quantity, selling switch, playset mapping); collection read/write
API v1 (grouped lines, totals, filters, sort, pagination, split into sub-lines, bulk edit); export (RBAPP,
Cardmarket); import wizard (preview + commit; RBAPP and Cardmarket first, other formats when samples
arrive); wishlist (table, API, UI, "add to wishlist" in the card detail); React collection screens (mobile,
desktop, wide); offline read of the collection; nav flip.

Out: sales records and stock deduction (F7); price alerts / watchlist (F4); deck vs collection (F5);
removing the Jinja collection or `rbcol_playset` (F11).

## Decisions already taken

- Purchase price optional per line; selling model = bulk "copies to sell" + selling switch + expandable
  sub-lines with their own price/condition/language, built on the synthetic `rbcol_id` rows (product.md F3).
- CSV import wizard formats: own RBAPP, Cardmarket export, riftdecks, Piltover Archive, other apps; ask the
  owner for sample files when the phase starts (product.md F3, roadmap §8).
- Defaults: mobile compact + grid, desktop regular + table, orange accent (product.md; F1 prefs Auto).
- Default sell price when switching on selling without a price = market × 1.05, 2 decimals (design-handoff
  §5.7; F7 relies on it).
- Destructive actions need `ConfirmDialog` + undo toast; selection is scoped to the visible filtered set
  (design-handoff §7.3 D1).
- F7 consumes, per line: `id`, card key, `foil`, `qty`, `condition`, `language`, `purchase_price` (EUR per
  unit, nullable), `selling` (bool), `sell_qty` (0..qty), `sell_price` (EUR per unit, nullable), and
  `PATCH /collection/{id}` for `selling`, `sell_qty`, `sell_price` (F7 phase spec "Consumed contracts").
- Conventions for this and later phases: new tables reference `rbusers.id` (like `rbuserprefs`), not the
  username; migrations take the next free revision number after the F2 ones (`0007`, `0008`).

## Requirements

### Data
- **F3-R1** Add `rbcol_purchase_price` NUMERIC(10,2) NULL CHECK ≥ 0 and `rbcol_sell_qty` INT NOT NULL DEFAULT 0 with CHECK `0 <= rbcol_sell_qty <= rbcol_quantity`. (F3-a)
- **F3-R2** `rbcol_selling` normalized to `Y`/`N` (`S` → `Y`), CHECK narrowed to `('Y','N')`; the API exposes a boolean. (F3-a)
- **F3-R3** Backfill `sell_qty` from the legacy fields (D-F3-1): playset set → `max(0, qty − playset)`; else selling `Y` → `qty`; else 0. `rbcol_playset` stays (deprecated, still written by Jinja). (F3-a)
- **F3-R4** Legacy Jinja routes keep `sell_qty` consistent: `update_quantity`, `update_playset`, `bulk_apply` recompute it with the R3 rule; Jinja `export_csv` uses `sell_qty`. (F3-a)
- **F3-R5** New table `rbwishlist` (user id FK, card by name with optional printing, qty wanted, foil preference, max price, note). (F3-f)
- **F3-R6** Exact-duplicate merge on add includes `purchase_price` in the key (lots bought at different prices stay separate). (F3-c)

### API
- **F3-R7** `GET /collection` returns groups (one per printing + foil) with their lines (sub-lines), card summary, market price, P/L and totals in `meta`. (F3-b)
- **F3-R8** `POST /collection`, `PATCH /collection/{id}`, `DELETE /collection/{id}`, `POST /collection/{id}/split`, `POST /collection/bulk` — all scoped to the current user, all-or-nothing. (F3-c)
- **F3-R9** `GET /collection/export?format=rbapp|cardmarket` + the list filters; CSV UTF-8 with BOM. (F3-d)
- **F3-R10** `POST /collection/import/preview` and `/import/commit` (formats `rbapp`, `cardmarket`; others after samples). (F3-e)
- **F3-R11** `GET/POST /wishlist`, `PATCH/DELETE /wishlist/{id}`. (F3-f)
- **F3-R12** `GET /meta/game` adds `conditions` (`MT, NM, EX, GD, LP, PL, PO`, ordered best → worst) and `languages` (D-F3-4). (F3-b)
- **F3-R13** `CardDetail.my_lines` gains `purchase_price`, `sell_qty`; `CardSummary.owned` unchanged. (F3-b)

### UI mobile (< 860)
- **F3-R14** `/collection`: summary strip (copies, unique, value), search + filter sheet, grid (tile with `N×`, foil, selling tag, price) or card list; tap → line sheet with inline edits (qty stepper, condition, language, purchase price, selling switch + sell qty + sell price), split, delete with confirm + undo. (F3-g)
- **F3-R15** Add flow: floating "Añadir" → sheet with `CardCombobox`, foil, qty, condition, language, purchase price, selling. (F3-g)

### UI desktop (≥ 1240) / wide (≥ 1600)
- **F3-R16** ≥ 1240: facet sidebar; table grouped by card with expand arrow for sub-lines; columns image, set, #, name, foil, qty, sell qty, selling, sell price, condition, language, purchase, market, P/L € and %, 7 d, updated; selection scoped to the filtered set with "select all N filtered"; bulk bar (condition, language, selling, sell qty rule, sell price rule, purchase price, delete). Summary band: value, cost, P/L, lines, unique, value on sale, % foil. (F3-h)
- **F3-R17** ≥ 1600: right panel with the selected group (price chart 30 d, all lines, decks using it). (F3-h)

### Import / export / wishlist UI
- **F3-R18** Import wizard `/collection/import`: upload or paste → detected format (overridable) → preview table with per-row status and resolution → mode (add / replace quantities) → commit → result summary. (F3-i)
- **F3-R19** Export dialog: format, scope (all / current filters / only lines on sale), download. (F3-i)
- **F3-R20** `/collection/wishlist` (tab of the collection): list/table with owned vs wanted, market vs max price; "Añadir a deseos" in the card detail. (F3-j)

### Offline
- **F3-R21** Read cache `rb-api-collection` (NetworkFirst 4 s, 200 entries, 14 days) for `GET /collection` and `GET /wishlist`; purged with the user caches; every edit control disabled offline. (F3-k)

### i18n / a11y
- **F3-R22** Namespace `collection`; conditions and languages translated in `enums` (`condition.NM` = "Casi nueva (NM)"…). Steppers have names and live value; switches `role="switch"`; tables have caption, `scope`, `aria-sort`; row checkboxes named; "select all" explicit. (F3-g..j)

### Security / authz / concurrency
- **F3-R23** Every new rule U in `tests/test_authz_matrix.py`; ids from the client are always filtered by the current user (another user's id → 404). (F3-b..f)
- **F3-R24** Quantity changes are atomic in SQL; `PATCH` accepts optional `if_updated_at` and answers 409 `stale_line` when the row changed meanwhile (two tabs). (F3-c)

### Performance
- **F3-R25** `GET /collection` p95 < 300 ms for 5 000 lines; ≤ 10 SQL statements per request; export streams. (F3-b, F3-d)

## Data model changes

| Change | Detail | Migration (next free revision) | Backfill / downgrade | Risk |
|---|---|---|---|---|
| `rbcollection` columns | `rbcol_purchase_price` NUMERIC(10,2) NULL CHECK ≥ 0 (`rbcollection_purchase_price_chk`); `rbcol_sell_qty` INT NOT NULL DEFAULT 0 CHECK `rbcol_sell_qty BETWEEN 0 AND rbcol_quantity` (`rbcollection_sell_qty_chk`) | `00NN_collection_selling` | R3 backfill; `S` → `Y`; downgrade drops the columns and restores the CHECK with `S` | Medium: table rebuild on SQLite; CHECK on existing data (preflight: abort listing ids if any row would fail) |
| New `rbwishlist` | `rbwsh_id` BIGINT PK; `rbwsh_user_id` INT NOT NULL FK `rbusers.id` ON DELETE CASCADE; `rbwsh_name_key` VARCHAR(200) NOT NULL; `rbwsh_name` VARCHAR(200) NOT NULL; `rbwsh_rbset_id`, `rbwsh_rbcar_id` TEXT NULL (both or neither; NULL = any printing); `rbwsh_foil` VARCHAR(3) NOT NULL DEFAULT 'any' CHECK IN ('any','N','S'); `rbwsh_qty` SMALLINT NOT NULL DEFAULT 1 CHECK 1..99; `rbwsh_max_price` NUMERIC(10,2) NULL; `rbwsh_note` VARCHAR(200) NULL; `rbwsh_created_at`, `rbwsh_updated_at`. UNIQUE (`user_id`, `name_key`, `rbset_id`, `rbcar_id`, `foil`) — NULL-safe via a computed key column `rbwsh_target` (`'*'` or `SET-ID`) | `00NN_wishlist` | none; downgrade drops | Low |

`rbcollection.rbcol_user` stays a username FK (moving it to the user id is out of scope; D-F3-6).

## API

All `/riftbound/api/v1`, U. `CollectionLine`:
`{id, foil, qty, condition, language, purchase_price, selling, sell_qty, sell_price, updated_at, market, value, pl_abs, pl_pct}`
(`market` = PRC-1 unit price for the line's foil; `value` = market × qty; `pl_*` only when `purchase_price` is set).
`CollectionGroup`: `{key: "OGN-79:N", card: CardSummary, foil, qty, sell_qty, value, lines: CollectionLine[]}`.

| Method | Path | Purpose | Unit |
|---|---|---|---|
| GET | `/collection` | Params: `q`, `set[]`, `domain[]`, `type[]`, `rarity[]`, `foil=any\|foil\|nonfoil`, `selling=any\|yes\|no`, `condition[]`, `language[]`, `has_purchase=any\|yes\|no`, `sort=number\|name\|price\|qty\|value\|pl\|trend_7d\|updated\|rarity`, `dir`, `page`, `per_page` (25-200, default 50). `data.items: CollectionGroup[]`; `meta: {page, per_page, total_groups, pages, totals{lines, qty, unique, value, cost, pl, selling_value, foil_pct}, facets, price_as_of}` | F3-b |
| POST | `/collection` | `{set_id, card_id, foil, qty, condition?, language?, purchase_price?, selling?, sell_qty?, sell_price?}` → 201 `{line, merged}` | F3-c |
| PATCH | `/collection/{id}` | Any of `qty, condition, language, purchase_price, selling, sell_qty, sell_price, if_updated_at`; `selling: true` without price fills market × 1.05; `qty` < `sell_qty` lowers `sell_qty` | F3-c |
| DELETE | `/collection/{id}` | 200 `{deleted: {...line}}` (enough for undo = POST again) | F3-c |
| POST | `/collection/{id}/split` | `{qty, condition?, language?, sell_price?, selling?, purchase_price?}` moves `qty` copies to a new (or identical existing) row; must leave ≥ 1 | F3-c |
| POST | `/collection/bulk` | `{ids[] ≤ 1000, set: {condition?, language?, selling?, sell_qty_rule?: "all"\|"none"\|"keep_n", keep?: 1..3, sell_price?, purchase_price?}}` or `{ids, delete: true}`; all-or-nothing | F3-c |
| GET | `/collection/export` | `format=rbapp\|cardmarket`, list filters, `only_selling=true` → `text/csv` attachment, BOM | F3-d |
| POST | `/collection/import/preview` | `{text, format?: auto\|rbapp\|cardmarket}` (≤ 2 MB, ≤ 10 000 rows) → `{format, rows[{line, status: ok\|warning\|error, reason_code?, card?, foil, qty, condition, language, purchase_price}], summary}` + `preview_id` (kept 30 min server-side, D-F3-3) | F3-e |
| POST | `/collection/import/commit` | `{preview_id, mode: add\|replace}` → `{created, merged, replaced, skipped}` | F3-e |
| GET/POST | `/wishlist` | list (with `owned` and `market`) / create | F3-f |
| PATCH/DELETE | `/wishlist/{id}` | edit / remove | F3-f |

New error codes (enum + both `errors.json` + contract test): `foil_not_allowed` (400, card cannot be foil),
`insufficient_quantity` (409, `params.available`; split or bulk sell qty beyond `qty` — F7 reuses the same
code for sales, `params.index`), `stale_line` (409, PATCH with an outdated `if_updated_at`),
`already_exists` (409, wishlist duplicate; F5 reuses it for deck names), `import_expired` (410, unknown or
expired `preview_id`), `import_format_unknown` (400, auto-detection failed).

## UI

| Route | Mobile < 860 | Desktop ≥ 1240 | Wide ≥ 1600 |
|---|---|---|---|
| `/collection` | Summary strip, search + filter sheet, grid (prefs Auto) or card list; FAB "Añadir"; line sheet for edits | Sidebar facets, grouped table with sub-lines, bulk bar, summary band, add drawer | + right panel of the selected group |
| `/collection/import` | Stepper wizard, one step per screen | Wizard with preview table full width | same |
| `/collection/wishlist` | List with owned/wanted and price vs max | Table (+ sidebar filters) | + card preview |

States: loading skeletons, empty ("Tu colección está vacía" + Añadir / Importar), error, offline (cached
view read-only, edit controls disabled with a hint). Components to port/build (design-handoff §2.5, §9 F3):
`Stepper`, `DataTable` (grouped rows, sticky header below the topbar), `BulkBar`, `ConfirmDialog` + undo
toast, `LineSheet`, `ImportWizard`. Nav: `collection` → `spa` `/collection`; `legacy-routes.json` keeps it;
"Versión clásica" link; the card detail's "Mis copias" links to `/collection?q=<card key>` (in-app).

## Units

| ID | Title | Depends on | Size | Risk | Summary |
|---|---|---|---|---|---|
| F3-a | Collection data: purchase price, sell qty | F2 done | ~450 | items 1, 3 | Migration + backfill + preflight, model, legacy routes keep `sell_qty` in sync, Jinja export uses it |
| F3-b | Collection read API | F3-a | ~550 | item 3 | `GET /collection` groups/lines/totals/facets/sort, `/meta/game` conditions + languages, `my_lines` fields |
| F3-c | Collection write API | F3-b | ~600 | items 3, 4 | POST/PATCH/DELETE/split/bulk, merge key, ×1.05 default, `stale_line`, `insufficient_quantity`, `foil_not_allowed` |
| F3-d | Export API | F3-b | ~350 | item 3 | RBAPP and Cardmarket CSV (streamed, BOM, filters, only selling) |
| F3-e | Import API | F3-c | ~550 | items 3, 6 | Parsers RBAPP + Cardmarket, auto-detect, preview store, commit add/replace; other formats as follow-up units once samples arrive |
| F3-f | Wishlist data + API | F3-a | ~450 | item 1 | `rbwishlist`, CRUD, `already_exists` |
| F3-g | Collection UI mobile | F3-c | ~650 | none | Route, grid/list, line sheet with inline edits, add sheet, confirm + undo, nav flip |
| F3-h | Collection UI desktop/wide | F3-g | ~650 | none | Sidebar, grouped table with sub-lines, bulk bar, summary band, wide panel |
| F3-i | Import wizard + export dialog | F3-d, F3-e, F3-g | ~600 | none | Wizard steps, preview table, export dialog |
| F3-j | Wishlist UI | F3-f, F3-g | ~450 | none | `/collection/wishlist`, add from card detail |
| F3-k | Offline collection | F3-h | ~250 | items 5, 6 | `rb-api-collection` runtime cache, purge, offline disabled edits |

## Open decisions

| ID | Question | Options | Recommendation | Blocks |
|---|---|---|---|---|
| D-F3-1 | How does `rbcol_playset` (copies kept) map to `sell_qty` (design-handoff §10-1)? | (a) R3 rule, keep playset deprecated; (b) drop playset now | (a). `sell_qty = qty − playset` when playset is set, else `qty` if selling, else 0. Export uses `sell_qty` | F3-a |
| D-F3-2 | Sample files for import formats | — | Owner sends one real export from Cardmarket, riftdecks, Piltover Archive and any other app before F3-e; RBAPP format = `set_id,card_id,name,foil,qty,condition,language,purchase_price,selling,sell_qty,sell_price` (header row, comma, UTF-8 BOM) | F3-d, F3-e |
| D-F3-3 | Where does the import preview live between preview and commit? | DB table / signed client payload / in-memory | Small table `rbimportpreviews` (user id, JSON rows, expires 30 min) — survives the 3 Gunicorn workers; in-memory would not | F3-e |
| D-F3-4 | Language list (design-handoff §10-11) | 5 prototype languages / Cardmarket list | Cardmarket's: English, French, German, Spanish, Italian, Simplified Chinese, Japanese, Portuguese, Russian, Korean, Traditional Chinese; existing free-text values kept and shown as-is | F3-b |
| D-F3-5 | Add merges into identical lines? | merge / always new line (prototype) | Merge (current behaviour) with `purchase_price` in the key; the response says `merged` and the toast says so | F3-c |
| D-F3-6 | Move `rbcol_user` from username to user id? | now / later / never | Not in F3 (big table rebuild, Jinja depends on it); revisit in F11 when Jinja goes | — |
| D-F3-7 | Wishlist vs F4 watchlist | one table / two | Two concepts: wishlist (cards I want, optional max price) in F3; F4 alerts can target wishlist entries ("avísame cuando baje de mi máximo") and owned cards | F3-f, F4-g |
| D-F3-8 | Undo window and bulk limits | — | Undo toast 8 s re-creates deleted lines; bulk ≤ 1 000 ids; "select all filtered" sends the filter, not ids, when > 1 000 (follow-up) | F3-c, F3-g |

## Risks and notes

- The Jinja collection stays usable until F11 and writes the same rows; R4 keeps `sell_qty` coherent. A Jinja
  edit and an app edit at the same time are covered by atomic SQL + `stale_line`.
- F7 depends on the line contract above; changing a field name later breaks F7 — treat `CollectionLine` as
  a contract in `docs/api.md`.
- Import of large files: parse in a streaming way, cap rows, never trust card ids (resolve against `rbcards`).
- CSV injection: exported text cells starting with `=`, `+`, `-`, `@` are prefixed with `'`.
- The Cardmarket export format is the one the Jinja export writes today (`name,language,quantity,price`,
  product name when mapped); keep it byte-compatible.
