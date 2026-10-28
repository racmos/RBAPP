# F3-i: Import wizard and export dialog

| Field | Value |
|---|---|
| Phase / unit | F3 / i — batch 1, unit 26 |
| Branch | `feat/f3i-import-export-ui` (from the F3-h branch) |
| Depends on | F3-d, F3-e, F3-g, F3-h (stack) |
| Size forecast | ~550 authored lines |
| Risk | `Risk: none` |
| TDD | ON (strict). Runner: `cd frontend && npx vitest run` |
| Sources | F3 phase spec (F3-R18, R19), `decisions-2026-10-25.md` (D-F3-2) |

## Objective

From the collection the user can download the collection (RBAPP or Cardmarket) and import an RBAPP file with a
clear preview before anything changes.

## Read first

- `src/collection/` (F3-g/h), `docs/api.md` (export, import preview/commit, reason codes)

## Specs

S1. Export dialog (`ExportDialog`, `Modal`): opened from the collection toolbar button `collection:export.open`
    (desktop toolbar and the mobile overflow of the header). Fields: format radio (`rbapp` default, `cardmarket`
    with the hint `collection:export.cardmarketHint`), scope radio (`all` | `filtered` = the current URL filters |
    `selling`; `cardmarket` forces `selling` and disables the others). Download = `fetch` of
    `GET /collection/export?…` through the API client (session + timeout), then a Blob download with the file name
    of `Content-Disposition`; toast `collection:export.done` with `X-Rows-Exported`. Offline → disabled.
S2. Route `/collection/import` (`ImportWizard`), linked from the toolbar (`collection:import.open`) and the empty
    state (replacing the F3-g temporary link). Four steps with a `Stepper` (`aria-current="step"`):
    1. **Fichero**: file input (`.csv`, ≤ 2 MB, read with `FileReader` as text) or a `textarea` to paste; button
       `collection:import.preview`. Client check: empty → `collection:import.errors.empty`; > 2 MB →
       `collection:import.errors.tooBig`.
    2. **Revisión**: summary (`collection:import.summary` with ok/warning/error counts and printings); table
       (desktop) / list (mobile) of rows: line, status badge (`collection:import.status.<status>`), card (image,
       name, `SET · #id`) or the raw ids, foil, qty, condition, language, prices, reasons
       (`collection:import.reason.<code>`, joined). Filter by status (`SegmentedControl` all/ok/warning/error).
       Rows with `error` are skipped on commit (text `collection:import.skipNote`).
    3. **Modo**: radio `add` (`collection:import.mode.add` + hint) or `replace` (`collection:import.mode.replace` +
       hint `collection:import.mode.replaceHint`, shown in a warning box); button `collection:import.commit`
       behind a `ConfirmDialog` when `replace`.
    4. **Resultado**: counts (`collection:import.result`), buttons `collection:import.goCollection` and
       `collection:import.again`.
    `import_expired` → back to step 1 with the translated error; `import_format_unknown` shown on step 1.
S3. Layouts: mobile one step per screen with back/next; desktop the review table full width with sticky header;
    wide the same with the summary as a side column. States: loading on preview/commit (button busy), errors
    translated, offline → the wizard shows `common:offline.editDisabled` and disables every action.
S4. The collection queries are invalidated after a commit.

## UI strings

| Key | ES | EN |
|---|---|---|
| `collection:export.open` | Exportar | Export |
| `collection:export.title` | Exportar colección | Export collection |
| `collection:export.format` | Formato | Format |
| `collection:export.formatRbapp` | RBAPP (copia completa, se puede volver a importar) | RBAPP (full copy, can be imported again) |
| `collection:export.formatCardmarket` | Cardmarket (cartas en venta) | Cardmarket (cards on sale) |
| `collection:export.cardmarketHint` | El mismo fichero que la exportación clásica, para subirlo a Cardmarket. | The same file as the classic export, to upload to Cardmarket. |
| `collection:export.scope` | Qué exportar | What to export |
| `collection:export.scopeAll` | Toda la colección | The whole collection |
| `collection:export.scopeFiltered` | Solo lo filtrado ahora | Only the current filters |
| `collection:export.scopeSelling` | Solo lo que está en venta | Only what is on sale |
| `collection:export.download` | Descargar | Download |
| `collection:export.done_one` | Exportada {{count}} fila. | {{count}} row exported. |
| `collection:export.done_other` | Exportadas {{count}} filas. | {{count}} rows exported. |
| `collection:import.open` | Importar | Import |
| `collection:import.title` | Importar colección | Import collection |
| `collection:import.steps.file` | Fichero | File |
| `collection:import.steps.review` | Revisión | Review |
| `collection:import.steps.mode` | Modo | Mode |
| `collection:import.steps.result` | Resultado | Result |
| `collection:import.fileLabel` | Fichero CSV en formato RBAPP | CSV file in RBAPP format |
| `collection:import.pasteLabel` | O pega aquí el contenido | Or paste the content here |
| `collection:import.formatHint` | Por ahora solo se admite el formato RBAPP (el que genera «Exportar»). | For now only the RBAPP format is supported (the one "Export" creates). |
| `collection:import.preview` | Revisar | Review |
| `collection:import.errors.empty` | Elige un fichero o pega el contenido. | Choose a file or paste the content. |
| `collection:import.errors.tooBig` | El fichero supera 2 MB. | The file is larger than 2 MB. |
| `collection:import.summary` | Correctas: {{ok}} · Con avisos: {{warning}} · Con errores: {{error}} · Cartas distintas: {{printings}} | OK: {{ok}} · With warnings: {{warning}} · With errors: {{error}} · Distinct cards: {{printings}} |
| `collection:import.status.ok` | Correcta | OK |
| `collection:import.status.warning` | Aviso | Warning |
| `collection:import.status.error` | Error | Error |
| `collection:import.statusFilter.all` | Todas | All |
| `collection:import.skipNote` | Las filas con error no se importarán. | Rows with errors will not be imported. |
| `collection:import.columns.line` | Línea | Line |
| `collection:import.columns.status` | Estado | Status |
| `collection:import.columns.card` | Carta | Card |
| `collection:import.columns.reasons` | Motivos | Reasons |
| `collection:import.reason.card_not_found` | La carta no existe en el catálogo. | The card is not in the catalog. |
| `collection:import.reason.name_mismatch` | El nombre no coincide; se usa el del catálogo. | The name does not match; the catalog name is used. |
| `collection:import.reason.invalid_value` | Hay un valor no válido. | A value is not valid. |
| `collection:import.reason.foil_not_allowed` | Esta carta no tiene versión foil. | This card has no foil version. |
| `collection:import.reason.invalid_qty` | La cantidad debe estar entre 1 y 9999. | The quantity must be between 1 and 9999. |
| `collection:import.reason.unknown_condition` | Estado desconocido; se importa sin estado. | Unknown condition; imported without one. |
| `collection:import.reason.invalid_price` | El precio no es válido. | The price is not valid. |
| `collection:import.reason.invalid_sell_qty` | Las copias a vender no pueden superar la cantidad. | Copies to sell cannot exceed the quantity. |
| `collection:import.reason.duplicate_row` | Fila repetida; se sumará a la anterior. | Repeated row; it will be added to the previous one. |
| `collection:import.mode.add` | Añadir a mi colección | Add to my collection |
| `collection:import.mode.addHint` | Suma las copias; las líneas iguales se juntan. | Adds the copies; identical lines are merged. |
| `collection:import.mode.replace` | Reemplazar estas cartas | Replace these cards |
| `collection:import.mode.replaceHint` | Para cada carta del fichero se borran tus líneas actuales de esa carta y se ponen las del fichero. El resto de tu colección no cambia. | For each card in the file your current lines of that card are deleted and the file's lines are added. The rest of your collection does not change. |
| `collection:import.commit` | Importar | Import |
| `collection:import.confirmReplace_one` | ¿Reemplazar {{count}} carta de tu colección? | Replace {{count}} card in your collection? |
| `collection:import.confirmReplace_other` | ¿Reemplazar {{count}} cartas de tu colección? | Replace {{count}} cards in your collection? |
| `collection:import.result` | Creadas: {{created}} · Sumadas: {{merged}} · Cartas reemplazadas: {{replaced}} · Omitidas: {{skipped}} | Created: {{created}} · Merged: {{merged}} · Cards replaced: {{replaced}} · Skipped: {{skipped}} |
| `collection:import.goCollection` | Ir a la colección | Go to the collection |
| `collection:import.again` | Importar otro fichero | Import another file |
| `collection:import.back` | Atrás | Back |
| `collection:import.next` | Siguiente | Next |

## Acceptance criteria

- [ ] AC1 `ExportDialog.test.tsx`: format/scope rules, request URL with filters, Blob download name, toast count, offline disabled (S1).
- [ ] AC2 `ImportWizard.test.tsx`: file and paste input, client checks, preview rendering with reasons and status filter, add and replace (confirm) commits, result, `import_expired` back to step 1, `import_format_unknown` on step 1, query invalidation (S2, S4).
- [ ] AC3 Layouts at 390, 1280, 1700; axe; parity; full lanes green; `docs/frontend.md`, `state.md` (S3).

## Delivery

PR title: `feat(collection): import wizard and export dialog (F3 unit i)`.

## After merge

Deploy. Manual (owner): export RBAPP, change a quantity in a spreadsheet, import it with "Reemplazar" and check
that only that card changed.

## Open questions

none

## Log

- L1 (implementer): no mobile overflow menu exists; on mobile "Exportar" and "Importar" sit in the `PageHeader` actions next to "Versión clásica".
- L2 (implementer): the toolbar "Exportar" button is disabled offline too; the dialog shows no offline text because `common:offline.editDisabled` ("cambios") does not fit a download.
- L3 (implementer): the step indicator is `StepIndicator`; `Stepper` is the existing numeric control of F3-g.
- L4 (implementer): the review table reuses `collection:table.columns.*` for foil, qty, condition, language and price headers; no strings outside the spec table were added.
- L5 (implementer): the review step's "Siguiente" is disabled when no row is ok or warning; reason codes are de-duplicated before joining (the backend can send `invalid_value` twice); a chosen file wins over pasted text; pasted text over 2 MB is refused too.
- L6 (implementer): no screenshots (not deployed, no browser run). The Cardmarket file name comes from `Content-Disposition` via the new `requestFile` helper in `api/client.ts` (the only module that calls `fetch`).
