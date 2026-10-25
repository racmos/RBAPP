# F2-b: Game meta, card DTO and price summary

| Field | Value |
|---|---|
| Phase / unit | F2 / b |
| Branch | `feat/f2b-game-meta-card-dto` (stacked on the previous unit's branch, `docs/requirements/BATCH-1.md` R1) |
| Depends on | F2-a merged (`app/schemas/game_domain.py`, `app/services/bans.py`) |
| Size forecast | ~550 authored lines (tests and docs included) |
| Risk | `Risk: items 1 and 3 (index migration 0008 on rbcm_price; CardSummary and GET /meta/game are contracts consumed by F2-c..j, F3-F6)` |
| TDD | ON (strict). Runners: `venv/bin/pytest` (backend), `cd frontend && npx vitest run` (frontend, untouched here) |
| Save as | `docs/requirements/F2/F2-b-game-meta-card-dto.md` (commit this document verbatim in the first commit if it is not in the repo yet) |

## Objective

The backend gets one place that turns a raw `rbcards` row into the clean card object every screen will use
(domains and tags as lists, type split from supertype, natural number, foil eligibility, base printing,
Cardmarket price with its source and 7/30-day trend), plus a public endpoint that tells the app the game's
modes, domains, types, rarities, sets and price freshness. Nothing visible changes for the user yet; the
catalog list (F2-c) and detail (F2-d) are thin layers over this unit.

## Read first

- `AGENTS.md`, `docs/knowledge/conventions.md`
- `docs/requirements/F2/README.md` (F2-R4, R5, R6, R11, R28; D-F2-1, D-F2-4, D-F2-5)
- `openspec/specs/price-resolution/spec.md` (PRC-1, PRC-2: must keep passing unchanged)
- `app/services/pricing.py`, `tests/test_pricing.py`, `app/models/cardmarket.py` (`RbcmPrice`, `RbcmProductCardMap`)
- `app/routes/domains/collection.py::_collection_query` (same canonical-product rule, for reference only)
- `app/models/card.py`, `app/models/set.py`, `app/services/riot_scraper.py::_parse_card` (how
  `rbcar_domain`, `rbcar_type`, `rbcar_tags`, card ids are written)
- `app/services/cardmarket_matcher.py::_expand_slots` (foil slots: Basic Rune none, common/uncommon N+S, rest none)
- `app/schemas/game_domain.py`, `app/services/bans.py` (F2-a), `app/api/v1/meta.py`
- `tests/test_migrations.py` (one class per revision)

## Scope

In:
- `app/schemas/game_domain.py`: domains, types, supertypes, rarities.
- `app/services/catalog.py`: parsing, natural sort key, foil eligibility, base printings, `card_summary`.
- `app/services/pricing.py`: `resolve_price_with_source`, batch `price_summaries` with trends.
- Migration `0008_price_product_date_idx` + model index.
- `GET /riftbound/api/v1/meta/game` (P).
- `docs/api.md` (created by F13-b): add `GameMeta` and `CardSummary`.

Out (do not do, even if tempting):
- Any list or detail endpoint (F2-c, F2-d). Frontend types (F2-e). Thumbnails (`image_thumb_src` is always
  `null` here; F2-j fills it).
- Changing PRC-1 behaviour, `resolve_price`'s signature, the collection queries or the Jinja pages.

## Specs

S1. First (D-F2-1), run on the dev database, read only, and paste the output in the PR:
    `SELECT rbcar_domain, count(*) FROM riftbound.rbcards GROUP BY 1 ORDER BY 1;` and the same for `rbcar_type`
    and `rbcar_rarity`. Adapt the tuples below to the real values (known values keep this order; extra real
    values are appended). Then `app/schemas/game_domain.py` adds (keeping `GAME_MODES`):
    `DOMAINS = ('Fury', 'Calm', 'Mind', 'Body', 'Chaos', 'Order', 'Colorless')`,
    `CARD_TYPES = ('Legend', 'Unit', 'Spell', 'Gear', 'Rune', 'Battlefield')`,
    `SUPERTYPES = ('Champion', 'Signature', 'Token', 'Basic')`,
    `RARITIES = ('Common', 'Uncommon', 'Rare', 'Epic', 'Showcase')` (tuple order = rank, lowest first).

S2. Parsing in `app/services/catalog.py` (pure functions):
  - `parse_domains(text)`: split on whitespace and commas, drop empties; a token equal to a `DOMAINS` value
    ignoring case becomes that value; other tokens are kept stripped; duplicates removed keeping order; NULL
    or empty → `[]`. Example: `"fury  CHAOS"` → `["Fury", "Chaos"]`.
  - `parse_type(text) -> (type, supertype)`: the last word, if it equals a `CARD_TYPES` value ignoring case,
    is the type; the words before it (if any) form the supertype, each word matched to `SUPERTYPES`
    ignoring case (unknown words kept), joined with a space; a last word that is not a known type → type =
    the whole stripped text, supertype `None`. NULL/empty → `(None, None)`.
    Examples: `Champion Unit` → `("Unit", "Champion")`; `Signature Spell` → `("Spell", "Signature")`;
    `basic rune` → `("Rune", "Basic")`; `Token Unit` → `("Unit", "Token")`; `Legend` → `("Legend", None)`;
    `Creature` → `("Creature", None)`.
  - `parse_tags(text)`: split on `,`, strip, drop empties, dedupe keeping order. `"Aphelios, Mount Targon"`
    → `["Aphelios", "Mount Targon"]`.
  - `card_number(card_id)`: the leading digits as `int`, else `None` (`"79a"` → 79, `"227s"` → 227,
    `"t03"` → `None`).
  - `is_foilable(type, rarity)`: `False` when type is `Rune`; otherwise `True` only for rarity
    `common`/`uncommon` (case-insensitive). Example: Showcase → `False`; Basic Rune (Common) → `False`.

S3. Ordering helpers:
  - `set_order(sets)`: sets ordered by `rbset_outdat` ascending with NULL last, then `rbset_id`; returns
    `{set_id: rank}`.
  - `natural_key(set_rank, card_id)`: `(set_rank, number is None, number or 0, card_id.casefold())`.
    Example in one set: `1, 2, 7, 7a, 10, t01` sort in that order.
  - `rarity_rank(rarity)`: index in `RARITIES` ignoring case; unknown → `len(RARITIES)` (sorts last).

S4. Base printings (`base_printing_keys(cards, set_rank) -> set[(set_id, card_id)]`, D-F2-4): group cards by
    `name_key` (F2-a). In each group the candidates are the printings whose `card_id` is all digits; if none,
    all printings. Order candidates by `(set_rank, number, card_id)`; the first is the base. Example: name
    with `OGN/79`, `OGN/79a`, `OGNX/257` (OGNX released later) → base `OGN/79`; a token group `t01`, `t02`
    → base `t01`.

S5. `resolve_price_with_source(row, *, rarity, foil) -> tuple[float | None, str | None]` in
    `app/services/pricing.py`: same chain as PRC-1; the source is the column name without `rbprc_`
    (`avg7_foil`, `avg7`, `low_foil`, `low`); `(None, None)` when nothing is available. `resolve_price`
    becomes `return resolve_price_with_source(...)[0]` (one implementation, PRC-2). Every existing
    `tests/test_pricing.py` case passes unchanged.

S6. `price_summaries(items) -> dict[(set_id, card_id), dict | None]` in `app/services/pricing.py`, where each
    item is `(set_id, card_id, rarity, foilable)`:
  - Canonical product per card and foil slot with the rule of `canonical_product_id` (exact foil mapping →
    unclassified NULL → any; lowest `idProduct`), slot `N` always, slot `S` only when `foilable`.
  - Latest row per product = the row with the greatest `rbprc_date` of that product.
  - `market, market_source` = `resolve_price_with_source(latest N row, rarity, foil='N')`;
    `market_foil, market_foil_source` = same on the latest S row with `foil='S'` (both `None` when not
    foilable or unmapped).
  - Trend: for the N product, the reference row for `d` days is the newest row dated on or before
    (latest date − d days). `trend_7d_pct` / `trend_30d_pct` = `round((now − then) / then * 100, 1)` with
    `now`/`then` resolved like `market`; `None` when either is `None` or `then` is 0.
  - `as_of` = ISO date (`YYYY-MM-DD`) of the latest N row (of the S row when there is no N row).
  - A card with no mapping at all → `None`.
  - Query count is constant (at most 6 SQL statements) for any number of items; a test counts statements
    with an SQLAlchemy `before_cursor_execute` listener for 1 and for 50 cards.
  - Example: common card, N product rows `20261001 avg7=1.00`, `20261014 avg7=1.10`, `20261021 avg7=1.21`
    → `market=1.21`, `market_source="avg7"`, `trend_7d_pct=10.0`, `trend_30d_pct=None` (no row 30 days
    back), `as_of="2026-10-21"`.

S7. `card_summary(card, *, set_rank, base_keys, price, bans, owned) -> dict` returns exactly the keys of the
    contract below, in that order. `key` = `"<set_id>-<card_id>"`; `image_src` = `card.image_src`;
    `image_thumb_src` = `None` (F2-j); `price` = the `price_summaries` value (or `None`); `bans` =
    `card_bans(card.rbcar_name, bans)` (F2-a); `owned` = `{"total": int, "foil": int}` given by the caller
    (`{"total": 0, "foil": 0}` default).

S8. Migration `0008_price_product_date_idx` (`down_revision = '0007_card_bans'`) creates index
    `idx_rbcm_price_product_date` on `riftbound.rbcm_price (rbprc_id_product, rbprc_date)`; downgrade drops
    it. `RbcmPrice.__table_args__` declares the same index (schema `riftbound`) so `flask db check` reports
    no drift.

S9. `GET /riftbound/api/v1/meta/game` (P), view function `meta_game` in `app/api/v1/meta.py` (endpoint
    `api_v1.meta_game`):
  - `modes` = `GAME_MODES`; `domains`, `types`, `supertypes`, `rarities` = the S1 tuple followed by any other
    distinct non-empty value found in the data (after S2 parsing), sorted case-insensitively.
  - `sets` = every `rbset` row in `set_order`, each `{id, name, released_on (ISO or null), card_count}` where
    `card_count` is the number of `rbcards` rows of the set (0 when none).
  - `price` = `{"provider": "cardmarket", "currency": "EUR", "updated_on": <ISO date of max(rbprc_date) or null>}`.
  - `rules` = `{}` (F5 adds `rules.deck`). Clients must ignore unknown keys (stated in `docs/api.md`).
  - Header `Cache-Control: no-cache`. Works anonymous and signed in; no user data.

S10. `docs/api.md` (exists since F13-b; extend it, LF): "API v1 reference" with the envelope, the error body, one section per
     endpoint (for now `GET /meta/game` and `GET /bans`, plus a pointer to `AGENTS.md` for auth/prefs) and a
     "Data shapes" section with `GameMeta` and `CardSummary` exactly as below, marked "additive changes
     only". `AGENTS.md` (CRLF) lists `GET /meta/game`, `app/services/catalog.py`, `app/schemas/game_domain.py`
     and links `docs/api.md`. Later units extend `docs/api.md`.

## API / data contract

Migration `0008_price_product_date_idx`: up creates the index, down drops it. No data change.

```http
GET /riftbound/api/v1/meta/game
```
```json
{
  "success": true,
  "data": {
    "modes": ["1v1", "2v2"],
    "domains": ["Fury", "Calm", "Mind", "Body", "Chaos", "Order", "Colorless"],
    "types": ["Legend", "Unit", "Spell", "Gear", "Rune", "Battlefield"],
    "supertypes": ["Champion", "Signature", "Token", "Basic"],
    "rarities": ["Common", "Uncommon", "Rare", "Epic", "Showcase"],
    "sets": [{"id": "OGN", "name": "Origins", "released_on": "2025-10-31", "card_count": 298}],
    "price": {"provider": "cardmarket", "currency": "EUR", "updated_on": "2026-10-20"},
    "rules": {}
  }
}
```

`CardSummary` (built by `card_summary`; F2-c/F2-d return it):

```json
{
  "set_id": "OGN", "card_id": "79a", "key": "OGN-79a", "number": 79,
  "name": "Jinx, Loose Cannon",
  "domains": ["Fury", "Chaos"],
  "type": "Unit", "supertype": "Champion", "type_raw": "Champion Unit",
  "tags": ["Jinx", "Zaun"],
  "energy": 3, "power": 1, "might": 4,
  "rarity": "Rare",
  "image_src": "/riftbound/static/images/cards/ogn/ogn_79a.png",
  "image_thumb_src": null,
  "foilable": false,
  "is_base": false,
  "price": {
    "market": 1.21, "market_source": "avg7_foil",
    "market_foil": null, "market_foil_source": null,
    "trend_7d_pct": 10.0, "trend_30d_pct": null,
    "as_of": "2026-10-21"
  },
  "bans": {"1v1": false, "2v2": true},
  "owned": {"total": 2, "foil": 0}
}
```

Authz: `api_v1.meta_game` → `P` in `tests/test_authz_matrix.py`. No new error code.

## UI

none

## Acceptance criteria

- [ ] AC1 `tests/test_catalog_service.py`: every S2 example, `natural_key` order, `rarity_rank`, `is_foilable`, base printings (S3, S4), `card_summary` key order and values (S7).
- [ ] AC2 `tests/test_pricing.py`: new `resolve_price_with_source` table (each chain link and `(None, None)`); all existing PRC-1/PRC-2 tests unchanged and green (S5).
- [ ] AC3 `tests/test_price_summaries.py`: S6 example, foil slot only when foilable, premium rarity uses the foil-first chain, unmapped → `None`, trend `None` cases, `as_of`, constant statement count for 1 and 50 cards (S6).
- [ ] AC4 `tests/test_price_index_migration.py`: chains after the current head (BATCH-1 G3); index exists with the two columns in order; downgrade removes it; models equal the schema at head (S8).
- [ ] AC5 `tests/test_api_meta_game.py`: shape and order, unknown data values appended, set order with a NULL release date, `card_count`, `updated_on` null and set, `Cache-Control: no-cache`, anonymous 200 (S9).
- [ ] AC6 `tests/test_authz_matrix.py` classifies `api_v1.meta_game` as P and passes.
- [ ] AC7 Performance note in the PR: `price_summaries` for all dev cards timed in `flask shell` (target < 150 ms).
- [ ] AC8 Full lanes green: `venv/bin/pytest`; `cd frontend && npm run lint && npm run typecheck && npx vitest run && npm run build && npm run check:dist`
- [ ] AC9 `docs/knowledge/state.md` updated (what changed, PR number placeholder, new follow-ups)
- [ ] AC10 `docs/api.md` extended (F13-b created it) and `AGENTS.md` updated (S10).

## Delivery

- Conventional Commits; commit messages end with the attribution lines the session supplies.
- Suggested slices: (1) game_domain + catalog parsing + base printings, (2) pricing + migration, (3) meta endpoint + docs.
- Push and PR only when the user says so. PR title: `feat(catalog): game meta endpoint, card DTO and price summaries (F2 unit b)`.
  PR body: summary, specs → tests map (S# → test file::name), timing of AC7, manual checks, rollback
  (`flask db downgrade -1` drops the index; code revert is safe).
- Never merge. The user merges.

## After merge (user asks gentle-shell, or does it)

- Deploy to dev with `docs/knowledge/ops-runbook.md` — **backup first** (migration `0008`), `flask db upgrade`,
  `flask db check`, restart.
- Live checks: anonymous `GET <URL>/riftbound/api/v1/meta/game` → 200 with every set of the dev catalog in
  release order and `price.updated_on` = the last Cardmarket load date.
- Manual checks for the user: compare the `domains`, `types`, `supertypes` and `rarities` lists with the
  values seen in the Jinja catalog; any unexpected value appended at the end is reported to the planner.

## Open questions

none — the CONFIRM items of the draft (D-F2-1, D-F2-4, D-F2-5) are answered in
`docs/knowledge/decisions-2026-10-25.md`; batch rules in `docs/requirements/BATCH-1.md` (G1-G12) apply.
