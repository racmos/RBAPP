# F4-c: Daily collection value snapshots

| Field | Value |
|---|---|
| Phase / unit | F4 / c — batch 1, unit 20 |
| Branch | `feat/f4c-value-snapshots` (from the F3-b branch) |
| Depends on | F4-a, F4-b (main), F3-b (stack) |
| Size forecast | ~350 authored lines |
| Risk | `Risk: item 1 (new table written every day without a human)` |
| TDD | ON (strict). Runner: `venv/bin/pytest` |
| Sources | F4 phase spec (F4-R4 chaining, F4-R7), `decisions-2026-10-25.md` (D-F4-4, D-F4-5, D-F4-11) |

## Objective

Every day, after the prices load, each user's collection value is saved, so the value history starts now
(it cannot be rebuilt later). Nothing is shown yet; the dashboard and charts come in batch 2.

## Read first

- `app/jobs/daily_prices.py`, `app/services/jobs.py` (`enqueue`, `JobAlreadyActive`), `app/models/job.py`,
  `migrations/versions/0008_jobs_daily_prices.py`
- `app/api/v1/collection.py` / the F3-b service that computes line `market` and `value` (reuse it; one rule)

## Specs

S1. Table `rbvaluesnaps` (migration `00NN_value_snapshots`), model `RbValueSnapshot` (`app/models/snapshot.py`):
    `rbvsn_user_id INTEGER NOT NULL` FK `rbusers.id` ON DELETE CASCADE (`rbvaluesnaps_user_fk`),
    `rbvsn_date DATE NOT NULL`, `rbvsn_value NUMERIC(12,2) NOT NULL`, `rbvsn_cost NUMERIC(12,2) NULL`,
    `rbvsn_qty INTEGER NOT NULL`, `rbvsn_unique INTEGER NOT NULL`, `rbvsn_unpriced INTEGER NOT NULL`,
    `rbvsn_created_at TIMESTAMP NOT NULL` default now; PK (`rbvsn_user_id`, `rbvsn_date`) (`rbvaluesnaps_pkey`).
S2. `app/services/snapshots.py` `take_snapshots(today: date) -> dict`: for every user with at least one
    collection line (D-F4-4), compute with the **same** pricing code as F3-b (D-F4-5): `value` = Σ market × qty
    over priced lines, `cost` = Σ purchase_price × qty (NULL when no line has one), `qty`, `unique` (distinct
    printings), `unpriced` (lines without market); upsert the row (user, today) — a second run the same day
    replaces the values. Returns `{"date", "users": n, "rows": n, "total_value": x}`. Bounded queries (no query per
    user: one pass over all lines grouped in Python is acceptable for the dev data size).
S3. Kind `value_snapshot` (`app/jobs/value_snapshot.py`, timeout 900 s, no params; unknown params → `JobFailed`);
    `today` = UTC date of the run (`clock.utcnow().date()`); migration `00NN_jobs_value_snapshot` extends
    `ck_rbjobs_kind` and `JOB_KINDS`.
S4. Chaining (F4-R4): when `daily_prices` finishes `success`, its handler's last step queues `value_snapshot`
    (`enqueue('value_snapshot')`); `JobAlreadyActive` is ignored (logged); the `daily_prices` result gains
    `"queued": ["value_snapshot"]` (or `[]`). A failure to queue never fails `daily_prices`.
S5. Runbook "Scheduled jobs": `value_snapshot` (queued after the daily load; by hand `flask jobs enqueue
    value_snapshot`), how to read today's rows with `flask shell`. `AGENTS.md` (table, kind). `state.md`.

## Acceptance criteria

- [ ] AC1 `tests/test_snapshots.py`: values for priced, unpriced and foil lines (same numbers as the F3-b totals for the same data); cost NULL vs set; users without lines skipped; upsert replaces; two users isolated (S2).
- [ ] AC2 `tests/test_value_snapshot_job.py`: kind registered, unknown params, result; `daily_prices` success queues it, failure does not, active job ignored (S3, S4).
- [ ] AC3 Migration round trips and drift for both revisions; FK cascade on user delete (S1, S3).
- [ ] AC4 Full lanes green; runbook, `AGENTS.md`, `state.md` (S5).

## Delivery

PR title: `feat(jobs): daily collection value snapshots after the price load (F4 unit c)`.

## After merge

**Backup first.** Deploy (`value_snapshots`, `jobs_value_snapshot`). Live: `flask jobs enqueue value_snapshot`,
then one row per user with a collection for today.

## Open questions

none
