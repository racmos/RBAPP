# F5-e: Decks v2 text import and export API

| Field | Value |
|---|---|
| Phase / unit | F5 / e |
| Branch | `feat/f5e-decks-import-export` (from `main` `f2faf09`, F5-a..d merged) |
| Depends on | F5-a (rules engine, `hard_limit_violations`), F5-c (content v2), F5-d (decks API, `_Catalog`, detail shape) |
| Size forecast | ~1 000 authored lines (tests and docs included) |
| Risk | `Risk: item 3 (the import preview, warning codes and export text are what F5-j and the public page consume), item 6 (the text format is matched by name: a wrong resolution would load the wrong card and no other test would see it; the owner's real sample is the guard)` |
| TDD | ON (strict). Runner: `venv/bin/pytest` (backend only) |
| Save as | `docs/requirements/F5/F5-e-decks-import-export.md` |

## Objective

A signed-in user pastes a deck exported by any deck site (the common text format) and gets a v2
deck: a preview first (content, legality in both modes, how many cards each section lacks, one
warning per line that did not land as written), then the import creates the deck. The import always
loads: missing cards, cards in the wrong block and broken hard limits are reported, never refused and
never dropped silently. Any deck exports back to the same text. No migration, no screen, no share link.

## Read first

- `AGENTS.md`, `docs/requirements/F5/README.md` (F5-R10), `openspec/design-handoff.md` §5.2, §5.4
- `docs/requirements/F5/F5-a-deck-rules-engine.md` (L14: legends store the bare name),
  `F5-d-decks-api.md`, `docs/api.md` → "Decks (F5-d)"
- `docs/requirements/F5/samples/deck-export-text-1.txt` (the owner's real deck)
- `app/services/decks.py`, `app/services/deck_rules.py`, `app/services/deck_migration.py`

## Scope

In:
- `app/services/deck_text.py` (pure: `parse_text`, `Resolver`, `build_content`, `format_text`,
  `card_label`), `app/services/decks.py` (`import_preview`, `import_deck`, `export_text`),
  3 routes in `app/api/v1/decks.py`, schemas `DeckImportPreview`, `DeckImport`, `DeckExportQuery`
- Authz matrix entries (all U)

Out (do not do, even if tempting):
- riftdecks / Piltover Archive parsers (owner: one common format; no samples)
- Any UI (F5-j), share link (F5-g), migration, change to `PUT /decks/<id>/content` (F5-d contract)

## Specs

S1. Owner decision (2026-11-04): the only format is the common text. `format` is `auto` (default)
  or `text`; anything else (`riftdecks`, `piltover`, `rbapp`, `TEXT`, ``) -> 400
  `import_format_unknown`, message `The deck format is not recognised. Use the text format.`
S2. Parser (`docs/api.md` → "Deck import/export (F5-e)"): lines split on CRLF/CR/LF and trimmed,
  blank lines ignored; headers case-insensitive with or without colon, aliases `Main Deck`, `Main`,
  `Runes`, `Rune`, `Rune Pool`, ...; `N Name`, `Nx Name`, `N x Name`, no quantity = 1; the same
  name twice in a block merges. Warnings `{line, text, reason_code, params}`: `no_zone`,
  `zone_unknown`, `quantity_invalid` (outside 1..99, line skipped), `unknown_card`,
  `ambiguous_card` (both left out of the content: a ref must name a printing), `wrong_zone` (kept
  in the block), `slot_taken` (extra legend -> workbench, extra champion -> main), `hard_limit`.
S3. Resolution: explicit `SET-ID` (whole text or a final parenthesis) when it exists, else
  `name_key`, else a legend as `Tag, Name`, else the accent-free name (several names -> ambiguous);
  the base printing of a name is chosen.
S4. `POST /decks/import/preview {text, format?}` -> `{deck_preview, warnings, counts}`; writes nothing.
S5. Text over 64 KB (UTF-8) or 2000 lines -> 400 `validation_error`, `code too_long`, `params {max}`.
S6. `POST /decks/import {text, format?, name?, mode?}` -> 201 `DeckDetail` + `warnings`; name =
  `name`, else the legend's text name, else `Imported deck`; a taken name gets ` (2)`, ` (3)` (cut
  to 80); mode default `1v1`; version 1 holds the content.
S7. Hard limits never block an import: content stored as is, one `hard_limit` warning per violation
  (`params` = `deck_limit_exceeded` params) and the legality issues.
S8. `GET /decks/<id>/export?format=text` -> `text/plain; charset=utf-8` attachment `<slug>.txt`;
  blocks Legend, Champion, MainDeck, Battlefields, Rune Pool, Sideboard, blank line between blocks,
  final newline, empty blocks omitted, workbench excluded, legend `Tag, Name`.
S9. Round trips: the owner's sample (synthetic catalog) imports as a legal deck and exports
  byte-identical; export -> import gives the same content (printings collapse to the base one).

## API / data contract

`docs/api.md` → "Deck import/export (F5-e)". No migration, no new error code.

## UI

none

## Acceptance criteria

- [x] AC1 Parser, resolver, placement and format: `tests/test_deck_text.py` (S2, S3, S8)
- [x] AC2 Endpoints: `tests/test_api_deck_import_export.py` (S1, S4-S9)
- [x] AC3 Authz matrix: 3 new rules U (`tests/test_authz_matrix.py`)
- [x] AC4 `docs/api.md`, `AGENTS.md`, `docs/knowledge/state.md`, F5 README updated

## Deviations and decisions (L)

- L1 (agent, owner decision of 2026-11-04 applied): F5-R10's `rbapp|riftdecks|piltover` formats
  are replaced by the one common text format.
- L2 (agent, deviation from the hand-off §5.4 and the task's "main sorted by name"): the export
  keeps the **content order** (one line per name, at its first printing) instead of sorting. The
  owner's sample is in neither "total desc, name" (§5.4) nor name order (`2 Blitzcrank,
  Impassive` closes its main deck, the sideboard is unsorted), so any sort would make its
  byte-identical round trip impossible; the import keeps the line order, so the content order is
  the order the site printed. A sorted export can be added later as an option without changing
  the import.
- L3 (parent decision (A), 2026-11-04): an import that breaks hard limits is stored **as is**
  (nothing moved or clamped: copies over 3 cannot be fixed by moving to the workbench, since the
  workbench counts). Consequence for F5-h: `PUT /decks/<id>/content` (unchanged F5-d contract)
  keeps refusing that content with 400 `deck_limit_exceeded` until **every** violation is fixed, so
  autosave fails while the user fixes them one by one. Candidate to decide when the editor exists
  (option B): `PUT` may keep an existing violation if it does not get worse (per rule and name),
  new violations still refused.
- L4 (agent): `slot_taken` is a reason code the task did not list: the content has one legend and
  one champion slot, so a second one (or qty > 1) must go somewhere visible (prototype §5.2: extra
  champions to main; legends to the workbench, as F5-c routes them).
- L5 (agent): warnings carry `params` (`{}` when none) in addition to `{line, text, reason_code}`
  so the UI can name the card, zone and limit; `hard_limit` warnings have `line: null`.
- L6 (agent): the accent-free match is the only source of `ambiguous_card`: `name_key` keeps accents
  (same as the rules engine) and the prototype's "name contains" fallback is not ported (it loads
  wrong cards silently).
- L7 (agent): Battlefield copies are all kept (`2 Star Spring` = two refs; legality says
  `battlefields_duplicate`); a printing missing from the catalog exports as `SET-ID`, which the
  import resolves back.
- L8 (owner feedback 2026-11-05, branch `feat/f5-import-one-button`): the owner's deck site
  ends every line with its printing in square brackets, zero-padded (`1 Riven, Broken Blade
  [RAD-043]`). The resolver reads a final `[SET-NNN]` (set and suffix case-insensitive, leading
  zeros of the number ignored, also for the other id forms) and never loads another printing
  silently: an unknown bracket id loads the name's base printing with the new `printing_unknown`
  (`params {id, name}`), or nothing with `unknown_card` `params {id}`; an existing id whose card
  is not the written name loads that printing with the new `name_mismatch` (`params {written,
  found}`, also for a parenthesis id; a parenthesis that is not an id stays silent, it may hold
  other words). The export is unchanged (no brackets). UI (F5-h import sheet): one "Import deck"
  button, no Preview: the first press checks, a clean text imports at once, a text with
  warnings stops with the validation panel and "Import anyway" (`docs/frontend.md`).

## Delivery

- Conventional Commits; push and PR only when the owner says so. PR title:
  `feat(decks): deck text import and export API (F5 unit e)`.

## After merge

- Deploy to dev with `docs/knowledge/ops-runbook.md` (no migration).
- Live checks: preview and import the owner's sample against the dev catalog; check that every
  line resolves (legend `Riven, The Exile`) and the export matches the file.

## Open questions

none
