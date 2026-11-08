# API

JSON API of Rift Manager. Everything under `/riftbound/api/v1/` uses the envelope below (the
Jinja web and its flat `{"success": ...}` endpoints were retired, PR 3/3 of the Jinja retirement).

## Envelope

Success:

```json
{"success": true, "data": {}, "meta": {}}
```

Failure:

```json
{"success": false, "error": "Validation Error", "message": "Invalid request data",
 "code": "validation_error",
 "details": [{"field": "name", "message": "Field required", "type": "missing",
              "code": "required"}]}
```

- `error` is the human name, `message` a clear sentence without internals.
- `code` is an `ErrorCode` (`app/api/error_codes.py`); every value has `code.<value>`
  in `frontend/src/i18n/locales/{es,en}/errors.json` (checked by `tests/test_error_catalogs.py`).
- Each item of `details` has `field`, `message`, `type` and `code` (a `DetailCode`,
  e.g. `required`, `invalid_value`, `out_of_range` with `params`), when it applies.
- Unexpected failures log the traceback and return a clear message; only a signed-in
  admin sees the exception text, under `detail` (`app/errors.py::unexpected_failure`).

## API v1 reference

Public endpoints under `/riftbound/api/v1/` (auth and preferences live in
`AGENTS.md` → "API v1"). Later units extend this reference.

### The `lang` preference (English-only app, owner feedback S21)

The React app is English-only. The API is unchanged: `GET /auth/session` and `GET`/`PATCH
/me/prefs` still carry `lang` (`es`, `en` or `null`), validated by `PrefsUpdate` and stored in
`rbuserprefs.rbprf_lang` with its CHECK `rbuserprefs_lang_chk`, so older clients and stored rows
keep working. The app ignores the value it receives and never sends `lang`. Dropping the column
needs its own migration (a later unit); until then, do not build anything new on `lang`.

### PATCH /me/account

`app/api/v1/me.py` (`api_v1.patch_me_account`, U), logic in `app/services/account.py`: the
signed-in user changes their own email and/or password (the React profile page,
`/riftbound/app/account/profile`; PR 1/3 of the Jinja retirement). Same rules as the Jinja
profile update (PROF-1, PROF-2).

- Body `AccountUpdate` (`app/schemas/validators.py`): `{email?, password?, current_password?}`.
  At least `email` or `password`; `email` is trimmed, at most 120 characters and must contain
  `@`; `password` is 8-128 characters and needs `current_password`; an email-only update does
  not need the password. Only the fields sent change, all or nothing.
- 200 -> `{user: {id, username, email, is_admin}}`, the fresh user (never a password). A
  password change keeps the session (Flask-Login keys it on the user id).
- 400 `validation_error` with `details[{field, message, type, code}]` (`password` too short,
  `email` invalid, a missing `current_password`, an empty body).
- 400 `current_password_incorrect` (`message` "The current password is incorrect"): nothing is
  written, the email included.
- 409 `email_taken` (`message` "That email address is already in use"): another account has
  the address, ignoring case; the caller's own address in another case is fine.
- 429 `rate_limited` with `Retry-After`: 10 calls per hour per IP (`ACCOUNT_RATE_LIMIT`,
  shared scope `account`); the limit also caps guesses of the current password.
- 401 `unauthenticated` for anonymous callers.

### GET /meta/game

`app/api/v1/meta.py` (`api_v1.meta_game`, P): game metadata for the catalog UI.
Anonymous and signed-in callers get 200; `Cache-Control: no-cache`. Response `data`
is a `GameMeta` (see "Data shapes"): `modes` from `GAME_MODES`; `domains`, `types`,
`supertypes`, `rarities` are the S1 tuples of `app/schemas/game_domain.py` followed by
any other distinct non-empty value found in the data (sorted case-insensitively). Types,
supertypes and domains are base values, never the stored compounds: `rbcar_type`
"Champion Unit" gives type `Unit` and supertype `Champion`, a bare "Token" only supertype
`Token`, and `rbcar_domain` "Body Chaos" gives `Body` and `Chaos`
(`catalog.type_facets` / `catalog.parse_domains`), so only a truly unknown word (type
"Creature", domain "Weird") is appended;
`sets` are every `rbset` row ordered newest first: release date descending, sets without a
date last, then id (owner feedback S19; every set dropdown and set button group of the app
uses this order, `sortSetsNewestFirst` in `frontend/src/lib/sets.ts` for lists that do not come
from here), each with
`{id, name, released_on (ISO|null), card_count}`; `price` is
`{provider: "cardmarket", currency: "EUR", updated_on (ISO|null)}` where `updated_on`
is the newest `rbcm_price` date; `rules` is `{deck: {main_size: 39, total_with_champion: 40,
runes: 12, battlefields: 3, sideboard: 10, copies_max: 3, workbench_max: 100}}` (F5-a:
`DECK_RULES` in `game_domain.py`, the values the deck rules engine `app/services/deck_rules.py`
uses; the UI never hardcodes them; other keys of `rules` are reserved for F15); `conditions` is
`["MT","NM","EX","GD","LP","PL","PO"]` (best to worst) and `languages` the 11 languages of
the collection (`CONDITIONS` / `LANGUAGES` in `game_domain.py`, F3-b). No new error code.

### GET /bans

`app/api/v1/bans.py` (U): `{items: [{name, mode, since, reason,
printings: [{set_id, card_id}]}]}` ordered by mode, then name; optional `?mode=1v1|2v2`
(any other value is a 400 `validation_error`). Query validation shares
`validate_query` with `GET /cards` (`app/schemas/validation.py`).

### GET /cards

`app/api/v1/cards.py` (`api_v1.list_cards`, U): one slice of the catalog in the
shared `CardSummary` shape, plus disjunctive facet counts. Anonymous → JSON 401.
Filtering, facets and sort MAY run in Python over the full catalog; at most 12 SQL
statements per request. Prices cover every matching card only when `sort` is
`price`/`trend_*` or a price bound is given, otherwise only the returned page.
Response: `data: {items: [CardSummary]}`,
`meta: {page, per_page, total, pages, facets, price_as_of (ISO|null)}`.
Facet key order is canonical (sets by release order, other facets by the
game-domain tuple order, then unknown values alphabetically) and preserved on
the wire (`sort_keys=False`; Flask `jsonify` sorts keys alphabetically).

Parameters (all optional; `extra='ignore'`; a min greater than its max is valid
and yields an empty result):

| Param | Type / domain | Default |
|---|---|---|
| `q` | str ≤ 100 chars (trimmed) | — |
| `text` | str ≤ 100 chars (ability text) | — |
| `set`, `domain`, `type`, `supertype`, `exclude_supertype`, `rarity`, `tag` | repeated str, each ≤ 50 chars, ≤ 50 values | `[]` |
| `domain_match` | `any` \| `all` \| `subset` | `any` |
| `energy_min`, `energy_max`, `power_min`, `power_max`, `might_min`, `might_max` | int 0-99 | — |
| `price_min`, `price_max` | float 0-100000 | — |
| `owned` | `any` \| `owned` \| `missing` | `any` |
| `banned_in` | `1v1` \| `2v2` \| `any` | — |
| `base_only` | bool | `false` |
| `sort` | `number` \| `name` \| `price` \| `trend_7d` \| `trend_30d` \| `rarity` \| `energy` \| `power` \| `might` | `number` |
| `dir` | `asc` \| `desc` | `asc` |
| `page` | int 1-10000 | 1 |
| `per_page` | int 1-192 | 48 |

Filter rules (case-insensitive; OR inside a parameter, AND across parameters):
`q` matches name/tag substring, `card_id`, `key` (`OGN-79a`), or the card `number`
when `q` is digits-only; `text` matches the ability; `set`/`rarity`/parsed
`type`/`supertype` match their lists; `exclude_supertype` drops cards with a listed
supertype (cards without supertype stay). Types, supertypes and domains are base values
(`catalog.type_facets`, `catalog.parse_domains`): "Champion Unit" is type `Unit` and
supertype `Champion`, "Token Battlefield" type `Battlefield` and supertype `Token`, a bare
"Token" supertype `Token` with no type, "Body Chaos" domains `Body` and `Chaos`; a card
counts in the facets under each of its base values and `type=Unit` / `domain=Body` /
`supertype=Token` match it the same way. `CardSummary.type`/`supertype`/`type_raw` are
unchanged (a bare "Token" is still `type: "Token"`, `supertype: null` there); `tag` needs one listed tag; `domain_match` = `any`
shares a domain, `all` requires every listed domain, `subset` requires every card
domain to be listed (a card without domains matches); ranges are inclusive and
exclude null-valued cards once bounded; price bounds apply to `price.market` and
exclude cards without a market price; `owned=owned|missing` filters on
`owned.total`; `banned_in` filters by ban mode (`any` = banned in at least one);
`base_only=true` keeps base printings only. `meta.facets` holds `set`, `domain`,
`type`, `supertype`, `rarity` counts computed over the cards matching every filter
except that facet's own, plus the top-30 `tag` list (`{tag, count}`) over the
cards matching every filter except `tag`. Sort ties always break by ascending
`natural_key`; `dir=desc` reverses the main key only; nulls are always last.
`meta.total` counts matching cards, `pages = ceil(total / per_page)` (0 when
total is 0); a page past the end returns `items: []` with 200.

```http
GET /riftbound/api/v1/cards?domain=Fury&sort=price&dir=desc&per_page=2
```

### GET /cards/<set_id>/<card_id>

`app/api/v1/cards.py` (`api_v1.get_card`, U): one card in the shared
`CardSummary` shape plus the keys below. Lookup is exact on both segments;
a missing card answers 404 with the standard envelope. Anonymous → JSON 401.
Filtering, ordering and user scoping run in Python over batched queries
(at most 10 SQL statements).

Response: `data: CardDetail` = `CardSummary` plus `ability` (text|null),
`artist` (already in the summary), `set: {id, name, released_on (ISO|null)}`,
`price_detail` (null when unmapped; else `{date, product_id, columns` with the
11 `rbprc_*` columns as floats|null, `foil_product_id`, `foil_columns}` from
the latest rows of the canonical products, foil only when foilable and a
different product), `printings: [CardMini]` (every printing of the name by
`natural_key`, including itself), `related: [CardMini]` (up to 12 base
printings of other names sharing ≥1 tag, most shared tags first, then name),
`ban_info` (`ban_info(name)`, `[]` when legal), `my_lines` (the current user's
rows of this printing ordered by foil N first, condition, language, id; each
`{id, foil (bool), qty, condition, language, selling, sell_price, playset,
updated_at (UTC `…Z`)}`), `in_decks` (the current user's decks v2: the current
version of each deck; `{deck_id, name, qty}` where `deck_id` is the deck id of
`GET /decks/<id>` and the app route `/decks/:id`, and `qty` sums every printing of
the same name over legend, champion, main, runes, battlefields and sideboard, never
the workbench; missing-card entries skipped; only decks with `qty > 0`, ordered by
name; one SQL statement). The legacy `rbdecks` table is not read.

```http
GET /riftbound/api/v1/cards/OGN/79
```

### GET /collection

`app/api/v1/collection.py` (`api_v1.list_collection_groups`, U, F3-b): the signed-in user's
collection as groups. Query via `validate_query` (`CollectionListQuery`): `q` (name
substring, card id, key `SET-ID` or tag), repeated `set`, `domain`, `type`, `rarity`,
`condition`, `language`; `foil=any|foil|nonfoil`, `selling=any|yes|no`,
`has_purchase=any|yes|no`; `sort=number|name|price|qty|value|pl|trend_7d|updated|rarity`
(`number` default; nulls last in both directions; ties by catalog order, non-foil first),
`dir=asc|desc`, `page`, `per_page` 25-200 (default 50). Card filters (`q`, `set`, `domain`,
`type`, `rarity`) drop groups; `type` and `domain` match base values as in `GET /cards`
(`type=Unit` keeps "Champion Unit", `domain=Body` keeps "Body Chaos"); line filters (`foil`, `selling`, `condition`, `language`,
`has_purchase`) drop lines, and a group lists and adds up only its matching lines.
`data.items` are `CollectionGroup`s; `meta` is `{page, per_page, total_groups, pages,
totals, facets, price_as_of, playset_size}`. `totals` cover every matching line, not only
the page: `{lines, qty, unique (distinct printings), value, cost (null without purchase
prices), pl (null without any), selling_value, foil_pct}`. `facets` are disjunctive group
counts for `set`, `rarity`, `condition`, `language` and `foil` (`{foil, nonfoil}`).
Money is rounded half up to 2 decimals, `pl_pct` to 1. At most 10 SQL statements whatever
the size of the collection (10 since F16-b: one batched query for the line locations). Other
users' lines never appear.

Locations (F16-b, additive): repeated `location` (location codes, ignoring case, at most 50) is
a line filter: it keeps the lines with copies in any of those locations (an unknown code
matches nothing; it also applies to `GET /collection/export`). Each line of `GET /collection`
appends `locations` (its first 5 locations in the user's order: `[{location_id, code,
description, qty}]`), `locations_more` (how many more it has) and `unassigned` (copies in no
location). The group keys do not change, and the lines of the write responses (`POST`,
`PATCH`, split, bulk, `GET /cards/<set>/<id>`) do not carry these keys.

```http
GET /riftbound/api/v1/collection?sort=value&dir=desc&per_page=25
```

### GET /collection/export

`app/api/v1/collection.py` (`api_v1.export_collection`, U, F3-d): the collection as a CSV download.
Query: every `GET /collection` filter (`q`, `set`, `domain`, `type`, `rarity`, `condition`,
`language`, `foil`, `selling`, `has_purchase`; `sort`, `dir`, `page` and `per_page` are accepted and
ignored), `format=rbapp|cardmarket` (default `rbapp`; anything else -> 400 `validation_error`) and
`only_selling=true|false` (default false, forced true for `cardmarket`). The answer is
`text/csv; charset=utf-8`, starts with a UTF-8 BOM, is streamed one row at a time (the filtered
lines are held in memory to order them) and carries `Content-Disposition: attachment` and
`X-Rows-Exported: <n>`. A text cell that starts with `=`, `+`, `-`, `@`, a tab or a carriage
return gets a leading `'` so a spreadsheet does not read it as a formula.

- **RBAPP** (`rbapp_collection_<YYYYMMDDHHMMSS>.csv`, UTC): comma, minimal quoting, `\n`; header
  `set_id,card_id,name,foil,qty,condition,language,purchase_price,selling,sell_qty,sell_price`;
  one row per line in `sort=number` order; `foil` `S`/`N`, `selling` `Y`/`N`, prices with a dot and
  two decimals, empty when null. Re-importable by F3-e.
- **Cardmarket** (`<YYYYMMDDHHMMSS>_cardmarket.csv`): same bytes as the old Jinja export
  (`QUOTE_ALL`, `\n`, header `name,language,quantity,price`, ordered by card name then non-foil
  first): only `selling` lines with `sell_qty` > 0; `name` is the Cardmarket product name of the
  mapped product (exact foil mapping, else unclassified, else any; newest `rbcm_products` row),
  else the card name; `quantity` is `sell_qty`; `price` is `sell_price`, else the market price,
  else `0.00`, formatted with `{:.2f}` like the Jinja export. A golden test compares the output with
  the Jinja route's bytes, frozen in `tests/fixtures/collection_export_cardmarket_golden.csv` before the
  route was removed.

### Collection import (F3-e)

Two steps, both `U`, JSON bodies. Only the RBAPP format (the file `GET /collection/export` writes)
is read; other formats wait for the owner's samples.

- `POST /collection/import/preview` `{text, format?: "auto"|"rbapp"}` -> 200 `{preview_id, format,
  rows, summary: {total, ok, warning, error, printings}}`. `text` is at most 2 MB and 10 000 data
  rows (else `validation_error`, field `text`, `out_of_range`, `params.max`). A UTF-8 BOM is
  stripped; the header is required and must contain every RBAPP column (any order, any case,
  extra columns ignored), else 400 `import_format_unknown`. Nothing is written to the collection.
  The parsed rows are stored in `rbimportpreviews` for 30 minutes; expired previews are deleted at
  the start of every preview request and a user keeps only their latest one.
- Each row is `{line (1-based, header = 1), status: ok|warning|error, reason_codes, card?
  (CardSummary when resolved), set_id, card_id, foil, qty, condition, language, purchase_price,
  selling, sell_qty, sell_price}`. Reason codes: errors `card_not_found`, `invalid_value` (foil,
  language or selling), `foil_not_allowed`, `invalid_qty` (1-9999), `invalid_price` (empty or >= 0
  up to 99999.99, `.` or `,` as decimal separator), `invalid_sell_qty` (0-`qty`); warnings
  `name_mismatch` (the key wins), `unknown_condition` (stored as null), `duplicate_row` (same merge
  key as an earlier row; merged on commit). `set_id` is upper-cased and `card_id` lower-cased;
  `foil` accepts `S|N|true|false|1|0`; an empty `sell_qty` is 0, or `qty` when `selling` is `Y`;
  a leading `'` that the export adds before formula-like text is removed.
- `POST /collection/import/commit` `{preview_id, mode: "add"|"replace"}` -> 200 `{created, merged,
  replaced, skipped}`. An unknown, expired or another user's preview -> 410 `import_expired`. One
  transaction, all or nothing: `add` adds every `ok`/`warning` row with the merge rule of
  `POST /collection`; `replace` first deletes the user's lines of every (set, card, foil) present
  in the valid rows (`replaced` counts them), printings not in the file are untouched. Error rows
  are skipped. The preview is deleted when the commit succeeds.

### Collection writes (F3-c)

`app/api/v1/collection.py`, all `U`, JSON bodies, scoped to the signed-in user: a line that is not
theirs answers 404 (never 403). Every write stamps `rbcol_chadat`; money is rounded half up to 2
decimals; lines come back as `CollectionLine` plus `set_id` and `card_id`.

- `POST /collection` `{set_id, card_id, foil, qty 1-9999, condition?, language?, purchase_price?,
  selling?, sell_qty?, sell_price?}` -> 201 `{line, merged}`. An identical line (same card, foil,
  condition, language, purchase price, selling flag and sell price, NULL-safe) is merged: `qty` and
  `sell_qty` are added in SQL. `selling: true` without `sell_qty` sells every copy; without
  `sell_price` it asks market x 1.05 (null without a market). Errors: unknown card ->
  `validation_error` on `card_id`; `foil: true` on a card with no foil version -> 400
  `foil_not_allowed`; `sell_qty` > `qty` -> 409 `insufficient_quantity`.
- `PATCH /collection/<id>` any of `qty, condition, language, purchase_price, selling, sell_qty,
  sell_price, if_updated_at` -> the line. Lowering `qty` below `sell_qty` lowers `sell_qty`;
  `sell_qty` > `qty` -> 409 `insufficient_quantity` (`params.available` = the quantity);
  `selling: true` on a line with nothing for sale sells every copy and, without any price, asks
  market x 1.05; `selling: false` keeps `sell_qty` and `sell_price`. The edit is applied only if the
  line still has the change time it was read with: a different `if_updated_at` (ISO, compared to the
  second) or a concurrent change -> 409 `stale_line`, nothing changed.
- `DELETE /collection/<id>` -> `{deleted: <line>}`; posting that object back to `POST /collection`
  restores the line (undo).
- `POST /collection/<id>/split` `{qty, condition?, language?, purchase_price?, selling?, sell_price?}`
  -> `{source, target, merged}`: moves `qty` copies (at least one stays, else 409
  `insufficient_quantity` with `available = quantity - 1`) into a new line made from the source with
  the given fields replaced, or into an identical existing line (quantity added in SQL). The source
  `sell_qty` is clamped to its new quantity; the target sells all its copies when `selling` is true,
  none otherwise. A split that changes nothing moves nothing (`merged: true`, source = target).
- `POST /collection/bulk` `{ids: 1-1000, set: {condition?, language?, selling?,
  sell_qty_rule: all|none|keep_n, keep: 1-9, sell_price?, purchase_price?}}` -> `{updated: n}`, or
  `{ids, delete: true}` -> `{deleted: [lines]}`. All or nothing: an id that is not the user's -> 404
  and nothing changes. `keep_n` sells `max(0, qty - keep)`.
  Locations (F16-x): without `set.location_id` every line keeps its locations (the other fields are
  changed in place). `location_id: <id>` (a location of the user, else the 404 envelope) puts all
  the copies of each line there (its assignment becomes `{id: quantity}`, unassigned copies
  included); `location_id: null` makes them all unassigned. `location_id` alone is a non-empty
  `set` (`null` included) and combines with the other fields in the same transaction. A locked
  location whose quantity would change on any line (a locked target, or copies of a line in a
  locked location) -> 409 `location_locked` with `params {codes: "B001-F001-P0002, DECK-001"}`
  (the user's order, joined with ", ") and nothing changes, the other fields included. A bad
  `location_id` (0, negative, not an integer) -> 400 `validation_error`.
- `POST /collection/keep-playset` `{set_id, card_id, keep}` -> `{name, keep_playset, kept,
  playset_size, playset_short}`: inserts or deletes the `rbkeepplayset` row of the card name
  (idempotent). `kept` counts the copies not for sale of every printing of the name.
- `GET`/`PATCH /me/prefs` also carry `playset_size` (`null` = 3, otherwise 1-9; out of range ->
  `validation_error`, `out_of_range`, `params {min: 1, max: 9}`).

New error codes: `foil_not_allowed` (400), `insufficient_quantity` (409, `params.available`),
`stale_line` (409).

### GET /products

`app/api/v1/products.py` (`api_v1.list_products`, U, F14-b): the sealed product catalog
(`rbproducts`, only `rbpdt_type = 'nonsingle'`; hidden products appear only to users who own
them, F14-c). Query via
`validate_query` (`ProductListQuery`): `q` (case-insensitive name substring), repeated `kind` and
`set` (case-insensitive), `owned=any|owned|missing` (F14-c: `owned` = the caller has at least one
copy in `rbuserproducts`, `missing` = none; it also narrows the facets and `total`), `listed=true|any` (default `true`: only products in the latest Cardmarket file),
`sort=name|price|change_7d|change_30d` (default `name`; nulls last in both directions, ties by
name), `dir=asc|desc`, `page`, `per_page` 24-96 (default 48). Any other value -> 400
`validation_error`. `data.items` are `ProductSummary`s; `meta` is `{page, per_page, total,
pages, facets: {kind, set}, price_as_of}`. The facets are disjunctive counts (each ignores its
own filter): `kind` in the `PRODUCT_KINDS` order, `set` by set release order then unknown set
ids by name; products with a NULL kind or set are not counted. `price_as_of` is the newest
`rbcm_price` date (as in `GET /cards`). At most 10 SQL statements whatever the size of the
catalog (6 today: the caller's owned quantities are one more).

```http
GET /riftbound/api/v1/products?kind=box&sort=price&dir=desc
```

### GET /products/<id>

`api_v1.get_product` (U): `ProductSummary` + `{description, columns: {avg7, trend, low, avg30}
(floats or null, the product's latest `rbcm_price` row) | null (no row), lines}`. `lines`
(F14-c) are the caller's `rbuserproducts` lines of the product, oldest first, each an
`OwnedProductLine` without `product`: `{id, quantity, purchase_price|null, note|null,
value|null, pl_abs|null, pl_pct|null, updated_at}` (`[]` when the caller owns none; another
user's lines are never shown). A missing id, a product that is not a non-single, or a hidden one
the caller does not own answers the 404 envelope; an unlisted product is shown with
`listed: false`. At most 6 SQL statements.

### GET /products/<id>/prices

`api_v1.get_product_prices` (U): `{range, points: [{date (ISO), value, avg7, trend, low}]}`,
ascending, one point per `rbcm_price` row of the product. Query `range: 30d|90d|1y|all = 90d`
(`ProductPricesQuery`; a bad range -> 400 `validation_error`, `field: "range"`,
`code: invalid_value`); the window runs from the latest row - 30/90/365 days inclusive (`all` =
every row). `value` follows the product rule below; a product without rows answers
`points: []`. Same 404 cases as the detail (a hidden product's history is shown to its owners).

### Owned products (F14-c)

`app/api/v1/me_products.py` (U), logic in `app/services/user_products.py`. The caller's sealed
products (`rbuserproducts`). The products total is **never** part of the collection value:
`GET /collection`, its totals and every F3 field ignore these lines; the daily snapshot keeps
them apart in `rbvsn_products_value`.

`OwnedProductLine` = `{id, product: ProductSummary, quantity, purchase_price|null, note|null,
value|null, pl_abs|null, pl_pct|null, updated_at (UTC, "YYYY-MM-DDTHH:MM:SSZ")}`, keys in this
order. `product.owned_qty` adds up all the caller's lines of that product. `value` = product
price (`ProductSummary.price.value`) x quantity, null without a price; P/L as F3-b: `pl_abs` =
(price - purchase) x quantity and `pl_pct` = (price - purchase) / purchase x 100, both only with a
price and a purchase price above 0. Money is rounded half up to cents, `pl_pct` to one decimal.

- `GET /me/products` (`api_v1.list_my_products`) -> `{items: [OwnedProductLine], total: {value,
  lines, qty, unpriced}}`: ordered by product name (case-insensitive), then id; hidden products
  the caller owns are included. `total.value` = sum of the priced line values (0 when none),
  `lines` = number of lines, `qty` = copies, `unpriced` = lines without a price. No pagination.
  At most 6 SQL statements whatever the number of lines.
- `POST /me/products` (`api_v1.create_my_product`) body `{product_id (int >= 1), quantity (strict
  int 1-9999), purchase_price? (0-99999.99 or null), note? (up to 200 characters, trimmed; empty =
  null)}` -> 201 `{line, merged}`. An unknown `product_id` or one that is not a non-single -> 400
  `validation_error` with `details: [{field: "product_id", message: "unknown product", type:
  "value_error", code: "invalid_value"}]` (a hidden non-single can be added). A line of the same
  product with the same purchase price (NULL-safe) gets the quantity added in SQL (`merged:
  true`); it keeps its note, or takes the sent one when it had none. A merge past 9999 copies ->
  400 `validation_error`, `field: "quantity"`, `code: out_of_range`, `params: {max: 9999}`, and
  nothing changes. Extra keys are ignored, so a deleted line can be posted back with its
  `product_id`.
- `PATCH /me/products/<id>` (`api_v1.update_my_product`) any of `{quantity, purchase_price,
  note}` (same domains; `quantity: null` is a 400; `null` clears the price or the note) -> 200 the
  `OwnedProductLine`. No merge on edit. `updated_at` is refreshed.
- `DELETE /me/products/<id>` (`api_v1.delete_my_product`) -> 200 `{deleted: OwnedProductLine}`
  (its `product.owned_qty` no longer counts the line).

An id that does not exist or is another user's line -> the 404 envelope (PATCH/DELETE).

### Locations (F16-b)

`app/api/v1/locations.py`, all `U`, logic in `app/services/locations.py` (F16-a). Everything is
scoped to the signed-in user: a location or line id that is not theirs (or does not exist) ->
the 404 envelope, never 403.

`Location` = `{id, code, description|null, position (1..n, the user's order), locked (bool),
deck_id|null (the mounted deck, F16-e), copies (copies kept there), cards (lines kept there)}`,
keys in this order. `code` is 1-32 letters, digits or `-`, unique per user ignoring case;
`description` is up to 200 characters (trimmed; empty = null).

- `GET /locations` (`api_v1.list_locations`) -> `{data: {items: [Location]}, meta:
  {unassigned_copies}}` in the user's order; `unassigned_copies` = the copies of all the user's
  lines that are in no location.
- `POST /locations` (`api_v1.create_location`) `{code, description?}` -> 201 `Location`, last in
  the order. A code the user already has (ignoring case) -> 409 `already_exists`; a bad code ->
  400 `validation_error` on `code` (`required`, `too_short`, `too_long` with `params.max` 32,
  `invalid_format`, or `invalid_value` when it is not a string).
- `GET /locations/next-code?bump=block|row|pack[&after=CODE]` (`api_v1.suggest_location_code`)
  -> `{code}`: the suggested `B001-F001-P0001` code (F16-R1a, D6): the chosen part goes up by one,
  the parts to its right restart at 1, widths and case are kept and codes the user already has
  are skipped. Without `after` it follows the user's newest location with that pattern, or is
  `B001-F001-P0001` when there is none; `after` without the pattern (`DECK-001`, `Binder`) or a
  result over 32 characters -> `code: null`. `bump` is required; another value -> 400.
- `PATCH /locations/<id>` (`api_v1.update_location`) any of `{code, description, locked}` ->
  `Location`. Only the sent keys change; `description: null` clears it; `code: null` or
  `locked: null` -> 400. A **locked location can be renamed** (code and description are only
  labels); what a lock makes read-only is the copies it holds. A duplicate code -> 409
  `already_exists` and nothing changes.
- `DELETE /locations/<id>` (`api_v1.delete_location`) -> `{deleted: Location}` (with its counts
  before the delete). Its copies become unassigned (line totals do not change) and the order
  closes up. A locked deck location (`deck_id` set) -> 409 `location_locked`; a locked ordinary
  location can be deleted.
- `PUT /locations/order` (`api_v1.reorder_locations`) `{ids}` -> `{items: [Location]}`: every
  location id of the user, each once, in the new order (positions 1..n). A missing, repeated,
  foreign or unknown id -> 400 `validation_error` on `ids` (`invalid_value`); nothing changes.

Copies of one collection line (F16-R4). `LineLocations` = `{locations: [{location_id, code,
description|null, locked, qty}] (the user's order), unassigned, total (the line quantity)}`.

- `GET /collection/<id>/locations` (`api_v1.get_line_locations`) -> `LineLocations`.
- `PUT /collection/<id>/locations` (`api_v1.put_line_locations`) `{assignments: [{location_id,
  qty (1-9999)}]}` (each location at most once, else 400) -> `LineLocations`. Replaces the line's
  assignment atomically; a location of the line that is not sent loses its copies (`[]` frees
  them all). A locked location whose quantity would change (raised, lowered or dropped) -> 409
  `location_locked`, so a locked location must be sent with its current quantity; then, a sum
  above the line quantity -> 409 `location_over_quantity` with `params {max: <line quantity>,
  requested: <sum>}`. Nothing changes on any error.
- `POST /collection/<id>/locations/move` (`api_v1.move_line_locations`) `{from_location_id|null,
  to_location_id|null, qty (1-9999)}` -> `LineLocations`; `null` is unassigned, the two sides must
  differ (else 400). From unassigned, more than the unassigned copies -> 409
  `location_over_quantity` (`params {max: <unassigned>, requested}`); from a location, more than
  it holds -> 409 `insufficient_quantity` (`params.available`); a locked side -> 409
  `location_locked`.

New error codes: `location_over_quantity` (409, `params.max`, `params.requested`) and
`location_locked` (409). `insufficient_unlocked` (deck mount) arrives with F16-e.

### Decks (F5-d)

`app/api/v1/decks.py`, all `U`, logic in `app/services/decks.py`, rules from
`app/services/deck_rules.py` (F5-a). Only the owner sees a deck (D-F5-9): another user's deck,
an unknown id or an unknown version seq -> the 404 envelope on every route, never 403;
anonymous -> 401 `unauthenticated`. Text import/export: "Deck import/export (F5-e)" below; the
share link and the public deck: "Deck sharing (F5-g)" below; deck vs collection (F5-f) is not
here yet.

Shapes (keys in this order):

- `Content` = content v2 (F5-R6, `app/schemas/deck_content.py`): `{v: 2, legend: ref|null,
  champion: ref|null, main: [line], runes: [line], battlefields: [ref], sideboard: [line],
  workbench: [line]}`, `ref = {set, id}`, `line = {set, id, qty ≥ 1}`. Printings are kept.
- `DeckCard` = `CardMini` (`set_id, card_id, key, name, domains, type, supertype, rarity,
  image_src, image_thumb_src, is_base, market, owned_total`) + `tags, energy, power, might,
  variants, keywords` (the last five added by F5-i). `market` is the non-foil price chain of the
  printing; `owned_total` the caller's copies of that printing. `energy`, `power`, `might` are
  `int | null` as stored; `variants` (≥ 1) counts the catalog printings that share the card's
  `name_key`, every set included (the "N alt arts" badge is `variants - 1`); `keywords` are the
  `[Name]` markers of the ability text (`catalog.keywords_of`, **approximate**: no column stores
  them): a trailing number dropped (`[Assault 2]` -> `Assault`), reminder text in parentheses,
  markers of fewer than two letters (`[2]`, `[>]`, `[A]`) and `:rb_*:` symbols skipped, each word
  capitalised, distinct, in order of first appearance. They come from the card rows the request
  already reads: no extra SQL statement.
- `Legality` = `{"1v1": Result, "2v2": Result}`, `Result = {legal, issues: [{code, params}],
  completeness: {legend, champion, main, runes, battlefields, sideboard: {have, need, missing}}}`
  (`deck_rules.validate`, issue codes in `F5-a-deck-rules-engine.md`). Always computed on read,
  with the bans of that moment (`ban_map`, by `name_key`); never stored.
- `DeckHead` = `{id, name, mode, visibility, created_at, updated_at, share}` (ISO UTC, `Z`);
  `share` = `{slug, url} | null` (F5-g, additive: every shape built on `DeckHead` carries it).
- `DeckListItem` = `DeckHead` + `{legend: DeckCard|null, champion: DeckCard|null, domains,
  counts: {main, runes, battlefields, sideboard, workbench}, value, value_unpriced, legal:
  {"1v1": bool, "2v2": bool}, issues: {"1v1": [code], "2v2": [code]}}`. `counts` sum the copies
  of each zone (battlefields: entries); the workbench is its own count and never part of `main`.
  `issues` are the distinct issue codes in engine order.
- `DeckDetail` = `DeckHead` + `{current_seq, content, cards: {"<set>-<id>": DeckCard},
  unknown_cards: [{zone, set, id}], domains, counts, value, value_unpriced, legality}`.
  `cards` holds every known printing of the content; a printing missing from the catalog is
  left out of `cards` and of the legality and listed in `unknown_cards` (it still counts in
  `counts` and as unpriced).
- `VersionItem` = `{seq, note|null, created_at, is_current}`; `VersionDetail` = `VersionItem` +
  `{content, cards, unknown_cards, domains, counts, value, value_unpriced, legality}`.

**Value rule** (EUR): Σ market price × copies over legend, champion, main, runes, battlefields
and sideboard, rounded to cents. The workbench never counts (product.md). `value_unpriced` = the
copies of those zones without a price (cards missing from the catalog included).

Routes:

- `GET /decks` (`api_v1.list_decks`) -> `{items: [DeckListItem]}`, newest `updated_at` first
  (then id descending). 9 SQL statements whatever the number of decks (user, heads, current
  versions, cards, sets, bans, prices ×2, owned copies).
- `POST /decks` (`api_v1.create_deck`) `{name (trimmed, 1-80), mode: 1v1|2v2}` -> 201
  `DeckDetail`: private, version 1 with the empty content as the current version. A name the
  caller already has (exact) -> 409 `already_exists`; another user's name is free.
- `GET /decks/<id>` (`api_v1.get_deck`) -> `DeckDetail` of the current version.
- `PATCH /decks/<id>` (`api_v1.update_deck`) any of `{name, mode, visibility: private|public}` ->
  `DeckDetail`. Only the sent keys change, none is nullable (400); a taken name -> 409
  `already_exists`. No version is created; `updated_at` is refreshed.
- `DELETE /decks/<id>` (`api_v1.delete_deck`) -> `{deleted: DeckHead}`; every version goes too.
- `POST /decks/<id>/duplicate` (`api_v1.duplicate_deck`) optional JSON body `{name?}` (no body,
  `{}`, `null` or a blank name = the default name; otherwise trimmed, 1-80 like `POST /decks`)
  -> 201 `DeckDetail` of a **new** deck of the caller: same `mode`, the source's **current**
  content copied as stored (every zone, workbench included; cards missing from the catalog and
  hard limits kept, no rules check), `visibility` private, no share link, its own version 1
  (`current_seq` 1, note null). Not copied: the version history and the version notes. Default
  name: the first free `<name> (copy)`, `<name> (copy 2)`, `<name> (copy 3)`... among the
  caller's decks, the source name cut (trailing spaces dropped) so the whole fits 80. An
  explicit name the caller already has -> 409 `already_exists` (as `POST /decks`); an invalid
  one -> 400 `validation_error`; a body that is not JSON -> 400. The source is not changed
  (`updated_at` and current version kept). Another user's deck or an unknown id -> 404. No
  audit row (deck writes are not audited). 16 SQL statements whatever the number of cards.
- `PUT /decks/<id>/content` (`api_v1.put_deck_content`) `{content: Content}` -> `DeckDetail`.
  Autosave (D-F5-3): rewrites the **current** version in place, refreshes the head's
  `updated_at`, creates no version. The shape is `DeckContentV2` (400 `validation_error`, fields
  like `content.main.0.qty`). A card not in the catalog -> 400 `validation_error` with one detail
  per card `{field: "content.main.1", message: "unknown card XXX-9", type: "value_error", code:
  "invalid_value"}`. A hard limit (F5-R9, `deck_rules.hard_limit_violations`: copies per name > 3
  over main + sideboard + workbench + champion, sideboard > 10, workbench > 100 distinct names,
  battlefields > 3, runes > 12, a token outside the workbench) -> 400 `deck_limit_exceeded` with
  `params` = the first violation `{rule: copies|sideboard|workbench|battlefields|runes|token,
  max, name?}` and a `message` naming them all (`The deck goes over a limit: copies (max 3)
  ("Desert Scout"); runes (max 12).`). Nothing is stored on any error. Soft rules (sizes not
  reached, identity, champion tag, bans) never block: they come back in `legality`.
- `GET /decks/<id>/versions` (`api_v1.list_deck_versions`) -> `{items: [VersionItem]}`, newest
  seq first.
- `POST /decks/<id>/versions` (`api_v1.create_deck_version`) `{note?: ≤ 200, trimmed, empty =
  null}` (send `{}` for no note; a JSON body is required) -> 201 `VersionDetail`: a copy of the
  current content as a **new** version (next seq), which becomes the current one; the older
  versions never change again through autosave.
- `GET /decks/<id>/versions/<seq>` (`api_v1.get_deck_version`) -> `VersionDetail`.
- `POST /decks/<id>/versions/<seq>/restore` (`api_v1.restore_deck_version`) -> 201
  `VersionDetail`: version `seq` is copied into a **new** version (next seq, note `Restored from
  version <seq>.`), which becomes the current one. No version is overwritten or deleted.
- `GET /decks/<id>/diff?a=&b=` (`api_v1.diff_deck_versions`, both ≥ 1, else 400 "Invalid query
  parameters") -> `{a, b, zones: {legend, champion, main, runes, battlefields, sideboard,
  workbench: {added, removed, changed}}, cards: {"<set>-<id>": DeckCard}}`. Entries
  `{set, id, before, after}` (copies; 1 for legend, champion and each battlefield) compare
  printings (set, id) from `a` to `b`: `added` only in `b`, `removed` only in `a`, `changed`
  in both with another quantity; ordered by card name (`name_sort_key`), then set and id.
  `cards` names every printing in an entry that is in the catalog.

New error code: `deck_limit_exceeded` (400, `params {rule, max, name?}`). Legality issues are
never HTTP errors.

### Deck import/export (F5-e)

`app/api/v1/decks.py`, all `U`, logic in `app/services/decks.py` over the pure
`app/services/deck_text.py`. One format only (owner, 2026-11-04): the common text every deck site
exports (`docs/requirements/F5/samples/deck-export-text-1.txt`):

```
Legend:
1 Riven, The Exile

Champion:
1 Riven, Broken Blade

MainDeck:
3 Discipline
...

Battlefields:
1 Star Spring

Rune Pool:
7 Chaos Rune
5 Calm Rune

Sideboard:
2 Decree of Focus
```

`format` is `auto` (default) or `text` (the same); anything else -> 400 `import_format_unknown`
(`The deck format is not recognised. Use the text format.`). `text` is at most 64 KB (UTF-8) and
2000 lines (a final newline ends a line), else 400 `validation_error` (`details[0]` `{field:
"text", code: "too_long", params: {max: 65536 | 2000}}`).

**Parser.** Lines split on `\r\n`, `\r` or `\n`, trimmed; blank lines ignored. Headers: case-insensitive,
with or without a final `:` / `：`, spaces collapsed: `Legend(s)`, `Champion(s)`, `Chosen Champion`,
`MainDeck`, `Main Deck`, `Main`, `Battlefield(s)`, `Rune Pool`, `Runes`, `Rune`, `Sideboard`,
`Side Board` (and the prototype's Spanish ones). Card lines: `N Name`, `Nx Name`, `N x Name`; a
line without a quantity is 1. The same name twice in a block is one line (quantities added).
Resolution: an explicit id `SET-ID` (the whole text, a final parenthesis `Name (OGN-247)` or a
final square bracket `Name [OGN-247]`) wins when it exists; else the `name_key` of the name (case,
typographic apostrophes, spaces); else a legend written `Tag, Name` (legends store the bare name,
the champion is a tag); else the name without accents. A name gives its base printing (`is_base`).
Ids ignore the case of the set and of the suffix and the leading zeros of the number: `[RAD-043]`,
`[rad-43]` and `(RAD-0043)` are `RAD` `43`, `[VEN-044A]` is `44a`, `[VEN-T04]` is `t04`.

**Square brackets** (owner, 2026-11-05: the export of the deck sites the owner uses ends each line
with its printing, `1 Riven, Broken Blade [RAD-043]`) are always a printing, never silently
replaced by another one: a bracket id that is not in the catalog loads the base printing of the
written name with `printing_unknown`, or nothing with `unknown_card` `params {id}` when the name
is not known either; an id whose card has another name than the written one loads that printing
with `name_mismatch` (also for a parenthesis id). A parenthesis that is not an id (`(Alt Art)`)
is not a warning: the name before it is read. The export never writes brackets (unchanged).

`Warning` = `{line: int|null, text, reason_code, params}` (`line` 1-based, `text` the trimmed
line), in line order, then the hard limits:

| reason_code | When | Effect |
|---|---|---|
| `no_zone` | a card line before any header or after an unknown one | placed by type (Legend -> legend, Champion Unit -> champion, Battlefield, Rune, else main) |
| `zone_unknown` | a `...:` line that is not a known header | its lines get `no_zone` |
| `quantity_invalid` | quantity outside 1..99 | line skipped |
| `unknown_card` (`params {id}` when written `Name [SET-NNN]`, else `{}`) | no card matches | not in the content |
| `printing_unknown` (`params {id, name}`) | the `[SET-NNN]` printing is not in the catalog, the name is | the base printing of the name |
| `name_mismatch` (`params {written, found}`) | the explicit printing exists but its card is not the written name (`found` = its text name) | **that printing** |
| `ambiguous_card` | only the accent-free match, and it fits several names | not in the content |
| `wrong_zone` (`params {name, zone}`) | the card's type does not belong in the block | **kept in that block**; legality flags it (`card_off_identity`) |
| `slot_taken` (`params {name, zone, to, qty}`) | a second legend / champion (or qty > 1) | extra legends -> workbench, extra champions -> main |
| `hard_limit` (`line: null`, `params` = the `deck_limit_exceeded` params) | the content breaks a hard limit (F5-R9) | **imported as is**; legality reports it |

- `POST /decks/import/preview` (`api_v1.preview_deck_import`) `{text, format?}` -> 200
  `{deck_preview: {content, cards, unknown_cards, domains, counts, value, value_unpriced,
  legality}, warnings: [Warning], counts: {lines, copies, unresolved}}`. `deck_preview` is what
  `GET /decks/<id>` gives for that content (legality in both modes with `completeness`).
  `counts`: card lines after merging, copies placed, copies left out. Writes nothing.
- `POST /decks/import` (`api_v1.import_deck`) `{text, format?, name?, mode?: 1v1|2v2 (default
  1v1)}` -> 201 `DeckDetail` + `warnings`: a new private deck whose version 1 (current) is the
  imported content. Name: `name` (trimmed; blank = none), else the legend's text name (`Riven,
  The Exile`), else `Imported deck`; a name the caller already has gets ` (2)`, ` (3)`... (cut
  so it fits 80). It loads with warnings and hard limits: the content is stored **as is**, so
  `PUT …/content` keeps answering `deck_limit_exceeded` until every hard limit is fixed (F5-e L3).
- `GET /decks/<id>/export?format=text` (`api_v1.export_deck`, `format` defaults to `text`) ->
  200 `text/plain; charset=utf-8`, `Content-Disposition: attachment; filename="<slug>.txt"`
  (deck name, accents folded, lowercase, runs of other characters `-`; `deck` when empty).
  Blocks in the order above, `Header:` then `N Name` lines, a blank line between blocks, a final
  newline, empty blocks omitted (an empty deck is an empty file), the workbench never exported.
  Lines keep the content order (the order the deck was imported or built in), one line per
  name with the total of its printings; a legend prints `Tag, Name` (first tag) unless its name
  already starts with a tag; a printing missing from the catalog prints `SET-ID`. Importing the
  export gives the same content (printings of one name come back as the base printing).

### Deck sharing (F5-g)

`app/api/v1/decks.py` over `app/services/deck_share.py`. A deck can have one read-only share
link (`rbdeckheads.rbdkh_share_slug`); `visibility` only decides whether the public view names
the owner (D-F5-4). There is no public index of decks: a deck is reachable only through its
link.

- `POST /decks/<id>/share` (`api_v1.share_deck`, U, no body) -> 200 `{slug, url}`. `slug` = 22
  url-safe random characters (`secrets.token_urlsafe(16)`, 128 bits; `[A-Za-z0-9_-]{22}`),
  unique (a taken slug is drawn again). `url` = `<request host>/riftbound/app/d/<slug>` (the
  F5-m page; built with `url_for`, never a fixed host). Idempotent: a deck that already has a
  slug gets the same one. The deck's `updated_at` does not change.
- `DELETE /decks/<id>/share` (`api_v1.unshare_deck`, U) -> 200 `{share: null}`; the slug is
  cleared and its URL answers 404 at once. A deck without a link answers the same (no-op).
  Sharing again draws a **new** slug; the old one stays dead. Deleting the deck kills its link.
- Both: owner only; another user's deck or an unknown id -> 404 envelope, nothing changes;
  anonymous -> 401 `unauthenticated`.
- `GET /decks` items and every `DeckDetail` carry `share` (`DeckHead`).

`GET /public/decks/<slug>` (`api_v1.public_deck`, **P**): no login, never touches the session
(no `Set-Cookie`), rate limited **60 per minute per IP** (Flask-Limiter, in-memory per worker;
over it -> 429 `rate_limited` with `Retry-After`, unknown slugs count too), `Cache-Control:
no-store` on every answer (a revoked link must stop working at once). An unknown, revoked or
malformed slug -> the same 404 envelope (`The requested resource was not found`), no hint of
which. 200 -> `PublicDeck` (keys in this order):

```
{name, mode, visibility, owner: {username} | null, updated_at,
 content: {v, legend, champion, main, runes, battlefields, sideboard},
 cards: {"<set>-<id>": DeckCard}, unknown_cards, domains,
 counts: {main, runes, battlefields, sideboard}, value, value_unpriced, legality}
```

- `owner` is `{username}` only when `visibility` is `public`; a shared private deck is
  anonymous (`null`).
- The **workbench is left out** everywhere: not in `content`, `cards`, `counts`, `value` or
  `legality` (legality is computed on the shown content, so a workbench card never shows up
  in an issue). Everything else is computed on read as in `GET /decks/<id>` (both modes, bans
  of the moment, non-foil market prices).
- `DeckCard.owned_total` is `null`: neither the owner's nor the viewer's collection is read.
- Never returned: deck id, user id, email, `created_at`, `current_seq`, versions and notes, the
  slug itself or any other deck's slug.
- 7 SQL statements (head + owner username, current version, cards, sets, bans, prices ×2).

### GET /cards/<set_id>/<card_id>/prices

`app/api/v1/cards.py` (`api_v1.get_card_prices`, U): daily price history.
Query `range: 30d|90d|1y|all = 90d` via `validate_query` (bad range → 400
`validation_error`, `field: "range"`, `code: invalid_value`). A missing card
answers 404; an unmapped card answers 200 with `product_id: null` and
`points: []`. Otherwise N product = canonical non-foil product; the window runs
from latest − 30/90/365 days inclusive (`all` = every row); one ascending point
per N row `{date, market (foil N), low, avg7, avg30, market_foil (same-date
foil-product row, foil S; null when not foilable or no row that day)}`.
At most 4 SQL statements.

```http
GET /riftbound/api/v1/cards/OGN/79/prices?range=30d
```

## Data shapes

Additive changes only: new keys may be appended, existing keys are never renamed,
retyped or removed without a new unit.

`GameMeta` = the `data` object of `GET /meta/game`:
`{modes: [str], domains: [str], types: [str], supertypes: [str], rarities: [str],
sets: [{id, name, released_on (ISO|null), card_count}] (newest first, undated last),
price: {provider, currency, updated_on (ISO|null)}, rules: {deck: {main_size, total_with_champion,
runes, battlefields, sideboard, copies_max, workbench_max}},
conditions: [str], languages: [str]}`.

`CardSummary` = the object `app/services/catalog.py::card_summary` builds for one
card (F2-c/F2-d return it): `{set_id, card_id, key ("<set>-<id>"), number (natural
card number|null), name, domains: [str], type, supertype|null, type_raw, tags: [str],
energy|power|might (int|null), rarity, image_src, image_thumb_src (null until F2-l),
foilable, is_base, price: {market, market_source, market_foil, market_foil_source,
trend_7d_pct, trend_30d_pct, as_of}|null, bans: {<mode>: bool},
owned: {total, foil}}` (`market_source` is the `rbprc_*` column the value came from).

`ProductSummary` (F14-b) is a contract for the product screens: additive changes only.
`ProductSummary` = `{id, name, kind|null, category|null, set_id|null, image_src
(`/riftbound/media/products/<rbpdt_image>` when the product has an image, else null; F14-d),
listed (bool), price: {value|null,
source (avg7|trend|low)|null, change_7d_pct|null, change_30d_pct|null, as_of (ISO)}|null,
owned_qty}`. `value` is the first of `rbprc_avg7`, `rbprc_trend`, `rbprc_low` of the latest row
that is not NULL and not 0 (no foil columns; `app/services/product_prices.py`); the changes use
the `CardSummary` reference-row rule (newest row on or before latest - 7/30 days) and rounding
(1 decimal) on that value; `price` is null when the product has no `rbcm_price` row. `owned_qty`
(F14-c) is the number of copies in the caller's `rbuserproducts` lines (0 when none).

`CollectionLine` and `CollectionGroup` (F3-b) are contracts for the collection screens, the
value snapshots and the sales: additive changes only.
`CollectionLine` = `{id, foil (bool), qty, condition|null, language|null,
purchase_price|null, selling (bool), sell_qty, sell_price|null, updated_at (UTC,
"YYYY-MM-DDTHH:MM:SSZ"), market|null, value|null, pl_abs|null, pl_pct|null}`: `market` is the
price of the line's own foil, `value` = market x qty, `pl_abs` = (market - purchase) x qty and
`pl_pct` = (market - purchase) / purchase x 100, both null unless there is a market price and
a purchase price above 0. In `GET /collection` (F16-b) each line also carries `locations`
(first 5, `[{location_id, code, description, qty}]`), `locations_more` and `unassigned`.
`CollectionGroup` = `{key ("<set>-<id>:N" or ":S"), card: CardSummary, foil (bool), qty,
sell_qty, value|null, lines: [CollectionLine] (by id), keep_playset, playset_short, kept}`.
`keep_playset` is true when the user marked the card name (`rbkeepplayset`);
`playset_short` is true when it is kept and the copies not for sale (`qty - sell_qty`) of
**every** printing and foil of that name, whatever the filters, are fewer than the user's
playset size (3 by default); `kept` is that number of copies (also for names not marked; F3-g). `GET /cards/<set>/<id>` `my_lines[]` also carry
`purchase_price` and `sell_qty`.

## Admin API

`app/api/admin/` (`api_admin`, `/riftbound/api/v1/admin/*`) is admin-only:
`before_request(require_admin)` answers JSON 401 to anonymous callers and JSON 403
to plain users. Bodies use the envelope above; query strings are validated with the
same body. Every write records an `rbadminaudit` row in the same transaction
(`app/services/audit.py`).

### Sets

- `GET /admin/sets` → `{[{id, name, release_date (ISO|null), card_count, declared_count}]}`,
  sets without release date first, then `release_date` descending, then `id`.
- `POST /admin/sets` `{id, name, release_date, declared_count?}` → 201 with the item.
  `id` is trimmed and upper-cased (`^[A-Z0-9]{2,10}$`); `name` 1-100 chars; `release_date`
  is required; `declared_count` 0-999 or null. A duplicate id → 409 `already_exists`
  (`params: {"field": "id"}`). Audit `set.create` with `{name, release_date}`.
- `PATCH /admin/sets/<id>` any of `{id, name, release_date, declared_count}` → 200.
  `release_date` cannot become null (400 `required`); changing `id` needs a set without
  cards, else 409 `set_in_use` (`params: {"cards": n}`); an existing new id → 409
  `already_exists`. Unknown set → 404. Audit `set.update` with `{field: [old, new]}`.
- `DELETE /admin/sets/<id>` → 200 `{"deleted": "<id>"}`; 409 `set_in_use` when cards
  exist. Audit `set.delete`.

### Cards

`AdminCard` = `{set_id, card_id, key ("<set>-<id>"), name, domain, type, tags, energy,
power, might, ability, rarity, artist, image, image_url, image_src}` (raw columns;
`image_*` from `CARD_IMAGES_DIR`).

- `GET /admin/cards` with `set` (repeatable), `rarity` (repeatable, exact,
  case-insensitive), `type`/`domain` (substrings, case-insensitive), `missing_image`
  (`true`), `q` (substring of the name, an exact card id, or a `SET-ID` key),
  `sort` = `number` (default: set id, then natural card id) | `name`, `dir` =
  `asc` (default) | `desc`, `page` ≥ 1, `per_page` ∈ {50, 100, 200} (default 50).
  → 200 `{items: [AdminCard], meta: {page, per_page, total, pages}}`.
- `POST /admin/cards` (`AdminCardInput`: `set_id` + `card_id` required, `name` required;
  numbers 0-99 or null; texts trimmed, empty → null) → 201. Unknown set → 400
  (`set_id`, `invalid_value`); duplicate key → 409 `already_exists` (`field: card_id`).
  Audit `card.create`.
- `PATCH /admin/cards/<set>/<id>` any `AdminCardInput` field except the keys
  (sending `set_id`/`card_id` → 400 `invalid_value`; `rbcar_banned` is never accepted) →
  200. Unknown card → 404. Audit `card.update` with `{field: [old, new]}`.
- `POST /admin/cards/<set>/<id>/image` (multipart, field `file`): ≤ 2 097 152 bytes
  (else 400 `out_of_range`, `params.max`); type by magic bytes — PNG `89 50 4E 47`,
  JPEG `FF D8 FF`, WebP `RIFF????WEBP` (else 400 `invalid_format`). The extension follows
  the bytes, not the name. Written with `card_image_path` over any existing file; the card's
  `image` becomes `<stem>.<ext>` (stem of the current image, else `<set lower>_<card>`).
  → 200 `AdminCard`. Audit `card.image` with `{image, bytes}`.
- `DELETE /admin/cards/<set>/<id>` → 200 `{"deleted": "<SET>-<id>"}`; 409 `card_in_use`
  (`params: {"collection_lines": n, "decks": m}`) when a collection line or a deck
  (`rbdck_cards` main/sideboard `{set, id}`) references it. The image file is not deleted.
  Audit `card.delete`.

### Products (F14-d)

`app/api/admin/products.py`, logic in `app/services/product_list.py` (list) and
`app/services/products.py` (`apply_admin_patch`, `expansion_set`). Only non-singles
(`rbpdt_type = 'nonsingle'`); hidden ones included. `AdminProduct` = `ProductSummary` +
`{hidden, kind_locked, set_locked, rbpdt_type, updated_at (UTC "YYYY-MM-DDTHH:MM:SSZ"|null)}`
(`owned_qty` is the calling admin's copies).

- `GET /admin/products` (`AdminProductQuery`) with `q` (case-insensitive name substring, or
  an exact product id), `kind` (repeatable, one of the `PRODUCT_KINDS`), `hidden` and
  `listed` = `any` (default) | `yes` | `no`, `no_set` / `no_image` (`true`: no set / no
  image), `sort` = `name` (default) | `updated` (`rbpdt_updated_at`, nulls last in both
  directions, ties by name), `dir` = `asc` (default) | `desc`, `page` ≥ 1, `per_page` ∈
  {50, 100, 200} (default 50); anything else → 400 `validation_error`. → 200
  `{items: [AdminProduct], meta: {page, per_page, total, pages}}`. Three SQL statements (plus
  the session user) whatever the size of the catalog.
- `PATCH /admin/products/<id>` any of `{hidden (bool), kind, set_id}` (a key that is absent
  is not touched; other keys → 400). `kind` in `PRODUCT_KINDS` sets it and
  `kind_locked = true`; `kind: null` unlocks it and recomputes it from the category
  (`kind_for`). `set_id` = an existing set id or `null` sets it and `set_locked = true`;
  `"auto"` unlocks it and recomputes it from the expansion of the product's latest
  non-single `rbcm_products` row (null when unmapped or absent). The daily
  `products_refresh` never changes a locked kind or set. An unknown set → 400 (`set_id`,
  `invalid_value`), a bad kind or `hidden` → 400; nothing is changed. A missing id or a
  product that is not a non-single → 404. `rbpdt_updated_at` moves only on a change. →
  200 `AdminProduct`. Audit `product.update` with `{field: [old, new]}` of what changed
  (`hidden`, `kind`, `kind_locked`, `set_id`, `set_locked`); no change, no row.
- `POST /admin/products/<id>/image` (multipart, field `file`): the card image rules
  (≤ 2 097 152 bytes, else 400 `out_of_range` with `params.max`; PNG / JPEG / WebP by magic
  bytes, else 400 `invalid_format`; no `file` → 400 `required`). Written with
  `product_image_path` as `<id>.<ext>` (the extension follows the bytes; the client file
  name is never used) in `PRODUCT_IMAGES_DIR`; a previous `<id>.<other ext>` file is
  deleted, any other name is left. `rbpdt_image` becomes the file name. → 200
  `AdminProduct`. Audit `product.image` with `{image, bytes}`. Same 404 cases.

Product images are served publicly at `GET /riftbound/media/products/<filename>`
(`media.product_image`): a plain file name with a `png`, `jpg`, `jpeg` or `webp`
extension inside `PRODUCT_IMAGES_DIR`, cached a week, no `Set-Cookie`; anything else is a
404 (same rules as `media.card_image`).

### Sync, jobs and change review

- `POST /admin/riot/sync` body `{sets?: [codes]}` (codes upper-cased; unknown → 400
  `validation_error`, `field: sets`, `invalid_value`, `params: {values: [...]}`) → 202
  `{"job_id": n}`; the job runs `riot_sync` with `trigger=manual`. Active sync → 409
  `job_running`. Audit `riot.sync_requested`. A scheduled run with nothing due ends
  `success` with `{"message": "nothing due", "sets": []}` and fetches nothing.
  Each set of the job `result` counts `images: {downloaded, existing, failed}` over every
  card of the set with an image URL (inserted, unchanged, applied, proposed and missing
  from the gallery): a missing file is downloaded, never overwritten. A proposed card keeps
  its stored `image`/`image_url`; only the ones it lacks come from the gallery.
  Comparison rules (owner feedback 2026-10-29, `riot_sync.gallery_value`): non-Legend,
  non-Signature names are "Name, Subtitle" (a bare gallery name equal to the start of a stored
  "Name, Subtitle" is no change); "Champion Legend" is "Legend"; with a set `rbset_ncard`, a card
  numbered above it is Showcase and at or below it a gallery "Showcase" keeps the stored
  rarity; image URLs are compared without query string and fragment. A rule that says "same"
  means no proposal and no write.
- `GET /admin/jobs` with `kind`, `status`, `limit` (1-100, default 20), newest first →
  `items[]` of `{id, kind, status, requested_by (username|null), requested_at,
  started_at, finished_at, message}`. `GET /admin/jobs/<id>` adds `params` and `result`;
  404 when missing.
- `GET /admin/riot/changes` with `status` (`pending` default, `approved`, `rejected`,
  `obsolete`, `all`), `set`, `field`, `q` (name substring or card id), `page` ≥ 1,
  `per_page` 50, 100 or 200 (default 50; any other value → 400 `validation_error`) →
  `items[]` of `{id, set_id, card_id, card_name, image_src, field,
  old_value, new_value, status, detected_at, job_id, decided_at, decided_by
  (username|null)}`, newest first; `meta = {page, per_page, total, pages,
  counts: {pending, approved, rejected, obsolete}}` (global counts).
  `obsolete` (S17): a pending proposal the sync rules no longer produce, set by
  `flask riot recheck-pending` (`decided_by` null); it is final, like approved and rejected.
- `POST /admin/riot/changes/<id>/approve`: pending only (else 409 `change_decided`); the
  card must still hold the old value (else 409 `change_stale`, nothing written). Numbers are
  parsed back to int; an approved `image_url` re-downloads the image over the card's file
  (a failure keeps the approval and adds `warnings: ["image_download_failed"]`). Audit
  `riot.change_approve`. → 200 with the item.
- `POST /admin/riot/changes/<id>/reject`: pending only → `rejected`. Audit
  `riot.change_reject`. → 200 with the item.
- `POST /admin/riot/changes/bulk` body `{ids: [1..500], action: "approve"|"reject"}` →
  200 `{"results": [{"id", "outcome": "approved"|"rejected"|"stale"|"decided"|"not_found"}],
  "counts": {...}}`; each id in its own transaction, ascending id order.
- `GET /admin/overview` gains `riot`: `{pending_changes, active_sets: [{id, name, window,
  next_run_at}], last_sync: {job_id, status, finished_at, trigger} | null,
  placeholder_sets: [codes whose name equals their id and have no release date]}`.
- `GET /admin/overview` gains `cardmarket` (CM-e, additive): `{last_load: {date
  ("YYYY-MM-DD"), status} | null, loaded_today, job_status (status of the latest
  `daily_prices` job) | null, unmatched, unmapped_expansions}`, the same values as
  `GET /admin/cardmarket/status` (one definition: `cardmarket_log.health`). The whole overview
  is at most twelve SQL statements beyond the session user (the Cardmarket part adds five:
  newest load day, its history rows, latest job, unmatched and unmapped COUNTs).

### Cardmarket load log (CM-a)

`app/api/admin/cardmarket.py`, logic in `app/services/cardmarket_log.py`. Computed on read from
`rbcm_load_history`, `rbcm_products`, `rbcm_price`, the matching tables and the `daily_prices`
jobs; no table of its own. A load day is a date of `rbcm_load_history` (the loader's UTC date).
Timestamps are naive UTC ISO strings, as in `GET /admin/jobs`.

- `GET /admin/cardmarket/loads` with `limit` (1-120, default 30; anything else or an unknown
  parameter → 400 `validation_error`) → `{items: [LoadDay]}`, newest day first. `LoadDay` =
  `{date ("YYYY-MM-DD"), files: [{type, rows, status, message, loaded_at}], status,
  products_total, new_products, new_products_sample, unmatched_singles, duration_seconds,
  job_id}`:
  - `files`: the latest history row of each file type (a re-run adds rows), in the order
    `price_guide`, `singles`, `nonsingles`.
  - `status` from those files: all `skipped` → `skipped`; a file in `error` or missing →
    `partial` when another one is `success`, else `error`; otherwise `success` (a skipped
    file only means it had not changed).
  - `products_total`: `rbcm_products` rows of the day (0 when the products were not loaded).
  - `new_products`: products of the day absent on the previous date with products (a
    product that left and came back counts again; removed products are not counted);
    `null` when the day has no products or no earlier date has any (the first load).
    `new_products_sample`: the first 20 by name, `{id_product, name, category, type,
    low_price (rbcm_price low of the day | null)}`.
  - `unmatched_singles`: only on the newest day, the current count of singles of the latest
    product date that are neither mapped (`rbcm_product_card_map`) nor ignored (same id and
    name in `rbcm_ignored`); `null` on older days.
  - `job_id` / `duration_seconds` (finished − started, rounded): the newest `daily_prices`
    job whose `result.validation.date` is the day, else the newest one that was running when
    a file of the day was loaded; `null` when none.
  Seven SQL statements (the session user included) whatever `limit`.
- `GET /admin/cardmarket/loads/<YYYY-MM-DD>` → the `LoadDay` of that day without
  `new_products_sample`, plus `new_products_list` (every new product, at most 500, same item
  shape), `truncated` (more than 500) and `job` (`{id, status, queued_at, started_at,
  finished_at, message, result}` | null; `result` is the stored job result untouched:
  `validation`, `auto_match`, `review`, `review_total`, `queued`). Here `files` lists every
  history row of the day in order (each run); `status` still uses the latest of each type.
  A day without a load, or a value that is not a real `YYYY-MM-DD` date → 404.
- `GET /admin/cardmarket/status` → `{last_load: {date, status, loaded_at (latest file)} |
  null, loaded_today (the newest day is today's UTC date), job: {id, status, queued_at,
  started_at, finished_at, message} | null (the latest `daily_prices` job), unmatched (same
  count as `unmatched_singles`), unmapped_expansions (`rbcm_expansions` without a set),
  prices_as_of ("YYYY-MM-DD" of the newest `rbcm_price` row | null)}`.
- `POST /admin/cardmarket/load` (no body) queues the `daily_prices` job (default
  allow-listed URLs, no params) → 202 `{job_id, job: {id, status, queued_at, started_at,
  finished_at, message}}`. A `daily_prices` job already queued or running → 409
  `job_running`, nothing written. Audit `cardmarket.load` (target `job`, id the job id).

### Cardmarket matching (CM-b)

`app/api/admin/cardmarket_matching.py`, logic in `app/services/cardmarket_matching.py`. Port of
the legacy Jinja admin endpoints of `price_bp` (`/riftbound/price/cardmarket-*`, `ignored/*`; removed
with the Jinja web, PR 3/3 of its retirement).
A **link** is one `rbcm_product_card_map` row: a Cardmarket product id to a card and a foil slot
(`N`, `S` or `null`; two `null`s are the same slot, `null` and `N` are not). **Products are
linked by Cardmarket id**: `rbproducts` is keyed by the Cardmarket id and `products_refresh`
creates the product of every non-single, so there is no product link to write
(`kind: "product"` → 400 `validation_error` on `kind`); creating a missing card or product from
a Cardmarket item is CM-c. **Unmatched** has one definition
(`cardmarket_log.unmatched_clauses`): a product of the latest product date that is neither
linked nor ignored (same id and name in `rbcm_ignored`); the `type=single` total equals
`unmatched` of `GET /admin/cardmarket/status`. **Clear / doubtful** is the decision of the
daily job (`daily_prices.classify_unmapped`, the read-only half of `match_clear_cases`). Writes
are audited in the same transaction (target type `cardmarket_product`, id the Cardmarket id).
Dates are `YYYY-MM-DD`. No job kind (it would need a migration of `ck_rbjobs_kind`): the
apply runs synchronously and is bounded.

- `GET /admin/cardmarket/unmatched` with `q` (name or id, substring), `type`
  (`single`|`nonsingle`; default both, like the legacy list), `category` (substring), `page`,
  `per_page` (25|50|100|200, default 50) → `{items, meta: {page, per_page, total, pages, date
  (latest product date | null)}}`, by name then id. Item `{id_product, name, type, category,
  expansion: {id, name, set_id} | null, low_price (low at the newest `rbcm_price` date, as the
  legacy list), first_seen_date, suggestions}`; `suggestions` (at most 3) `{kind: "card",
  id: "SET-ID", name, set, number, score, free_foils}` by normalised name (the matcher's index,
  legends also as `tags, name`): exact name 1.0, a close name its similarity (≥ 0.75), ×0.9 for
  a card outside the set of the product's expansion; `free_foils` are the slots still free
  (`["N","S"]`, `[null]` or `[]`). A non-single gets `{kind: "product", id, name, set,
  number: null, score: 1.0, free_foils: []}` when the product of the same id exists. Nine SQL
  statements (session user included) whatever the page size.
- `GET /admin/cardmarket/unmatched/<id_product>/candidates` with `q` (2-100 chars) →
  `{product: {id_product, name, type, category, expansion, date (newest row), link: {set_id,
  card_id, foil, match_type} | null}, cards: [{set_id, card_id, name, rarity, type, image_src,
  links: [{id_product, foil}]}], products: [{id, name, set_id, kind, category}]}`. With `q`:
  cards whose name or `SET-ID` contains it (20, by name); without: the suggested cards (20).
  `products` only for a non-single (by name with `q`, else the product of the same id). Any
  Cardmarket id of any date; an unknown one → 404.
- `POST /admin/cardmarket/links` `{id_product, kind?: "card", card: {set_id, card_id}, foil:
  "N"|"S"|null}` → 201 `Link` (`match_type: "manual"`, confidence 1.0). Unknown Cardmarket id →
  404; unknown card → 400 `validation_error` on `card`; already linked → 409 `already_exists`
  `params {field: "id_product", set_id, card_id, foil}` ("Unlink it first"; the legacy map
  silently moved it: use `PUT`); the slot belongs to another product → 409 `already_exists`
  `params {field: "card", linked_id_product}`. Audit `cardmarket.link` `{set_id, card_id, foil}`.
  `Link` = `{id_product, product_name, product_type (newest row), in_latest_load, set_id,
  card_id, card_name, foil, match_type, confidence, low_price, price_date (the product's newest
  price)}`.
- `PUT /admin/cardmarket/links/<id_product>` `{card, foil}` → `{link, previous}`: unlink and
  link in one transaction (its own slot is not a conflict); no link → 404, unknown card → 400,
  slot of another product → 409 as above; any failure leaves the old link. Audit
  `cardmarket.relink` `{from, to}`.
- `DELETE /admin/cardmarket/links/<id_product>` → `{link}` (the removed `Link`, so the client
  can post it back); no link → 404. Audit `cardmarket.unlink` `{set_id, card_id, foil,
  match_type}`.
- `GET /admin/cardmarket/links` with `q` (product name, id, card name or number), `set`
  (substring), `foil` (`N`|`S`|`none`), `match_type` (`auto`|`manual`), `conflicts` (`true`:
  only the slots held by more than one product, the legacy conflict rule), `page`, `per_page`
  → `{items: [Link], meta: {page, per_page, total, pages, conflict_slots}}`; by product name
  (conflicts: by slot). Every link, also of products gone from the latest load. Five SQL
  statements whatever the page size.
- `GET /admin/cardmarket/ignored` → `{items: [{id_product, name, low_price, ignored_at}]}`,
  newest first. `POST` `{id_product, name}` → 201 `{item, created: true}`, or 200 `created:
  false` when already ignored (audit `cardmarket.ignore` only when created). `DELETE
  /ignored/<id_product>?name=` restores that name, or every name of the id → `{removed:
  [{id_product, name}]}`; none → 404. Audit `cardmarket.unignore` `{names}`.
- `POST /admin/cardmarket/auto-match/preview` (no body) → `{date, proposed (pairs the matcher
  proposes), clear, doubtful, links: [{id_product, product_name, low_price, set_id, card_id,
  card_name, foil}], review (first 200), review_total}`; writes nothing.
- `POST /admin/cardmarket/auto-match/apply` `{max_groups?: 1-200 (default 200)}` → `{date,
  linked, clear, remaining_clear, doubtful, links}`: links the first `max_groups` clear cases
  as the daily job does (`auto`, 0.7). The doubtful ones are never linked (the legacy
  auto-match links every proposal; that stays only in the legacy page). Audit
  `cardmarket.auto_match` (target `cardmarket`, id the date) `{linked, clear, doubtful,
  max_groups}`.
- `GET /admin/cardmarket/review` with `reason` (`ignored_pair`|`no_candidates`|`conflict`|
  `ambiguous`), `page`, `per_page` → `{items, meta: {page, per_page, total, pages, date,
  reasons: {reason: count}}}`: the doubtful cases of the latest load, computed now with the
  daily job's rule (the job result keeps only 200 and goes stale after manual links). Item as
  in the job result: `{product_id, name, expansion_id, reason, candidates: [{set, id, name}]}`.

Not ported: the legacy unmap by card (`rbset_id` + `rbcar_id`; unlink by Cardmarket id
instead), the legacy unified mapped + unmapped browser (split into `unmatched` and `links`),
card/product upsert (CM-c), unmapped expansions (CM-d), the price CSV (dropped).

### Cardmarket expansions (CM-d)

`app/api/admin/cardmarket_expansions.py`, logic in `app/services/cardmarket_expansions.py`.
Port of the legacy `/riftbound/price/cardmarket-unmapped-expansions` and
`/cardmarket-map-expansion` (the legacy file is unchanged). An expansion is one
`rbcm_expansions` row; `rbexp_rbset_id` is a soft FK to `rbset` (NULL = **not mapped**). The
mapping lets the matcher prefer cards of that set (CM-b suggestions) and lets
`products_refresh` give products the set of their expansion on its next run; prices never
depend on it. **Unmapped** has one definition (`cardmarket_log.unmapped_expansions_count`): the
`unmapped_expansions` of `GET /admin/cardmarket/status` and `meta.unmapped` below. Writes are
audited in the same transaction (target type `cardmarket_expansion`, id the expansion id).

- `GET /admin/cardmarket/expansions` with `unmapped` (`true`|`false`, default `false`) →
  `{items: [{id, name, products_count, singles_count, sealed_count, mapped_set_id | null,
  mapped_set_name | null}], sets: [{id, name, release_date | null}], meta: {unmapped, total,
  date}}`. Every expansion, unmapped first, then by id (`unmapped=true` keeps the unmapped
  ones). Counts are of the latest product date (`date`, `YYYY-MM-DD` or null): `sealed_count` is
  the non-singles. `mapped_set_name` is null when the mapped id is not a set of ours. `sets` are
  every set, newest release first, undated last. Seven SQL statements (session user included)
  whatever the number of expansions and sets.

  Each item also carries the context that tells an expansion apart when Cardmarket gives it no
  name (additive, CM-d samples), all of the latest product date: `sample_products: [{id_product,
  name, type ("single" | "nonsingle"), low_price | null}]`, its 3 dearest singles then its 2
  dearest sealed products by the low price of that day (unpriced last, then by product id; `[]`
  when it has no product on that date); `price_range: {min, max} | null`, the lowest and highest
  low price of its singles (null when none is priced); `first_seen: "YYYY-MM-DD" | null`, the
  earliest Cardmarket `dateAdded` of its products on that date (null when none, or not a date;
  older snapshots are not read); and the **suggested set**: of its products that have a card link
  (`rbcm_product_card_map`), `linked_count` is how many (0 when none) and `suggested_set_id`,
  `suggested_set_name`, `suggested_count` (how many point to it) and `suggested_confidence`
  (`suggested_count / linked_count`, 3 decimals) name the set of ours most of them point to (a
  tie goes to the lower set id; links to an id that is not a set of ours count in `linked_count`
  but are never suggested); all four are null when there is no such set. The `expansion` items
  of `PUT` and `DELETE` below carry the same keys.
- `PUT /admin/cardmarket/expansions/<id>` `{set_id, create_set?: {name, release_date,
  declared_count?}}` → `{expansion (as an item above), previous (set id | null),
  created_set (the `POST /admin/sets` item | null)}`. Without `create_set`, `set_id` must be a
  set of ours (400 `validation_error` on `set_id`, "unknown set"). With `create_set` the set is
  created first, exactly as `POST /admin/sets` does it: the same `AdminSetCreate` validation
  (`set_id` follows its id rule and is upper-cased; field errors are named `set_id` and
  `create_set.<field>`), the same row and the same `set.create` audit row; a set that exists →
  409 `already_exists` `params {field: "set_id"}`. Create, map and audits are one transaction:
  any failure leaves neither the set nor the mapping. Re-mapping a mapped expansion is allowed
  and returns `previous`; the same set again writes nothing. Unknown expansion → 404 (before
  any set is created). Audit `cardmarket.expansion.map` `{name, set_id, previous}`.
- `DELETE /admin/cardmarket/expansions/<id>/mapping` → `{expansion, previous}` (the set id it
  was mapped to, so the client can undo with `PUT`); the set stays. Unknown expansion → 404;
  not mapped → 404 "Cardmarket expansion <id> is not mapped.". Audit
  `cardmarket.expansion.unmap` `{name, previous}`.

Not ported: the legacy `rbexp_name` override and the download URLs of the legacy list.

### Audit log (CM-e)

`app/api/admin/audit.py`, logic in `app/services/audit_log.py`. Read-only views of
`rbadminaudit`, the row every admin write records in its own transaction
(`app/services/audit.py::record`). `details` are passed through as stored: they are small
summaries written by the admin code (names, ids, old/new values, counts; at most 4 KB), and no
action stores a password, a hash or a token, so nothing is filtered. Timestamps are naive UTC
ISO strings.

- `GET /admin/audit` with `actor` (case-insensitive substring of the stored username, `%` and `_`
  literal; `system` matches the job and CLI rows), `action`, `target_type`, `target_id` (exact),
  `from`, `to` (`YYYY-MM-DD`, inclusive UTC days; `to` before `from` → 400 on `to`), `page` ≥ 1,
  `per_page` 50, 100 or 200 (default 50); anything else or an unknown parameter → 400
  `validation_error` "Invalid query parameters" → `{items: [AuditItem], meta: {page, per_page,
  total, pages}}`, newest first (equal times: higher id first). `AuditItem` = `{id, created_at,
  actor: {id, username} | null, action, target_type, target_id | null, detail}`: `actor` is null
  for the system (a job or the CLI); a deleted user keeps the stored username with `id` null;
  `detail` is the stored JSON (object, list or null) untouched. Two SQL statements (COUNT and the
  page) beyond the session user, whatever the page size. Dates use `idx_rbadminaudit_created`,
  a target type with an id `idx_rbadminaudit_target`; `actor` and `action` alone scan the table
  (fine at the admin volume; an index on `rbaud_action` would be the first to add if it grows).
- `GET /admin/audit/facets` (no parameters) → `{actions: [{action, count}], target_types:
  [{target_type, count}]}`, by name: the values present, for the filter selects. Two SQL
  statements (two GROUP BYs).

Actions recorded today: `set.create|update|delete`, `card.create|update|image|delete`,
`product.update|image`, `riot.sync_requested|insert|apply|recheck|change_approve|change_reject`,
`cardmarket.load|link|relink|unlink|ignore|unignore|auto_match`,
`cardmarket.expansion.map|unmap`. Target types: `set`, `card` (`SET-ID`), `product`,
`cardmarket_product` and `cardmarket_expansion` (Cardmarket ids), `cardmarket` (auto-match, the
load date), `job`, `card_change`.
