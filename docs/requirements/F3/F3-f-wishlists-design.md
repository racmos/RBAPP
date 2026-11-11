# F3-f: Wishlists (design, owner decisions 2026-11-11)

| Field | Value |
|---|---|
| Phase / unit | F3 / f, plus slices in F3-j, F4-g and F5-f |
| Status | **Approved by the owner 2026-11-11 (A1-A6 answered).** F3-f-1 done (#130, deployed 2026-11-11); F3-f-2 (lists + lines API) implemented. F3-j (UI) implemented. Next: F4-g alerts. |
| Replaces | F3-R5 / F3-R11 / F3-R20 of the F3 phase spec (one flat `rbwishlist` table per user) |
| Risk | Migration (own PR, `pg_dump` before deploy); alert job reads prices daily |

## Decisions (owner, binding)

1. **Several lists per user.** At most **20 lists** per user and **100 cards per list**. One list is the
   **default**: "Add to wishlist" saves there unless the user picks another.
2. **Price alert.** A line may carry a **max price**. After each daily Cardmarket price update, every card whose
   market price is **at or below** its max price raises **one alert for that day**. A line **without a price
   never alerts**.
3. **Alerts screen** (inside the wishlist area). Each alert shows the card and the price reached. Expanding it
   lists the wishlists that hold the card; clicking a list opens that wishlist.
4. **Owned vs wanted.** A line shows the **quantity wanted**, an indicator with the copies the user already
   owns of **this version** (printing), and indicators with the copies owned of **other versions**: alternate
   arts, and, for common and uncommon cards, the foil copies.
5. **From a deck.** The deck editor has "Add missing cards to a wishlist": the user picks the list and only the
   **missing count** of each card is added to it.

## Assumptions (A1-A6, answered by the owner 2026-11-11)

- **A1.** 100 cards per list = 100 **lines** (distinct targets), not 100 copies. A line's quantity is free
  (1..99). *Confirmed.*
- **A2.** The same card may be in several lists. Within one list a target is the card **printing (set + number)
  plus foil** and adding it again **sums the quantities** (capped at 99). A foil copy, or an alternate-art
  printing of the same card, is a **different line**, never merged. *Confirmed.*
- **A3.** **Daily alerts, not a one-time crossing.** The `price_alerts` job runs once a day right after the
  Cardmarket prices are updated. Each day a card's market price is at or below the max price of any of its
  lines, **one alert is raised for that card and day** (not one per list). If the price stays at or below the
  max, the alert comes again the next day. No re-arm state is needed. *Corrected by the owner.*
- **A4.** The user marks the **default list with a star** in the wishlist menu; it stays the default until the
  user marks another. "Add to wishlist" saves there. The first list is created automatically (name
  "Wishlist") and starts as the default; renaming is allowed; the default list cannot be deleted until another
  one is starred. *Confirmed.*
- **A5.** Deleting a list deletes its lines (confirmation, Undo toast). **Alerts already raised are kept.** An
  expanded alert shows the lists that hold the card **now**; a deleted list is not listed (it has no link), so
  nothing points at a list that no longer exists. *Confirmed.*
- **A6.** A "version" is the **printing: set + number**. An indicator shows the **quantity of copies** owned of
  that printing; by-name lines (any printing) count every printing. *Confirmed.*

## Data model (migration `00NN_wishlists`, next free number, own PR)

| Table | Columns |
|---|---|
| `rbwishlists` | `rbwls_id` PK; `rbwls_user_id` FK `rbusers.id` ON DELETE CASCADE; `rbwls_name` VARCHAR(80) NOT NULL; `rbwls_is_default` BOOL NOT NULL DEFAULT false; `rbwls_position` INT; `rbwls_created_at`, `rbwls_updated_at`. UNIQUE (`user_id`, lower(`name`)); partial UNIQUE (`user_id`) WHERE `is_default` (one default per user) |
| `rbwishlistlines` | `rbwsl_id` PK; `rbwsl_list_id` FK `rbwishlists.id` ON DELETE CASCADE; `rbwsl_name_key`, `rbwsl_name`; `rbwsl_rbset_id`, `rbwsl_rbcar_id` TEXT NULL (both or neither; NULL = any printing); `rbwsl_foil` ('any','N','S') DEFAULT 'any'; `rbwsl_qty` SMALLINT 1..99; `rbwsl_max_price` NUMERIC(10,2) NULL CHECK >= 0; `rbwsl_note` VARCHAR(200); `rbwsl_created_at`, `rbwsl_updated_at`. UNIQUE (`list_id`, `name_key`, target key, `foil`), NULL-safe through a computed target column |
| `rbwishlistalerts` | `rbwal_id` PK; `rbwal_user_id` FK; `rbwal_name_key`, `rbwal_name`; `rbwal_rbset_id`, `rbwal_rbcar_id` NULL; `rbwal_price` NUMERIC(10,2) (price reached); `rbwal_max_price` (threshold at that time); `rbwal_price_date` DATE (the day of the price update); UNIQUE (`user`, target, `price_date`); `rbwal_created_at`; `rbwal_read_at` NULL. The lists that hold the card are read **live** when the alert is expanded, not stored |

The 20-list and 100-line limits are enforced in the service (409 `wishlist_limit` with `params {max, scope}`), not
by constraints. There is no arming state: the alert is a daily evaluation (A3). `rbwishlistalerts` is unique per
(`user`, `name_key`, `set`, `card`, `price_date`) so a re-run of the job the same day cannot duplicate it.

### As built (F3-f-1, migration `0026_wishlists`, models in `app/models/wishlist.py`)

Deviations from the table above (no change to any decision or assumption):

- **No computed target column.** The NULL-safe unique target is an expression unique index instead:
  `rbwishlistlines_target_uq` on (`list_id`, `name_key`, `coalesce(rbset_id, '*')`, `coalesce(rbcar_id, '*')`,
  `foil`), and `rbwishlistalerts_target_uq` on (`user_id`, `name_key`, `coalesce(rbset_id, '*')`,
  `coalesce(rbcar_id, '*')`, `price_date`). Both dialects (PostgreSQL 18, SQLite in the tests) support it, it needs
  no column the service has to keep in step, and two by-name lines (NULL printing) collide as they should.
- **Constraints the table did not spell out:** `rbwls_name` must not be blank (`length(trim(name)) >= 1`);
  `rbwls_position` is NOT NULL, ≥ 1 and unique per user (`rbwishlists_user_position_uq`, like `rblocations`; the
  service renumbers in two steps as `locations._renumber` does); `rbwal_rbset_id`/`rbwal_rbcar_id` are both or
  neither like the lines; `rbwal_price` and `rbwal_max_price` are NOT NULL and ≥ 0.
- **Sizes and types:** `name_key` and `name` VARCHAR(200); set and card ids TEXT like `rbcollection`; the max price
  and the alert prices NUMERIC(10,2); timestamps are UTC `TIMESTAMP` like the other tables.
- **Indexes:** no separate index on `rbwsl_list_id`: `rbwishlistlines_target_uq` leads with it, so it serves the
  cascade and "the lines of a list". `ix_rbwishlistlines_name_key` (alert job, "lists holding this card"),
  `ix_rbwishlistalerts_user_created` on (`user_id`, `created_at`) ascending (PostgreSQL reads it backwards for newest
  first), `ix_rbwishlistalerts_user_unread` on (`user_id`) WHERE `rbwal_read_at IS NULL`, and the one-default
  partial unique index `rbwishlists_user_default_uq` on (`user_id`) WHERE `rbwls_is_default`.

### As built (F3-f-2, lists and lines API: `app/services/wishlists.py`, `app/api/v1/wishlists.py`)

No change to any decision or assumption. Where this design was silent (full contract in `docs/api.md` → "Wishlists
(F3-f-2)"):

- **Default list.** The first `GET /wishlists` of a user without lists creates `Wishlist` (race-safe through the
  unique indexes). A user whose first list comes from `POST /wishlists` (no GET before) gets that list as the
  default instead, so no list is created that the user did not ask for. `is_default: false` on the default list is
  a 400 `validation_error` (star another list instead); deleting the default list is a 409 with the new code
  `wishlist_default`.
- **Deleting a list** returns the list and its lines (`{deleted, lines}`), so the Undo toast of F3-j can rebuild it.
- **Line order** is the order the lines were added (by id); `q` filters by name; no paging (≤ 100). The list meta
  is `{total (returned), line_count (in the list), max_lines, market_total, unpriced}`.
- **Targets.** `set_id` + `card_id` (both or neither) is a printing target and wins over `name`; otherwise `name`
  is matched by `name_key` and stored with the catalog's spelling. A by-name `foil: "S"` needs at least one
  foilable printing of the name (else `foil_not_allowed`).
- **Merge on add** sums quantities (cap 99) and a sent non-null max price or note replaces the line's; the answer
  is 200 with `merged: true` (201 for a new line). A foil change by PATCH that collides with another line is a 409
  `already_exists`, not a silent merge.
- **Move / copy** merges collisions into the target line (cap 99; the target keeps its max price and note and only
  fills empty ones); a target line already at 99 counts as `skipped`; with `move` the source line goes away in
  every case. Only lines that would be new count against the 100-line limit.
- **Price** (`market`): the line's printing for its foil wish (`any` = the cheaper finish); a by-name line takes
  the cheapest priced printing of the name, and `market` names the printing and finish that gave it.
  `reached` is null without a max price and false when there is no market price.
- **Indicators.** `this_version` = copies of the printing (by-name: every printing); `other_versions.total` =
  copies of the other printings of the name; `alt_art` = of those, the printings that are not the base printing
  (the catalog has no art flag, so alternate arts and later reprints both count); `foil` = the foil copies of
  the other printings (only common and uncommon cards have foils, so it is 0 for rarer cards). Computed in
  7 SQL statements whatever the number of lines.

### As built (F3-j, wishlists UI: `frontend/src/wishlists/`, `docs/frontend.md` → "Wishlists (F3-j)")

No change to any decision or assumption, no backend change. Where this design was silent:

- **Where it lives.** `/collection/wishlists` and `/collection/wishlists/alerts` are tabs of the
  collection ("Collection | Wishlists" on top of both areas, then "Lists | Price alerts" inside the
  wishlist area); no new top-level nav entry, and Collection stays the current nav entry on them. The open
  list is `?list=<id>` (absent or unknown = the starred list) and the search `?q=`.
- **List menu.** Phones: a list switcher (name, star, count) opens the lists in a sheet; desktop: a rail
  beside the lines. The star itself is the "Make default" action (the default's star is disabled with its
  reason); the per-list menu has Rename, Move up, Move down and Delete (disabled on the default list with
  "Star another list first"). On pointer devices the rail's lists can also be dragged.
- **Undo of a list delete** recreates the list under its name, posts its lines back in order and puts it
  back at its position (three calls; the list and lines get new ids and dates). If the name was taken in
  the meantime the Undo fails with that error.
- **Lines.** "Not reached" is shown when a max price is set and the market is above it (or unpriced); a
  line without a max price shows the muted "No alert price". "Other versions" is not shown for by-name
  lines (the API counts every printing as this version). The market price shows its value with the price
  date as a tooltip (not its source column). The finish of a line is chosen when it is added and not
  edited afterwards (the API's foil PATCH is not used by the UI yet).
- **Add.** The sheet stays open for the next card. Foil is disabled when the chosen printing has no foil
  version; with "Any printing" it is left to the server (`foil_not_allowed`), since another printing of the
  name may have one.
- **Card detail.** One tap adds one copy of that printing, any finish, to the default list (the button is
  named after it); "Choose list…" opens every list. "In wishlists: <names>" is not shown: no endpoint says
  which lists hold a card without reading every list's lines.
- **Alerts screen** is a shell (title, explanation, empty state, no request) until F4-g adds the API and
  the unread badge.

## API (U, every row scoped to the caller; another user's id is a 404)

| Method | Path | Purpose |
|---|---|---|
| GET / POST | `/wishlists` | lists with `line_count`, `is_default`; create (max 20) |
| PATCH / DELETE | `/wishlists/<id>` | rename, make default / delete (with its lines) |
| PUT | `/wishlists/order` | reorder |
| GET / POST | `/wishlists/<id>/lines` | lines with indicators / add (merge, max 100) |
| PATCH / DELETE | `/wishlists/<id>/lines/<line_id>` | qty, foil, max price, note / remove |
| POST | `/wishlists/<id>/lines/move` | move or copy lines to another list |
| GET | `/wishlist-alerts` | alerts newest first, `?unread=true`; each with the card, `price`, `max_price`, `price_date` |
| GET | `/wishlist-alerts/<id>/lists` | lists holding that card now (for the expanded row) |
| POST | `/wishlist-alerts/read` | mark read (all or ids) |
| POST | `/decks/<id>/missing-to-wishlist` | `{wishlist_id?}` (default list when absent): adds the missing count of each card (F5-f; counts per name across printings as DECK-1) |

**Line indicators** (computed on read, batched, no N+1): `wanted` (qty), `owned_this_version` (copies of that
printing, foil and non-foil), `owned_other_versions` (copies of other printings of the same name) split into
`alt_art` and, for common/uncommon, `foil`. A line with `max_price` also carries `market` and `reached` (bool).

## Alert job (F4-g, `price_alerts`, queued by `daily_prices` after a successful load)

For every line with a `max_price`, compare the card's price (same price resolution as the rest of the app) with
the max: when the price is at or below it, create **one** alert per user, card and day (the lowest max price among
the user's lines of that card decides; not one per list). Lines without a price are skipped. The job runs once per
day after a successful price load and is idempotent for the same price date. Push notifications reuse the F4 notification infrastructure
later; this unit only writes the alerts and exposes them in the wishlist area.

## UI (F3-j, mobile first like the collection)

- `/collection/wishlists`: list switcher (name, count, default marker), new / rename / delete / make default, the
  selected list's lines (qty wanted, owned-this-version badge, other-versions badges, market vs max, note) with
  inline edits, add through `CardCombobox`, move / copy to another list.
- `/collection/wishlists/alerts`: alerts with the price reached; expanding shows the lists holding the card,
  each a link to that list; unread badge on the tab.
- Card detail: "Add to wishlist" (default list, or choose).
- Deck editor (F5-f): "Add missing cards to a wishlist" with a list picker and the count of cards that will be
  added; reports lines skipped because the list is full.

## Units (build order, each its own commit, migration its own PR)

1. **F3-f-1** migration + models + round-trip/drift test.
2. **F3-f-2** services + API for lists and lines + indicators + limits (+ docs, authz matrix, error codes).
3. **F3-j** UI (lists, lines, add from card detail) and the alerts screen shell.
4. **F4-g** `price_alerts` job, alerts API, unread badge.
5. **F5-f** deck vs collection and "missing to wishlist".

## Open for the owner

Nothing open. Anything new that changes the tables should be said before F3-f-1: it costs a migration.
