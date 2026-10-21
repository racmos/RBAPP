# F2-d: Card detail and price history API

| Field | Value |
|---|---|
| Phase / unit | F2 / d |
| Branch | `feat/f2d-card-detail-api` (from up-to-date `main`) |
| Depends on | F2-b merged (F2-c recommended first: it adds `app/api/v1/cards.py` and the upgraded `validate_query`; if F2-c is not merged yet, create the module and stop to ask — do not duplicate `validate_query`) |
| Size forecast | ~450 authored lines (tests and docs included) |
| Risk | `Risk: item 3 (CardDetail and the price series are contracts consumed by F2-g, F3 and F5)` |
| TDD | ON (strict). Runners: `venv/bin/pytest` (backend), `cd frontend && npx vitest run` (frontend, untouched here) |
| Save as | `docs/requirements/F2/F2-d-card-detail-api.md` (commit this document verbatim in the first commit if it is not in the repo yet) |

## Objective

A signed-in client can load everything the card detail screen shows in one request — the card, its real
Cardmarket price columns, every printing of the same name, related cards, in which modes it is banned, the
user's own copies and the user's decks that use it — and the card's daily price history for a chosen range.

## Read first

- `AGENTS.md`, `docs/knowledge/conventions.md`
- `docs/requirements/F2/README.md` (F2-R8, R9, R13, R28; D-F2-5, D-F2-6)
- `docs/api.md` (F2-b/F2-c), `app/services/catalog.py`, `app/services/pricing.py` (`canonical_product_id`,
  `resolve_price_with_source`, `price_summaries`), `app/services/bans.py` (`name_key`, `ban_info`)
- `app/api/v1/cards.py`, `app/schemas/validation.py::validate_query` (F2-c)
- `app/models/collection.py`, `app/models/deck.py` (`rbdck_cards` = `{"main": [{"set","id","qty"}], "sideboard": [...]}`,
  versions = rows with the same user and name and increasing `rbdck_seq`)
- `app/routes/domains/deck.py::_enrich_cards_for_view` (how deck JSON is read today), `openspec/specs/deck-viewing/spec.md`

## Scope

In:
- `GET /riftbound/api/v1/cards/{set_id}/{card_id}` and `GET …/prices`.
- `CardMini` shape for printings and related cards. `docs/api.md`, `AGENTS.md`.

Out (do not do, even if tempting):
- Editing collection lines or decks. Wishlist/watchlist. Cardmarket product URLs (not stored).
- Frontend (F2-g).

## Specs

S1. `GET /riftbound/api/v1/cards/<set_id>/<card_id>` (U), view `get_card` (endpoint `api_v1.get_card`).
    Lookup is exact on both segments. Missing card → 404 with the standard envelope
    `{"success": false, "error": "Not Found", "message": "The requested resource was not found"}`.
    `data` = `CardSummary` (F2-b, with `owned` and `bans` as in F2-c) plus the keys of S2-S7.

S2. `ability` (text or `null`), `artist` (text or `null`), `set` = `{id, name, released_on}`.

S3. `price_detail`: `null` when the card has no product mapping; otherwise
    `{"date": "YYYY-MM-DD", "product_id": int, "columns": {...}, "foil_product_id": int | null, "foil_columns": {...} | null}`.
    `columns` = the latest row of the canonical non-foil product with keys `low, avg1, avg7, avg30, trend,
    low_foil, avg1_foil, avg7_foil, avg30_foil, trend_foil, low_ex` (floats, `null` when NULL). The foil
    product (only when `foilable` and its canonical product differs from the non-foil one) gives
    `foil_columns` with the same keys; otherwise both foil keys are `null`.

S4. `printings`: every card whose `name_key` equals this card's (including itself), ordered by
    `natural_key`, each as `CardMini`:
    `{set_id, card_id, key, name, domains, type, supertype, rarity, image_src, image_thumb_src, is_base, market, owned_total}`
    (`market` = `price.market` of that printing, `owned_total` = the current user's copies of it).

S5. `related`: up to 12 `CardMini`, base printings only, that share at least one tag with this card and have a
    different `name_key`; ordered by number of shared tags (desc), then name casefolded. A card without tags
    → `[]`.

S6. `ban_info` = `ban_info(name)` from F2-a (`[]` when not banned); `bans` (from the summary) stays.

S7. User data, current user only:
  - `my_lines`: the user's `rbcollection` rows of this exact printing, ordered by foil (`N` first), condition,
    language, id; each `{id, foil (bool), qty, condition, language, selling (bool: rbcol_selling in Y/S),
    sell_price (float | null), playset (int | null), updated_at (ISO 8601 UTC)}`.
  - `in_decks`: for each deck name of the user, only the row with the highest `rbdck_seq`; sum `qty` of the
    entries of `main` and `sideboard` whose `(set, id)` card has this card's `name_key`; include decks with
    a sum > 0 as `{deck_id, name, qty}` ordered by name. Entries pointing to a missing card are skipped.
  - Example: user A has deck `Aggro` seq 1 (2× OGN/79) and seq 2 (3× OGN/79 + 1× OGNX/257 in sideboard);
    user B has a deck with OGN/79 → A gets `[{"deck_id": <seq 2 id>, "name": "Aggro", "qty": 4}]`; B's deck
    never appears for A.

S8. `GET /riftbound/api/v1/cards/<set_id>/<card_id>/prices` (U), view `get_card_prices` (endpoint
    `api_v1.get_card_prices`), query schema `CardPricesQuery(range: Literal['30d','90d','1y','all'] = '90d')`
    via `validate_query`.
  - Missing card → 404 envelope. Invalid `range` → 400 `validation_error`, detail `field: "range"`,
    `code: "invalid_value"`.
  - Unmapped card → 200 `{"range": "90d", "currency": "EUR", "foilable": <bool>, "product_id": null, "points": []}`.
  - Otherwise: N product = canonical non-foil product; window = rows dated from (latest date − 30/90/365 days)
    inclusive to the latest date (`all` = every row); one point per N row in ascending date:
    `{date, market, low, avg7, avg30, market_foil}` where `market` is resolved with `foil='N'` (PRC-1) and
    `market_foil` is resolved with `foil='S'` on the foil product's row of the **same date** (`null` when not
    foilable or no row that day).
  - Example: N rows on 2026-07-01 and 2026-10-20 (latest), `range=90d` → only the 2026-10-20 point
    (2026-07-01 is 111 days earlier).

S9. Efficiency: detail ≤ 10 SQL statements and prices ≤ 4 (statement counter in tests); detail < 200 ms on dev
    for a card with 5 printings (timing in the PR).

S10. Docs: `docs/api.md` gets both endpoints, `CardDetail`, `CardMini` and `PricePoint`; `AGENTS.md` (CRLF)
     lists them in "API v1".

## API / data contract

No migration.

```http
GET /riftbound/api/v1/cards/OGN/79
```
```json
{
  "success": true,
  "data": {
    "set_id": "OGN", "card_id": "79", "key": "OGN-79", "number": 79, "name": "Jinx, Loose Cannon",
    "domains": ["Fury", "Chaos"], "type": "Unit", "supertype": "Champion", "type_raw": "Champion Unit",
    "tags": ["Jinx", "Zaun"], "energy": 3, "power": 1, "might": 4, "rarity": "Rare",
    "image_src": "/riftbound/static/images/cards/ogn/ogn_79.png", "image_thumb_src": null,
    "foilable": false, "is_base": true,
    "price": {"market": 1.21, "market_source": "avg7_foil", "market_foil": null, "market_foil_source": null,
              "trend_7d_pct": 10.0, "trend_30d_pct": null, "as_of": "2026-10-20"},
    "bans": {"1v1": true, "2v2": false}, "owned": {"total": 3, "foil": 0},
    "ability": "[Accelerate] When I attack, deal 2 to an enemy unit here.",
    "artist": "…",
    "set": {"id": "OGN", "name": "Origins", "released_on": "2025-10-31"},
    "price_detail": {"date": "2026-10-20", "product_id": 812345,
      "columns": {"low": 0.9, "avg1": 1.3, "avg7": 1.15, "avg30": 1.05, "trend": 1.2, "low_foil": null,
                  "avg1_foil": null, "avg7_foil": 1.21, "avg30_foil": 1.1, "trend_foil": null, "low_ex": 1.0},
      "foil_product_id": null, "foil_columns": null},
    "printings": [
      {"set_id": "OGN", "card_id": "79", "key": "OGN-79", "name": "Jinx, Loose Cannon", "domains": ["Fury", "Chaos"],
       "type": "Unit", "supertype": "Champion", "rarity": "Rare", "image_src": "…", "image_thumb_src": null,
       "is_base": true, "market": 1.21, "owned_total": 3}
    ],
    "related": [],
    "ban_info": [{"mode": "1v1", "since": "2026-09-01", "reason": "Too strong"}],
    "my_lines": [{"id": 17, "foil": false, "qty": 3, "condition": "NM", "language": "English", "selling": false,
                  "sell_price": null, "playset": null, "updated_at": "2026-10-01T09:30:00Z"}],
    "in_decks": [{"deck_id": 42, "name": "Aggro", "qty": 3}]
  }
}
```

```http
GET /riftbound/api/v1/cards/OGN/79/prices?range=30d
```
```json
{"success": true, "data": {"range": "30d", "currency": "EUR", "foilable": false, "product_id": 812345,
  "points": [{"date": "2026-10-19", "market": 1.18, "low": 0.9, "avg7": 1.12, "avg30": 1.04, "market_foil": null},
             {"date": "2026-10-20", "market": 1.21, "low": 0.9, "avg7": 1.15, "avg30": 1.05, "market_foil": null}]}}
```

Authz: `api_v1.get_card`, `api_v1.get_card_prices` → `U`. No new error code.

## UI

none

## Acceptance criteria

- [ ] AC1 `tests/test_api_card_detail.py`: summary keys present; 404 envelope; `price_detail` null/unmapped and with foil product for a common; printings order and `owned_total`; related rules (shared-tag order, base only, other names only, max 12, no tags → []); `ban_info`; `my_lines` order and fields; `in_decks` S7 example with two users (S1-S7).
- [ ] AC2 `tests/test_api_card_prices.py`: default range, each range window, S8 example, `market_foil` same-date rule, unmapped 200 with `[]`, invalid range 400, 404 (S8).
- [ ] AC3 Statement counts of S9; detail timing in the PR.
- [ ] AC4 `tests/test_authz_matrix.py` classifies both endpoints as U; anonymous 401 JSON.
- [ ] AC5 Full lanes green: `venv/bin/pytest`; `cd frontend && npm run lint && npm run typecheck && npx vitest run && npm run build && npm run check:dist`
- [ ] AC6 `docs/knowledge/state.md` updated (what changed, PR number placeholder, new follow-ups)
- [ ] AC7 `docs/api.md` / `AGENTS.md` updated (S10).

## Delivery

- Conventional Commits; commit messages end with the attribution lines the session supplies.
- Push and PR only when the user says so. PR title: `feat(api): card detail and price history (F2 unit d)`.
  PR body: summary, specs → tests map (S# → test file::name), S9 timings, manual checks, rollback (revert; no migration).
- Never merge. The user merges.

## After merge (user asks gentle-shell, or does it)

- Deploy to dev with `docs/knowledge/ops-runbook.md` (no migration; restart).
- Live checks (signed in): `GET <URL>/riftbound/api/v1/cards/<a real set>/<a real id>` → 200 with
  `printings` ≥ 1; `…/prices?range=all` → 200, points ascending; `GET …/cards/NOPE/1` → 404 JSON.
- Manual checks for the user: none (no UI yet).

## Open questions

- CONFIRM D-F2-5: the detail exposes the raw Cardmarket columns (`columns`) and the UI will show
  "Mercado", "Mín.", "Media 30 d" and "Mercado foil".
- CONFIRM D-F2-6: ranges `30d`, `90d` (default), `1y`, `all`.
