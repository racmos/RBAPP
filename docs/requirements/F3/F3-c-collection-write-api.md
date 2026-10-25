# F3-c: Collection write API — add, edit, delete, split, bulk, playset

| Field | Value |
|---|---|
| Phase / unit | F3 / c — batch 1, unit 21 |
| Branch | `feat/f3c-collection-write-api` (from the F4-c branch) |
| Depends on | F3-a, F3-b (stack) |
| Size forecast | ~600 authored lines |
| Risk | `Risk: item 3 (write contract used by the UI and F7) + item 4 (concurrent edits from two tabs or Jinja)` |
| TDD | ON (strict). Runner: `venv/bin/pytest` |
| Sources | F3 phase spec (F3-R6, R8, R24, R26-R28, "API"), `decisions-2026-10-25.md` (D-F3-5, 8, 9, 10) |

## Objective

The app can change the collection safely: add a card (merging identical lines), edit any field of a line,
delete with undo, split copies into a sub-line, apply bulk changes, mark a card name to keep a playset and
change the playset size.

## Read first

- F3-b service and shapes (`docs/api.md` → `CollectionLine`), `app/services/collection_rules.py`,
  `app/services/catalog.py` (`is_foilable`), `app/services/pricing.py`
- `app/routes/domains/collection.py` (`_find_exact_duplicate`, atomic add), `app/api/v1/me.py` +
  `app/schemas/prefs_domain.py` (prefs PATCH)

## Specs

S1. Common rules: every endpoint is `U`, scoped to `rbcol_user = current_user.username`; an id that is not the
    user's → 404 (never 403); every write sets `rbcol_chadat = clock.utcnow()`; quantity changes are atomic in
    SQL (`UPDATE … SET rbcol_quantity = rbcol_quantity + :n`); money rounded half up to 2 decimals; responses
    use `CollectionLine` (F3-b) plus `set_id` and `card_id`.
S2. `POST /collection` body `{set_id, card_id, foil, qty, condition?, language?, purchase_price?, selling?,
    sell_qty?, sell_price?}`: `qty` 1-9999; `condition` in `/meta/game.conditions` or null; `language` any text
    1-40 or null; `purchase_price`/`sell_price` 0-99999.99 or null; unknown card → `validation_error`
    (`card_id`, `invalid_value`); `foil: true` on a card where `is_foilable` is false → 400 `foil_not_allowed`.
    `selling: true` without `sell_qty` → `sell_qty = qty`; without `sell_price` → market × 1.05 (null when no
    market). Exact duplicate (user, set, card, foil, condition, language, purchase_price, selling, sell_price;
    NULL-safe) → merge: `qty += n`, `sell_qty += sell_qty`; response 201 `{line, merged: true}`, else 201
    `{line, merged: false}`.
S3. `PATCH /collection/<id>` body any of `{qty, condition, language, purchase_price, selling, sell_qty,
    sell_price, if_updated_at}`: `if_updated_at` (ISO) different from the row's `rbcol_chadat` → 409
    `stale_line`, nothing changed; `qty` below the current `sell_qty` lowers `sell_qty` to `qty`; `sell_qty` >
    `qty` → 409 `insufficient_quantity`, `params: {"available": qty}`; `selling: true` without a price and the
    line has none → market × 1.05; `selling: false` keeps `sell_qty` and `sell_price`. 200 → the line.
S4. `DELETE /collection/<id>` → 200 `{"deleted": <line with set_id, card_id>}` (enough to POST it back for undo).
S5. `POST /collection/<id>/split` body `{qty, condition?, language?, purchase_price?, selling?, sell_price?}`:
    `qty` must leave ≥ 1 copy (else 409 `insufficient_quantity`, `params.available = line qty − 1`); moves `qty`
    copies into a new row with the source values overridden by the given fields, or merges into an identical
    existing row (S2 key); the source `sell_qty` is clamped to its new `qty`; the target `sell_qty` = its `qty`
    when `selling` is true, else 0. 200 `{source, target, merged}`.
S6. `POST /collection/bulk`: `{ids: [1..1000], set: {condition?, language?, selling?, sell_qty_rule?:
    "all"|"none"|"keep_n", keep?: 1-9, sell_price?, purchase_price?}}` or `{ids, delete: true}`. All-or-nothing:
    any id not owned → 404 and nothing changes. `sell_qty_rule`: `all` → `qty`, `none` → 0, `keep_n` →
    `max(0, qty − keep)` (`keep` required). 200 `{"updated": n}` or `{"deleted": [lines]}`.
S7. Keep a playset: `POST /collection/keep-playset` body `{set_id, card_id, keep: bool}`: resolves the card's
    name, inserts or deletes the `rbkeepplayset` row for (user, `name_key`) (idempotent) → 200 `{name,
    keep_playset, kept, playset_size, playset_short}`.
S8. Playset size: `GET /me/prefs` returns `playset_size` (`null` = 3); `PATCH /me/prefs` accepts `playset_size`
    1-9 or null (`validation_error`, `out_of_range`, `params {min: 1, max: 9}` otherwise). The frontend `Prefs`
    type gains the field (no UI here).
S9. Error codes (enum, both `errors.json`, catalog test):
    `foil_not_allowed` 400 — ES "Esta carta no existe en versión foil." EN "This card has no foil version.";
    `insufficient_quantity` 409 — ES "No hay suficientes copias (disponibles: {{available}})." EN "Not enough copies (available: {{available}}).";
    `stale_line` 409 — ES "Esta línea ha cambiado en otra ventana. Recarga y vuelve a intentarlo." EN "This line changed in another window. Reload and try again.".
S10. Docs: `docs/api.md` (endpoints, rules), `AGENTS.md`, `state.md`.

## Acceptance criteria

- [ ] AC1 `tests/test_api_collection_add.py`: validation, unknown card, foil rule, selling defaults (×1.05, null market), merge key with purchase price, merged flag (S2).
- [ ] AC2 `tests/test_api_collection_edit.py`: each field, stale guard, qty lowering sell_qty, insufficient quantity, selling price default, another user's id → 404 (S1, S3).
- [ ] AC3 `tests/test_api_collection_delete_split.py`: delete payload re-POSTable (undo), split to a new row and into an identical row, ≥ 1 copy rule, sell_qty clamping (S4, S5).
- [ ] AC4 `tests/test_api_collection_bulk.py`: every `set` field and rule, delete, all-or-nothing with a foreign id, 1000-id limit (S6).
- [ ] AC5 `tests/test_api_keep_playset.py` + prefs tests: toggle idempotent, short flag, `playset_size` validation and default (S7, S8).
- [ ] AC6 Atomic quantity: a statement-capture test shows the merge (S2) and the split into an existing row (S5) run one `UPDATE … rbcol_quantity = rbcol_quantity + …` (no read-modify-write). Error catalog test; authz matrix green; full lanes green; docs (S9, S10).

## Delivery

PR title: `feat(collection): collection write API with split, bulk and playset (F3 unit c)`.

## After merge

Deploy (no migration).

## Open questions

none
