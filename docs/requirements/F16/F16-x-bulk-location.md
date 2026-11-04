# F16-x: Bulk location of the selected collection lines

| Field | Value |
|---|---|
| Phase / unit | F16 / x (F16-e stays reserved for "mount a deck") |
| Branch | `feat/bulk-location` (from `main` `90a8df7`) |
| Depends on | F16-a (#87), F16-b (#88), F16-c/d (#89), merged and deployed |
| Size forecast | ~700 authored lines (about 55 % tests) |
| Risk | `Risk: item 3 (POST /collection/bulk gains an optional key; the 409 location_locked gains params)` |
| TDD | ON (strict). Runners: `venv/bin/pytest` (backend), `cd frontend && npx vitest run` (frontend) |
| Save as | `docs/requirements/F16/F16-x-bulk-location.md` |

## Objective

In the collection's multi-select the user can also change the location of the selected lines.
Owner request (2026-11-04), verbatim: "En collection en seleccion multiple debería poder cambiarse
la localización, si se seleccionan varios de diferente localizaciones, salvo que se deplieguen las
localizaciones y se selecione una, deben mantener las que tengan. Por ejemplo si cambio el lenguaje
de 5 cartas y tienen diferentes localizaciones, las localizaciones no cambian solo el campo que se
indicó."

## Read first

- `AGENTS.md`, `docs/knowledge/conventions.md`
- `docs/requirements/F16/README.md` (R3, R4), `F16-b-locations-api.md`, `F16-cd-locations-ui.md`
- `docs/api.md` → "Collection writes (F3-c)" (bulk) and "Locations (F16-b)"
- `app/services/collection_write.py` (`bulk_set`), `app/services/locations.py`
  (`set_line_locations`), `frontend/src/collection/BulkBar.tsx`

## Scope

In:
- `POST /collection/bulk` `set.location_id` (optional, positive integer or `null`)
- The "Location" field of the desktop bulk bar (the only multi-select; the phone has none)

Out (do not do, even if tempting):
- A multi-select on the phone; moving only some copies of each line in bulk
- Grouping the collection by location, a location page with its total value (F16-R5 follow-ups)
- Deck mounting (F16-e); no migration

## Specs

S1. `set.location_id` absent: every selected line keeps its locations, whatever the other fields
  change (this was already true: `bulk_set` edits the lines in place and never touches
  `rbcollection_locations`; pinned by a test).
  - Example: five lines in different locations, `set: {language: "German"}` → the five lines are in
    German and every `rbcollection_locations` row is unchanged.
S2. `set.location_id: N` (a location of the user): all the copies of each selected line end up in
  N (its assignment is replaced by `{N: quantity}`, unassigned copies included). Line quantities
  never change. `{updated: n}` as today.
S3. `set.location_id: null`: all the copies of each selected line become unassigned.
S4. `location_id` counts as a non-empty `set` (`null` is an explicit value, read through
  `model_fields_set`) and combines with the other `set` fields in one transaction.
S5. A location that is not the user's (or does not exist) → the 404 envelope; a line that is not the
  user's → 404 (as today). Nothing changes.
S6. A locked location whose quantity would change on any selected line (a locked target N, or copies
  of a selected line in a locked location) → 409 `location_locked`, `params: {codes: "<code>, ..."}`
  (the locked locations in the user's order, joined with ", "), `message: "Locked locations cannot
  change: <codes>. Unlock them first."`. Nothing changes, the other `set` fields included.
S7. A bad `location_id` (0, negative, text, decimal, boolean) → 400 `validation_error`.
S8. UI: the bulk bar gets a "Location" select: first and default option "Keep current locations"
  (sends no key), then the user's locations in their order (locked ones disabled), then
  "Unassigned" (`location_id: null`).
S9. UI: when the selected lines that are loaded hold copies in more than one place (a location or
  unassigned), the helper "Mixed: lines keep their locations unless you pick one" is shown under
  the select and describes it (`aria-describedby`).
S10. UI: a change without a chosen location sends no `location_id` key.
S11. UI: the apply confirmation adds "All their copies go to <code>." or "All their copies become
  unassigned." to "Apply the changes to N lines?".
S12. UI: after a bulk change `['collection']` and `['locations']` are refreshed; a 409
  `location_locked` shows "Locked locations can't change: <codes>. Unlock them first." in the bar
  (`role="alert"`) instead of a toast.

## API / data contract

`POST /collection/bulk` `{ids, set: {..., location_id?: int >= 1 | null}}` → `{updated: n}`;
errors as S5-S7. No migration, no new error code (`location_locked` gains `params.codes` on this
endpoint only).

## UI

Desktop collection (≥ 1240 px) bulk bar; strings in `collection.json` → `bulk.location`,
`bulk.keepLocations`, `bulk.unassigned`, `bulk.mixedLocations`, `bulk.locationLocked`,
`bulk.confirm.location`, `bulk.confirm.unassigned`.

## Acceptance criteria

- [x] AC1 S1-S7: `tests/test_api_collection_bulk_locations.py`
- [x] AC2 S8-S12 at 1280 and 1700 px, axe: `frontend/src/collection/CollectionBulkLocation.test.tsx`
- [x] AC3 Full lanes green: `venv/bin/pytest`; `cd frontend && npm run lint && npm run typecheck && npx vitest run && npm run build && npm run check:dist`
- [x] AC4 `docs/knowledge/state.md`, `docs/api.md`, `docs/frontend.md`, `AGENTS.md` updated

## Delivery

- Conventional Commits. Push and PR only when the owner says so. PR title:
  `feat(collection): bulk location of the selected lines (F16 unit x)`. Never merge.

## After merge

- Frontend rebuild + restart only (no migration).
- Owner computer: select lines in different locations, change only the language → their locations
  stay; select them again, pick a location → every copy is there; pick "Unassigned" → none placed.

## Log

- L1 (agent): S6 follows the existing replacement rule of `set_line_locations` (a locked location
  whose quantity *would change*). A locked target N already holding every copy of every selected
  line changes nothing and is accepted; any line that would put copies into a locked N is refused.
- L2 (agent): the "mixed" helper reads the `locations` of the selected lines loaded on the current
  page (first 5 per line plus `locations_more`, `unassigned`); lines selected through "Select all N
  filtered lines" that are on other pages are not read.
- L3 (agent): the bulk bar has no dialog of its own (the confirmation closes on Apply), so the
  `location_locked` message is shown inside the bar, next to Apply, as an alert.

## Open questions

none
