# F13-b: Catalog admin API — sets and cards

| Field | Value |
|---|---|
| Phase / unit | F13 / b — batch 1, unit 3 |
| Branch | `feat/f13b-catalog-admin-api` (from the F13-a branch) |
| Depends on | F13-a, M-d (stack) |
| Size forecast | ~550 authored lines |
| Risk | `Risk: item 2 (file upload, catalog writes by the admin)` |
| TDD | ON (strict). Runner: `venv/bin/pytest` |
| Sources | `docs/requirements/F13/README.md` (F13-R4…R11), `decisions-2026-10-25.md` (D-F13-3, D-F13-12, D-F13-21) |

## Objective

The admin can create, edit and delete sets (with the release date that drives the Riot sync) and cards,
and upload a card image, through the admin API. Every write is audited. Nothing visible changes yet (the UI
is F13-f).

## Read first

- `app/api/admin/` (F13-a), `app/services/audit.py`, `app/services/card_images.py` (M-d)
- `app/models/set.py`, `app/models/card.py`, `app/models/collection.py`, `app/models/deck.py`
  (`rbdck_cards` JSON), `app/schemas/validators.py` (`SetCreate`/`SetUpdate`), `app/schemas/validation.py`
- `app/routes/domains/sets.py`, `app/routes/domains/cards.py` (current Jinja admin writes, for the rules)
- `app/api/error_codes.py`, `tests/test_error_catalogs.py`

## Scope

In: the endpoints below, three error codes, audit of every write. Out: window/next-run fields of sets (F13-d),
Riot sync (F13-c…e), UI (F13-f), ban editing (F10), changing card keys (D-F13-21).

## Specs

S1. Validation errors use the `validate_json` error body (`validation_error`, `details[]` with detail codes).
    Query parameters are validated with a pydantic model per endpoint and the same body. Unknown body fields →
    `validation_error` (`extra='forbid'`).
S2. Sets — `GET /admin/sets` (`api_admin.list_sets`): every set as
    `{id, name, release_date (ISO|null), card_count, declared_count}` (`card_count` = rows in `rbcards`,
    `declared_count` = `rbset_ncard`), ordered: sets without release date first, then `release_date`
    descending, then `id`. One query (aggregate join).
S3. `POST /admin/sets` body `{id, name, release_date, declared_count?}`:
    - `id`: trimmed, upper-cased, `^[A-Z0-9]{2,10}$`; `name`: 1-100 chars trimmed; `release_date`: required ISO
      date (D-F13-3); `declared_count`: 0-999 or null.
    - Duplicate id → 409 `already_exists`, `params: {"field": "id"}`. Created → 201 with the S2 item.
    - Audit `set.create`, target `set`/`<id>`, details `{name, release_date}`.
S4. `PATCH /admin/sets/<set_id>` body any of `{id, name, release_date, declared_count}`:
    - `release_date` can change but not become null (`validation_error`, detail `required`).
    - `id` change only when the set has no cards; otherwise 409 `set_in_use`, `params: {"cards": n}`. A new id
      that exists → 409 `already_exists` (`field: id`).
    - Unknown set → 404 envelope. Returns 200 with the S2 item. Audit `set.update`, details = changed fields as
      `{field: [old, new]}`.
S5. `DELETE /admin/sets/<set_id>`: 409 `set_in_use` (`params.cards`) when cards exist; else 200
    `{"deleted": "<id>"}`; audit `set.delete`.
S6. Cards — `GET /admin/cards` (`api_admin.list_cards`), query: `set` (repeatable), `rarity` (repeatable, exact,
    case-insensitive), `type` (substring of `rbcar_type`, case-insensitive), `domain` (substring of
    `rbcar_domain`, case-insensitive), `missing_image` (`true`), `q` (case-insensitive substring of the name,
    or an exact card id, or a key `SET-ID`), `sort` = `number` (default: set id, then natural card id) | `name`,
    `dir` = `asc` (default) | `desc`, `page` ≥ 1, `per_page` ∈ {50, 100, 200} (default 50).
    `data.items[]` = `AdminCard` (below); `meta = {page, per_page, total, pages}`. Bounded queries (≤ 3).
S7. `POST /admin/cards` body `AdminCardInput` with `set_id` and `card_id` required: `card_id` trimmed,
    lower-cased, `^[a-z0-9]{1,10}$`; `set_id` must exist (else `validation_error`, field `set_id`,
    `invalid_value`); duplicate key → 409 `already_exists` (`field: card_id`). 201 + `AdminCard`. Audit
    `card.create`.
S8. `PATCH /admin/cards/<set_id>/<card_id>`: any `AdminCardInput` field except the keys (D-F13-21: sending
    `set_id`/`card_id` → `validation_error`, `invalid_value`). `rbcar_banned` is never accepted (it is not in the
    schema). 404 when missing. Audit `card.update` with the changed fields `{field: [old, new]}`.
S9. `POST /admin/cards/<set_id>/<card_id>/image` (multipart, field `file`):
    - ≤ 2 097 152 bytes (else `validation_error`, field `file`, `out_of_range`, `params.max = 2097152`); type
      detected by magic bytes: PNG `89 50 4E 47`, JPEG `FF D8 FF`, WebP `RIFF????WEBP` (else
      `validation_error`, `invalid_format`). The extension is the detected one (`png`, `jpg`, `webp`).
    - File name: the stem of the card's current `image` when it has one, else `<set_id lower>_<card_id>`;
      written with `card_image_path` (M-d) over any existing file; the card's `image` is updated to
      `<stem>.<ext>`. 200 + `AdminCard`. Audit `card.image`, details `{image, bytes}`.
S10. `DELETE /admin/cards/<set_id>/<card_id>`: 409 `card_in_use`, `params: {"collection_lines": n, "decks": m}`
     when any `rbcollection` row or any deck references the card; else 200 `{"deleted": "<SET>-<id>"}`; the
     image file is not deleted. Decks: read how `rbdck_cards` stores card references (the F2 phase spec says
     main + sideboard keyed by set and card id); count the decks whose JSON contains the key; record the method
     in the PR. Audit `card.delete`.
S11. Error codes (enum + both `errors.json` + catalog test):
     `already_exists` 409 — ES "Ya existe un elemento con ese identificador." EN "An item with that identifier already exists.";
     `set_in_use` 409 — ES "El set tiene cartas; no se puede cambiar su código ni borrarlo." EN "The set has cards; its code cannot be changed and it cannot be deleted.";
     `card_in_use` 409 — ES "La carta está en colecciones o mazos; no se puede borrar." EN "The card is used in collections or decks; it cannot be deleted.".
S12. Docs: `docs/api.md` (create if missing: envelope, error body, an "Admin API" section with these endpoints
     and shapes), `AGENTS.md` (admin endpoints list), `state.md`.

## API / data contract

`AdminCard` = `{set_id, card_id, key, name, domain, type, tags, energy, power, might, ability, rarity, artist,
image, image_url, image_src}` — raw column values (`domain`, `type`, `tags` as stored text), `key` =
`"<set_id>-<card_id>"`, `image_src` from M-d. `AdminCardInput` = the same fields minus `key`, `image_src`
(`name` required on create, 1-200 chars; numbers 0-99 or null; texts trimmed, empty → null).

```json
POST /riftbound/api/v1/admin/sets
{"id": "tst", "name": "Test set", "release_date": "2026-12-04"}
→ 201 {"success": true, "data": {"id": "TST", "name": "Test set", "release_date": "2026-12-04", "card_count": 0, "declared_count": null}}
```

## UI

none

## Acceptance criteria

- [ ] AC1 `tests/test_admin_sets_api.py`: list order and counts; create (upper-casing, duplicate, missing date, bad id); patch (date, null date refused, id change with/without cards, id collision); delete (in use, ok); audit rows written in the same transaction (rollback test) (S2-S5).
- [ ] AC2 `tests/test_admin_cards_api.py`: every filter, sort, pagination and `meta`; create/patch/delete rules; keys and `banned` refused; `card_in_use` with a collection line and with a deck (S6-S8, S10).
- [ ] AC3 `tests/test_admin_card_image.py`: PNG/JPEG/WebP accepted by magic bytes, wrong type and > 2 MB refused, stem rule, file written under a temp `CARD_IMAGES_DIR`, audit (S9).
- [ ] AC4 `tests/test_error_catalogs.py` covers the three codes (S11); authz matrix green.
- [ ] AC5 Full lanes green; docs and `state.md` updated (S12).

## Delivery

PR title: `feat(admin): sets and cards admin API with image upload and audit (F13 unit b)`.

## After merge

Deploy (no migration). Live (admin session, with CSRF header): `GET /riftbound/api/v1/admin/sets` lists every set.

## Open questions

none
