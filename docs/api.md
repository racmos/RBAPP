# API

JSON API of Rift Manager. Jinja pages keep their own flat `{"success": ...}` bodies;
everything under `/riftbound/api/v1/` uses the envelope below.

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

### GET /meta/game

`app/api/v1/meta.py` (`api_v1.meta_game`, P): game metadata for the catalog UI.
Anonymous and signed-in callers get 200; `Cache-Control: no-cache`. Response `data`
is a `GameMeta` (see "Data shapes"): `modes` from `GAME_MODES`; `domains`, `types`,
`supertypes`, `rarities` are the S1 tuples of `app/schemas/game_domain.py` followed by
any other distinct non-empty value found in the data (sorted case-insensitively);
`sets` are every `rbset` row ordered by release date (NULLs last), then id, each with
`{id, name, released_on (ISO|null), card_count}`; `price` is
`{provider: "cardmarket", currency: "EUR", updated_on (ISO|null)}` where `updated_on`
is the newest `rbcm_price` date; `rules` is `{}` (reserved for F15); `conditions` is
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
`type`/`supertype` match their lists; `exclude_supertype` drops listed supertypes
(cards without supertype stay); `tag` needs one listed tag; `domain_match` = `any`
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
updated_at (UTC `…Z`)}`), `in_decks` (per deck name the highest `rbdck_seq`
row only; `{deck_id, name, qty}` summed over main + sideboard entries of the
same name, missing-card entries skipped, ordered by name).

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
`type`, `rarity`) drop groups; line filters (`foil`, `selling`, `condition`, `language`,
`has_purchase`) drop lines, and a group lists and adds up only its matching lines.
`data.items` are `CollectionGroup`s; `meta` is `{page, per_page, total_groups, pages,
totals, facets, price_as_of, playset_size}`. `totals` cover every matching line, not only
the page: `{lines, qty, unique (distinct printings), value, cost (null without purchase
prices), pl (null without any), selling_value, foil_pct}`. `facets` are disjunctive group
counts for `set`, `rarity`, `condition`, `language` and `foil` (`{foil, nonfoil}`).
Money is rounded half up to 2 decimals, `pl_pct` to 1. At most 10 SQL statements whatever
the size of the collection. Other users' lines never appear.

```http
GET /riftbound/api/v1/collection?sort=value&dir=desc&per_page=25
```

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
- `POST /collection/keep-playset` `{set_id, card_id, keep}` -> `{name, keep_playset, kept,
  playset_size, playset_short}`: inserts or deletes the `rbkeepplayset` row of the card name
  (idempotent). `kept` counts the copies not for sale of every printing of the name.
- `GET`/`PATCH /me/prefs` also carry `playset_size` (`null` = 3, otherwise 1-9; out of range ->
  `validation_error`, `out_of_range`, `params {min: 1, max: 9}`).

New error codes: `foil_not_allowed` (400), `insufficient_quantity` (409, `params.available`),
`stale_line` (409).

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
sets: [{id, name, released_on (ISO|null), card_count}],
price: {provider, currency, updated_on (ISO|null)}, rules: {},
conditions: [str], languages: [str]}`.

`CardSummary` = the object `app/services/catalog.py::card_summary` builds for one
card (F2-c/F2-d return it): `{set_id, card_id, key ("<set>-<id>"), number (natural
card number|null), name, domains: [str], type, supertype|null, type_raw, tags: [str],
energy|power|might (int|null), rarity, image_src, image_thumb_src (null until F2-l),
foilable, is_base, price: {market, market_source, market_foil, market_foil_source,
trend_7d_pct, trend_30d_pct, as_of}|null, bans: {<mode>: bool},
owned: {total, foil}}` (`market_source` is the `rbprc_*` column the value came from).

`CollectionLine` and `CollectionGroup` (F3-b) are contracts for the collection screens, the
value snapshots and the sales: additive changes only.
`CollectionLine` = `{id, foil (bool), qty, condition|null, language|null,
purchase_price|null, selling (bool), sell_qty, sell_price|null, updated_at (UTC,
"YYYY-MM-DDTHH:MM:SSZ"), market|null, value|null, pl_abs|null, pl_pct|null}`: `market` is the
price of the line's own foil, `value` = market x qty, `pl_abs` = (market - purchase) x qty and
`pl_pct` = (market - purchase) / purchase x 100, both null unless there is a market price and
a purchase price above 0.
`CollectionGroup` = `{key ("<set>-<id>:N" or ":S"), card: CardSummary, foil (bool), qty,
sell_qty, value|null, lines: [CollectionLine] (by id), keep_playset, playset_short}`.
`keep_playset` is true when the user marked the card name (`rbkeepplayset`);
`playset_short` is true when it is kept and the copies not for sale (`qty - sell_qty`) of
**every** printing and foil of that name, whatever the filters, are fewer than the user's
playset size (3 by default). `GET /cards/<set>/<id>` `my_lines[]` also carry
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

### Sync, jobs and change review

- `POST /admin/riot/sync` body `{sets?: [codes]}` (codes upper-cased; unknown → 400
  `validation_error`, `field: sets`, `invalid_value`, `params: {values: [...]}`) → 202
  `{"job_id": n}`; the job runs `riot_sync` with `trigger=manual`. Active sync → 409
  `job_running`. Audit `riot.sync_requested`. A scheduled run with nothing due ends
  `success` with `{"message": "nothing due", "sets": []}` and fetches nothing.
- `GET /admin/jobs` with `kind`, `status`, `limit` (1-100, default 20), newest first →
  `items[]` of `{id, kind, status, requested_by (username|null), requested_at,
  started_at, finished_at, message}`. `GET /admin/jobs/<id>` adds `params` and `result`;
  404 when missing.
- `GET /admin/riot/changes` with `status` (`pending` default, `approved`, `rejected`,
  `all`), `set`, `field`, `q` (name substring or card id), `page` ≥ 1, `per_page` ≤ 100
  (default 50) → `items[]` of `{id, set_id, card_id, card_name, image_src, field,
  old_value, new_value, status, detected_at, job_id, decided_at, decided_by
  (username|null)}`, newest first; `meta = {page, per_page, total, pages,
  counts: {pending, approved, rejected}}` (global counts).
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
