# API

JSON API of Rift Manager. Jinja pages keep their own flat `{"success": ...}` bodies;
everything under `/riftbound/api/v1/` uses the envelope below.

## Envelope

Success:

```json
{"success": true, "data": {}, "meta": {}}
```

Failure:

```json
{"success": false, "error": "Validation Error", "message": "Invalid request data",
 "code": "validation_error",
 "details": [{"field": "name", "message": "Field required", "type": "missing",
              "code": "required"}]}
```

- `error` is the human name, `message` a clear sentence without internals.
- `code` is an `ErrorCode` (`app/api/error_codes.py`); every value has `code.<value>`
  in `frontend/src/i18n/locales/{es,en}/errors.json` (checked by `tests/test_error_catalogs.py`).
- Each item of `details` has `field`, `message`, `type` and `code` (a `DetailCode`,
  e.g. `required`, `invalid_value`, `out_of_range` with `params`), when it applies.
- Unexpected failures log the traceback and return a clear message; only a signed-in
  admin sees the exception text, under `detail` (`app/errors.py::unexpected_failure`).

## Admin API

`app/api/admin/` (`api_admin`, `/riftbound/api/v1/admin/*`) is admin-only:
`before_request(require_admin)` answers JSON 401 to anonymous callers and JSON 403
to plain users. Bodies use the envelope above; query strings are validated with the
same body. Every write records an `rbadminaudit` row in the same transaction
(`app/services/audit.py`).

### Sets

- `GET /admin/sets` → `{[{id, name, release_date (ISO|null), card_count, declared_count}]}`,
  sets without release date first, then `release_date` descending, then `id`.
- `POST /admin/sets` `{id, name, release_date, declared_count?}` → 201 with the item.
  `id` is trimmed and upper-cased (`^[A-Z0-9]{2,10}$`); `name` 1-100 chars; `release_date`
  is required; `declared_count` 0-999 or null. A duplicate id → 409 `already_exists`
  (`params: {"field": "id"}`). Audit `set.create` with `{name, release_date}`.
- `PATCH /admin/sets/<id>` any of `{id, name, release_date, declared_count}` → 200.
  `release_date` cannot become null (400 `required`); changing `id` needs a set without
  cards, else 409 `set_in_use` (`params: {"cards": n}`); an existing new id → 409
  `already_exists`. Unknown set → 404. Audit `set.update` with `{field: [old, new]}`.
- `DELETE /admin/sets/<id>` → 200 `{"deleted": "<id>"}`; 409 `set_in_use` when cards
  exist. Audit `set.delete`.

### Cards

`AdminCard` = `{set_id, card_id, key ("<set>-<id>"), name, domain, type, tags, energy,
power, might, ability, rarity, artist, image, image_url, image_src}` (raw columns;
`image_*` from `CARD_IMAGES_DIR`).

- `GET /admin/cards` with `set` (repeatable), `rarity` (repeatable, exact,
  case-insensitive), `type`/`domain` (substrings, case-insensitive), `missing_image`
  (`true`), `q` (substring of the name, an exact card id, or a `SET-ID` key),
  `sort` = `number` (default: set id, then natural card id) | `name`, `dir` =
  `asc` (default) | `desc`, `page` ≥ 1, `per_page` ∈ {50, 100, 200} (default 50).
  → 200 `{items: [AdminCard], meta: {page, per_page, total, pages}}`.
- `POST /admin/cards` (`AdminCardInput`: `set_id` + `card_id` required, `name` required;
  numbers 0-99 or null; texts trimmed, empty → null) → 201. Unknown set → 400
  (`set_id`, `invalid_value`); duplicate key → 409 `already_exists` (`field: card_id`).
  Audit `card.create`.
- `PATCH /admin/cards/<set>/<id>` any `AdminCardInput` field except the keys
  (sending `set_id`/`card_id` → 400 `invalid_value`; `rbcar_banned` is never accepted) →
  200. Unknown card → 404. Audit `card.update` with `{field: [old, new]}`.
- `POST /admin/cards/<set>/<id>/image` (multipart, field `file`): ≤ 2 097 152 bytes
  (else 400 `out_of_range`, `params.max`); type by magic bytes — PNG `89 50 4E 47`,
  JPEG `FF D8 FF`, WebP `RIFF????WEBP` (else 400 `invalid_format`). The extension follows
  the bytes, not the name. Written with `card_image_path` over any existing file; the card's
  `image` becomes `<stem>.<ext>` (stem of the current image, else `<set lower>_<card>`).
  → 200 `AdminCard`. Audit `card.image` with `{image, bytes}`.
- `DELETE /admin/cards/<set>/<id>` → 200 `{"deleted": "<SET>-<id>"}`; 409 `card_in_use`
  (`params: {"collection_lines": n, "decks": m}`) when a collection line or a deck
  (`rbdck_cards` main/sideboard `{set, id}`) references it. The image file is not deleted.
  Audit `card.delete`.

### Sync, jobs and change review

- `POST /admin/riot/sync` body `{sets?: [codes]}` (codes upper-cased; unknown → 400
  `validation_error`, `field: sets`, `invalid_value`, `params: {values: [...]}`) → 202
  `{"job_id": n}`; the job runs `riot_sync` with `trigger=manual`. Active sync → 409
  `job_running`. Audit `riot.sync_requested`. A scheduled run with nothing due ends
  `success` with `{"message": "nothing due", "sets": []}` and fetches nothing.
- `GET /admin/jobs` with `kind`, `status`, `limit` (1-100, default 20), newest first →
  `items[]` of `{id, kind, status, requested_by (username|null), requested_at,
  started_at, finished_at, message}`. `GET /admin/jobs/<id>` adds `params` and `result`;
  404 when missing.
- `GET /admin/riot/changes` with `status` (`pending` default, `approved`, `rejected`,
  `all`), `set`, `field`, `q` (name substring or card id), `page` ≥ 1, `per_page` ≤ 100
  (default 50) → `items[]` of `{id, set_id, card_id, card_name, image_src, field,
  old_value, new_value, status, detected_at, job_id, decided_at, decided_by
  (username|null)}`, newest first; `meta = {page, per_page, total, pages,
  counts: {pending, approved, rejected}}` (global counts).
- `POST /admin/riot/changes/<id>/approve`: pending only (else 409 `change_decided`); the
  card must still hold the old value (else 409 `change_stale`, nothing written). Numbers are
  parsed back to int; an approved `image_url` re-downloads the image over the card's file
  (a failure keeps the approval and adds `warnings: ["image_download_failed"]`). Audit
  `riot.change_approve`. → 200 with the item.
- `POST /admin/riot/changes/<id>/reject`: pending only → `rejected`. Audit
  `riot.change_reject`. → 200 with the item.
- `POST /admin/riot/changes/bulk` body `{ids: [1..500], action: "approve"|"reject"}` →
  200 `{"results": [{"id", "outcome": "approved"|"rejected"|"stale"|"decided"|"not_found"}],
  "counts": {...}}`; each id in its own transaction, ascending id order.
- `GET /admin/overview` gains `riot`: `{pending_changes, active_sets: [{id, name, window,
  next_run_at}], last_sync: {job_id, status, finished_at, trigger} | null,
  placeholder_sets: [codes whose name equals their id and have no release date]}`.
