# F5-h: Decks UI (mobile first)

> **Stage 1 done (2026-11-05):** read-only decks in the app: nav `decks` → `spa`, `/decks` list
> (mode, legend/champion with domain pips, counts per zone, legality badges 1v1/2v2 with the first
> reasons on a tap, value, date; empty/skeleton/error/offline) and `/decks/:id` (legality of both
> modes with every issue explained, completeness per section, collapsible sections, sticky summary
> bar, unknown cards). AC1-AC7 below. Stage 2 (editing) follows in the same branch.
>
> **Stage 2 done (2026-11-05):** editing with the TS rules (refused controls disabled with the
> reason), section searches, legend purge, auto runes, undo toasts, autosave with the hard-limit
> banner (decision A), rename/mode, save as version, share link, export, delete, New deck and text
> Import. AC8-AC10 below.

| Field | Value |
|---|---|
| Phase / unit | F5 / h |
| Branch | `feat/f5h-decks-ui` (from `main` `83e54c2`) |
| Depends on | F5-b (TS rules, #92), F5-d (decks API, #94), F5-e (import/export API, #95), F5-g (share, in review) |
| Size forecast | ~650 authored lines + tests (two stages: read-only, then editing) |
| Risk | `Risk: none` (frontend only; no backend change, no migration) |
| TDD | ON (strict). Runner: `cd frontend && npx vitest run` |
| Save as | `docs/requirements/F5/F5-h-decks-ui-mobile.md` |

## Objective

The user sees their decks in the new app (owner priority: check that the migrated decks are right),
with the legality per game mode explained in plain words, and then edits them on a phone without
ever being able to break a hard limit, each disabled control saying why.

## Read first

- `AGENTS.md` (Frontend), `docs/frontend.md`, `docs/requirements/F5/README.md` (F5-R14, F5-R19, UI
  table), `F5-a-deck-rules-engine.md` (issue codes and params, completeness), `F5-b-deck-rules-ts.md`
  (the TS library: reuse, never reimplement), `F5-d-decks-api.md`, `docs/api.md` → "Decks (F5-d)",
  "Deck import/export (F5-e)", "Deck sharing (F5-g)"
- Patterns: `frontend/src/products/`, `frontend/src/locations/`, `frontend/src/components/card/`

## Scope

In:
- Stage 1 (read-only): api functions and types for the F5-d/e/g endpoints, deck queries, nav flip,
  `/decks` list, `/decks/:id` view, the `decks` i18n namespace with every issue code.
- Stage 2 (editing): steppers and moves with the TS rules, card search per zone, legend change purge,
  auto runes, undo toast, name/mode edit, autosave, save as version, new deck, import sheet, delete,
  share link, export link.

Out (do not do, even if tempting):
- The R13 Jinja read-only switch (parent, with a final `flask decks migrate`), desktop/wide layouts
  (F5-i), the versions/diff screen (F5-j), the public page `/d/:slug` (F5-m), the offline cache
  (F5-l), any backend change.

## Specs

S1. Nav: the `decks` entry is `spa` at `/decks` (top, bottom, hub, more); the Jinja page stays at
  `/riftbound/deck` (legacy routes key `decks`) behind a "Classic version" link on `/decks`.
S2. `/decks` lists `GET /decks` items in the server order (newest first): name (link to
  `/decks/:id`), mode badge, legend (`Tag, Name`) and champion names or "No legend" / "No champion",
  deck domain pips, "Main n/39", "Runes n/12", "Battlefields n/3", "Sideboard n/10" (needs from
  `/meta/game` `rules.deck`), legality "1v1: Legal" / "1v1: Not legal" per mode, value (EUR) and
  "N cards without price", "Updated <date>".
S3. A not legal badge is a button (`aria-expanded`); a tap shows the list "Why it is not legal in
  <mode>" with the first 3 reasons (short text per code, `decks:issueShort.<code>`) and "And N more".
S4. States: skeleton "Loading decks", "Your decks could not be loaded." with Retry, empty "No decks
  yet" (+ New deck / Import), offline (cached list, "You need a connection to make changes.", New deck
  disabled).
S5. `/decks/:id`: back link "All decks"; header with name, mode, version and date; "Legality" region
  with one group per mode ("1v1: Not legal (deck mode)") listing every issue as a sentence from its
  code and params (`decks:issue.<code>`, context `missing|over` for sized issues and the `reason` for
  `card_off_identity`, zones as `decks:zoneIn.<zone>`); "Sections" list from `completeness`
  ("Main deck: 39/39", "Sideboard: 8/10 (2 missing)", "... (1 too many)").
S6. Sections in this order, collapsible (`details`, open): Legend, Champion, Main deck, Battlefields,
  Runes, Sideboard; "Workbench (not counted)" only with cards. A row: thumb, name, `×qty`, type label,
  domain pips, price or "No price". Empty section: "No cards.". `unknown_cards` in a "Cards not in the
  catalog" region (`OGN-999 (Main deck)`).
S7. Sticky summary bar "Deck summary": main n/39, runes n/12, legality chips per mode, value.
S8. Every `ISSUE_CODES` entry has a message and a short text; every `HARD_RULES` rule a limit
  message (`decks:limit.<rule>`, for `deck_limit_exceeded`).
S9-S20 (stage 2): see "Stage 2" below.

## API / data contract

None changed. Frontend types in `frontend/src/api/types.ts` mirror `docs/api.md`: `DeckCard`,
`DeckContentV2`, `DeckListItem`, `DeckDetail`, `DeckVersionItem`/`Detail`, `DeckImportPreview`,
`DeckShare`.

## UI

Routes `/riftbound/app/decks` and `/riftbound/app/decks/:id` (lazy, inside the auth guard). One
column (max 760 px) on every width; the desktop/wide layout is F5-i. Strings: `decks` namespace.

## Stage 2 (editing)

S9. Steppers and move actions use `canAdd` / `canMove`; a refused control is disabled with the reason
  as `title` and `aria-describedby`; hard limits can never be reached from the UI.
S10. Card search per zone (`CardCombobox` filters); `applyLegend` purge on a legend change;
  `applyChampion`; auto runes button; undo toast for removals.
S11. Name / mode edit (`PATCH`), autosave (1 s debounce, `PUT …/content`, saving / saved / error;
  `deck_limit_exceeded` keeps the local state and shows the reason; an imported deck over a hard limit
  shows a banner listing the violations), "Save as version" (optional note).
S12. New deck (`POST /decks`), Import sheet (preview with warnings and per-section counts, then
  import), delete with confirmation, share link (create, copy, revoke; the public page is F5-m),
  export link (`GET /decks/<id>/export?format=text`). Offline disables every edit.

## Acceptance criteria

- [x] AC1 S1: `src/shell/navRegistry.test.tsx` (decks flip), `src/decks/DecksPage.test.tsx` (nav
  entry and "Classic version" link)
- [x] AC2 S2, S3: `src/decks/DecksPage.test.tsx` (list, legality badges and reasons)
- [x] AC3 S4: `src/decks/DecksPage.test.tsx` (empty, skeleton, error + retry, offline)
- [x] AC4 S5-S7: `src/decks/DeckView.test.tsx` (legality, completeness, sections, rows, summary bar,
  workbench, unknown cards, 404, 1280 px)
- [x] AC5 S8: `src/decks/issues.test.ts` (every issue code with its params, short texts, hard limits)
- [x] AC6 axe clean at 390 px (list and view)
- [x] AC7 Stage 1 frontend lanes green: lint, typecheck, vitest, build, check:dist
- [x] AC8 S9-S11: `src/decks/DeckEditor.test.tsx` (4th copy and 13th rune refused with the reason
  as description, remove + autosave + saved state + server legality, move and full sideboard,
  undo, hard-limit banner blocks saving until fixed, `deck_limit_exceeded` keeps the local deck +
  retry, search add, legend purge + undo, rename + 409, save as version, share create/copy/stop,
  export link, delete, unknown cards block editing until removed, offline, axe);
  `src/decks/editor.test.ts` (pure operations, value rule, `toDeckCard`)
- [x] AC9 S12: `src/decks/DecksPage.test.tsx` (New deck with validation and 409, Import preview
  with counts and warnings in words, import opens the deck)
- [x] AC10 `docs/frontend.md`, `docs/knowledge/state.md`, `AGENTS.md`, F5 `README.md` updated

## Delivery

- Conventional Commits; push and PR only when the owner says so. Never merge.

## After merge

- Frontend build only. Live check: `/riftbound/app/decks` lists the owner's 3 migrated decks.

## Log

- L1 (agent): `DeckCard` has no `energy` / `power` (`app/services/card_detail.py::_card_mini`), so the
  rows show type and domain pips, not energy/power pips. Showing them needs `energy`, `power` (and
  `might`) on `DeckCard`: a backend change, reported, not made.
- L2 (agent): `GET /decks` items carry issue codes only, so the list shows a short text per code
  (`decks:issueShort`); the full sentences with params are on `/decks/:id`.
- L3 (agent): the legend is named `Tag, Name` (first tag) like the text export, since the catalog
  stores the bare legend name (F5-a L14).
- L5 (agent): the legality shown while editing is the server's, as of the last save (it refreshes
  after each autosave, "Legality as of the last save." while unsaved): `validate` needs the bans
  and the frontend has no bans endpoint call yet. Completeness, counts and value are computed
  locally at once; add and move checks use `canAdd` / `canMove`, which need no bans.
- L6 (agent): a deck with printings missing from the catalog cannot be edited or saved (the server
  refuses unknown cards with `validation_error`); the user removes them with one explicit button.
- L7 (agent): the workbench section shows only with cards (S6); cards reach it through the "To
  bench" moves. Legend and champion searches appear when the slot is empty (remove first, with
  undo). Undo restores the whole deck as it was before that removal.
- L4 (agent): the card detail's "In my decks" links still point to the Jinja deck view
  (`/riftbound/deck/view/<id>`, legacy ids); out of this unit's surfaces.

## Open questions

none
