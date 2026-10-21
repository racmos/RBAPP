# F2-c: Cards list API — filters, facets, sort, pagination

| Field | Value |
|---|---|
| Phase / unit | F2 / c |
| Branch | `feat/f2c-cards-list-api` (from up-to-date `main`) |
| Depends on | F2-b merged (`app/services/catalog.py`, `price_summaries`, `card_summary`) |
| Size forecast | ~550 authored lines (tests and docs included) |
| Risk | `Risk: item 3 (GET /cards and the upgraded validate_query are contracts consumed by the catalog UI, the combobox, F3 and F5)` |
| TDD | ON (strict). Runners: `venv/bin/pytest` (backend), `cd frontend && npx vitest run` (frontend, untouched here) |
| Save as | `docs/requirements/F2/F2-c-cards-list-api.md` (commit this document verbatim in the first commit if it is not in the repo yet) |

## Objective

A signed-in client can ask for any slice of the card catalog in one request: free-text search, every facet
the catalog UI needs (set, domain, type, supertype, rarity, tag, numeric ranges, price, owned, banned),
sorting and pagination, and gets back the cards in the shared `CardSummary` shape plus facet counts that
tell the UI how many results each other option would give.

## Read first

- `AGENTS.md`, `docs/knowledge/conventions.md`
- `docs/requirements/F2/README.md` (F2-R7, R12, R13, R27, R28; D-F2-3, D-F2-13)
- `docs/api.md` (F2-b: `CardSummary`), `app/services/catalog.py`, `app/services/pricing.py::price_summaries`,
  `app/services/bans.py` (`ban_map`, `card_bans`)
- `app/schemas/validation.py` (`validate_json`, `_detail`, the unused `validate_query`), `app/schemas/validators.py`
- `app/api/v1/bans.py` (F2-a: manual `mode` validation to move onto `validate_query`)
- `app/models/collection.py` (`rbcol_user` is the username; `rbcol_foil` 'S'/'N')
- `tests/test_authz_matrix.py`, `tests/conftest.py` (`make_user`, `login_as`, `authenticated_client`)

## Scope

In:
- `validate_query` rewrite (lists, codes) and `GET /bans` moved onto it.
- `CardListQuery` schema; `GET /riftbound/api/v1/cards` in `app/api/v1/cards.py`.
- Owned counts for the current user; bans; prices; facets; sort; pagination.
- `docs/api.md` and `AGENTS.md`.

Out (do not do, even if tempting):
- Card detail and price history (F2-d). Any frontend code (F2-e/f). Thumbnails (F2-j).
- Changing `/riftbound/collection/api/cards` or the Jinja catalog.

## Specs

S1. `validate_query(schema)` in `app/schemas/validation.py` is rewritten:
  - Input dict: for each schema field whose annotation is a list, `request.args.getlist(name)`; for the
    others `request.args.get(name)`. Empty strings are dropped (a field sent as `?price_min=` is absent).
    Unknown parameters are ignored.
  - Pydantic does the coercion (`int`, `float`, `bool` from `true/false/1/0`, `Literal`).
  - On error → 400 with the same body as `validate_json` but `message: "Invalid query parameters"`:
    `{"success": false, "error": "Validation Error", "message": "Invalid query parameters", "code": "validation_error", "details": [{"field": "per_page", "message": "...", "type": "less_than_equal", "code": "out_of_range", "params": {"max": 192}}]}`
    (reuse `_detail`).
  - The validated model is `request.validated_query`.
  - `GET /bans` (F2-a) uses it with schema `BanListQuery(mode: Literal['1v1','2v2'] | None)`; its existing
    tests keep passing (the body for `mode=3v3` keeps `field: "mode"`, `code: "invalid_value"`).

S2. `CardListQuery` (`app/schemas/validators.py`, `extra='ignore'`), all optional:

    | Param | Type / domain | Default |
    |---|---|---|
    | `q` | str, ≤ 100 chars | — |
    | `text` | str, ≤ 100 chars (ability text) | — |
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

  - Example: `?per_page=500` → 400, detail `field: "per_page"`, `code: "out_of_range"`, `params: {"max": 192}`.
  - Example: `?sort=popularity` → 400, `field: "sort"`, `code: "invalid_value"`.
  - A min greater than its max is not an error: the result is empty.

S3. Filters (case-insensitive comparisons; OR inside a parameter, AND across parameters):
  - `q` (trimmed): the card matches if its name contains `q`, or one of its tags contains `q`, or `q` equals
    its `card_id` or its `key` (`OGN-79a`); when `q` is only digits it also matches every card whose
    `number` equals it (`79` → `79`, `79a`, `79s`).
  - `text`: the ability text contains it.
  - `set`: `set_id` in the list. `rarity`: in the list. `type`: parsed type in the list. `supertype`: parsed
    supertype in the list. `exclude_supertype`: parsed supertype not in the list (cards without supertype
    stay). `tag`: at least one tag equal to a listed value.
  - `domain` with `domain_match`: `any` → at least one shared domain; `all` → every listed domain is on the
    card; `subset` → every card domain is listed (a card without domains matches).
  - Ranges: inclusive; a card whose value is `null` is excluded as soon as that range has a bound.
  - `price_min`/`price_max` apply to `price.market`; a card without a market price is excluded when either
    bound is given.
  - `owned=owned` → `owned.total > 0`; `owned=missing` → `owned.total == 0`.
  - `banned_in=1v1|2v2` → banned in that mode; `any` → banned in at least one mode.
  - `base_only=true` → `is_base` only.

S4. Facets in `meta.facets` (disjunctive): for each of `set`, `domain`, `type`, `supertype`, `rarity` the counts
    are computed over the cards that match every filter **except that facet's own parameter**. Only values
    with a count > 0 appear; keys in canonical order (sets by release order, the others by the
    `game_domain` tuple order, then unknown values alphabetically). A card with two domains counts once in
    each. `tag` is a list of the top 30 `{tag, count}` (count desc, then tag) over the cards matching every
    filter except `tag`.
  - Example: 3 Fury cards and 2 Calm cards in OGN, query `domain=Fury` → `items` has 3 cards, `facets.domain`
    = `{"Fury": 3, "Calm": 2}`, `facets.set` = `{"OGN": 3}`.

S5. Sort (ties always broken by `natural_key` ascending, F2-b S3):
  - `number` → `natural_key`; `name` → name casefolded; `rarity` → `rarity_rank`; `price` → `price.market`;
    `trend_7d` / `trend_30d` → the trend; `energy` / `power` / `might` → the value.
  - `dir=desc` reverses the main key only; `null` values (no price, no trend, no energy…) are always last.

S6. Pagination: `meta.total` = number of matching cards, `meta.pages` = `ceil(total / per_page)` (0 when
    total is 0), `items` = the requested page; a page past the end returns `items: []` with status 200.
    `meta.price_as_of` = the ISO date of the newest `rbprc_date` (or `null`).

S7. User data: `owned` = `{total, foil}` summed from the current user's `rbcollection` rows of that exact
    printing (`foil` counts rows with `rbcol_foil = 'S'`); never from another user. `bans` from one
    `ban_map()` call.

S8. Efficiency: at most 12 SQL statements per request whatever the catalog size (test with 200 cards and a
    statement counter). Prices are computed for every matching card only when `sort` is `price`/`trend_*` or a
    price bound is given; otherwise only for the returned page. Filtering, facets and sort MAY run in
    Python over the full catalog (no PostgreSQL-only SQL). p95 < 300 ms on the dev database for: default
    query, `sort=price&dir=desc`, `q=jinx`, `domain=Fury&domain=Chaos&domain_match=subset` (measured in
    `flask shell` with the test client, 20 runs each, numbers in the PR).

S9. `GET /riftbound/api/v1/cards` (U), view function `list_cards` in `app/api/v1/cards.py` (endpoint
    `api_v1.list_cards`), imported in `app/api/v1/__init__.py`. Anonymous → JSON 401. Response:
    `{"success": true, "data": {"items": [CardSummary, …]}, "meta": {"page", "per_page", "total", "pages", "facets", "price_as_of"}}`.

S10. Docs: `docs/api.md` gets the `GET /cards` section (parameter table of S2, filter rules of S3, facets,
     sort, example); `AGENTS.md` (CRLF) lists `app/api/v1/cards.py` and `GET /cards` in "API v1".

## API / data contract

No migration.

```http
GET /riftbound/api/v1/cards?domain=Fury&sort=price&dir=desc&per_page=2
```
```json
{
  "success": true,
  "data": {
    "items": [
      {"set_id": "OGN", "card_id": "41", "key": "OGN-41", "number": 41, "name": "…", "domains": ["Fury"],
       "type": "Unit", "supertype": null, "type_raw": "Unit", "tags": [], "energy": 2, "power": null,
       "might": 3, "rarity": "Epic", "image_src": "/riftbound/static/images/cards/ogn/ogn_41.png",
       "image_thumb_src": null, "foilable": false, "is_base": true,
       "price": {"market": 12.5, "market_source": "avg7_foil", "market_foil": null, "market_foil_source": null,
                 "trend_7d_pct": -3.1, "trend_30d_pct": 8.0, "as_of": "2026-10-20"},
       "bans": {"1v1": false, "2v2": false}, "owned": {"total": 1, "foil": 0}}
    ]
  },
  "meta": {
    "page": 1, "per_page": 2, "total": 57, "pages": 29,
    "facets": {
      "set": {"OGN": 40, "SFD": 17},
      "domain": {"Fury": 57, "Calm": 51, "Mind": 49, "Body": 55, "Chaos": 50, "Order": 47},
      "type": {"Legend": 3, "Unit": 30, "Spell": 18, "Gear": 6},
      "supertype": {"Champion": 6, "Signature": 3},
      "rarity": {"Common": 20, "Uncommon": 17, "Rare": 12, "Epic": 6, "Showcase": 2},
      "tag": [{"tag": "Noxus", "count": 9}]
    },
    "price_as_of": "2026-10-20"
  }
}
```

Errors: 400 `validation_error` (S1, S2); 401 anonymous. Authz: `api_v1.list_cards` → `U`. No new error code.

## UI

none

## Acceptance criteria

- [ ] AC1 `tests/test_validate_query.py`: lists from repeated params, empty strings dropped, unknown params ignored, bool coercion, error body identical in shape to `validate_json` with `message: "Invalid query parameters"` and detail codes (S1).
- [ ] AC2 `tests/test_api_bans.py` still green after moving onto `validate_query` (S1).
- [ ] AC3 `tests/test_api_cards.py::TestQueryValidation`: the S2 examples, defaults, min > max → empty 200 (S2).
- [ ] AC4 `tests/test_api_cards.py::TestFilters`: one test per S3 rule, including `q` by digits, key, tag; the three `domain_match` modes; null exclusion in ranges and price; `owned` with two users (never the other user's rows); `banned_in`; `base_only` (S3, S7).
- [ ] AC5 `tests/test_api_cards.py::TestFacets`: the S4 example, disjunctive counts for each facet, canonical key order, top-30 tags (S4).
- [ ] AC6 `tests/test_api_cards.py::TestSortAndPages`: each sort key both directions with nulls last and natural tiebreak; total/pages/past-the-end page; `price_as_of` (S5, S6).
- [ ] AC7 Statement count ≤ 12 with 200 cards; prices only for the page on the default sort (S8). Timings of S8 in the PR.
- [ ] AC8 `tests/test_authz_matrix.py` classifies `api_v1.list_cards` as U; anonymous 401 JSON (S9).
- [ ] AC9 Full lanes green: `venv/bin/pytest`; `cd frontend && npm run lint && npm run typecheck && npx vitest run && npm run build && npm run check:dist`
- [ ] AC10 `docs/knowledge/state.md` updated (what changed, PR number placeholder, new follow-ups)
- [ ] AC11 `docs/api.md` / `AGENTS.md` updated (S10).

## Delivery

- Conventional Commits; commit messages end with the attribution lines the session supplies.
- Suggested slices: (1) `validate_query` + bans, (2) filters + facets, (3) sort/pages/owned + docs.
- Push and PR only when the user says so. PR title: `feat(api): cards list with filters, facets and sort (F2 unit c)`.
  PR body: summary, specs → tests map (S# → test file::name), S8 timings, manual checks, rollback (revert; no migration).
- Never merge. The user merges.

## After merge (user asks gentle-shell, or does it)

- Deploy to dev with `docs/knowledge/ops-runbook.md` (no migration; restart).
- Live checks (signed in, browser devtools or `curl` with the session cookie):
  - `GET <URL>/riftbound/api/v1/cards?per_page=5` → 200, 5 items, `meta.total` = number of cards in the catalog.
  - `GET <URL>/riftbound/api/v1/cards?per_page=500` → 400 `validation_error`.
  - anonymous `GET <URL>/riftbound/api/v1/cards` → 401 JSON.
- Manual checks for the user: none (no UI yet).

## Open questions

- CONFIRM D-F2-3: catalog API for signed-in users only (U).
- CONFIRM D-F2-13: default `per_page` 48, max 192; default sort `number` ascending.
