# deck-viewing Specification

Source: change f0-foundation (archived 2026-10-19)

> **Jinja retirement (2026-11-08, PR 3/3).** The Jinja deck routes (`/riftbound/deck/...`) were removed; `/riftbound/deck` and `/riftbound/deck/view/<any>` answer a 302 to `/riftbound/app/decks`. DECK-2..DECK-4 no longer apply and are kept as history; DECK-1 is amended below (owner-only decks, D-F5-9); decks v2 are specified in `docs/requirements/F5/` and `docs/api.md` → "Decks (F5-d)" and "Deck sharing (F5-g)".

> Tags: `[a]`..`[e]` = delivery unit of change f0-foundation. All scenarios are pytest-testable (SQLite). Until F5 every logged-in user could see every deck; since D-F5-9 (F5-d) a deck is visible only to its owner (DECK-1).

## Requirements

### Requirement: DECK-1 A deck is visible only to its owner (amended by D-F5-9)

A deck MUST be visible only to its owner: every `/riftbound/api/v1/decks/<id>...` route resolves only the caller's decks, and another user's deck answers exactly like an unknown id (404, never 403, nothing disclosed or changed). A deck the owner shared is read by anyone through its share slug, `GET /riftbound/api/v1/public/decks/<slug>` (public, read-only, no workbench, the owner's username only when the deck is public, no collection read: `owned_total` is `null`); an unknown, revoked or malformed slug answers the same 404. Owned copies (`owned_total`) on the owner's routes come from the owner's collection, who is the viewer.

#### Scenario: Another user's deck
- GIVEN user A owns deck 7 and user B is signed in
- WHEN B requests `GET /decks/7` (or any write on it)
- THEN the answer is a 404 envelope and deck 7 is unchanged

#### Scenario: Shared deck
- GIVEN user A shared deck 7 and got slug `S`
- WHEN anyone (signed in or not) requests `GET /public/decks/S`
- THEN the answer is the read-only deck without the workbench, and `owned_total` is `null`

#### Scenario: Revoked link
- GIVEN user A revoked the share of deck 7
- WHEN anyone requests `GET /public/decks/S`
- THEN the answer is a 404

History (f0-foundation `[c]`, Jinja routes, superseded): "DECK-1 have/missing use the viewer's collection". On all three view routes (`/riftbound/deck/view/<int:id>`, `/view/<name>`, `/view/<name>/<seq>`), `have` per card MUST be `min(viewer's total owned quantity across foil variants, needed quantity)` and `missing = needed - have`, computed from the VIEWER's collection, never the owner's.

Because the name routes resolve only the viewer's own decks (DECK-2), the comparison against another user's deck is exercised through the id route (R7).

#### Superseded scenario: Another user's deck
- GIVEN user A owns deck `Foo` needing 3x `OGN/1` and owns 4 copies; user B owns 1 copy
- WHEN B views the deck by id
- THEN the card shows `have=1`, `missing=2`

#### Superseded scenario: Viewer owns none
- GIVEN the same deck and user C with no copies
- WHEN C views it by id
- THEN `have=0`, `missing=3`

#### Superseded scenario: Owner views own deck
- GIVEN the same deck
- WHEN A views it
- THEN `have=3`, `missing=0`

### Requirement: DECK-2 Name lookup is scoped to the viewer [c]

`/view/<name>` and `/view/<name>/<seq>` MUST only resolve decks owned by the VIEWER (aligned with design D19): `/view/<name>` returns the viewer's highest `seq` of that name; `/view/<name>/<seq>` the viewer's exact `seq`. If the viewer has no such deck the status MUST be 404, even if another user has a deck with that name (no owner disclosure). Other users' decks remain reachable only via `/view/<int:id>`.

#### Scenario: Viewer owns one
- GIVEN `alice` and `bob` both have deck `Foo`
- WHEN `bob` views `/riftbound/deck/view/Foo`
- THEN bob's highest-seq `Foo` is shown

#### Scenario: Viewer owns none
- GIVEN `alice` has `Foo`, and `carol` has none
- WHEN `carol` requests `/view/Foo` or `/view/Foo/1`
- THEN the status is 404

#### Scenario: Unknown
- GIVEN no deck named `Nope`
- WHEN `/view/Nope` or `/view/Nope/1` is requested
- THEN the status is 404

### Requirement: DECK-3 versions endpoint works [c]

`GET /riftbound/deck/versions/<name>` MUST return 200 `{success:true, versions:[...]}` listing the CURRENT user's versions of that deck, newest `seq` first, each as `{id, name, seq, snapshot (ISO-8601), mode, format, ncards}`. Another user's decks MUST NOT appear. No match: `versions: []`. It MUST NOT return 500.

#### Scenario: Two versions
- GIVEN the user has `Foo` seq 1 and seq 2
- WHEN `GET /riftbound/deck/versions/Foo` is requested
- THEN `versions` has 2 entries ordered seq 2, seq 1, each with the keys above

#### Scenario: Other user's deck hidden
- GIVEN only `bob` has `Foo`
- WHEN alice requests `/versions/Foo`
- THEN status 200 and `versions == []`

### Requirement: DECK-4 Dead legacy routes removed [c]

`POST /riftbound/deck/update/<set>/<card>` and `DELETE /riftbound/deck/delete/<set>/<card>` MUST NOT exist (they always failed). Requests to them MUST return 404, and they MUST be absent from `app.url_map` and the authorization matrix.

#### Scenario: Removed routes
- GIVEN an authenticated user
- WHEN `POST /riftbound/deck/update/OGN/1` and `DELETE /riftbound/deck/delete/OGN/1` are sent
- THEN both return 404

#### Scenario: Save still works
- GIVEN an authenticated user
- WHEN `POST /riftbound/deck/save` is sent with a valid deck JSON
- THEN a deck row is created with the next `seq`, as before
