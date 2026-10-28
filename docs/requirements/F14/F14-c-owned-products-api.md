# F14-c: Owned products API and the separate products total

| Field | Value |
|---|---|
| Phase / unit | F14 / c — batch 1, unit 29 |
| Branch | `feat/f14c-owned-products-api` (from the F14-b branch) |
| Depends on | F14-b, F4-c (stack) |
| Size forecast | ~450 authored lines |
| Risk | `Risk: item 1 (new user table; snapshot column)` |
| TDD | ON (strict). Runner: `venv/bin/pytest` |
| Sources | F14 phase spec (F14-R5, R6, data model, D-F14-5, D-F14-6), `decisions-2026-10-22.md` ("Products") |

## Objective

Each user records how many of each sealed product they own (with an optional purchase price and note) and sees a
"products" total that is **never** added to the value of the card collection; the daily snapshot keeps that total
too.

## Read first

- F14-b (`app/api/v1/products.py`, `product_price_summaries`), `app/services/snapshots.py` (F4-c), F3-c
  conventions (scoping, 404 for foreign ids, money rounding)

## Specs

S1. Table `rbuserproducts` (migration `00NN_user_products`), model `RbUserProduct` (`app/models/user_product.py`):
    `rbupr_id BIGINT` PK (Integer on SQLite); `rbupr_user_id INTEGER NOT NULL` FK `rbusers.id` ON DELETE CASCADE;
    `rbupr_id_product INTEGER NOT NULL` FK `rbproducts.rbpdt_id_product` ON DELETE RESTRICT; `rbupr_quantity
    INTEGER NOT NULL` CHECK 1-9999; `rbupr_purchase_price NUMERIC(10,2) NULL` CHECK ≥ 0; `rbupr_note
    VARCHAR(200) NULL`; `rbupr_created_at`, `rbupr_updated_at` TIMESTAMP NOT NULL. Index (`rbupr_user_id`).
S2. Migration `00NN_snapshot_products_value`: `rbvaluesnaps.rbvsn_products_value NUMERIC(12,2) NULL`.
S3. `GET /me/products` (U): `{items: [line…], total: {value, lines, qty, unpriced}}` with `line = {id, product:
    ProductSummary, quantity, purchase_price, note, value, pl_abs, pl_pct, updated_at}` (`value` = price ×
    quantity or null; P/L as F3-b S3). Ordered by product name, then id. `total.value` = Σ priced line values.
S4. `POST /me/products` body `{product_id, quantity (1-9999), purchase_price?, note?}`: product must be a
    non-single (else `validation_error`, `product_id`, `invalid_value`); a line of the same product with the same
    purchase price (NULL-safe) → merge quantity (`merged: true`); 201 `{line, merged}`.
    `PATCH /me/products/<id>` any of `{quantity, purchase_price, note}`; `DELETE /me/products/<id>` → 200
    `{deleted: line}`. Foreign ids → 404.
S5. F14-b updates: `owned_qty` real; `owned` filter real; hidden products visible to their owners; product detail
    `lines` = the caller's lines.
S6. Separation (F14-R6): no collection endpoint, total or F3 field changes; `take_snapshots` (F4-c) also writes
    `rbvsn_products_value` (Σ priced product lines) and takes a row for users who own products but no cards
    (cards value 0). Test: adding products leaves `GET /collection` totals and `rbvsn_value` unchanged.
S7. Docs: `docs/api.md`, `AGENTS.md` (table, "products total is never part of the collection value"), `state.md`.

## Acceptance criteria

- [ ] AC1 Migrations round trip and drift; FK restrict on product delete; cascade on user delete (S1, S2).
- [ ] AC2 `tests/test_api_me_products.py`: list and totals, add/merge, patch, delete, validation, foreign ids (S3, S4).
- [ ] AC3 `tests/test_api_products.py` (extend): `owned_qty`, owned filter, hidden visible to owners (S5).
- [ ] AC4 `tests/test_products_separation.py`: collection totals and `rbvsn_value` unchanged; `rbvsn_products_value` written; products-only user gets a row (S6).
- [ ] AC5 Authz matrix; full lanes green; docs (S7).

## Delivery

PR title: `feat(products): owned products with a separate total and snapshot (F14 unit c)`.

## After merge

**Backup first** (`user_products`, `snapshot_products_value`). Deploy.

## Open questions

none

## Log

- L1 (implementer): a merge that would go past 9999 is refused with 400 `validation_error` (`quantity`, `out_of_range`, `max 9999`) and nothing changes; without it the database CHECK would give a 500.
- L2 (implementer): on a merge the existing line keeps its note and takes the new one only if it had none; a note is trimmed and an empty note is null.
- L3 (implementer): a hidden non-single product can be added (the spec only requires a non-single); `PATCH` returns the line itself as `data` (like the F3-c collection PATCH) and never merges.
- L4 (implementer): `rbvsn_products_value` is NULL for users with no product lines and 0 for users whose lines all lack a price; a line value uses the unrounded price times quantity, rounded once to cents, and the total adds the rounded line values.
- L5 (implementer): the `owned` filter also narrows the facets and `total`; the detail `lines` have the shape of `GET /me/products` items without `product`; `take_snapshots` returns one extra key, `products_value`.
- L6 (implementer): `list_products`, `get_product` and `get_product_prices` take the user id (not the username) because `rbuserproducts` is keyed by user id.
