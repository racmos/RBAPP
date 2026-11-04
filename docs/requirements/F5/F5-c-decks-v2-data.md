# F5-c: Decks v2 data model + migration of the existing decks

| Field | Value |
|---|---|
| Phase / unit | F5 / c (own PR: it carries a migration) |
| Branch | `feat/f5c-decks-v2-data` (from `main` `807cd28`, F5-a merged) |
| Depends on | F5-a (rules engine: card classes, completeness, hard limits) |
| Size forecast | ~600 authored lines (tests and docs included) |
| Risk | `Risk: item 1 (migration and routing heuristics on real data), item 3 (content v2 and the head/version tables are what F5-d, F5-e and F8 consume)` |
| TDD | ON (strict). Runner: `venv/bin/pytest` (backend only; no frontend change) |
| Save as | `docs/requirements/F5/F5-c-decks-v2-data.md` |

## Objective

Decks get their v2 storage: a deck head (owner, name, game mode, visibility, share link, current
version) with numbered versions holding the v2 content (legend, champion, main deck, runes,
battlefields, sideboard, workbench). Every existing legacy deck can be copied into it with a command
the owner reviews first: each card lands in the zone its type says, nothing is dropped silently and
the legacy table stays untouched. No new API route (F5-d) and no UI.

## Read first

- `AGENTS.md`, `docs/knowledge/conventions.md` (database and migrations), `docs/migrations.md`
- `docs/requirements/F5/README.md` (F5-R5, F5-R6, F5-R7, F5-R13, D-F5-1, D-F5-2, "Data model changes")
- `docs/requirements/F5/F5-a-deck-rules-engine.md` (S2, S4, S5, S6, S10)
- `app/models/deck.py`, `app/routes/domains/deck.py`, `app/schemas/validators.py` (`DeckSave`),
  `openspec/specs/deck-viewing/spec.md` (DECK-1..4)
- `app/services/deck_rules.py`, `app/services/catalog.py` (`parse_type`, `parse_domains`, `parse_tags`)
- `migrations/versions/0024_locations.py`, `0021_user_products.py`, `tests/migration_helpers.py`,
  `app/cli/riot.py`

## Scope

In:
- Migration `0025_decks_v2` (tables only), models `RbDeckHead` / `RbDeckVersion`
- Content v2 Pydantic model `app/schemas/deck_content.py`
- Routing service `app/services/deck_migration.py` and CLI `flask decks migrate [--dry-run] [--strict]`
- Runbook "Decks v2 migration" (deploy order with the dump first)

Out (do not do, even if tempting):
- Any API route, the 410 on `POST /deck/save` and the Jinja read-only switch (moved to F5-d/h, L4)
- Copying the data inside the revision (L2)
- Any change to `rbdecks` or the Jinja deck pages

## Specs

S1. Migration `0025_decks_v2` (down `0024_locations`) creates, in schema `riftbound`:
  `rbdeckheads`: `rbdkh_id` BIGINT PK (`rbdeckheads_pkey`); `rbdkh_user_id` INT NOT NULL FK
  `rbusers.id` ON DELETE CASCADE (`rbdeckheads_user_fk`); `rbdkh_name` VARCHAR(80) NOT NULL;
  `rbdkh_mode` VARCHAR(3) NOT NULL CHECK IN GAME_MODES (`rbdeckheads_mode_chk`); `rbdkh_visibility`
  VARCHAR(8) NOT NULL DEFAULT `'private'` CHECK IN (`'private'`, `'public'`)
  (`rbdeckheads_visibility_chk`); `rbdkh_share_slug` VARCHAR(24) NULL UNIQUE
  (`rbdeckheads_share_slug_uq`); `rbdkh_current_version_id` BIGINT NULL (no FK, L3);
  `rbdkh_legacy_name` VARCHAR(200) NULL; `rbdkh_created_at`, `rbdkh_updated_at` TIMESTAMP NOT NULL;
  UNIQUE (`rbdkh_user_id`, `rbdkh_name`) (`rbdeckheads_user_name_uq`).
  `rbdeckversions`: `rbdkv_id` BIGINT PK (`rbdeckversions_pkey`); `rbdkv_deck_id` BIGINT NOT NULL FK
  `rbdeckheads.rbdkh_id` ON DELETE CASCADE (`rbdeckversions_deck_fk`); `rbdkv_seq` INT NOT NULL CHECK
  `>= 1` (`rbdeckversions_seq_chk`); `rbdkv_content` JSONB (JSON on SQLite) NOT NULL; `rbdkv_note`
  VARCHAR(200) NULL; `rbdkv_legacy_id` INT NULL UNIQUE (`rbdeckversions_legacy_uq`, L1);
  `rbdkv_created_at` TIMESTAMP NOT NULL; UNIQUE (`rbdkv_deck_id`, `rbdkv_seq`)
  (`rbdeckversions_deck_seq_uq`). The upgrade copies no data; the downgrade drops both tables;
  `rbdecks` is not touched by either.
S2. `RbDeckHead` and `RbDeckVersion` (`app/models/deck_v2.py`) declare the same names (no drift after
  `flask db upgrade`); the mode CHECK is built from `GAME_MODES`, the visibility CHECK from
  `deck_content.VISIBILITIES`.
S3. `DeckContentV2` (F5-R6) checks the shape only: `v` is the integer 2; `legend` / `champion` are
  `{set, id}` or null; `main`, `runes`, `sideboard`, `workbench` are lists of `{set, id, qty}` with
  `qty` an integer ≥ 1; `battlefields` is a list of `{set, id}`; strings non-empty; unknown keys,
  strings for numbers and booleans are refused; a missing zone is empty. `validate_content` returns
  every key in the order `v, legend, champion, main, runes, battlefields, sideboard, workbench`. No
  deck rule (sizes, copies, types, ≤ 3 battlefields) is checked there.
S4. `route_deck(raw, cards)` routes the legacy main deck in line order: the first Legend (not a token)
  → `legend` (one copy); with a legend, the first Champion Unit (not a token) sharing a tag with it →
  `champion` (one copy; its other copies and other champions stay in `main`); Battlefields → the first
  3 distinct names (one copy each) in `battlefields`, every other copy → `workbench`; Runes → `runes`
  up to 12 copies, the rest → `workbench`; tokens and the other Legends → `workbench`; the rest →
  `main`. The legacy `sideboard` → `sideboard` up to 10 copies (the rest → `workbench`), tokens →
  `workbench`. Lines of one printing are merged per zone, in first-seen order. Card classes, sizes and
  shared tags come from `deck_rules` / `DECK_RULES`.
S5. Nothing is dropped silently. A line whose card is not in the catalog, a line that is not
  `{set: str, id: str, qty: int ≥ 1 | digits}`, a cards value that is not an object and an unknown
  key are left out of the content (L5) and listed in `unresolved` as `{zone, label}`, labels
  `OGN-999 x2`, `invalid line {"set": "OGN"}` (JSON, sorted keys), `cards are not an object`,
  `unknown key "extra"`.
S6. `notes`, in this order: one per card moved or left out, in line order (texts below), then
  `no cards` (nothing at all), then `no Champion Unit shares a tag with the legend: champion left
  empty` (legend without champion) or `no legend: champion left empty` (no legend, a Champion Unit in
  the main deck), then one per hard limit the content still breaks
  (`deck_rules.hard_limit_violations`): `hard limit copies (max 3): "Shurima Guard"`,
  `hard limit workbench (max 100)`. Moved / left-out texts: `extra legend OGN-L2 "The Exile" x1 ->
  workbench`, `battlefield OGN-B4 "Field 4" x1 -> workbench`, `token OGN-T1 "Sand Soldier" x2 (main)
  -> workbench`, `rune over 12: OGN-R2 "Order Rune" x2 -> workbench`, `sideboard over 10: OGN-U3 "Sun
  Disc Keeper" x2 -> workbench`, `unresolved OGN-999 x2 (main): not in the catalog, left out`,
  `unresolved invalid line {...} (main): left out`.
S7. `flask decks migrate` groups `rbdecks` by (user, name), code-point order: one head per group
  (owner = `rbusers.id` of the username; mode = the mode of the latest row by seq, a value outside
  GAME_MODES → `1v1` with the note `mode "Standard" is not a game mode: 1v1`; visibility `private`;
  `legacy_name` = the legacy name; created = earliest snapshot, updated = latest), one version per
  row (seq kept, NULL = 1, a taken seq → the next free one with `seq 1 taken: stored as 2`; content
  from S4; created = the row's snapshot; note `Migrated from rbdecks #12.` plus ` Left out: OGN-999
  x2, ….` when S5 left something out, cut to 200 characters); current version = the highest seq. A
  name over 80 characters is cut (`name longer than 80 characters: shortened`); a name already taken
  by the user gets ` (2)`, ` (3)`… (`name taken: renamed to "…"`). A deck whose user does not exist is
  skipped. A legacy description is not copied (`description not copied (it stays in rbdecks)`).
S8. Idempotent: a legacy row whose id is in `rbdkv_legacy_id` is never copied again. A row saved
  after a run whose (user, name) already has a head becomes a new version of that head (S7 seq
  rule); the head's current version and `updated_at` follow, its mode does not change.
S9. Report (stdout), per deck: `Deck <user> / "<legacy name>": ` + `new deck "<name>", mode <mode>,
  N version(s)` | `N new version(s) for deck "<name>"` | `up to date` | `user not found, skipped`;
  head notes as `  - <note>`; per version `  seq <n> (rbdecks #<id>, YYYY-MM-DD HH:MM): legend <ref |
  none>; champion <ref | none>; main h/39; runes h/12; battlefields h/3; sideboard h/10; workbench
  <copies>` and its notes as `    - <note>`; then `Total: N decks (a new, b updated, c up to date, d
  skipped), N versions, N unresolved lines.` (singular for 1). `--dry-run` adds `Dry run: nothing was
  changed.` and writes nothing. Without it the plan is written in one transaction and the last line is
  `Done: N decks created, N updated, N versions copied.`.
  - Example (synthetic, 3 decks of one user, one version each):
    ```
    Deck ana / "Azir Control": new deck "Azir Control", mode 1v1, 1 version
      seq 1 (rbdecks #1, 2030-01-01 10:00): legend OGN-L1 "Emperor of the Sands"; champion OGN-C1 "Azir, Ascendant"; main 5/39; runes 12/12; battlefields 3/3; sideboard 2/10; workbench 0
    Deck ana / "Draft": new deck "Draft", mode 1v1, 1 version
      seq 1 (rbdecks #3, 2030-01-03 10:00): legend none; champion none; main 0/39; runes 0/12; battlefields 0/3; sideboard 0/10; workbench 0
        - no cards
        - description not copied (it stays in rbdecks)
    Deck ana / "Riven": new deck "Riven", mode 2v2, 1 version
      seq 1 (rbdecks #2, 2030-01-02 10:00): legend OGN-L2 "The Exile"; champion OGN-C2 "Riven, Broken"; main 0/39; runes 0/12; battlefields 0/3; sideboard 0/10; workbench 2
        - token OGN-T1 "Sand Soldier" x2 (main) -> workbench
        - unresolved OGN-999 x1 (main): not in the catalog, left out
    Total: 3 decks (3 new, 0 updated, 0 up to date, 0 skipped), 3 versions, 1 unresolved line.
    Dry run: nothing was changed.
    ```
S10. `--strict`: when any line is unresolved, stderr `Strict: N unresolved line(s); nothing was
  changed.`, exit 1, nothing written (with or without `--dry-run`); the report is still printed.
S11. `POST /deck/save` and every Jinja deck page keep working on `rbdecks` exactly as before (L4).

## API / data contract

No route. Migration `0025_decks_v2` (S1; reversible; the downgrade drops every v2 deck and version).
CLI `flask decks migrate [--dry-run] [--strict]` (S7-S10). Content v2 (S3) is the contract of
`rbdkv_content` for F5-d/e.

## UI

none

## Acceptance criteria

- [x] AC1 S1: `tests/test_decks_v2_migration.py` (constraints, checks, uniques, cascades, round trip,
  drift, `rbdecks` untouched, docstring states the data loss)
- [x] AC2 S2: `tests/test_deck_v2_models.py`
- [x] AC3 S3: `tests/test_deck_content_schema.py`
- [x] AC4 S4-S6: `tests/test_deck_routing.py` (normal deck, two legends, champion choice / no shared
  tag / no legend, 5 battlefields, tokens, unknown and invalid lines, empty deck, other shapes, runes
  over 12, sideboard over 10, merged lines + hard limit, purity)
- [x] AC5 S7-S11: `tests/test_decks_migrate_cli.py` (the 3-deck shape of the dev data, dry run,
  strict, idempotence, several versions, a later legacy save, repeated seqs, long names and unknown
  modes, unknown user, Jinja save still works, help)
- [x] AC6 Full backend lane green: `venv/bin/pytest` (no frontend change)
- [x] AC7 `docs/knowledge/state.md`, `docs/knowledge/ops-runbook.md`, `AGENTS.md`, F5 `README.md`

## Delivery

- Conventional Commits; its own PR (migration). PR title:
  `feat(decks): decks v2 tables and legacy deck migration (F5 unit c)`. Never merge.

## After merge

- Deploy with `docs/knowledge/ops-runbook.md` → "Decks v2 migration": `pg_dump` first, `flask db
  upgrade` + `flask db check`, restart, `flask decks migrate --dry-run`, the owner reviews the report,
  then `flask decks migrate`; a second `--dry-run` reports every deck `up to date`.
- Manual checks for the owner: read the dry-run report of the 3 dev decks (legend, champion and the
  workbench lines are what they expect). The Jinja deck pages are unchanged.

## Log

- L1 (agent): `rbdkv_legacy_id` (not in F5-R5) records the `rbdecks.id` a version came from: it makes
  the copy idempotent per row and lets a re-run pick up rows saved in Jinja after the first run (S8),
  which matters because saving stays enabled (L4). No FK (`rbdecks` goes away in F11).
- L2 (agent, as recommended by the parent): the revision creates the tables only; the data copy is the
  CLI (dry run first, owner review, then the real run), so the schema change and the data copy can be
  rolled back separately and the routing can be re-run.
- L3 (agent): `rbdkh_current_version_id` has no FK: heads and versions would reference each other
  (circular FK, awkward on SQLite and for drops); the deck services keep it pointing at a version of
  the deck (F5-d).
- L4 (agent, deviation from F5-R13 / D-F5-2 timing): the Jinja pages keep reading and writing
  `rbdecks`, and `POST /deck/save` is **not** disabled here. The v2 editor does not exist until
  F5-d/h, so a 410 now would leave users with no way to edit a deck, and showing Jinja pages from the
  new tables would mean a second view of the same data with nothing to edit it. The read-only switch
  (banner + 410) moves to the unit that ships the editor (F5-d API or F5-h UI), right after a final
  `flask decks migrate` run (S8 picks up anything saved in between). Pinned by
  `test_jinja_saving_still_works_and_a_rerun_copies_it`.
- L5 (agent): F5-R7 says unknown ids are "kept in a `dropped[]` list in the version note and reported".
  They are left out of the content (a v2 version only holds resolvable cards, otherwise every engine
  call raises `UnknownCard`), listed in the version note (`Left out: …`, ≤ 200 characters) and printed
  by the report; `--strict` turns them into a failure.
- L6 (agent): users: the spec's `user_id` FK to `rbusers.id` is the convention for new tables
  (D-F3-6 "new tables use rbusers.id"; `rbuserprefs`, `rbuserproducts`); `rblocations` (F16-a) is the
  exception that kept the username. Column names carry the table prefix (`rbdkh_`, `rbdkv_`).
- L7 (agent): routing choices beyond F5-R7: extra Legends and extra battlefield copies go to the
  workbench (the legend and battlefield slots' overflow) rather than the main deck, where they would
  be a type issue; runes over 12 go to the workbench (runes > 12 is a hard limit that would block every
  later save); the legacy sideboard keeps cards of any type (a wrong type is a soft issue the owner
  sees in the editor), only tokens and the 11th card on move.
- L8 (agent): the legacy description, format (`Standard`) and `max_set` have no v2 column; they stay in
  `rbdecks` and the report says when a description exists. Owner to decide in F5-d if decks need a
  description.
- L9 (agent): a head's mode is set when it is created (latest legacy row); later legacy rows added by a
  re-run do not change it, so a mode the owner changes in v2 is never overwritten.
- L10 (agent, for F5-d/h): until the R13 switch, a deck deleted in v2 would be re-created by a re-run
  (its versions' `legacy_id`s go with it). Run the final `flask decks migrate` before the switch and do
  not run it after.

## Open questions

none
