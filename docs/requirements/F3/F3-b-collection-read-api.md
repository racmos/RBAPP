# F3-b: Collection read API — groups, lines, totals, playset flag

| Field | Value |
|---|---|
| Phase / unit | F3 / b — batch 1, unit 19 |
| Branch | `feat/f3b-collection-read-api` (from the F3-a branch) |
| Depends on | F3-a, F2-b/c/d (stack) |
| Size forecast | ~550 authored lines |
| Risk | `Risk: item 3 (CollectionGroup/CollectionLine are contracts for F3-c…i, F4-c, F7)` |
| TDD | ON (strict). Runner: `venv/bin/pytest` |
| Sources | F3 phase spec (F3-R7, R12, R13, R23, R25, R28, "API"), `decisions-2026-10-25.md` (D-F3-4, D-F3-10) |

## Objective

The app can read a user's collection as groups (one per printing and foil) with their lines, prices, profit
and loss, totals and the playset warning, filtered, sorted and paged on the server.

## Read first

- `app/services/catalog.py` (`card_summary`), `app/services/pricing.py` (`price_summaries`) — F2-b
- `app/api/v1/cards.py` (F2-c: filters, disjunctive facets, `validate_query`), `app/api/v1/` card detail (F2-d,
  `my_lines`), `app/api/v1/meta.py` (`/meta/game`)
- `app/services/collection_rules.py`, `app/models/playset.py` (F3-a)

## Specs

S1. `GET /collection` (U, `api_v1.list_collection`), params exactly as the phase spec "API" row (`q`, `set[]`,
    `domain[]`, `type[]`, `rarity[]`, `foil=any|foil|nonfoil`, `selling=any|yes|no`, `condition[]`,
    `language[]`, `has_purchase=any|yes|no`, `sort=number|name|price|qty|value|pl|trend_7d|updated|rarity`,
    `dir`, `page`, `per_page` 25-200 default 50), validated with `validate_query` (F2-c). `q` matches name
    substring, card id, key `SET-ID` or tag, like F2-c.
S2. Grouping: one `CollectionGroup` per (set, card, foil) of the current user's lines (`rbcol_user =
    current_user.username`); lines ordered by `rbcol_id`. Shapes exactly as the phase spec:
    `CollectionLine = {id, foil, qty, condition, language, purchase_price, selling, sell_qty, sell_price,
    updated_at, market, value, pl_abs, pl_pct}` and `CollectionGroup = {key, card: CardSummary, foil, qty,
    sell_qty, value, lines, keep_playset, playset_short}`. `foil` is `true|false` in JSON; `selling` boolean;
    money as numbers with 2 decimals; `updated_at` = `rbcol_chadat` ISO.
S3. Prices: `market` = `price_summaries` market (non-foil line) or market_foil (foil line); `value` = market ×
    qty (null when market is null); `pl_abs` = (market − purchase_price) × qty and `pl_pct` = (market −
    purchase_price) / purchase_price × 100 rounded half up to 1 decimal (`Decimal`, `ROUND_HALF_UP`; money is
    rounded half up to 2 decimals), both null unless market and a purchase price > 0 exist.
S4. Playset (D-F3-10): `keep_playset` = a `rbkeepplayset` row exists for (user, `name_key(card name)`);
    `kept` = `kept_copies` over **all** the user's lines of that name (every printing and foil, regardless of
    filters); `playset_short` = `keep_playset and kept < playset_size(user)`. The same values for every group of
    that name.
S5. `meta = {page, per_page, total_groups, pages, totals, facets, price_as_of, playset_size}`;
    `totals` over all lines matching the filters (not just the page): `lines`, `qty`, `unique` (distinct
    printings), `value` (Σ value), `cost` (Σ purchase × qty, null when no line has one), `pl` (Σ pl_abs, null when
    none), `selling_value` (Σ over `selling` lines of (sell_price or market) × sell_qty), `foil_pct` (foil qty ×
    100 / qty, 1 decimal, 0 when empty). `facets` = disjunctive counts of groups for `set`, `rarity`,
    `condition`, `language`, `foil`, same technique as F2-c.
S6. Sorts: `number` (set release order + natural id, F2-b), `name`, `price` (market), `qty`, `value`, `pl`
    (pl_abs), `trend_7d`, `updated` (max line `updated_at`), `rarity` (rank); nulls last in both directions;
    tiebreak natural order then foil (non-foil first).
S7. `GET /meta/game` adds `conditions` = `["MT","NM","EX","GD","LP","PL","PO"]` (best → worst) and `languages`
    = `["English","French","German","Spanish","Italian","Simplified Chinese","Japanese","Portuguese","Russian",
    "Korean","Traditional Chinese"]` (D-F3-4).
S8. `GET /cards/{set}/{id}` (F2-d) `my_lines[]` items gain `purchase_price` and `sell_qty`.
S9. Performance: ≤ 10 SQL statements per request whatever the size (statement-count test with 3 and 60
    lines); p95 < 300 ms for 5 000 lines measured once in `flask shell` on generated data (PR body).
S10. Docs: `docs/api.md` (`CollectionLine`, `CollectionGroup` marked as contracts, additive changes only;
     endpoint and params), `state.md`.

## API / data contract

```json
GET /riftbound/api/v1/collection?sort=value&dir=desc&per_page=25
{"success": true,
 "data": {"items": [{"key": "OGN-79:N", "card": {"…": "CardSummary"}, "foil": false, "qty": 4, "sell_qty": 1,
   "value": 4.84, "keep_playset": true, "playset_short": false,
   "lines": [{"id": 1201, "foil": false, "qty": 4, "condition": "NM", "language": "English",
     "purchase_price": 0.80, "selling": true, "sell_qty": 1, "sell_price": 1.30, "updated_at": "2026-10-25T09:12:00",
     "market": 1.21, "value": 4.84, "pl_abs": 1.64, "pl_pct": 51.3}]}]},
 "meta": {"page": 1, "per_page": 25, "total_groups": 1, "pages": 1, "price_as_of": "2026-10-25", "playset_size": 3,
   "totals": {"lines": 1, "qty": 4, "unique": 1, "value": 4.84, "cost": 3.20, "pl": 1.64, "selling_value": 1.30, "foil_pct": 0.0},
   "facets": {"set": {"OGN": 1}, "rarity": {"Rare": 1}, "condition": {"NM": 1}, "language": {"English": 1}, "foil": {"foil": 0, "nonfoil": 1}}}}
```

Authz: `api_v1.list_collection` U. No new error code.

## Acceptance criteria

- [ ] AC1 `tests/test_api_collection_read.py`: grouping and line order; only own lines (another user's lines never appear); each filter; each sort with nulls last; pagination; totals over all filtered lines; facets disjunctive (S1-S6).
- [ ] AC2 `tests/test_api_collection_prices.py`: market by foil, value, pl with and without purchase price, unpriced lines (S3).
- [ ] AC3 `tests/test_api_collection_playset.py`: keep flag per name across printings and foil, kept copies ignore filters, custom playset size, short vs not short (S4).
- [ ] AC4 `tests/test_api_meta_game.py` (extend): conditions and languages (S7); card detail `my_lines` fields (S8).
- [ ] AC5 Statement-count test (S9); authz matrix green; full lanes green; docs and `state.md` (S10).

## Delivery

PR title: `feat(collection): collection read API with groups, totals and playset flag (F3 unit b)`.

## After merge

Deploy (no migration). Live: signed in, `GET /riftbound/api/v1/collection` returns the owner's collection with totals.

## Open questions

none

## Log

- L1 (implementer): `updated_at` is serialised as UTC with a trailing `Z` (`2026-10-25T09:12:00Z`), like `my_lines[].updated_at` of F2-d, instead of the naive form shown in the contract example, so a browser reads it as UTC.
- L2 (implementer): group `key` for a foil group is `<set>-<id>:S` (the example only shows `:N`), the foil code the database already uses.
- L3 (implementer): S9 p95 < 300 ms for 5 000 lines was measured on SQLite in memory (the dev database must not receive generated data): about 340 ms p95 with 1 300 cards and 1 105 groups, of which roughly half is the fixed catalog load shared with `GET /cards`. The statement bound (<= 10) holds.
- L4 (implementer): line filters (`foil`, `selling`, `condition`, `language`, `has_purchase`) act on lines and a group shows and adds up only the matching lines; the spec does not say. Card filters act on groups.
