# F3-d: Collection export API — RBAPP and Cardmarket CSV

| Field | Value |
|---|---|
| Phase / unit | F3 / d — batch 1, unit 22 |
| Branch | `feat/f3d-collection-export-api` (from the F3-c branch) |
| Depends on | F3-b, F3-c (stack) |
| Size forecast | ~350 authored lines |
| Risk | `Risk: item 3 (file formats other tools read; Cardmarket must stay byte-compatible)` |
| TDD | ON (strict). Runner: `venv/bin/pytest` |
| Sources | F3 phase spec (F3-R9, "API", "Risks"), `decisions-2026-10-25.md` (D-F3-2) |

## Objective

The user downloads the collection as a CSV: the RBAPP format (everything, re-importable with F3-e) or the
Cardmarket format (only the copies on sale, the same file the Jinja export produces today).

## Read first

- `app/routes/domains/collection.py::export_csv` (format, BOM, file name, `X-Rows-Exported`) — after F3-a it
  uses `rbcol_sell_qty`
- F3-b service (filters, `market`), `app/services/pricing.py`

## Specs

S1. `GET /collection/export?format=rbapp|cardmarket` (U, `api_v1.export_collection`) + every F3-b filter +
    `only_selling=true|false` (default false; forced true for `cardmarket`). Unknown format → `validation_error`.
    Response `text/csv; charset=utf-8`, UTF-8 BOM, header `Content-Disposition: attachment; filename="…"`,
    header `X-Rows-Exported: n`. Streamed (generator), no full list in memory.
S2. RBAPP format: comma, minimal quoting, `\n` line endings, header
    `set_id,card_id,name,foil,qty,condition,language,purchase_price,selling,sell_qty,sell_price`; one row per
    line ordered like F3-b `sort=number`; `foil` `S`/`N`; `selling` `Y`/`N`; numbers with a dot and 2 decimals,
    empty when null. File name `rbapp_collection_<YYYYMMDDHHMMSS>.csv` (UTC).
S3. Cardmarket format: identical to the Jinja export after F3-a — `QUOTE_ALL`, `\n`, header
    `name,language,quantity,price`; name = mapped Cardmarket product name, else card name; quantity =
    `sell_qty` (rows with 0 skipped); price = `sell_price` or the resolved market price or `0.00`; only
    `selling` lines. File name `<YYYYMMDDHHMMSS>_cardmarket.csv` (no set/rarity in the name, because the API
    filters are free). A golden test compares the API output with the Jinja export for the same set and rarity
    filter (bytes equal after the BOM).
S4. CSV injection: a text cell starting with `=`, `+`, `-` or `@` is prefixed with `'` in both formats (the
    Jinja export is not changed; the golden test data has no such names).
S5. Docs: `docs/api.md` (both formats, column by column), `state.md`.

## Acceptance criteria

- [ ] AC1 `tests/test_api_collection_export.py`: RBAPP header, row values (nulls empty, decimals), order, filters, `only_selling`; Cardmarket golden comparison with the Jinja export; BOM, headers, file names with a frozen clock; injection prefix; another user's lines never exported (S1-S4).
- [ ] AC2 Streaming: the view returns a generator response (test checks `response.is_streamed`).
- [ ] AC3 Authz matrix green; full lanes green; docs (S5).

## Delivery

PR title: `feat(collection): CSV export in RBAPP and Cardmarket formats (F3 unit d)`.

## After merge

Deploy. Manual (owner): download both files and open them in a spreadsheet; upload the Cardmarket one to
Cardmarket's stock import as you do today.

## Open questions

none
