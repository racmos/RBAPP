# F3-f: Wishlists (design, owner decisions 2026-11-11)

| Field | Value |
|---|---|
| Phase / unit | F3 / f, plus slices in F3-j, F4-g and F5-f |
| Status | **Design for owner review. No code until approved.** |
| Replaces | F3-R5 / F3-R11 / F3-R20 of the F3 phase spec (one flat `rbwishlist` table per user) |
| Risk | Migration (own PR, `pg_dump` before deploy); alert job reads prices daily |

## Decisions (owner, binding)

1. **Several lists per user.** At most **20 lists** per user and **100 cards per list**. One list is the
   **default**: "Add to wishlist" saves there unless the user picks another.
2. **Price alert.** A line may carry a **max price**. When the card's market price reaches it, the user is
   warned **once each time it is reached**. A line **without a price never alerts**.
3. **Alerts screen** (inside the wishlist area). Each alert shows the card and the price reached. Expanding it
   lists the wishlists that hold the card; clicking a list opens that wishlist.
4. **Owned vs wanted.** A line shows the **quantity wanted**, an indicator with the copies the user already
   owns of **this version** (printing), and indicators with the copies owned of **other versions**: alternate
   arts, and, for common and uncommon cards, the foil copies.
5. **From a deck.** The deck editor has "Add missing cards to a wishlist": the user picks the list and only the
   **missing count** of each card is added to it.

## Assumptions to confirm (owner)

- **A1.** "100 cards per list" = 100 **lines** (distinct card targets), not 100 copies. A line's quantity is free
  (1..99).
- **A2.** The same card may be in several lists. Within one list a target (name + printing + foil) is unique and
  adding it again **merges** (quantities add, capped at 99).
- **A3.** "Each time it is reached" = **crossing**: the alert fires when the market price is at or below the
  max price and it was above it (or unknown) on the previous check; it fires again only after the price has
  gone back above the max. One alert per card per crossing, not one per list.
- **A4.** The default list is created for each user on first use (name "Wishlist"); it can be renamed and a
  different list can be made the default; the default list can be deleted only after another one is chosen.
- **A5.** Deleting a list deletes its lines (confirmation in the UI, Undo toast). Alerts already raised stay in
  the log; the list names they showed become "(deleted list)".
- **A6.** "Version" = printing (set + card id). A line may target a card **by name** (any printing) or a **specific
  printing**; the "this version" indicator of a by-name line counts every printing.

## Data model (migration `00NN_wishlists`, next free number, own PR)

| Table | Columns |
|---|---|
| `rbwishlists` | `rbwls_id` PK; `rbwls_user_id` FK `rbusers.id` ON DELETE CASCADE; `rbwls_name` VARCHAR(80) NOT NULL; `rbwls_is_default` BOOL NOT NULL DEFAULT false; `rbwls_position` INT; `rbwls_created_at`, `rbwls_updated_at`. UNIQUE (`user_id`, lower(`name`)); partial UNIQUE (`user_id`) WHERE `is_default` (one default per user) |
| `rbwishlistlines` | `rbwsl_id` PK; `rbwsl_list_id` FK `rbwishlists.id` ON DELETE CASCADE; `rbwsl_name_key`, `rbwsl_name`; `rbwsl_rbset_id`, `rbwsl_rbcar_id` TEXT NULL (both or neither; NULL = any printing); `rbwsl_foil` ('any','N','S') DEFAULT 'any'; `rbwsl_qty` SMALLINT 1..99; `rbwsl_max_price` NUMERIC(10,2) NULL CHECK >= 0; `rbwsl_note` VARCHAR(200); `rbwsl_created_at`, `rbwsl_updated_at`. UNIQUE (`list_id`, `name_key`, target key, `foil`), NULL-safe through a computed target column |
| `rbwishlistalerts` | `rbwal_id` PK; `rbwal_user_id` FK; `rbwal_name_key`, `rbwal_name`; `rbwal_rbset_id`, `rbwal_rbcar_id` NULL; `rbwal_price` NUMERIC(10,2) (price reached); `rbwal_max_price` (threshold at that time); `rbwal_price_date` DATE; `rbwal_created_at`; `rbwal_read_at` NULL. The lists that hold the card are read **live** when the alert is expanded, not stored |

The 20-list and 100-line limits are enforced in the service (409 `wishlist_limit` with `params {max, scope}`), not
by constraints. Crossing state per target lives in `rbwishlistlines.rbwsl_alert_armed` (BOOL, default true): true
= may fire, set to false when an alert fires and back to true when the price is above the max again.

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
the max: on a crossing create **one** alert per user and card (not per list), then disarm; re-arm when the price is
above the max. Lines without a price are skipped. Push notifications reuse the F4 notification infrastructure
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

A1 to A6 above. Anything else you want different, say it now: changing the table later costs a migration.
