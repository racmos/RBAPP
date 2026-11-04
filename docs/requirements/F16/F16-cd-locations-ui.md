# F16-c/d: Storage locations, screens (mobile, desktop and wide) and collection integration

| Field | Value |
|---|---|
| Phase / unit | F16 / c and d (one PR, one document) |
| Branch | `feat/f16cd-locations-ui` (from `main` `14cb551`) |
| Depends on | F16-a (#87) and F16-b (#88), merged and deployed 2026-11-03 |
| Size forecast | ~2,600 authored lines (about 45 % tests) |
| Risk | `Risk: item 3 (the CollectionLine type gains optional location keys; the collection screens read them)` |
| TDD | ON (strict). Runner: `cd frontend && npx vitest run` (frontend only) |
| Save as | `docs/requirements/F16/F16-cd-locations-ui.md` |

## Objective

The user manages their storage locations from the app (create with a suggested code, rename,
describe, lock, order, delete) on a phone and on a computer, sees where the copies of each
collection line are, moves them between locations, filters the collection by location and gives
the cards they add a location that stays for the session. No backend change.

## Read first

- `AGENTS.md` (Frontend section, ESLint folder boundaries, only `api/client.ts` calls `fetch`)
- `docs/requirements/F16/README.md` (R1-R5, R4a, D1-D6, Log L1-L3),
  `docs/requirements/F16/F16-b-locations-api.md`, `docs/api.md` → "Locations (F16-b)"
- `docs/frontend.md`; models: `frontend/src/products/`, `frontend/src/collection/`

## Scope

In:
- `frontend/src/locations/` (screen, sheets, panel, queries, labels), route `/locations`, nav entry
  `locations`, `locations` i18n namespace
- API functions and types for the 9 F16-b endpoints
- Collection: line sheet block, item and table summary, location filter, quick-add location

Out (do not do, even if tempting):
- Any backend change; an endpoint that lists the cards of one location
- Bulk location changes from the selection bar (F16-R4 "in bulk"), grouping the collection by location
  and a location page with its total value (F16-R5): follow-ups
- Deck mounting (F16-e)

## Specs

S1. Nav entry `locations` (`spa`, `/locations`, icon `pin`, placements top, hub, more) right after
    `products`; route `/locations` lazy inside the shell, `requireAuth`; document title
    "Locations · Rift Manager".
S2. Below 1240 px: the locations in the user's order (code bold, description or "No description",
    "N copies · M cards", "Locked" badge, "Deck" badge when `deck_id`), then a fixed row
    "Unassigned: N copies" / "Always last: it cannot be moved.".
S3. Order: "Move <code> up" / "Move <code> down" (ends disabled) send `PUT /locations/order` with every
    id; the list changes at once and goes back, with the translated error, when saving fails. From
    1240 px a row can also be dragged onto another (pointer devices); keyboard users keep the buttons.
S4. "New location" sheet: the code starts as `GET /locations/next-code?bump=pack`; "Next block", "Next
    row", "Next pack" call `next-code?bump=…&after=<current code>`; `code: null` shows "This code has no
    block-row-pack pattern to continue."; the user can type any code. Checked before sending: empty →
    "Enter a code.", not 1-32 letters, digits or `-` → "Use 1 to 32 letters, digits or hyphens.";
    `already_exists` → "You already have a location with this code." on the field; success → toast
    "Location created." and the sheet closes.
S5. Location sheet ("Location <code>"): code and description saved with "Save" (only the changed keys),
    toast "Location saved."; switch "Lock this location" (`PATCH {locked}`); "View cards" →
    `/collection?location=<CODE>`; "Delete location" → confirmation "Delete <code>?" / "Its N copies go
    back to unassigned." → `DELETE`, toast "Location deleted."; a 409 (`location_locked` on a deck
    location) is shown in the sheet with its translated text. A locked location can be renamed.
S6. From 1240 px: table (caption "Your locations in order"; Position, Code, Description, Copies, Cards,
    Lock, Actions) in `TableScroll fit`, description edited inline ("Description of <code>"), switch
    "Lock <code>" per row, icon buttons "Move <code> up/down", "Edit <code>", "Delete <code>". From
    1600 px a collapsible `SidePanel` `locations-detail` ("Location details") shows the selected row
    (first by default): code, description, badges, position, copies, cards, "View cards".
S7. States: skeleton, empty ("No locations yet" + "New location"), error with "Retry", offline (cached
    list, every write disabled, `common:offline.editDisabled`), axe clean at 390, 1280 and 1700 px.
S8. Line sheet, every line: "Where they are" with the first 5 locations as `CODE — description × qty`,
    "and N more" (loads `GET /collection/<id>/locations`, then lists all, locked ones with "· Locked"),
    "Unassigned: n" and "Change locations" (disabled offline): From (unassigned or the line's
    locations, locked disabled), To (unassigned or any location, locked disabled), "Copies to move"
    (max = what the source holds), "Move copies" → `POST /collection/<id>/locations/move`, toast
    "Copies moved."; errors (`location_over_quantity`, `location_locked`, `insufficient_quantity`) in
    place.
S9. Collection item: one clamped line with the first code and `+N` other locations (screen readers
    hear "Location: …"); empty but present when the copies are in no location. Table: last column
    "Where" (button "Where: <summary>" that opens the line sheet; ≤ 96 px, one clamped line) that keeps
    the 1440 px fit.
S10. Collection filter "Location": chips of the user's codes (and codes of the URL they do not have),
    repeated `location` params in the URL and in `GET /collection` (and the filtered export); chips in
    the active list read "Location: <code>".
S11. Quick add: "Location" select (None + the locations in order, locked disabled), kept in
    `rb_quick_add_v1` as `location_id` (an id that no longer exists is ignored); after each add the
    added copies go from unassigned into the location ("Added to your collection in <code>." / "Added to
    a line you already had, in <code>."); when that fails the card stays added: "The card was added but
    stays unassigned: <reason>".

## API / data contract

No change. Uses `docs/api.md` → "Locations (F16-b)" and the `GET /collection` additions. Frontend type
`StorageLocation` (named so it does not shadow the DOM `Location`); `CollectionLine` gains optional
`locations`, `locations_more`, `unassigned` (present on `GET /collection` lines only).

## UI

See Specs and `docs/frontend.md` → "Locations (F16-c/d)". Strings: `locations` namespace and
`collection:where.*`, `collection:add.location*`, `collection:filters.location`,
`collection:table.columns.where`, `nav:items.locations`.

## Acceptance criteria

- [x] AC1 `src/locations/LocationsPage.test.tsx` (390 px: S1-S5, S7)
- [x] AC2 `src/locations/LocationsDesktop.test.tsx` (1280 and 1700 px: S3, S6, S7; the drag is driven
      by its DOM events in jsdom, which has no layout or pointer)
- [x] AC3 `src/collection/LineSheet.locations.test.tsx` (S8)
- [x] AC4 `src/collection/CollectionLocations.test.tsx`, `CollectionItem.test.tsx`,
      `CollectionTable.test.tsx`, `params.test.ts` (S9, S10)
- [x] AC5 `src/collection/AddSheet.locations.test.tsx` (S11)
- [x] AC6 `src/shell/navRegistry.test.tsx`, `src/test/eslint-boundaries.test.ts` (S1, folder rules)
- [x] AC7 Frontend lanes green: `npm run lint && npm run typecheck && npx vitest run && npm run build &&
      npm run check:dist`
- [x] AC8 `docs/knowledge/state.md`, `docs/frontend.md`, `AGENTS.md` updated

## Delivery

- Conventional Commits; one PR for c and d. PR title:
  `feat(locations): storage locations screens and collection integration (F16 units c and d)`.
- Never merge. The user merges.

## After merge

- Deploy to dev with `docs/knowledge/ops-runbook.md` (frontend build only, no migration).
- Live checks: `/riftbound/app/locations` loads; the nav shows "Locations".
- Manual checks for the user: on the phone create two locations with the suggested codes, move one up,
  lock one; in the collection open a card, "Change locations", move a copy; filter by a location; add a
  card with a location and add another (the location stays). On a computer drag a row in
  `/locations`, open the wide panel at ≥ 1600 px.

## Open questions

none

## Log

- L1 (agent): the quick add places the added copies with `POST /collection/<id>/locations/move`
  `{from_location_id: null, to_location_id, qty}` instead of reading the line's assignment and sending
  `PUT` with the quantity added: one atomic call, the line's other locations stay by construction and
  nothing can race between the read and the write. The result is the same assignment.
- L2 (agent): "Where they are" is a `role="group"`, not a region: the sheet has one per line and
  landmarks must be unique (axe `landmark-unique`).
- L3 (agent): the table "Where" button is named "Where: <summary>" without the card name (the row
  gives the context), so the existing tests that look for the card's buttons by name keep one match.
- L4 (agent): the `locations` namespace is new (`src/i18n/resources.ts`, approved by the owner);
  collection-side strings stay in `collection.json`.
- L5 (agent): from 1240 to 1599 px a row click does nothing but the row actions; the panel and the
  selection exist from 1600 px, as in products.
