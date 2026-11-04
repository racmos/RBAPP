# F5-d: Decks v2 JSON API

| Field | Value |
|---|---|
| Phase / unit | F5 / d |
| Branch | `feat/f5d-decks-api` (from `main` `95bc90c`, F5-c merged) |
| Depends on | F5-a (rules engine, hard limits), F5-c (`rbdeckheads` / `rbdeckversions`, content v2) |
| Size forecast | ~1 100 authored lines (tests and docs included; the size forecast of the README was ~600) |
| Risk | `Risk: item 3 (the deck shapes, legality payload, diff and error params are what F5-e..j, F16-e and F8 consume), item 4 (versions and autosave: seq allocation and in-place writes of the current version under concurrent requests)` |
| TDD | ON (strict). Runner: `venv/bin/pytest` (backend only; no frontend change but the error catalog entry) |
| Save as | `docs/requirements/F5/F5-d-decks-api.md` |

## Objective

A signed-in user manages their v2 decks through the JSON API: list them with legality per game mode
and value, create, rename, change mode or visibility, delete, autosave the content (refused only when
it breaks a hard limit, with the reason), keep a history of versions (snapshot, restore) and compare
two versions. Only the owner ever sees a deck. No migration, no screen, no import/export (F5-e), no
deck vs collection (F5-f), no share link (F5-g).

## Read first

- `AGENTS.md`, `docs/knowledge/conventions.md`, `docs/knowledge/product.md` → "Game rules"
- `docs/requirements/F5/README.md` (F5-R8, F5-R9, the API table, D-F5-3, D-F5-9)
- `docs/requirements/F5/F5-a-deck-rules-engine.md` (`validate`, `completeness`,
  `hard_limit_violations`), `docs/requirements/F5/F5-c-decks-v2-data.md` (S1-S3, L3, L4, L8, L10)
- `app/services/deck_rules.py`, `app/schemas/deck_content.py`, `app/models/deck_v2.py`,
  `app/services/card_detail.py` (`_card_mini`), `app/services/pricing.py` (`price_summaries`),
  `app/services/bans.py` (`ban_map`, `name_key`)

## Scope

In:
- `app/api/v1/decks.py` (11 routes), `app/services/decks.py`, request schemas in
  `app/schemas/validators.py` (`DeckCreate`, `DeckPatch`, `DeckContentPut`, `DeckVersionCreate`,
  `DeckDiffQuery`)
- Error code `deck_limit_exceeded` (enum + English catalog)
- Authz matrix entries (all U)

Out (do not do, even if tempting):
- Any migration or model change
- Import/export (F5-e), vs collection (F5-f), share link and public endpoint (F5-g), any UI (F5-h..j)
- The R13 Jinja read-only switch (deferred to F5-h, L6)

## Specs

S1. `POST /decks` `{name, mode}`: `name` trimmed, 1-80 characters; `mode` in GAME_MODES. Creates a
  private head and version 1 holding the empty content v2, which is the current version; answers 201
  `DeckDetail`. A name the user already has (exact) → 409 `already_exists`, message `You already have
  a deck with that name.`; another user's name is free. A bad body → 400 `validation_error`, nothing
  stored.
S2. `GET /decks` → `{items: [DeckListItem]}` of the caller only, newest `updated_at` first, then id
  descending. `DeckListItem` = `{id, name, mode, visibility, created_at, updated_at, legend:
  DeckCard|null, champion: DeckCard|null, domains, counts: {main, runes, battlefields, sideboard,
  workbench}, value, value_unpriced, legal: {1v1, 2v2}, issues: {1v1: [code], 2v2: [code]}}`.
  `counts` sum the copies per zone (battlefields: entries; the workbench is its own count). The
  number of SQL statements does not grow with the decks (9).
S3. `GET /decks/<id>` → `DeckDetail` = head fields + `{current_seq, content, cards:
  {"<set>-<id>": DeckCard}, unknown_cards: [{zone, set, id}], domains, counts, value,
  value_unpriced, legality: {1v1, 2v2: {legal, issues, completeness}}}`. `DeckCard` = `CardMini` +
  `tags`. A card missing from the catalog is left out of `cards` and of the legality and listed in
  `unknown_cards`.
S4. `PATCH /decks/<id>` any of `{name, mode, visibility: private|public}`: only the sent keys change,
  none may be null (400); a taken name → 409 `already_exists`; no version is created; `updated_at` is
  refreshed; answers `DeckDetail`.
S5. `DELETE /decks/<id>` → `{deleted: DeckHead}` and every version of the deck is gone.
S6. Owner only (D-F5-9): another user's deck or an unknown id (and an unknown version seq) → the 404
  envelope on every deck route, nothing changes; anonymous → 401 `unauthenticated` on every route.
S7. `PUT /decks/<id>/content` `{content}`: `content` is checked by `DeckContentV2` (400
  `validation_error`, fields like `content.main.0.qty`); a card not in the catalog → 400
  `validation_error` with one detail per card `{field: "content.main.1", message: "unknown card
  XXX-9", type: "value_error", code: "invalid_value"}`. Nothing is stored on any error.
S8. Hard limits (F5-R9) through `deck_rules.hard_limit_violations`: copies per name > 3 (main +
  sideboard + workbench + champion), sideboard > 10, workbench > 100 distinct names, battlefields > 3,
  runes > 12, a token outside the workbench → 400 `deck_limit_exceeded`, `params` = the first
  violation `{rule, max, name?}`, `message` naming all of them: `The deck goes over a limit: copies
  (max 3) ("Desert Scout"); runes (max 12); token (max 0) ("Sand Soldier").` Nothing is stored.
S9. Soft rules (sizes not reached, identity, champion tag, duplicate battlefields, bans) never block a
  save: the response carries them in `legality`. A save rewrites the **current** version in place,
  refreshes the head's `updated_at` (the deck moves to the top of the list) and creates no version.
S10. `POST /decks/<id>/versions` `{note?}` (≤ 200, trimmed, empty = null; `{}` for none) → 201
  `VersionDetail`: a copy of the current content as a new version with the next seq, which becomes
  the current one; later saves edit it and the older versions stay as they were.
S11. `GET /decks/<id>/versions` → `{items: [{seq, note, created_at, is_current}]}`, newest seq first.
S12. `GET /decks/<id>/versions/<seq>` → `VersionDetail` (`VersionItem` + the S3 analysis fields).
  `POST /decks/<id>/versions/<seq>/restore` → 201 `VersionDetail`: version `seq` copied into a new
  version (next seq, note `Restored from version <seq>.`), which becomes the current one; nothing is
  overwritten or deleted.
S13. `GET /decks/<id>/diff?a=&b=` (both integers ≥ 1, else 400 `Invalid query parameters`) → `{a, b,
  zones: {legend, champion, main, runes, battlefields, sideboard, workbench: {added, removed,
  changed}}, cards}`; entries `{set, id, before, after}` per printing from `a` to `b` (copies; 1 for
  legend, champion and each battlefield), ordered by `name_sort_key` of the card name, then set and
  id; `cards` = `DeckCard` of every catalogued printing named in an entry.
  - Example: `a` main `OGN-U1 x2, SFD-U1 x1`, `b` main `OGN-U1 x3, OGN-F1 x1` → main `added [OGN-F1
    0→1]`, `removed [SFD-U1 1→0]`, `changed [OGN-U1 2→3]`.
S14. Value and legality are computed on read, never stored: value (EUR) = Σ market price × copies over
  legend, champion, main, runes, battlefields and sideboard, rounded to cents; the workbench never
  counts; `value_unpriced` = copies of those zones without a price. Legality uses the bans of the
  moment (`ban_map`, by `name_key`), for both modes, whatever the deck's own mode.

## API / data contract

Routes (all U, `app/api/v1/decks.py`): `GET`/`POST /decks`, `GET`/`PATCH`/`DELETE /decks/<id>`,
`PUT /decks/<id>/content`, `GET`/`POST /decks/<id>/versions`, `GET /decks/<id>/versions/<seq>`,
`POST /decks/<id>/versions/<seq>/restore`, `GET /decks/<id>/diff?a=&b=`. Shapes in `docs/api.md` →
"Decks (F5-d)". New error code `deck_limit_exceeded` (400, `params {rule, max, name?}`); reused
`already_exists` (409), `validation_error` (400). No migration.

## UI

none

## Acceptance criteria

- [x] AC1 S1, S3-S5: `tests/test_api_decks.py` (`TestCreate`, `TestDetail`, `TestPatch`, `TestDelete`)
- [x] AC2 S2, S14: `tests/test_api_decks.py::TestList` (shape, order, value, issues, 9 statements with
  1 and 7 decks, bans read at every request), `TestCompleteDecks` (sideboard 8 → only
  `sideboard_size` missing 2; 10 → legal in both modes; a 1v1 ban → legal only in 2v2),
  `TestMigratedDecks` (decks copied by `flask decks migrate` are listed, read and saved)
- [x] AC3 S7-S9: `tests/test_api_deck_versions.py::TestPutContent`
- [x] AC4 S10-S12: `tests/test_api_deck_versions.py::TestVersions`, `TestRestore`
- [x] AC5 S13: `tests/test_api_deck_versions.py::TestDiff`
- [x] AC6 S6: `tests/test_api_deck_versions.py::TestOwnerOnly` (every route: another user's deck,
  unknown id, anonymous) and the 404 tests of each class
- [x] AC7 `deck_limit_exceeded` translated: `tests/test_error_catalogs.py`; authz:
  `tests/test_authz_matrix.py`
- [x] AC8 Full backend lane green: `venv/bin/pytest`
- [x] AC9 `docs/knowledge/state.md`, `docs/api.md`, `AGENTS.md`, F5 `README.md` updated

## Delivery

- Conventional Commits. PR title: `feat(decks): decks v2 JSON API (F5 unit d)`. Never merge.

## After merge

- Deploy to dev with `docs/knowledge/ops-runbook.md` (no migration). Do **not** run `flask decks
  migrate` again yet (L6).
- Live checks: `GET /riftbound/api/v1/decks` signed in lists the migrated decks with legality;
  another user's deck id answers 404.
- Manual checks for the owner: none (no screen).

## Log

- L1 (agent): shapes beyond F5-R8: `counts` per zone (workbench apart), `issues` per mode (distinct
  codes) next to `legal`, `value_unpriced`, `unknown_cards` (a printing removed from the catalog after
  the save is listed, not a 500), `DeckCard` = `CardMini` + `tags` (the editor needs tags for the
  champion rule), `cards` as a map keyed `"<set>-<id>"` so a content ref is resolved without a scan.
- L2 (agent, value rule): the value counts every zone but the workbench (product.md), each printing
  at its non-foil market price (`price_summaries`); unpriced copies are counted apart instead of
  being treated as 0 silently.
- L3 (agent, D-F5-3 as recommended): autosave (`PUT …/content`) rewrites the current version;
  `POST …/versions` snapshots it into a new current version, so the history only changes through
  explicit snapshots. Restore never rewrites: it copies the old version into a new current one (an
  undo of a restore is another restore).
- L4 (agent): two routes beyond the F5-R8 table, needed by the versions UI (F5-j):
  `GET /decks/<id>/versions/<seq>` and `POST /decks/<id>/versions/<seq>/restore`.
- L5 (agent, diff): compared per printing (set, id), not per name, because printings are kept in the
  content (F5-R6) and swapping a printing is a change the owner wants to see; cards missing from the
  catalog still appear in the entries (ordered by their `set-id`) but not in `cards`.
- L6 (agent, deviation from F5-R13 / D-F5-2 timing, follows F5-c L4): the Jinja read-only switch is
  **deferred to F5-h** (the unit that ships the v2 editor). Until then `POST /deck/save` and every
  Jinja deck page keep working on `rbdecks`, and the two stores can diverge. `flask decks migrate`
  must be run right before the switch (it picks up anything saved in Jinja in between, F5-c S8) and
  never after it (F5-c L10: a deck deleted in v2 would be re-created by a re-run).
- L7 (agent, D-F5-9): the v2 API is owner-only (404, never 403). The DECK-1 note in
  `openspec/specs/deck-viewing/spec.md` ("any signed-in user can open any deck by id") still holds
  for the Jinja pages until the F5-h switch; the spec amendment is made with that switch (the
  openspec file is outside this unit's edit surface).
- L8 (agent): `deck_limit_exceeded` carries the first violation as `params` (the F5-R9 shape is one
  object) and names all of them in `message`; the client can recompute the full list with
  `hardLimitViolations` (F5-b). An unknown card is a `validation_error`, not a hard limit.
- L9 (agent, risk item 4): every write locks the head row (`SELECT … FOR UPDATE` on PostgreSQL) before
  reading the next seq or the current version, so two snapshots never take the same seq and an
  autosave never lands in a version a concurrent snapshot just left behind; the unique
  (`deck`, `seq`) constraint is the last guard. SQLite (tests) ignores the lock, so this is not
  covered by a test.
- L10 (agent): `POST …/versions` uses `@validate_json`, so it needs a JSON body (`{}` for no note).
- L11 (agent, F5-c L8): no description field on v2 decks (owner did not ask for one).
- L12 (agent): every deck response reads the whole card catalog once (one statement) to run the rules;
  fine at today's catalog size, revisit if the catalog grows by an order of magnitude.

## Open questions

none
