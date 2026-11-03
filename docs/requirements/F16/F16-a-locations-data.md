# F16-a: Storage locations, data layer

| Field | Value |
|---|---|
| Phase / unit | F16 / a |
| Branch | `feat/f16a-locations-data` (from up-to-date `main`) |
| Depends on | F3 (collection writes, merged) |
| Size forecast | ~1,150 authored lines (about 60 % tests) |
| Risk | `Risk: item 1 (migration 0024: two new tables; the collection writes now also change location quantities)` |
| TDD | ON (strict). Runner: `venv/bin/pytest` (backend only) |
| Save as | `docs/requirements/F16/F16-a-locations-data.md` |

## Objective

The data layer knows where each copy of a collection line is kept: a user has storage locations
(code, description, their own order, a lock), a line can be spread over several of them, and the
copies in no location are "unassigned". One service takes copies in the user's order, skipping
locked locations, for the deck mount of F16-e and for every quantity drop of the collection. No
API and no UI yet (F16-b, F16-c).

## Read first

- `AGENTS.md` (Database Changes, Testing), `docs/knowledge/conventions.md`, `docs/migrations.md`
- `docs/requirements/F16/README.md` (R1, R1a, R2, R3, R4, R6, R7, model, D1-D6)
- `app/models/collection.py` (owner reference `rbcol_user` → `rbusers.username`, D-F3-6)
- `app/services/collection_write.py`, `app/services/collection_rules.py`
- `tests/migration_helpers.py`, `tests/test_card_changes_obsolete_migration.py` (pattern)

## Scope

In:
- Migration `0024_locations`, models `RbLocation` and `RbCollectionLocation`
- `app/services/locations.py`: CRUD, order, lock, suggested code, copies per location,
  take in order, release on a quantity drop
- `app/services/collection_write.py`: edit, delete, split and bulk delete keep the invariant

Out (do not do, even if tempting):
- Endpoints, error codes, `GET /collection` changes (F16-b); screens (F16-c, F16-d)
- Mounting decks, `DECK-001` codes, the `rbloc_deck_id` foreign key (F16-e; decks v2 is F5)
- The legacy Jinja collection routes and the CSV import (they do not touch locations; F11)

## Specs

S1. Table `riftbound.rblocations` (migration `0024_locations`, model `RbLocation` in
    `app/models/location.py`): `rbloc_id` BIGINT PK `rblocations_pkey` (INTEGER on SQLite);
    `rbloc_user` VARCHAR(64) NOT NULL FK `rblocations_user_fk` → `rbusers.username` ON UPDATE
    CASCADE ON DELETE CASCADE; `rbloc_code` VARCHAR(32) NOT NULL with CHECK `rblocations_code_chk`
    (1-32 letters, digits or `-`: `rbloc_code ~ '^[A-Za-z0-9-]{1,32}$'` on PostgreSQL,
    `NOT GLOB '*[^A-Za-z0-9-]*' AND length BETWEEN 1 AND 32` on SQLite); `rbloc_description`
    VARCHAR(200) NULL; `rbloc_position` INTEGER NOT NULL, CHECK `rblocations_position_chk`
    (`>= 1`), UNIQUE `rblocations_user_position_uq` (`rbloc_user`, `rbloc_position`);
    `rbloc_locked` BOOLEAN NOT NULL DEFAULT false; `rbloc_deck_id` BIGINT NULL, UNIQUE
    `rblocations_deck_uq`, no foreign key yet (F16-e); `rbloc_updated_at` TIMESTAMP NOT NULL.
    The code is unique per user ignoring case: unique expression index
    `rblocations_user_code_uq` on (`rbloc_user`, `lower(rbloc_code)`), the same DDL on
    PostgreSQL and SQLite 3.9+.
S2. Table `riftbound.rbcollection_locations` (model `RbCollectionLocation`): `rbcll_line_id` FK
    `rbcollection_locations_line_fk` → `rbcollection.rbcol_id` ON DELETE CASCADE;
    `rbcll_location_id` FK `rbcollection_locations_location_fk` → `rblocations.rbloc_id` ON
    DELETE CASCADE; `rbcll_qty` INTEGER NOT NULL, CHECK `rbcollection_locations_qty_chk`
    (`>= 1`); PK `rbcollection_locations_pkey` (`rbcll_line_id`, `rbcll_location_id`); index
    `ix_rbcollection_locations_location`. The downgrade drops both tables (data loss stated in
    the revision docstring).
S3. `create_location(user, code, description=None)` puts the location last (next position).
    A code outside S1 → `InvalidCode`; a description over 200 → `InvalidDescription`; `''` is
    stored as NULL; a code the user already has, ignoring case → `DuplicateCode` (another
    user may have it). `update_location(user, id, *, code=…, description=…)` changes only what
    is sent, the same checks; a locked location can be renamed. Ids of other users or unknown
    → `LocationNotFound`.
S4. `delete_location(user, id)` deletes the location, its copies become unassigned (the line
    totals do not change) and the order closes up (1..n); it returns the number of copies
    freed. A locked location with `rbloc_deck_id` → `LocationLocked`, nothing changes; a locked
    ordinary location can be deleted.
S5. `reorder_locations(user, ids)` takes every location id of the user, each once, and sets
    positions 1..n in that order; a missing, repeated, foreign or unknown id → `InvalidOrder`,
    nothing changes. `list_locations(user)` follows the order.
S6. `set_locked(user, id, locked)` locks or unlocks.
S7. `suggest_next_code(user, last_code, bump)` (R1a, D6): `bump` is `block`, `row` or `pack`
    (anything else → `ValueError`). The chosen part of `B<n>-F<n>-P<n>` goes up by one and the
    parts to its right restart at 1, keeping widths and the letters' case:
    `B001-F001-P0001` + `pack` → `B001-F001-P0002`, + `row` → `B001-F002-P0001`, + `block` →
    `B002-F001-P0001`; `B999-F001-P0001` + `block` → `B1000-F001-P0001`. A code the user
    already has (ignoring case) is skipped by bumping the same part again. `last_code=None`
    uses the user's newest location with the pattern, or returns `B001-F001-P0001`. A code
    without the pattern (`DECK-001`, `Binder`) → `None`; a result over 32 characters → `None`.
S8. Copies per location: `assign_copies(user, line_id, location_id, qty)` (from unassigned;
    more than the unassigned copies → `LocationOverQuantity(available)`), `move_copies(user,
    line_id, from_id, to_id, qty)` (`None` = unassigned on either side; more than the source
    holds → `NotEnoughCopies(available)`), `remove_copies(...)` (back to unassigned). A locked
    location on either side → `LocationLocked`; qty < 1 → `ValueError`; foreign lines →
    `LineNotFound`, foreign locations → `LocationNotFound`. Invariant: for every line,
    Σ `rbcll_qty` ≤ `rbcol_quantity`. `unassigned(line)` = quantity − Σ location quantities.
    `line_locations(user, line_id)` → `{locations: [{location_id, code, description, locked,
    qty}] in the user's order, unassigned}`.
S9. `take_copies(user, wants, into_location_id)` (R6, D1, D2): each `Want(qty, line_ids=… |
    set_id+card_id=… | name=…)` (exactly one selector; a printing covers every foil; a name
    covers every printing via `name_key`) is taken in order: the user's unlocked locations by
    position (lines by id inside a location), then unassigned copies by line id; copies already
    in the target are not counted. Wants sharing lines never count a copy twice. On success the
    copies move into the target location (which may be locked) and the `Move(line_id,
    from_location_id, to_location_id, qty)` list is returned; line totals never change. When
    any want is short → `Shortfall(missing, locked)`, nothing changes: `missing` = `[{index,
    line_ids, set_id, card_id, name, qty, available}]`, `locked` = `[{location_id, code, qty}]`
    of the locked locations holding copies of the short wants, in the user's order.
S10. Collection writes (R7, D4): a quantity drop (`edit_line` with a lower `qty`), `delete_line`,
    `split_line` and `bulk_delete` take the lost copies with `locations.release` in the same
    order as S9 (unlocked locations by position, then unassigned). When the copies outside
    locked locations are not enough → `LockedCopies(available, locked)`, a subclass of
    `InsufficientQuantity`, so the existing API answers 409 `insufficient_quantity` with
    `params.available` = the copies that could be removed; nothing changes (bulk: all or
    nothing). A split carries the location quantities it takes to the target line (the copies
    stay where they are). Adding copies and raising a quantity leave the locations alone.

## API / data contract

Migration `0024_locations` (S1, S2), reversible; no endpoint, no error code (F16-b adds
`already_exists`, `location_over_quantity`, `insufficient_unlocked`).

## UI

none

## Acceptance criteria

- [x] AC1 Round trip and drift: `tests/test_locations_migration.py` (S1, S2)
- [x] AC2 Service: `tests/test_locations_service.py` (S3-S9)
- [x] AC3 Collection writes: `tests/test_locations_collection_writes.py`, existing collection
      suites green (S10)
- [x] AC4 Full backend lane green: `venv/bin/pytest`
- [ ] AC5 `docs/knowledge/state.md` and `AGENTS.md` updated (structure: new model, service, table
      names)

## Delivery

- Conventional Commits; commit messages end with the attribution lines the session supplies.
- Own PR (migration). PR title: `feat(locations): storage locations data layer (F16 unit a)`.
- Never merge. The user merges.

## After merge

- Deploy to dev with `docs/knowledge/ops-runbook.md`, backup first (migration `0024`).
- Live checks: `flask db current` → `0024_locations`; `flask db check` → no drift.
- Manual checks for the user: none (no UI).

## Open questions

none
