# F14: Products — phase spec

Status: planned · Depends on: F3 (collection screens and patterns; the phase runs after F3), F4-b (daily Cardmarket load job), F13-a (admin foundation), F2 (price chart, `price_summaries` pattern, `(product, date)` price index, offline read cache) · Source: `docs/knowledge/decisions-2026-10-22.md` ("Products", "Scraping scope", "Daily prices"), product.md "Architecture decisions" (prices), `app/models/cardmarket.py` · Phase IDs are identifiers, not order; the order lives in `docs/knowledge/roadmap.md`.

## Goal

Users track the sealed Cardmarket products they own (boxes, cases, sleeves, …): they browse the products
with their current price and price history, record how many of each they own, and see a separate
"products" total. That total is never added to the value of the card collection.

## Current state

| Area | What exists today |
|---|---|
| Cardmarket raw data | `CardmarketLoader` (`app/services/cardmarket_loader.py`) downloads the singles file, the **non-singles file** (`products_nonsingles_22.json`) and the price guide. Products go to `rbcm_products` (`rbprd_date`, `rbprd_id_product`, name, category id/name, expansion id, metacard id, `rbprd_type` `single`/`nonsingle`), one row set per loaded day; prices go to `rbcm_price` (one row per product per day: `avg`, `low`, `trend`, `avg1/7/30` and their foil variants, `low_ex`). Categories in `rbcm_categories`, expansions in `rbcm_expansions` (`rbexp_rbset_id` soft link to `rbset`, NULL = unmapped). F4-b runs the load every day (06:30, retry 08:00 Europe/Madrid). |
| Curated products | `RbProducts` (`rbproducts`, "curated product master table (future use)"): PK (`rbpdt_id_set`, `rbpdt_id_product`), `rbpdt_name` NOT NULL, `rbpdt_description`, `rbpdt_type` (`single`/`nonsingle`, free text), `rbpdt_image_url`, `rbpdt_image`. Written only by hand from the Jinja admin page (`POST /riftbound/price/cardmarket-upsert-product`, search and detail endpoints in `price_bp`); the loader imports the model but does not write it. |
| Pricing | `app/services/pricing.py` resolves card prices (PRC-1 fallback chain with foil rules); no rule for sealed products. F2-b adds the `(product, date)` index on `rbcm_price` and `price_summaries` (7/30-day trends). |
| Ownership | None: `rbcollection` holds cards only. |
| Value history | F4-c writes a daily card-collection value snapshot per user (`rbvaluesnaps`); products are not in it. |
| Frontend | No products screen or nav entry. F2 provides `PriceChart`/`Sparkline`; F3 provides the collection table/grid patterns; F13-a provides `AdminLayout`. |

## Scope

In: product catalog built from the Cardmarket non-singles data (curated in `rbproducts`); current price
and price history per product; owned products per user (quantity); separate products total; admin
curation (hide, type, set, image); products screens (mobile, desktop, wide) and nav entry.

Out: adding products to the card collection value; selling products (F7 covers cards); wishlist and price
alerts for products (D-F14-9); CSV import/export of products; sources other than Cardmarket.

## Decisions already taken

- New section for sealed Cardmarket products (boxes, cases, sleeves, …) with price and history, and the
  quantity owned (owner, 2026-10-22).
- Their value is a separate "products" total, not added to the cards' collection value (owner, 2026-10-22).
- The phase runs after F3 (owner, 2026-10-22).
- Cardmarket products, both singles and sealed, are one of the three "scraping" sources (owner,
  2026-10-22).
- The Cardmarket load runs every day at 06:30 Europe/Madrid with a retry at 08:00, validates the load and
  records the result (owner, 2026-10-22; F4-b).
- Prices are Cardmarket only, EUR only (product.md).
- New tables reference `rbusers.id`; every new screen defines mobile, desktop and wide layouts; edits need
  a connection (roadmap cross-phase contracts, product.md).

## Requirements

### Catalog
- **F14-R1** Every Riftbound non-single product present in the latest Cardmarket load is in the product
  catalog with Cardmarket id, name, Cardmarket category, product type (D-F14-3), set when its expansion is
  mapped in `rbcm_expansions`, and image if any. A step after each successful daily load adds new products
  and updates names/categories; it never deletes a product (a product absent from the latest file is
  marked as not listed). Where the catalog lives is D-F14-1; which categories count is D-F14-2. (F14-a)
- **F14-R2** The admin can hide/unhide a product, override its type and set, and upload or link its image
  (D-F14-8); hidden products disappear from the user catalog but stay visible to owners of the product.
  Every admin write is audited in `rbadminaudit` (F13-a). (F14-d)

### Prices
- **F14-R3** Current price per product from the latest `rbcm_price` row with the sealed-product price rule
  (D-F14-4); 7- and 30-day change computed the same way as F2-b's `price_summaries` (which is keyed by
  card), in a product-keyed batch variant. A product without a usable price is
  "unpriced" (shown as such, counted, never as 0 €). (F14-b)
- **F14-R4** Price history per product from `rbcm_price` for ranges `30d|90d|1y|all`. (F14-b)

### Ownership and totals
- **F14-R5** Owned products per user: product, quantity (1..9999) and the optional fields of D-F14-5.
  Create, update, delete, always scoped to the signed-in user (ids from the client are never trusted).
  Adding a product the user already owns follows D-F14-5. (F14-c)
- **F14-R6** Products total of a user = Σ (quantity × current price) over priced lines, plus the count of
  unpriced lines. It is returned by the products API only; the card collection value and every collection
  endpoint stay unchanged. History of the total: D-F14-6. (F14-c)

### API, security, quality
- **F14-R7** Every new rule classified in `tests/test_authz_matrix.py` (catalog and ownership `U`,
  curation `A`); list endpoints use bounded queries (query-count tests) and server-side pagination.
- **F14-R8** Namespace `products` in both catalogs with the ES/EN parity test; product types have display
  names in both languages. New error codes, if any, follow the catalog contract test.
- **F14-R9** Offline behaviour per D-F14-12; edits always need a connection.

### UI
- **F14-R10** `/products` with two tabs, "Mis productos" (owned lines + total band) and "Catálogo"
  (filters type, set, text; sort by name, price, change), and `/products/:id` (detail with price chart,
  owned quantity editor). Nav entry `products` (`spa`). Layouts in "UI". (F14-e, F14-f)

## Data model changes

| Revision (unit) | Change | Risk |
|---|---|---|
| `00xx_products_catalog` (F14-a) | Depends on D-F14-1. Recommended: `rbproducts` becomes the catalog keyed by Cardmarket id: unique `rbpdt_id_product`; add `rbpdt_category` TEXT, `rbpdt_hidden` BOOLEAN NOT NULL DEFAULT false, `rbpdt_listed` BOOLEAN NOT NULL DEFAULT true, `rbpdt_type` CHECK IN the D-F14-3 list (existing rows mapped, `single` rows reviewed first: they are card products, not sealed). | item 1 |
| `00xx_user_products` (F14-c) | `rbuserproducts` (`rbupr_`): `id` BIGINT PK; `user_id` INT NOT NULL FK `rbusers.id` ON DELETE CASCADE; `id_product` INT NOT NULL (Cardmarket id); `quantity` INT NOT NULL CHECK 1..9999; optional fields per D-F14-5 (recommended `purchase_price` NUMERIC(10,2) NULL CHECK ≥ 0, `note` VARCHAR(200) NULL); `created_at`, `updated_at`. Index (`user_id`). | item 1 |
| `00xx_snapshot_products_value` (F14-c, only if D-F14-6 is accepted) | `rbvaluesnaps.rbvsn_products_value` NUMERIC(12,2) NULL. | item 1 |

All reversible with round-trip and drift tests; downgrades drop the new table/columns (data loss
documented). F9-k's account purge must list `rbuserproducts`.

## API

| Method | Path | Auth | Purpose | Unit |
|---|---|---|---|---|
| GET | `/products` | U | Catalog list: filters `type`, `set`, `q`, `owned`; sort; pagination; current price + 7/30-day change | F14-b |
| GET | `/products/{id}` | U | Detail + owned quantity of the caller | F14-b |
| GET | `/products/{id}/prices` | U | Price history (`range=30d|90d|1y|all`) | F14-b |
| GET / POST | `/me/products` | U | Owned lines + `{total, unpriced}` / add a line | F14-c |
| PATCH / DELETE | `/me/products/{line_id}` | U | Edit / remove an owned line | F14-c |
| GET | `/admin/products` | A | Curation list (hidden, not listed, unmapped set, missing image) | F14-d |
| PATCH | `/admin/products/{id}` | A | Hide/unhide, type, set | F14-d |
| POST | `/admin/products/{id}/image` | A | Upload image (multipart) | F14-d |

Error codes: reuses `already_exists` (if D-F14-5 keeps one line per product) and `validation_error`;
no new code expected.

## UI

| Route | Mobile < 860 | Desktop ≥ 1240 | Wide ≥ 1600 |
|---|---|---|---|
| `/products` | Total band (value, lines, unpriced) on top; tabs "Mis productos" / "Catálogo"; grid of product tiles (image, name, type, price, change) with a quantity stepper on owned tiles | Table with type, set, quantity, unit price, line value, 7/30-day change; filters in a left rail; total band | Table + persistent detail panel with the price chart of the selected product |
| `/products/:id` | Image, price, change, chart (range tabs), owned quantity editor | Two columns: image + data / chart + owned lines | Same as desktop with a wider chart |
| `/admin/products` | Cards with key fields and actions menu | `DataTable` + detail drawer (type, set, hidden, image) | Three panes |

Components: `ProductTile`, `ProductTable`, `ProductsTotal` (visibly separate from any collection value),
reuse `PriceChart`, `Sparkline` (F2) and F3's quantity control. States: loading, empty ("Aún no tienes
productos"), unpriced, error, offline.

## Units

| ID | Title | Depends on | Size | Risk | Summary |
|---|---|---|---|---|---|
| F14-a | Product catalog data | F4-b, F13-a | ~450 | Risk: item 1 + item 3 (migration of `rbproducts`; step chained to the daily load) | Migration per D-F14-1, catalog refresh step after each successful load (new/updated/not listed), type mapping from categories. |
| F14-b | Products read API | F14-a, F2-b | ~400 | Risk: item 3 (new public contract) | `/products`, `/products/{id}`, `/products/{id}/prices`, sealed price rule. |
| F14-c | Owned products API + total | F14-b | ~450 | Risk: item 1 (new user table) | `rbuserproducts`, `/me/products` CRUD scoped to the user, products total, optional snapshot column (D-F14-6). |
| F14-d | Admin curation | F14-a, F13-a | ~400 | Risk: item 2 (file upload, admin writes) | Curation API + `AdminLayout` screen, image upload, audit. |
| F14-e | Products UI mobile + nav | F14-c | ~550 | Risk: none | `/products` tabs, tiles, total band, `/products/:id`, nav entry `products`. |
| F14-f | Products UI desktop/wide + offline | F14-e | ~450 | Risk: none | Table, rail, detail panel, offline per D-F14-12, dashboard hook per D-F14-7. |

## Open decisions

| ID | Question | Options | Recommendation | Blocks |
|---|---|---|---|---|
| D-F14-1 | Where the product catalog lives | reuse `rbproducts` (reshape) / read `rbcm_products` directly / new table | Reuse `rbproducts`, keyed by Cardmarket id, filled from the non-singles data after each load; `rbcm_products` stays the raw daily copy | F14-a |
| D-F14-2 | Which products count (sleeves and accessories may not be in the Riftbound non-singles file) | every non-single of the file / a category allow-list | Every non-single product of the Riftbound file; the admin hides what does not belong; products outside the file wait until a source exists | F14-a |
| D-F14-3 | Product type list | Cardmarket category as is / fixed list mapped from categories | Fixed list (`booster`, `box`, `case`, `bundle`, `starter`, `sleeves`, `accessory`, `other`) mapped from the Cardmarket category, admin can override | F14-a, F14-d |
| D-F14-4 | Price used for a sealed product | `avg7` / `trend` / `low` / chain | Chain `avg7 → trend → low` (no foil fields); NULL and 0 count as missing, like PRC-1. The implementer checks which fields the price guide fills for non-singles on the dev database (read only) | F14-b |
| D-F14-5 | Fields of an owned line and duplicates | quantity only / + purchase price + note; one line per product / several | Quantity + optional purchase price + note; several lines per product allowed when the purchase price differs (same rule as F3-R6), otherwise adding merges the quantity | F14-c |
| D-F14-6 | History of the products total | none / column in the F4-c snapshot / own table | Nullable `rbvsn_products_value` in the daily snapshot, shown as its own series (never summed with the cards) | F14-c, F14-f |
| D-F14-7 | Products total on the dashboard (F4-e) | yes, own KPI / no | Yes, as its own KPI next to the collection value, clearly labelled | F14-f (coordination with F4-e) |
| D-F14-8 | Product images | Cardmarket / admin upload / placeholder | Admin upload or image URL stored in the data directory (same safety rules as card images); placeholder per type when missing | F14-d |
| D-F14-9 | Wishlist and price alerts for products | in F14 / later | Later (after F4-g watchlist exists); out of F14 | — |
| D-F14-10 | Selling products (F7) | in F7 / later / never | Later, outside F7's card contract | — |
| D-F14-11 | Who sees the product catalog | signed-in users / public | Signed-in users (`U`), like the card catalog | F14-b |
| D-F14-12 | Products offline | read cache like the collection / online only | Read cache `rb-api-products` (NetworkFirst, purged on logout), extending the offline list in product.md, which needs the owner's yes | F14-f |
| D-F14-13 | Existing `rbproducts` rows of type `single` written from the Jinja admin | keep / migrate out / drop | Keep them out of the products catalog (filter `nonsingle`); review on the dev database before the migration | F14-a |

## Risks and notes

- **Data shape unknown in detail**: which categories and price fields the non-singles data really carries
  is checked on the dev database (read only) at the start of F14-a; the type list and price rule may need
  the owner if they differ from the recommendations.
- **Separate totals** (item 6): a test asserts that adding owned products changes neither the collection
  value endpoints nor the F4-c card snapshot value.
- **`rbproducts` reshape**: its PK (`rbpdt_id_set`, `rbpdt_id_product`) allows the same Cardmarket id under
  two sets; the migration must check for duplicates on the dev data before adding the unique key.
- **Daily load coupling**: the catalog refresh runs only after a successful load; a failed load keeps the
  previous catalog and prices.
- **Order**: F10-g (Cardmarket mappings port) also touches `rbproducts` upserts; if F14 runs first, F10-g
  ports on top of F14's shape.
