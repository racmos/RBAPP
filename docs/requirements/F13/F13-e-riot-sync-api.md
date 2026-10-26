# F13-e: Riot sync and change approval API

| Field | Value |
|---|---|
| Phase / unit | F13 / e — batch 1, unit 6 |
| Branch | `feat/f13e-riot-sync-api` (from the F13-d branch) |
| Depends on | F13-c, F13-d (stack) |
| Size forecast | ~450 authored lines |
| Risk | `Risk: item 1 (approved changes write cards)` |
| TDD | ON (strict). Runner: `venv/bin/pytest` |
| Sources | F13 phase spec (F13-R18, R20-R25), `decisions-2026-10-25.md` (D-F13-5, 8, 16, 22) |

## Objective

The admin can start a sync, follow its job, and approve or reject the changes the monthly sync proposed, one
by one or in bulk, safely (a change is applied only if the card still has the value it had when detected).

## Read first

- `app/api/admin/` (F13-a/b), `app/services/riot_sync.py`, `app/models/card_change.py`, `app/models/job.py`,
  `app/services/jobs.py`, `app/services/audit.py`, `app/services/card_images.py`

## Specs

S1. `POST /admin/riot/sync` body `{sets?: [codes]}`: codes upper-cased and validated against `rbset`
    (unknown → `validation_error`, field `sets`, `invalid_value`, `params: {"values": [...]}`); queues
    `riot_sync` with `trigger=manual`, `sets` joined by commas, `requested_by` = current user → 202
    `{"job_id": n}`. Active `riot_sync` → 409 `job_running`. Audit `riot.sync_requested`.
S2. `GET /admin/jobs?kind=&status=&limit=` (`limit` 1-100, default 20; newest first) → `items[]` of
    `{id, kind, status, requested_by (username|null), requested_at, started_at, finished_at, message}`.
    `GET /admin/jobs/<id>` → the same plus `params` and `result`; 404 when missing. Read only.
S3. `GET /admin/riot/changes?status=pending|approved|rejected|all` (default `pending`) `&set=&field=&q=&page=
    &per_page=` (50 default, 100 max; `q` = name substring or card id): `items[]` of
    `{id, set_id, card_id, card_name, image_src, field, old_value, new_value, status, detected_at, job_id,
    decided_at, decided_by}`, ordered `detected_at` desc then id; `meta = {page, per_page, total, pages,
    counts: {pending, approved, rejected}}`. ≤ 3 statements.
S4. `POST /admin/riot/changes/<id>/approve`: only a `pending` row (else 409 `change_decided`); the card's
    current value of `field` must equal `old_value` with the S5 comparison of F13-c (else 409 `change_stale`,
    nothing written, row unchanged); then set the field (numbers parsed back to int), mark `approved`,
    `decided_at`, `decided_by`; `image_url` approved → download the new image over the card's file (a
    download failure keeps the change approved and returns `warnings: ["image_download_failed"]`). Audit
    `riot.change_approve` (details `{card, field, old, new}`) in the same transaction. 200 → the S3 item.
S5. `POST /admin/riot/changes/<id>/reject`: only `pending` (else 409 `change_decided`) → `rejected`; audit
    `riot.change_reject`. 200 → the S3 item.
S6. `POST /admin/riot/changes/bulk` body `{ids: [1..500 ints], action: "approve"|"reject"}` → 200
    `{"results": [{"id": 1, "outcome": "approved"|"rejected"|"stale"|"decided"|"not_found"}], "counts": {...}}`;
    each id in its own transaction, in ascending id order (S4/S5 rules); never all-or-nothing.
S7. `GET /admin/overview` gains `riot`: `{"pending_changes": n, "active_sets": [{"id", "name", "window",
    "next_run_at"}], "last_sync": {"job_id", "status", "finished_at", "trigger"} | null, "placeholder_sets":
    [codes of sets whose name equals their code and have no release date]}`.
S8. Error codes (enum, both `errors.json`, catalog test):
    `job_running` 409 — ES "Ya hay una sincronización en curso. Espera a que termine." EN "A sync is already running. Wait until it finishes.";
    `change_stale` 409 — ES "La carta ha cambiado desde que se detectó este cambio. Revisa la carta." EN "The card changed after this change was detected. Check the card.";
    `change_decided` 409 — ES "Este cambio ya se aprobó o rechazó." EN "This change was already approved or rejected.".
S9. Docs: `docs/api.md` (these endpoints), `AGENTS.md`, `state.md`.

## Acceptance criteria

- [ ] AC1 `tests/test_admin_riot_api.py`: sync queued (202, params, audit), unknown set, `job_running`; jobs list filters/limit/order and detail (S1, S2).
- [ ] AC2 `tests/test_admin_changes_api.py`: list filters, order, counts; approve (applied, numbers parsed, audit), stale, decided, image download mocked (ok and failing → warning); reject; bulk mixed outcomes with per-id transactions (S3-S6).
- [ ] AC3 `tests/test_admin_api.py` (extend): overview `riot` block with a frozen clock (S7).
- [ ] AC4 Error catalog test covers the three codes; authz matrix green (S8).
- [ ] AC5 Full lanes green; docs and `state.md` (S9).

## Delivery

PR title: `feat(riot): sync, jobs and change approval admin API (F13 unit e)`.

## After merge

Deploy (no migration). Live: `POST /admin/riot/sync` from the browser console as admin (with CSRF) → 202; the
job shows up in `GET /admin/jobs?kind=riot_sync`.

## Open questions

none

## Log

- L1 (implementer): no product deviations. `decided_by` is the username (not the id) so the
  review UI shows it without another lookup; `counts` are global (all statuses) for the tab badges;
  ties order by id descending (newest first). Numbers compare as ints, NULL and empty text as equal
  (same rule as F13-c). A scheduled run with nothing due never fetches (returns before `sync`).
  F13-a overview tests were extended (frozen clock) for the new `riot` block instead of replaced.
