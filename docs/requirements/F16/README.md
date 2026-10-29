# F16: Storage locations and mounted decks — phase spec (DRAFT)

Status: **draft written by the implementing agent from the owner's request (2026-10-29); the owner answered the 6 decisions the same day; the planner reviews it before any unit is cut** · Depends on: F3 (collection), F5-c/F5-d (decks v2 tables and API) for the deck part · Source: owner message of 2026-10-29 (quoted in the Log) · Phase IDs are identifiers, not order.

## Goal

The owner knows where each copy of a card physically is: in a binder, a box, a deck pool, or a deck that is
built. A **location** has a unique alphanumeric code and a description. A collection line can be spread over
several locations. Locations have an order the user sets, and cards are taken from them in that order when a
deck is built; locations can be locked so they are skipped. A built deck gets its own locked location.

## Current state

| Area | What exists today |
|---|---|
| Collection | `rbcollection`: one line per user, printing, foil, condition and language, with `rbcol_quantity` (1..9999). No place information. |
| Decks | Legacy `rbdecks` (Jinja, snapshot JSON). Decks v2 (tables, API, "deck vs collection") are F5 and not built yet. |

## Model (proposal)

- `rblocations`: `id`, owner (same reference as `rbcollection`), `code` (1–32 chars, letters, digits and `-`;
  **unique per user, case-insensitive**), `description` (≤ 200), `position` (1..n, unique per user),
  `locked` (bool), `deck_id` (NULL, or the mounted deck; at most one location per deck), `updated_at`.
- `rbcollection_locations`: `line_id` → `rbcollection` (ON DELETE CASCADE), `location_id` → `rblocations`,
  `qty ≥ 1`; PK (`line_id`, `location_id`).
- Invariant: for every line, the sum of its location quantities is **≤ `rbcol_quantity`**. The rest is
  "sin ubicar" (unassigned), derived, never stored. `rbcol_quantity` stays the total of the line wherever the
  copies are; it only drops when copies are sold or removed.

## Requirements

- **F16-R1a** Suggested code for a new collection location: `B001-F001-P0001` (B = bloque, F = fila,
  P = paquete). The next code is the previous one with the **rightmost changed part incremented**; the user
  chooses which part starts a new one reading left to right (a new block resets F and P to 001/0001, a new
  row resets P). The code stays free text under the R1 rules; the suggestion never overrides what the user
  types. (D6)
- **F16-R1** CRUD of locations (code, description). A code cannot be repeated (409 `already_exists`); it
  can be renamed at any time (it is only a label). Deleting a location is allowed when it
  is empty or the user confirms; its copies go back to "sin ubicar". A deck location cannot be deleted
  while locked.
- **F16-R2** Order: the user orders their locations on the Locations screen (move up/down and drag on
  pointer devices; the order is saved all at once, `PUT /locations/order`). New locations go last.
- **F16-R3** Lock/unlock any location. A locked location is skipped by every automatic take (R6, R7) and its
  quantities are read-only for the user until unlocked.
- **F16-R4** A line can have several locations with a quantity each (assign, move, remove copies between
  locations, from the line sheet and in bulk by selecting lines). Over-assigning is rejected (409
  `location_over_quantity`).
- **F16-R5** The collection line shows the **total** of copies (as today) and a short location summary.
  Tapping the line shows, among its other data, its first 5 locations as `code — description × qty` (in
  the user's location order) plus "and N more" opening the full list, and the unassigned remainder.
  The collection can be filtered and grouped by location code; a location page lists its cards and total
  value.
- **F16-R6** **Mounting a deck** (button "Marcar como montado" in the deck, with a confirmation that lists
  what will be taken): for every card of the deck, take the copies from the user's unlocked locations in
  order of `position`, then from "sin ubicar" last; if there are not enough copies the whole operation is
  refused with the list of missing cards (409 `insufficient_unlocked`, nothing changes). On success a
  location is created for the deck (`code` generated, unique, e.g. `DECK-001`; `description` = deck title;
  `deck_id` set; `locked`) and the taken copies move into it. The total of every line does not change.
- **F16-R7** Selling or removing copies (quantity decrease, delete, sale in F7) takes them in the same order
  and skips locked locations; if the copies available outside locked locations are not enough, the change is
  refused (409) and the message says which location holds the rest.
- **F16-R8** **Unlocking** the deck location (from the deck or from Locations) ends the "mounted" state of
  the deck. The copies stay in that location, which becomes an ordinary one (same code, same position) and is
  taken in order like any other, **until the deck is deleted or the user presses "devolver cartas"**; both
  move the copies to "sin ubicar" and the deck location disappears. Building the deck again repeats R6. A
  deck can exist without being mounted. (D3)
- **F16-R9** Offline: the screens read from cache; every change needs a connection (cross-phase contract).

## Out of scope

Barcode/QR labels; moving cards between users; location per product (F14); CSV import/export of
locations (a `location` column can be added later); hand simulator.

## Decisions (owner, 2026-10-29)

1. Copies with no location rank last, are never lockable and show as "Sin ubicar". **Accepted.**
2. A deck card without a printing takes the copies by location order, whatever the printing. **Accepted.**
3. Unlocking keeps the copies in the ex-deck location until the deck is deleted or the user presses
   "devolver cartas" (then "sin ubicar"). **Accepted, with that addition.**
4. Sales and removals follow the same order and skip locked locations. **Accepted.**
5. The order is one per user: each user orders their own locations. Locations belong to a user; the same
   user can keep the same card in several locations. **Accepted.**
6. Deck locations: generated code `DECK-001`… **Accepted.** Collection locations: suggested code
   `B001-F001-P0001` (bloque, fila, paquete), consecutive, with the user choosing from left to right which
   part is new (R1a).

## Units (proposal)

| Unit | Content | Depends on |
|---|---|---|
| F16-a | Data: migrations for both tables, models, order/uniqueness rules, service for take-in-order and invariants | F3 |
| F16-b | Locations API (CRUD, order, lock) + line assignment endpoints + `locations` in `GET /collection` lines | F16-a |
| F16-c | Locations screen (mobile) + line sheet block + filter by code | F16-b |
| F16-d | Desktop/wide locations and collection integration | F16-c |
| F16-e | Mount / unmount deck (API + deck UI), "deck vs collection" shows mounted copies | F16-b, F5-d |

## Log

- L1 (owner, 2026-10-29): "me interesa saber la ubicacion donde las tengo guardadas, puede ser una
  referencia o nombre de archivado, pero tambien puede ser en pool para decks o incluso puede estar en uso
  en un deck [...] cuantas hay en cada localización". Locations are "un código alfanumérico que no se pueda
  repetir y un campo con una descripción"; decks mounted with a confirmation "se deben descontar esas cartas
  de la colección" in the user's order of locations; a location can be locked and is skipped; a mounted
  deck gets its own reference, described by the deck title, locked until the user unlocks it "en el deck o en
  ubicaciones"; a line can have several locations, the line shows the total of copies "mientras no se hayan
  vendido", and tapping shows "las primeras 5 ubicaciones código y descripción".
- L2 (agent): "descontar de la colección" is read as "take them out of the free locations into the deck's
  locked location": the line total stays the same until a sale. If the owner meant the total to drop, the
  deck would not count as owned; say so and R6 changes.
- L3 (owner, 2026-10-29): answers to the six decisions: 1, 2, 4 accepted; 3 accepted "hasta que el deck se
  borre o se pulse para devolver cartas a copias sin ubicación"; 5 each user orders their own locations;
  6 `DECK-…` for decks and `B001-F001-P0001` (B bloque, F fila, P paquete) for the collection, consecutive,
  "manda de izquierda a derecha para indicar uno nuevo". "Descontar" read correctly (L2).
