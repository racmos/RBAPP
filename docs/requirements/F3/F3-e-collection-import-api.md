# F3-e: Collection import API — RBAPP format with preview and commit

| Field | Value |
|---|---|
| Phase / unit | F3 / e — batch 1, unit 23 |
| Branch | `feat/f3e-collection-import-api` (from the F3-d branch) |
| Depends on | F3-c, F3-d (stack) |
| Size forecast | ~550 authored lines |
| Risk | `Risk: item 1 (bulk writes to users' collections; new table) + item 6 (untrusted file input)` |
| TDD | ON (strict). Runner: `venv/bin/pytest` |
| Sources | F3 phase spec (F3-R10, "API"), `decisions-2026-10-25.md` (D-F3-2, D-F3-3) |

## Objective

A user uploads a collection CSV in the RBAPP format (the one F3-d exports), sees row by row what will happen,
and then adds it to the collection or replaces the quantities of the printings it contains. Other formats wait
for the owner's samples.

## Read first

- F3-d (`docs/api.md` → RBAPP format), F3-c service (merge key, foil rule, defaults), `app/services/catalog.py`
  (`is_foilable`), `app/services/bans.py` (`name_key`)

## Specs

S1. Table `rbimportpreviews` (migration `00NN_import_previews`), model `RbImportPreview`: `rbimp_id VARCHAR(36)`
    PK (UUID4 text), `rbimp_user_id INTEGER NOT NULL` FK `rbusers.id` ON DELETE CASCADE, `rbimp_format
    VARCHAR(16) NOT NULL`, `rbimp_rows JSON NOT NULL` (JSONB on PostgreSQL), `rbimp_created_at TIMESTAMP NOT
    NULL`, `rbimp_expires_at TIMESTAMP NOT NULL` (created + 30 min). Index on `rbimp_expires_at`. Expired rows
    are deleted at the start of every preview request.
S2. `POST /collection/import/preview` body `{text, format?: "auto"|"rbapp"}` (default `auto`): `text` ≤ 2 MB
    and ≤ 10 000 data rows (else `validation_error`, field `text`, `out_of_range`); BOM stripped; header
    required. Format detection: the header contains every RBAPP column (any order, extra columns ignored,
    case-insensitive) → `rbapp`; otherwise 400 `import_format_unknown`.
S3. Row parsing and status (`ok`, `warning`, `error`), each row `{line, status, reason_codes[], card?, foil,
    qty, condition, language, purchase_price, selling, sell_qty, sell_price}` (`line` = 1-based line in the file,
    header is line 1; `card` = `CardSummary` when resolved):
    - `set_id` (upper-cased) + `card_id` (lower-cased) not in the catalog → error `card_not_found`;
    - `name` differs from the catalog name by `name_key` → warning `name_mismatch` (the key wins);
    - `foil` in `S|N|true|false|1|0` (case-insensitive) else error `invalid_value`; `S` on a non-foilable card
      → error `foil_not_allowed`;
    - `qty` integer 1-9999 else error `invalid_qty`;
    - `condition` empty or in `/meta/game.conditions` (case-insensitive) else warning `unknown_condition`
      (stored as null); `language` ≤ 40 chars else error `invalid_value`;
    - `purchase_price`, `sell_price`: empty or a number ≥ 0 with `.` or `,` as decimal separator, else error
      `invalid_price`;
    - `selling` empty|`Y`|`N` else error `invalid_value`; `sell_qty` empty (0, or `qty` when selling is `Y`) or
      0-`qty` else error `invalid_sell_qty`;
    - a row with the same merge key (F3-c S2) as an earlier row → warning `duplicate_row` (merged on commit).
S4. Preview response 200 `{preview_id, format, rows: [...], summary: {total, ok, warning, error,
    printings}}`; the rows are stored in `rbimportpreviews` (only what commit needs).
S5. `POST /collection/import/commit` body `{preview_id, mode: "add"|"replace"}`: unknown, expired or another
    user's preview → 410 `import_expired`. One transaction:
    - `add`: every `ok`/`warning` row goes through the F3-c add rule (merge identical lines);
    - `replace`: for each (set, card, foil) present in the valid rows, the user's existing lines of that
      printing and foil are deleted, then the rows are added; printings not in the file are untouched;
    - error rows are skipped. Response 200 `{created, merged, replaced, skipped}` (`replaced` = number of
      printings replaced). The preview row is deleted.
S6. Error codes (enum, both `errors.json`, catalog test): `import_expired` 410 — ES "La vista previa ha caducado.
    Vuelve a subir el fichero." EN "The preview expired. Upload the file again."; `import_format_unknown` 400 —
    ES "No se reconoce el formato del fichero. Usa el formato RBAPP (exportación de la app)." EN "The file format
    is not recognised. Use the RBAPP format (the app's export).".
    Row reason codes are not error codes; their texts live in the `collection` namespace (F3-i).
S7. Docs: `docs/api.md` (preview/commit, reason codes), `AGENTS.md` (table), `state.md`.

## Acceptance criteria

- [ ] AC1 `tests/test_api_import_preview.py`: format detection (any column order, extra columns, BOM, wrong header → `import_format_unknown`), every reason code, limits, stored rows, expired rows purged (S1-S4).
- [ ] AC2 `tests/test_api_import_commit.py`: add with merges, replace of printings present only, skipped errors, counts, foreign/expired preview → 410, one transaction (failure leaves nothing), preview deleted (S5).
- [ ] AC3 Round trip: export RBAPP (F3-d) then import with `replace` leaves the collection identical.
- [ ] AC4 Migration round trip and drift; error catalog; authz matrix; full lanes green; docs (S1, S6, S7).

## Delivery

PR title: `feat(collection): CSV import preview and commit for the RBAPP format (F3 unit e)`.

## After merge

**Backup first** (`import_previews`). Deploy.

## Open questions

none

## Log

- L1 (implementer): the commit adds rows with the merge rule of `POST /collection` but without its defaults for the sell price (market x 1.05): the file's price, or none, is kept as written, so exporting and importing with `replace` leaves the collection identical. `sell_qty` follows S3 (empty = 0, or `qty` when `selling` is `Y`).
- L2 (implementer): a user keeps only their latest preview; making a new one deletes the previous one (bounds the storage a user can take).
- L3 (implementer): `replaced` counts (set, card, foil) printings, so a card present as normal and foil counts twice.
- L4 (implementer): rows with the same merge key are added up first, so the commit runs one statement per distinct line; `merged` still counts every row that did not create a line.
- L5 (implementer): a leading `'` before `= + - @ tab CR` in a text cell is removed on import (the export adds it, F3-d S4), so the round trip keeps the text.
