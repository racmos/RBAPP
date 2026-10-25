# F13-d: Riot sync schedule — due sets, two timers, set windows in the admin API

| Field | Value |
|---|---|
| Phase / unit | F13 / d — batch 1, unit 5 |
| Branch | `feat/f13d-riot-sync-schedule` (from the F13-c branch) |
| Depends on | F13-c (stack) |
| Size forecast | ~300 authored lines |
| Risk | `Risk: item 5 (two systemd timers on the server) + item 4 (overlapping runs)` |
| TDD | ON (strict). Runner: `venv/bin/pytest` |
| Sources | F13 phase spec (F13-R4, R13, R18, R19), `decisions-2026-10-25.md` (D-F13-1, 2, 3, 19, 20) |

## Objective

The sync runs by itself: every day at 08:00 and 14:00 Europe/Madrid a timer queues `riot_sync`, and the job
processes only the sets that are due at that slot. The admin set list shows each set's window and next run.

## Read first

- `app/services/riot_sync.py`, `app/jobs/riot_sync.py` (F13-c), `app/cli/jobs.py` (`--param`)
- `docs/systemd/` (F4-a/F4-b templates), `docs/knowledge/ops-runbook.md` → "Scheduled jobs"
- `app/api/admin/` sets endpoints (F13-b)

## Specs

S1. `due_sets(sets: list[(set_id, release_date)], slot: str, today: date) -> list[(set_id, window)]` (pure):
    - slot `am`: sets in `pre_release`, sets in `post_release`, and — only when `today.day == 1` — sets in
      `monthly` (this includes sets without a release date, D-F13-3).
    - slot `pm`: sets in `pre_release` only.
    - Sets in `none` are never due.
S2. `next_run(release_date, now_local) -> datetime | None` (pure, Europe/Madrid aware): the next 08:00 or 14:00
    at which S1 would include the set (`none` window → the 08:00 of `R−21`; `monthly` → 08:00 on the next 1st).
S3. The `riot_sync` handler with `trigger=schedule` requires `slot` (`am`|`pm`, else `JobFailed('riot_sync:
    invalid params')`), computes `today` and the due sets from S1 and calls `sync` with them; no due set →
    success with result `{"trigger": "schedule", "slot": "am", "today": "…", "message": "nothing due",
    "sets": []}` and no gallery fetch. `trigger=manual` is unchanged (every requested set, D-F13-5).
S4. A scheduled enqueue while a `riot_sync` is queued or running exits as `flask jobs enqueue` already does
    (exit 1, "already queued or running"); the timer service must not fail the unit: use
    `SuccessExitStatus=1` in the service template and document it.
S5. Templates `docs/systemd/riftbound-riot-sync-am.{service,timer}` (`OnCalendar=*-*-* 08:00:00
    Europe/Madrid`, `ExecStart=… flask jobs enqueue riot_sync --param trigger=schedule --param slot=am`) and
    `riftbound-riot-sync-pm.{service,timer}` (14:00, `slot=pm`); same user, paths and environment as
    `riftbound-daily.*`; `Persistent=false`.
S6. `GET /admin/sets` items gain `window` (S2 of F13-c, for today in Europe/Madrid) and `next_run_at` (ISO
    with offset, or null). Response order unchanged.
S7. Runbook "Scheduled jobs" → "Riot sync": install/enable both timers, `systemctl list-timers`, `journalctl -u
    riftbound-riot-sync-am`, run by hand, what "nothing due" means, rollback (disable both timers).
    `docs/knowledge/state.md`: pending check "install the Riot sync timers".

## Acceptance criteria

- [ ] AC1 `tests/test_riot_schedule.py`: S1 for each window and slot, the 1st of the month, sets without date; S2 across a DST change and month end (S1, S2).
- [ ] AC2 `tests/test_riot_sync_job.py` (extend): scheduled run with no due set (no fetch, message), with due sets (only those passed to `sync`), missing/invalid slot (S3).
- [ ] AC3 `tests/test_jobs_systemd.py` (extend): both templates exist with the exact `OnCalendar`, `ExecStart` and `SuccessExitStatus=1` (S4, S5).
- [ ] AC4 `tests/test_admin_sets_api.py` (extend): `window` and `next_run_at` with a frozen clock (S6).
- [ ] AC5 Full lanes green; runbook and `state.md` (S7).

## Delivery

PR title: `feat(riot): sync schedule with am/pm timers and set windows (F13 unit d)`.

## After merge

Deploy (no migration). Server: install and enable `riftbound-riot-sync-am.timer` and `-pm.timer` (adapted to
the host like the other timers); `systemctl list-timers | grep riot` shows both.

## Open questions

none
