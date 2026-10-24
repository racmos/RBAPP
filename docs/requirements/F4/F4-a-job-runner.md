# F4-a: Job runner + timers

| Field | Value |
|---|---|
| Phase / unit | F4 / a |
| Branch | `feat/f4a-job-runner` (from up-to-date `main`) |
| Depends on | M-c merged (#31) — done |
| Size forecast | ~500 authored lines (tests and docs included) |
| Risk | `Risk: item 1 (new table + migration), item 4 (two runners claiming the same job), item 5 (systemd units on the server)` |
| TDD | ON (strict). Runners: `venv/bin/pytest` (backend), `cd frontend && npx vitest run` (unchanged) |
| Written by | gentle-shell on the owner's instruction (2026-10-24, "continua tu ya con lo que hay planificado"), from `docs/requirements/F4/README.md` F4-R1..F4-R3 |

## Objective

The server can run background work without a request: a job is queued (by a timer, the CLI or, later, an
admin endpoint), a runner started every minute by systemd claims it, runs it and records the result. This
unit builds only the runner, its CLI and one diagnostic job kind; F4-b registers `daily_prices`, F13 and
F10-d register theirs (decision "Job runner", owner 2026-10-22: "Built once in F4-a (`rbjobs` +
`flask jobs run-pending`); F10-d and every later phase only register job kinds.").

## Read first

- `AGENTS.md` ("Database Changes", "Testing" test policy), `docs/knowledge/conventions.md`
- `docs/requirements/F4/README.md` (F4-R1..F4-R3, "Risks and notes" → Overlapping runs)
- `app/cli/users.py` (CLI group pattern and its registration in `app/__init__.py`), `app/utils/clock.py`
- `migrations/versions/0006_user_prefs.py` (latest revision, style), `tests/migration_helpers.py`, `tests/conftest.py`
- `docs/knowledge/ops-runbook.md` → "Scheduled jobs", `docs/riftbound.service`

## Specs

S1. Table `riftbound.rbjobs`, model `RbJob` in `app/models/job.py`, migration `0007_jobs`
    (down_revision `0006_user_prefs`), reversible:
    `rbjob_id` BIGINT PK (INTEGER on SQLite through a variant, so autoincrement works);
    `rbjob_kind` VARCHAR(32) NOT NULL, CHECK `rbjob_kind IN ('heartbeat')` (named `ck_rbjobs_kind`; every
    later unit that registers a kind extends it with its own migration);
    `rbjob_params` JSON NOT NULL default `{}`; `rbjob_status` VARCHAR(10) NOT NULL default `'queued'`,
    CHECK IN ('queued','running','success','error') (`ck_rbjobs_status`);
    `rbjob_requested_by` INTEGER NULL FK `rbusers.id` ON DELETE SET NULL;
    `rbjob_requested_at` DATETIME NOT NULL (default `clock.utcnow()`), `rbjob_started_at` NULL,
    `rbjob_finished_at` NULL; `rbjob_result` JSON NULL; `rbjob_message` VARCHAR(300) NULL.
    Partial unique index `ux_rbjobs_active_kind` on `rbjob_kind` WHERE `rbjob_status IN ('queued','running')`
    (one active job per kind; `postgresql_where` and `sqlite_where`). Index `ix_rbjobs_status_requested`
    on (`rbjob_status`, `rbjob_requested_at`). Table and column comments like the other revisions.
S2. Registry `app/jobs/registry.py`: `JobKind(name, handler, timeout_seconds)`; `register(kind)` (a name
    registered twice raises `ValueError`); `get(name)` (unknown → `None`); `names()` sorted. A handler is
    `handler(params: dict) -> dict` (the dict is stored in `rbjob_result`). Kind `heartbeat`
    (`app/jobs/heartbeat.py`, timeout 60 s) returns `{"ok": true, "at": "<ISO UTC of clock.utcnow()>"}`.
    Registration happens on app creation (one import point, `app/jobs/__init__.py`).
S3. Service `app/services/jobs.py` (no Flask request objects):
    - `enqueue(kind, params=None, requested_by=None) -> RbJob`: unknown kind → `UnknownJobKind`; an active
      job (queued/running) of the same kind → `JobAlreadyActive(job_id)`, detected by the unique index
      (IntegrityError → rollback) so two concurrent enqueues cannot both succeed.
    - `claim_next() -> RbJob | None`: oldest queued job, claimed atomically with
      `UPDATE rbjobs SET rbjob_status='running', rbjob_started_at=now WHERE rbjob_id=:id AND rbjob_status='queued'`;
      if the update touched 0 rows another runner won: try the next one. Never returns a job twice.
    - `expire_stale(now)`: every `running` job whose `started_at + timeout_seconds < now` (kind timeout;
      unknown kind → 3600 s) becomes `error`, `finished_at=now`, message `Timed out after <N> s`.
    - `run_pending() -> list[RbJob]`: `expire_stale`, then claim and run jobs one by one until none is
      queued. Success → `success`, `rbjob_result` = handler return, `finished_at`. Exception → `error`,
      message `"<ExceptionClass>: <first line of the text>"` cut to 300 characters, traceback logged with
      `logger.exception`; the runner continues with the next job. A job whose kind is no longer registered
      → `error`, message `Unknown job kind`.
    - All timestamps from `clock.utcnow()` (frozen in tests).
S4. CLI group `flask jobs` (`app/cli/jobs.py`, registered like `users`). Exact output (stdout unless said):
    - `flask jobs enqueue <kind> [--param key=value]...` → `Queued job <id> (<kind>).` exit 0.
      Unknown kind → stderr `Error: unknown job kind '<kind>'. Known kinds: heartbeat.` exit 2.
      Active job → stderr `Error: a '<kind>' job is already queued or running (job <id>).` exit 1.
      A `--param` without `=` → stderr `Error: --param must be key=value.` exit 2. Values are strings.
      Rejected input writes no row.
    - `flask jobs run-pending` → one line per job `Job <id> (<kind>): success` or
      `Job <id> (<kind>): error: <message>`, then `Ran <n> job(s).`; with nothing queued `No pending jobs.`
      Exit 0 even when a job failed (the failure is recorded; the timer must not loop on it).
    - `flask jobs list [--limit N]` (default 20, newest first) → header
      `ID  KIND  STATUS  REQUESTED (UTC)  FINISHED (UTC)  MESSAGE` and one row per job (timestamps
      `YYYY-MM-DD HH:MM:SS`, empty cells as `-`); none → `No jobs.`; `--limit` < 1 → exit 2.
S5. systemd templates under `docs/systemd/` (placeholders only, no host values):
    `riftbound-jobs.service` (oneshot, same user/WorkingDirectory/EnvironmentFile as
    `docs/riftbound.service`, `ExecStart=/usr/bin/flock -n /run/riftbound/jobs.lock <venv>/bin/flask jobs run-pending`,
    `RuntimeDirectory=riftbound`), `riftbound-jobs.timer` (`OnCalendar=*-*-* *:*:00`, `Persistent=false`),
    `riftbound-daily.service` + `.timer` (`OnCalendar=*-*-* 06:30:00 Europe/Madrid`,
    `ExecStart=… flask jobs enqueue daily_prices`) and `riftbound-daily-retry.service` + `.timer`
    (`OnCalendar=*-*-* 08:00:00 Europe/Madrid`; its command is defined by F4-b). The daily and retry units
    carry a comment "Install with F4-b (the daily_prices kind does not exist before it)".
S6. `docs/knowledge/ops-runbook.md` → "Scheduled jobs": what the runner is; install/enable of the jobs
    timer (copy, `systemctl daemon-reload`, `enable --now riftbound-jobs.timer`); check with
    `flask jobs enqueue heartbeat` and `flask jobs list` a minute later; logs with
    `journalctl -u riftbound-jobs.service`; run by hand; disable (rollback) with
    `systemctl disable --now riftbound-jobs.timer`; the daily timers wait for F4-b. Upgrade order: backup,
    `flask db upgrade`, `flask db check`, restart, then the timer.
S7. Tests (test policy):
    - migration round trip for `0007_jobs` (upgrade, downgrade to `0006_user_prefs`, upgrade) and model/schema
      drift empty, with `tests/migration_helpers.py`;
    - the CHECKs and the partial unique index reject what they must (bad kind, bad status, a second queued
      job of the same kind) and accept a new queued job once the previous one finished;
    - every S4 output, exit code and "no row written" case through `app.test_cli_runner()`;
    - claim: two `claim_next()` calls on one queued job → exactly one job returned once; a job claimed by
      another runner between select and update is skipped (simulate by updating it first);
    - timeout: a `running` job started `timeout + 1` s ago becomes `error` with `Timed out after 60 s`;
      one started `timeout - 1` s ago stays `running`;
    - a failing handler records the 300-character message and the runner continues with the next job;
    - a PostgreSQL-only check is not required (no `postgres` marker test), the `migrations-pg` CI job runs
      the round trip on PostgreSQL 18.
S8. Docs: `AGENTS.md` (structure: `app/jobs/`, `app/models/job.py`, `app/services/jobs.py`,
    `app/cli/jobs.py`, `docs/systemd/`; table list gains `rbjobs`; Model list gains `RbJob`; CLI line
    mentions `flask jobs enqueue|run-pending|list`), `docs/knowledge/state.md` (unit row F4-a, next unit F4-b),
    `docs/requirements/README.md` (F4-a row). Line endings preserved (AGENTS.md is CRLF).
S9. Lanes green: `pytest`, frontend lint, typecheck, `vitest run`, build, `check:dist`; `flask db upgrade`
    + `flask db check` + `flask db downgrade 0006_user_prefs` clean on a scratch PostgreSQL if one is
    available, otherwise left to CI (`migrations-pg`).

## API / data contract

No HTTP endpoint (F10-d adds `POST /admin/jobs`). Data: S1.

## UI

none

## Acceptance criteria

- [ ] AC1 S1 migration round trip + drift test green; `migrations-pg` green in CI.
- [ ] AC2 Every S4 message and exit code covered by a test.
- [ ] AC3 Claim and timeout tests (S7) green.
- [ ] AC4 Templates and runbook (S5, S6); no host values.
- [ ] AC5 Docs and state (S8); lanes green (S9).

## Delivery

Commits: (1) model + migration + tests; (2) registry + service + heartbeat + tests; (3) CLI + tests;
(4) systemd templates + runbook + docs/state. PR title `feat(jobs): job runner and timers (F4 unit a)`.

## After merge (owner, on the server)

Backup the database, `flask db upgrade`, `flask db check`, restart the service, install and enable
`riftbound-jobs.timer` (S6), then `flask jobs enqueue heartbeat` and `flask jobs list` a minute later.

## Open questions

none

## Log

- L1 (owner, 2026-10-24): "continua tu ya con lo que hay planificado"
- L2 (gentle-shell): the kind CHECK holds only the registered kinds; each unit that adds a kind extends it
  by migration (F13 spec already plans that for `riot_sync`). Overlap safety = `flock -n` on the timer plus
  the atomic claim plus the partial unique index.
