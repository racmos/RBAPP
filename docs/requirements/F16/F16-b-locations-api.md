# F16-b: Storage locations, JSON API

| Field | Value |
|---|---|
| Phase / unit | F16 / b |
| Branch | `feat/f16b-locations-api` (stacked on `feat/f16a-locations-data`, PR #87) |
| Depends on | F16-a (migration 0024, `RbLocation`, `RbCollectionLocation`, `app/services/locations.py`) |
| Size forecast | ~1,100 authored lines (about 60 % tests) |
| Risk | `Risk: item 3 (GET /collection lines gain locations, locations_more, unassigned and a location filter: an additive change to the CollectionLine contract)` |
| TDD | ON (strict). Runner: `venv/bin/pytest` (backend only) |
| Save as | `docs/requirements/F16/F16-b-locations-api.md` |

## Objective

The React client can manage a user's storage locations (create, rename, describe, lock, order,
delete), see and change where the copies of each collection line are, get the suggested next
code, and read a short location summary on every line of the collection, filtering it by
location. No UI yet (F16-c, F16-d). No migration.

## Read first

- `AGENTS.md` (API v1, envelope, `@validate_json` / `@validate_query`, Adding a New Route,
  error codes)
- `docs/requirements/F16/README.md` (R1, R1a, R2, R3, R4, R5, D1-D6),
  `docs/requirements/F16/F16-a-locations-data.md`
- `app/services/locations.py`, `app/models/location.py`
- `app/api/v1/collection.py`, `app/services/collection_read.py` (the `GET /collection` contract
  and its 10-statement bound), `app/api/v1/me_products.py` (pattern)

## Scope

In:
- `app/api/v1/locations.py`: the locations endpoints and the line assignment endpoints
- `app/services/locations.py`: API shapes and counts (`location_item`, `location_items`,
  `owned_item`, `unassigned_total`), the atomic replacement `set_line_locations`;
  `LocationOverQuantity` also carries `requested`
- `app/services/collection_read.py`: line locations and the `location` filter
- Error codes `location_over_quantity`, `location_locked` (enum, English catalog)

Out (do not do, even if tempting):
- A migration (none is needed)
- Deck mount, `DECK-001` codes, `insufficient_unlocked` (F16-e)
- Screens (F16-c, F16-d); a location page with its cards and value (F16-c reads
  `GET /collection?location=`)
- Location keys in the write responses or `GET /cards/<set>/<id>` `my_lines`
- A group-level location total (`qty - Σ unassigned` of its lines gives it)

## Specs

S1. `GET /locations` (U) → `{data: {items: [Location]}, meta: {unassigned_copies}}` in the
    user's order. `Location` = `{id, code, description, position, locked, deck_id, copies,
    cards}` in this order; `copies` = copies kept there, `cards` = lines kept there;
    `unassigned_copies` = copies of the user's lines in no location.
S2. `POST /locations` `{code, description?}` → 201 `Location`, last. Duplicate code ignoring
    case → 409 `already_exists`. Code: 1-32 letters, digits or `-` (400 `validation_error` on
    `code`: `required`, `too_short`, `too_long`, `invalid_format`, `invalid_value`).
    Description ≤ 200, trimmed, empty = null.
S3. `GET /locations/next-code?bump=block|row|pack[&after=CODE]` → `{code}` from
    `suggest_next_code` (F16-a S7): `B001-F001-P0001` when the user has no patterned code and
    no `after`; `null` when `after` has no pattern or the result is over 32 characters. `bump`
    required.
S4. `PATCH /locations/<id>` any of `{code, description, locked}` → `Location`; only sent keys
    change; `code: null` / `locked: null` → 400; duplicate → 409 `already_exists`, nothing
    changes. **Decision: a locked location can be renamed and re-described** (labels only); the
    lock makes its quantities read-only (F16-R3).
S5. `DELETE /locations/<id>` → `{deleted: Location}` (counts before the delete); copies become
    unassigned; order closes up. Locked deck location → 409 `location_locked`.
S6. `PUT /locations/order` `{ids}` → `{items: [Location]}`; anything but every id of the user
    once → 400 `validation_error` on `ids` (`invalid_value`), nothing changes.
S7. `GET /collection/<id>/locations` → `{locations: [{location_id, code, description, locked,
    qty}], unassigned, total}`.
S8. `PUT /collection/<id>/locations` `{assignments: [{location_id, qty 1-9999}]}` (each location
    once) replaces the line's assignment atomically. A locked location whose quantity would
    change → 409 `location_locked` (checked first); sum > line quantity → 409
    `location_over_quantity`, `params {max, requested}`; foreign ids → 404.
S9. `POST /collection/<id>/locations/move` `{from_location_id|null, to_location_id|null, qty}`
    (sides differ) → S7 shape. From unassigned beyond the unassigned copies → 409
    `location_over_quantity` `{max: unassigned, requested}`; from a location beyond what it
    holds → 409 `insufficient_quantity` `{available}`; locked side → 409 `location_locked`.
S10. `GET /collection` lines append `locations` (first 5 in the user's order, `[{location_id,
    code, description, qty}]`), `locations_more`, `unassigned`. Group keys unchanged; write
    responses unchanged.
S11. `GET /collection?location=CODE` (repeated, ignoring case, ≤ 50): a line filter, any of the
    codes; applies to `GET /collection/export` too.
S12. `GET /collection` stays within 10 SQL statements whatever the size (9 → 10: one batched
    query for the locations), with or without the filter.

## API / data contract

See `docs/api.md` → "Locations (F16-b)" and "GET /collection". New error codes
`location_over_quantity` (409) and `location_locked` (409). No migration.

## UI

none

## Acceptance criteria

- [x] AC1 `tests/test_api_locations.py` (S1-S6)
- [x] AC2 `tests/test_api_line_locations.py` (S7-S9)
- [x] AC3 `tests/test_api_collection_locations.py` (S10-S12), `tests/test_api_collection_read.py`
      line contract updated (additive)
- [x] AC4 `tests/test_authz_matrix.py` classifies the 9 new rules (U); `tests/test_error_catalogs.py`
      covers the 2 new codes
- [ ] AC5 Full backend lane green: `venv/bin/pytest`
- [ ] AC6 `docs/knowledge/state.md` and `AGENTS.md` updated (endpoints, error codes)

## Delivery

- Conventional Commits; commit messages end with the attribution lines the session supplies.
- Own PR, stacked on PR #87. PR title: `feat(locations): storage locations JSON API (F16 unit b)`.
- Never merge. The user merges.

## After merge

- Deploy to dev with `docs/knowledge/ops-runbook.md` (no migration).
- Live checks: `GET /riftbound/api/v1/locations` → 200 `{items: [], meta: {unassigned_copies}}`
  for a user without locations; `GET /riftbound/api/v1/collection` lines carry `locations`.
- Manual checks for the user: none (no UI).

## Open questions

none
