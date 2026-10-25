# F14-b: Products read API — list, detail, price history

| Field | Value |
|---|---|
| Phase / unit | F14 / b — batch 1, unit 28 |
| Branch | `feat/f14b-products-read-api` (from the F14-a branch) |
| Depends on | F14-a, F2-b (price index, `price_summaries` pattern) (stack) |
| Size forecast | ~450 authored lines |
| Risk | `Risk: item 3 (new public contract ProductSummary)` |
| TDD | ON (strict). Runner: `venv/bin/pytest` |
| Sources | F14 phase spec (F14-R3, R4, R7, "API", D-F14-4, D-F14-11) |

## Objective

The app can list sealed products with their current price and 7/30-day change, open a product with its price
history, and know how many the user owns.

## Read first

- `app/services/pricing.py` (`price_summaries`, trend rule), `app/api/v1/cards.py` (F2-c list conventions),
  `app/services/products.py` (F14-a), the F14-a PR body (which price fields non-singles really fill)

## Specs

S1. Price rule (D-F14-4): `product_price(row) -> (value, source)` = first of `rbprc_avg7`, `rbprc_trend`,
    `rbprc_low` that is not NULL and not 0 (source `avg7` | `trend` | `low`); no foil fields. If the F14-a
    preflight showed that one of the three is never filled for non-singles, keep the order anyway (the chain
    skips it). `product_price_summaries(ids)` = latest row value + `change_7d_pct` / `change_30d_pct` with the
    same reference-row rule and rounding as F2-b `price_summaries`, `as_of`; constant query count (≤ 4).
S2. `ProductSummary` = `{id, name, kind, category, set_id, image_src, listed, price: {value, source,
    change_7d_pct, change_30d_pct, as_of} | null, owned_qty}`. `image_src` = null until F14-d (then
    `/riftbound/media/products/<file>`); `owned_qty` = Σ quantity of the caller's lines (0 until F14-c; the
    field exists now and reads `rbuserproducts` once that table exists — in this unit it is always 0).
S3. `GET /products` (U, `api_v1.list_products`): `q` (name substring), `kind[]`, `set[]`, `owned=any|owned|missing`
    (`owned`/`missing` behave as `any` until F14-c), `listed=true|any` (default `true`), `sort=name|price|change_7d|
    change_30d` (default `name`), `dir`, `page`, `per_page` 24-96 (default 48). Only `rbpdt_type = 'nonsingle'`;
    hidden products excluded (F14-c adds "unless owned"). `meta = {page, per_page, total, pages, facets: {kind,
    set}, price_as_of}`. Nulls last in price sorts.
S4. `GET /products/<id>` (U): `ProductSummary` + `{description, columns: {avg7, trend, low, avg30} of the latest
    row | null, lines: []}` (`lines` filled by F14-c); 404 envelope when missing, not a non-single, or hidden and
    not owned.
S5. `GET /products/<id>/prices?range=30d|90d|1y|all` (default 90d): `{range, points: [{date, value, avg7, trend,
    low}]}` ascending, `value` by S1; invalid range → `validation_error`.
S6. Docs: `docs/api.md` (`ProductSummary` as contract, endpoints), `state.md`.

## Acceptance criteria

- [ ] AC1 `tests/test_product_prices.py`: chain order, zero/NULL skipped, changes and `as_of`, statement count for 1 and 50 products (S1).
- [ ] AC2 `tests/test_api_products.py`: filters, facets, sorts with nulls last, pagination, singles and hidden excluded, `listed` filter (S2, S3).
- [ ] AC3 `tests/test_api_product_detail.py`: detail, 404 cases, price history ranges and invalid range (S4, S5).
- [ ] AC4 Authz matrix (U for the three rules); full lanes green; docs (S6).

## Delivery

PR title: `feat(products): products list, detail and price history API (F14 unit b)`.

## After merge

Deploy (no migration). Live: `GET /riftbound/api/v1/products` lists the sealed products with prices.

## Open questions

none
