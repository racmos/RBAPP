# F7: Sales — phase spec

Status: planned · Depends on: F3 (purchase price, selling model, collection API), F4 (daily Cardmarket load, chart components, dashboard) · Source: roadmap §5 (F7), design-handoff §3.9, §3.13, §5.7, §6-20/21/34, §7.2-V1, §7.5-R3, §9 F7, §10-1/§10-11, product.md "Scope by phase"

## Goal

The owner (and every user) manages what they sell from their collection: a list of active listings built
from the collection lines marked for sale, a history of sales with buyer, status and date, real margin when
the line has a purchase price and, when it does not, a comparison with that day's market price. Recording a
sale deducts the copies from the collection in the same transaction. A Cardmarket-compatible CSV export
keeps working (same format as today) from the new app.

## Current state

- **No sales model.** Nothing stores a sale; the prototype's `RB.SALES` is static data (design-handoff §3.9).
- **Selling data lives on `rbcollection`** (`app/models/collection.py`): `rbcol_selling` (`Y`/`N`; the CHECK
  `rbcollection_selling_chk` also allows a legacy `S`), `rbcol_playset` (1..3, copies kept),
  `rbcol_sell_price` (unit price for the surplus), `rbcol_condition`, `rbcol_language`, `rbcol_foil`
  (`S`/`N`), synthetic PK `rbcol_id` (several rows per card allowed), owner by **username**
  (`rbcol_user` → `rbusers.username`, ON UPDATE CASCADE). F3 replaces/extends this with purchase price,
  "copies to sell", the selling switch and sub-lines (see "Consumed contracts").
- **Legacy routes** (`app/routes/domains/collection.py`): `update_selling`, `update_playset` (auto-sets
  `selling` from the surplus), `update_sell_price`, `bulk_apply` (playset with foil priority),
  `export_csv` (POST, `@validate_json(CollectionExport)`: required `rbset_id` + `rarity`; rows with
  `rbcol_selling='Y'` and `quantity - playset > 0`; columns `name,language,quantity,price`, `QUOTE_ALL`,
  `\n` line ends, UTF-8 BOM, `name` = Cardmarket product name when mapped else `rbcar_name`, price =
  `rbcol_sell_price` else `resolve_price(...)` else `0.00`, file `YYYYMMDDHHMMSS_<set>_<rarity>.csv`,
  header `X-Rows-Exported`). Used by the Jinja collection page.
- **Prices**: `app/services/pricing.py` (`resolve_price`, `canonical_product_id`, `latest_price_for_card`);
  `rbcm_price.rbprc_date` is text `YYYYMMDD`, one row per product per loaded day (F4 makes the load daily).
- **Frontend**: nav entry `sales` is `planned` (`frontend/src/shell/navRegistry.ts`, placements `top`, `hub`).
  Primitives available: `Modal`, `Sheet`, `ConfirmDialog`, `Toast`, `Field`, `Input`, `Select`, `Switch`,
  `SegmentedControl`, `Badge`, `EmptyState`, `ErrorState`, `Skeleton`, `OfflineBanner`, `PageHeader`.
  Charts (`Sparkline`, `PriceChart`) come from F2/F4; `StatCard`, `DataTable`, `Stepper` from F2/F3.
- **Tests**: `tests/test_collection_*` cover the legacy selling/export paths; no sales tests.

## Scope

In:
- Sales table and service: create (deducts inventory), edit, status changes, cancel with optional restock,
  delete cancelled sales; snapshots of purchase price and market price at sale time.
- Listings endpoint (lines on sale + market comparison + flags), summary/KPIs, monthly series, totals by set.
- Cardmarket export from the API (byte-identical to the legacy export), sales-history CSV.
- Sales screen in React (mobile, desktop, wide), sell dialog, history, filters, export dialog.
- Nav entry `sales` → `spa` (also in the "Más" sheet on mobile, design-handoff §0.1-9 / R4).
- Feed for the F4 dashboard "Recent sales" block.

Out:
- Cardmarket API integration (order sync, automatic listing upload). Multi-currency (EUR only).
- Editing the selling flags or the purchase price of a line (F3 owns them; F7 calls F3's endpoints).
- Invoices, taxes, shipping labels. Public seller page.

## Decisions already taken

- Margin rule (product.md F7, roadmap F7, design-handoff §3.9 "Reglas"): **real margin** = sale − purchase
  price when the line has a purchase price; otherwise a **comparison with that day's market price**.
- Selling **deducts inventory** (product.md F7; design-handoff §6-20).
- Purchase price is optional per line and owned by F3 (product.md F3; cross-phase contract).
- Prices: Cardmarket only, EUR only; fallback chain `avg7_foil → avg7 → low_foil → low` via `resolve_price`
  (product.md "Data"; openspec/specs/price-resolution PRC-1/PRC-2: no route picks `rbprc_*` columns itself).
- Default sell price = market × 1.05 is an F3 rule (design-handoff §5.7); F7 only reads `sell_price`.
- Desktop shows more data (two/three columns), never stretches (product.md; design-handoff §3.0, §3.13).
- Offline is read-only; every edit needs a connection (product.md "Offline").

## Consumed contracts (from F3/F4, must be confirmed when F7 starts)

| From | What F7 assumes | If different |
|---|---|---|
| F3 | Each collection line (including sub-lines, which are separate `rbcol_id` rows) exposes: `id`, card key, `foil`, `qty`, `condition`, `language`, `purchase_price` (EUR **per unit**, nullable), `selling` (switch), `sell_qty` (copies to sell, 0..qty), `sell_price` (EUR per unit, nullable). | Adjust F7-c listings and the deduction rule in F7-a; record in D-F7-8. |
| F3 | `PATCH /collection/{id}` updates `sell_price`, `selling`, `sell_qty` (used by the listing inline edits). | F7-e calls whatever F3 exposes. |
| F3 | The legacy `rbcol_playset` → `sell_qty` mapping (product.md F3: "confirmed at the start of F3"). | Changes the export quantity rule (D-F7-8). |
| F4 | `rbcm_price` loaded daily; `GET /dashboard` has a `recent_sales` slot; chart primitives exist. | F7-f ships its own minimal bar chart. |

## Requirements

### Data
- **F7-R1** MUST store each sale as one row per card line sold (table `rbsales`), owned by `rbusers.id`.
- **F7-R2** MUST snapshot at creation: card name, set id, card id, foil, condition, language, quantity, unit
  sale price, purchase price per unit (from the line, nullable), market unit price, its source column and
  price date (nullable when no price exists).
- **F7-R3** The market snapshot MUST use the newest `rbcm_price` row of the card's canonical product with
  `rbprc_date <= sold_on` (that day's price, or the latest before it), resolved with F2-b
  `resolve_price_with_source` (the `resolve_price` chain plus the source column) for the line's rarity and
  foil. No row → market fields NULL.
- **F7-R4** Money columns MUST be `NUMERIC(10,2)`, `>= 0` (CHECKs); quantity `1..9999`.

### Inventory and lifecycle
- **F7-R5** `POST /sales` MUST, in one transaction per request, lock each source line (PostgreSQL
  `SELECT … FOR UPDATE`), verify `qty_sold <= sell_qty` of the line, decrement `qty` and `sell_qty`, delete
  the line when `qty` reaches 0 (the CHECK forbids 0), and insert the sale(s). Any failing item rolls back
  the whole request (all-or-nothing) with 409 `insufficient_quantity` naming the item index.
- **F7-R6** A line not owned by the caller MUST answer 404 (never reveal other users' ids).
- **F7-R7** Status values `pending`, `shipped`, `cancelled`. Allowed transitions: pending→shipped,
  pending→cancelled, shipped→cancelled. Others → 409 `invalid_status_transition`.
- **F7-R8** `POST /sales/{id}/cancel {restock}`: `restock=true` returns the copies to the source line if it
  still exists (qty and sell_qty += n), otherwise re-creates a line from the snapshot (selling on,
  `sell_price` = sale unit price, purchase price restored). Idempotent: cancelling a cancelled sale → 409.
- **F7-R9** `DELETE /sales/{id}` MUST be allowed only for `cancelled` sales (409 `invalid_status_transition`
  otherwise) and never touches inventory.
- **F7-R10** SHOULD accept an optional client reference (`client_ref`, unique per user) so a double submit
  returns the first result instead of selling twice.

### Margin and KPIs
- **F7-R11** For each sale: `revenue = unit_price × qty − fees`. If `purchase_price` is set:
  `margin = revenue − purchase_price × qty`, `margin_pct = margin / (purchase_price × qty)` (NULL when the
  cost is 0) and `margin_kind = "real"`. Otherwise, if `market_price` is set: `vs_market = revenue −
  market_price × qty`, `margin_kind = "market"`. Otherwise `margin_kind = "none"`. Computed in the backend.
- **F7-R12** KPIs MUST never add "real" and "market" figures together: the summary returns them in separate
  fields (D-F7-5). Revenue and margins count `shipped` sales only; `pending` is reported separately (D-F7-1).
- **F7-R13** Listings MUST include: line data, market unit price today (same chain), `delta_pct` of
  `sell_price` vs market, estimated margin (real if purchase price else vs market), and flag
  `above_market` when `sell_price > market` and `below_cost` when `sell_price < purchase_price`.

### Export
- **F7-R14** `GET /sales/export?format=cardmarket&set=<id>&rarity=<r>` MUST produce output byte-identical to
  the legacy `export_csv` for the same data (characterization test first), after moving the row building to
  `app/services/cardmarket_export.py`; the legacy route calls the same service until F11 removes it.
- **F7-R15** `format=history` SHOULD export the filtered sales as CSV with BOM (`sold_on, set, card, name,
  foil, condition, language, qty, unit_price, fees, purchase_price, market_price, margin_kind, margin,
  status, buyer, order_ref`).

### API, authz, i18n, a11y
- **F7-R16** Every endpoint is `U`, scoped to `current_user`, classified in `tests/test_authz_matrix.py`,
  uses `@validate_json` for bodies and the `{success,data,meta}` envelope.
- **F7-R17** New error codes with ES/EN messages in both `errors.json` and the contract test.
- **F7-R18** All UI text in namespace `sales` (ES/EN parity); enums `enums.sale_status.*`; money with
  `formatMoney` (EUR, app locale); dates with the app locale.
- **F7-R19** Tables have `<caption>`, `scope`, `aria-sort`; status is text + colour; money inputs use
  `inputmode="decimal"`, `min=0`, `aria-invalid` + `aria-describedby` (design-handoff §7.2-V1, §7.4).

### Offline and performance
- **F7-R20** Offline: buttons that write are disabled with the offline reason; reads are served by the F2
  offline API cache (strategy D-F2-7, purge on logout F2-R24) only if the owner extends offline to sales
  (D-F7-9), otherwise the `ErrorState` offline variant.
- **F7-R21** `GET /sales/listings` and `GET /sales` MUST run a bounded number of SQL queries independent of
  the row count (query-count test, ≤ 5 per request); pagination `per_page` 25/50/100 (desktop 200).

## Data model changes

Revision `00xx_sales` (next free number at F7 time). Reversible; no backfill (no sales exist).

| Table `riftbound.rbsales` | Type | Notes |
|---|---|---|
| `rbsal_id` | BIGINT PK (INTEGER on SQLite, as `rbcol_id`) | |
| `rbsal_user_id` | INTEGER NOT NULL FK `rbusers.id` ON DELETE CASCADE | new tables use the user id, like `rbuserprefs` |
| `rbsal_rbset_id`, `rbsal_rbcar_id` | TEXT NOT NULL | no FK: the sale survives catalog edits |
| `rbsal_card_name` | TEXT NOT NULL | snapshot |
| `rbsal_foil` | CHAR(1) NOT NULL CHECK IN ('S','N') | |
| `rbsal_condition`, `rbsal_language` | VARCHAR(8) NULL, VARCHAR(40) NULL | snapshot |
| `rbsal_qty` | INTEGER NOT NULL CHECK 1..9999 | |
| `rbsal_unit_price` | NUMERIC(10,2) NOT NULL CHECK >= 0 | |
| `rbsal_fees` | NUMERIC(10,2) NOT NULL DEFAULT 0 CHECK >= 0 | D-F7-3 |
| `rbsal_purchase_price` | NUMERIC(10,2) NULL | per unit, snapshot |
| `rbsal_market_price` | NUMERIC(10,2) NULL | per unit, snapshot |
| `rbsal_market_source` | VARCHAR(16) NULL | `avg7_foil`/`avg7`/`low_foil`/`low` |
| `rbsal_market_date` | VARCHAR(8) NULL | `YYYYMMDD` of the price row |
| `rbsal_status` | VARCHAR(10) NOT NULL CHECK IN ('pending','shipped','cancelled') | |
| `rbsal_sold_on` | DATE NOT NULL | user's local date (D-F7-7) |
| `rbsal_buyer` | VARCHAR(80) NULL | |
| `rbsal_order_ref` | VARCHAR(40) NULL | groups lines of one order |
| `rbsal_channel` | VARCHAR(16) NULL CHECK IN ('cardmarket','in_person','other') | D-F7-6 |
| `rbsal_notes` | VARCHAR(500) NULL | |
| `rbsal_source_rbcol_id` | BIGINT NULL FK `rbcollection.rbcol_id` ON DELETE SET NULL | |
| `rbsal_client_ref` | VARCHAR(40) NULL | UNIQUE (`rbsal_user_id`, `rbsal_client_ref`) |
| `rbsal_restocked` | BOOLEAN NOT NULL DEFAULT false | set by cancel with restock |
| `rbsal_created_at`, `rbsal_updated_at` | TIMESTAMP NOT NULL | `clock.utcnow()` |

Indexes: (`rbsal_user_id`, `rbsal_sold_on` DESC), (`rbsal_user_id`, `rbsal_status`), (`rbsal_user_id`,
`rbsal_rbset_id`). Downgrade drops the table (data loss: the deploy section says "backup first").
Risk: item 1 (new table + FK into `rbcollection`).

## API

Base `/riftbound/api/v1`. All `U`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/sales` | History. Query: `status[]`, `from`, `to`, `buyer`, `set`, `q` (card name), `margin_kind`, `sort` (`sold_on`,`unit_price`,`margin`,`name`), `dir`, `page`, `per_page`. `meta`: `total`, `totals` (qty, revenue, real_margin, vs_market, pending_revenue). |
| POST | `/sales` | Create. Body `{items:[{line_id, qty, unit_price}] (1..50), sold_on, status, buyer?, fees?, order_ref?, channel?, notes?, client_ref?}`. Fees apply to the first item (D-F7-3). Returns the created sales. 201. |
| GET | `/sales/{id}` | One sale with computed margin fields. |
| PATCH | `/sales/{id}` | `unit_price`, `fees`, `sold_on`, `status` (transitions F7-R7), `buyer`, `order_ref`, `channel`, `notes`. Market snapshot is not recomputed unless `sold_on` changes. |
| POST | `/sales/{id}/cancel` | `{restock: bool}` (F7-R8). |
| DELETE | `/sales/{id}` | Only cancelled sales. |
| GET | `/sales/listings` | Lines on sale (F7-R13). Query: `set`, `q`, `flag` (`above_market`,`below_cost`), `sort`, `dir`, `page`, `per_page`. |
| GET | `/sales/summary` | `range` = `30d`/`90d`/`12m`/`all`: KPIs (revenue, items_sold, orders, real_margin + avg %, vs_market, pending count/value, active listings count/value), `monthly[]` (month, revenue, real_margin, vs_market), `by_set[]`. |
| GET | `/sales/export` | `format=cardmarket` (+ `set`, `rarity` required, as today) or `format=history` (+ the `/sales` filters). CSV download. |

Error codes: `insufficient_quantity` is introduced by F3-c (409, `params.available`); F7 reuses it and adds
`params.index`. New in F7 (enum + ES/EN catalogs + contract test): `invalid_status_transition` (409, `params.from`, `params.to`). Unknown/foreign ids → 404
without code (existing behaviour).

## UI

Route `/riftbound/app/sales` (`requireAuth`), sub-routes `/sales/listings` (default) and `/sales/history`
(tabs are URLs, design-handoff §5.8). Lazy route module `sales/`.

| Breakpoint | Layout |
|---|---|
| Mobile < 860 | `PageHeader` ("N anuncios activos" / "N active listings") + KPI grid 2 cols (Ingresos, Vendidas, Margen real, Anuncios activos). Tabs Listings / History (`SegmentedControl`). Listings = cards (thumb 44×58, name, `qty× · cond · lang · FOIL`, market, price input, Δ%, badges "Por encima de mercado"/"Bajo coste", buttons **Vender** and **Quitar de venta**). History = list cards (date, name, qty, price, margin with kind label, status badge); filters in a `Sheet`. No horizontal-scroll tables (R3). |
| Desktop ≥ 1240 | KPI band (6 stats incl. pending and vs-market). Two columns: listings dense table (thumb, card, set, foil, cond, lang, qty on sale, market, price inline, Δ%, est. margin, actions) / history table (date, card, qty, price, fees, cost, market, margin, status, buyer). Filters inline above each table. Multi-select listings → **Vender seleccionadas** (one order). |
| Wide ≥ 1600 | Three columns: listings / history / sticky rail with monthly revenue + margin chart (12 m), totals by set, alerts list (above market, below cost), export shortcuts. |

Sell dialog (`Modal`, sheet on mobile): per item qty `Stepper` (1..sell_qty), unit price (default listing
price), date (default today, local), status (default `pending`), buyer, channel, fees, order ref, notes;
live preview of revenue and margin with its kind ("Margen real" / "vs mercado del día" / "Sin precio").
Cancel dialog: `ConfirmDialog` with switch "Devolver N copias a la colección" (default on). Export dialog:
format (Cardmarket / historial), set + rarity selects for Cardmarket (from F2 `GET /meta/game`).

States: skeleton tables/cards; empty listings ("No tienes cartas a la venta" + link to Collection); empty
history; `ErrorState` with retry; offline banner + disabled writes. Toasts on create/cancel with undo only
for cancel→restock (re-sell is not undone automatically).

Components to build: `SalesKpis`, `ListingsTable`/`ListingCard`, `SalesHistoryTable`/`SaleCard`,
`SellDialog`, `CancelSaleDialog`, `ExportSalesDialog`, `MonthlySalesChart` (reuse F4 chart primitives).
i18n namespace `sales` (≈ 90 keys), enums `sale_status`, `sale_channel`.

## Units

| ID | Title | Depends on | Size | Risk | Summary |
|---|---|---|---|---|---|
| F7-a | Sales table + create API | F3 done | ~500 | Risk: item 1 + item 4 (migration; row locks on concurrent sells) | Migration `rbsales`, model, `services/sales.py` (create with lock, deduction, snapshots, client_ref), `POST /sales`, `GET /sales`, `GET /sales/{id}`, reuse of `insufficient_quantity` (from F3-c), authz rows. |
| F7-b | Sale lifecycle | F7-a | ~350 | Risk: item 4 (restock races with edits of the line) | `PATCH`, `cancel` with restock/re-create, `DELETE` cancelled, transitions + `invalid_status_transition`. |
| F7-c | Listings + summary API | F7-a | ~400 | Risk: item 3 (consumes F3 line contract) | `GET /sales/listings` (market today, Δ, flags, est. margin), `GET /sales/summary` (KPIs, monthly, by set), query-count tests. |
| F7-d | Export service | F7-a | ~350 | Risk: item 3 (legacy export consumers: Cardmarket upload format) | Characterization test of legacy `export_csv`, extract `services/cardmarket_export.py`, `GET /sales/export` (cardmarket, history). |
| F7-e | Sales UI: listings + sell | F7-a, F7-c | ~600 | Risk: none | Route, KPIs, listings (mobile cards / desktop table), inline price + stop selling via F3, sell dialog (single + multi), nav flip to `spa` + "Más", i18n. |
| F7-f | Sales UI: history, export, wide rail | F7-b, F7-d, F7-e | ~600 | Risk: none | History list/table, filters, edit/cancel/delete dialogs, export dialog, wide rail with monthly chart and alerts, F4 dashboard "recent sales" wiring. |

## Open decisions

| ID | Question | Options | Recommendation | Blocks |
|---|---|---|---|---|
| D-F7-1 | Which statuses count as revenue? | shipped only / pending + shipped | Shipped only; pending shown as its own KPI | F7-c |
| D-F7-2 | Cancel/delete and inventory | always restock / ask / never | Ask with "return copies" switch on by default; delete only cancelled sales | F7-b |
| D-F7-3 | Track fees/shipping? | none / one `fees` field per sale / per order | One optional `fees` (commission + shipping cost), subtracted from revenue | F7-a |
| D-F7-4 | Cardmarket export format | keep `name,language,quantity,price` / add condition, foil, comments | Keep byte-identical; add a v2 format only with a sample file Cardmarket accepts (owner provides) | F7-d |
| D-F7-5 | One "Profit" KPI or separate real vs market | merged / separate | Separate ("Margen real" and "vs mercado"), never summed | F7-c |
| D-F7-6 | Sales channel field | none / enum cardmarket, in_person, other | Optional enum | F7-a |
| D-F7-7 | Sale date | date only / timestamp | Date (user's local date); market snapshot by that date | F7-a |
| D-F7-8 | Export quantity and "copies to sell" | today `qty − playset` / F3 `sell_qty` | Follow F3's decision (design-handoff §10-1); export uses `sell_qty` | F7-a, F7-d |
| D-F7-9 | Offline reads for sales | none / SWR like collection | None in F7 (product.md lists catalog, collection, decks only) | F7-e |
| D-F7-10 | Condition/language enums vs Cardmarket (design-handoff §10-11) | keep 7 conditions + free language / served by meta | Use whatever F3 adds to `GET /meta/game` | F7-e |
| D-F7-11 | Sell from a line not marked for sale (direct sale)? | only listings / any line | Only lines with `sell_qty > 0`; the dialog can raise `sell_qty` first via F3 | F7-a |

## Risks and notes

- **Concurrency**: two tabs selling the same line, or a sale racing an F3 bulk edit. Row locks on PostgreSQL;
  SQLite tests cannot prove the lock — add a `@pytest.mark.postgres` test with two sessions.
- **Snapshot drift**: editing `sold_on` re-resolves the market snapshot; editing a catalog card later does not
  change past sales (by design).
- **Legacy export**: the Jinja collection page keeps calling `/riftbound/collection/export_csv` until F11; both
  paths must share the service (one implementation, PRC-2 spirit).
- **Username FK**: `rbcollection` is keyed by username; `rbsales` by user id. The service resolves both from
  `current_user`; never accept a user id from the client.
- **Dashboard**: F4 may ship the "Recent sales" block hidden; F7-f turns it on (cross-phase).
- The prototype's `cost` column was mandatory; here it is optional and shown as "—" (design-handoff §3.9).
