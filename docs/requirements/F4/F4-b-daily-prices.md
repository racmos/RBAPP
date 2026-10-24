# F4-b: Daily Cardmarket load job

| Field | Value |
|---|---|
| Phase / unit | F4 / b |
| Branch | `feat/f4b-daily-prices` (from up-to-date `main`) |
| Depends on | F4-a merged (#32) and deployed — done |
| Size forecast | ~450 authored lines (tests and docs included) |
| Risk | `Risk: item 1 (writes product/price/map rows every day without a human), item 3 (CLI gains an option), item 5 (two new timers on the server), item 6 (Cardmarket file format can change; external input)` |
| TDD | ON (strict). Runners: `venv/bin/pytest`; no network in tests (mock `requests.get` / the loader's `_download_json`) |
| Written by | gentle-shell on the owner's instruction (2026-10-24), from `docs/requirements/F4/README.md` (F4-R3..F4-R4, D-F4-1, D-F4-2, D-F4-10) |

## Objective

Prices refresh by themselves: every day at 06:30 Europe/Madrid a `daily_prices` job loads the Cardmarket
files, validates what it loaded, links the products that match a card without doubt, and lists the doubtful
ones for review; if it failed, an 08:00 timer queues it once more. Owner decisions (2026-10-22): "Cardmarket
load every day at 06:30 Europe/Madrid; retry at 08:00 if it failed. The job validates the load (files,
rows, new products) and records the result." and "Auto-match: Yes after every load, clear cases only.
Doubtful cases go to a review list".

## Read first

- `AGENTS.md` (Testing policy, "Adding a Job Kind"), `docs/requirements/F4/F4-a-job-runner.md`
- `app/services/cardmarket_loader.py` (`run`, `_update_product_card_map`, `_check_already_loaded`, `_record_history`)
- `app/services/cardmarket_matcher.py` (`auto_match`), `app/models/cardmarket.py`, `app/models/job.py`
- `app/jobs/`, `app/services/jobs.py`, `app/cli/jobs.py`, `docs/systemd/riftbound-daily*.{service,timer}`

## Specs

S1. Kind `daily_prices` (`app/jobs/daily_prices.py`, timeout 1800 s), registered at the import point.
    Migration `0008_jobs_daily_prices` extends `ck_rbjobs_kind` to `IN ('heartbeat', 'daily_prices')`
    (downgrade restores `('heartbeat')`; it fails clearly if `daily_prices` rows exist — delete them first,
    documented in the runbook). `JOB_KINDS` in `app/models/job.py` follows.
S2. The handler runs, in order: (a) `CardmarketLoader().run()` with the default allow-listed URLs (no
    params accepted: an unknown param → the job ends `error` with message `daily_prices takes no params`);
    (b) validation (S3); (c) auto-match of clear cases (S4); (d) review list (S5). If the loader returns
    `success: false`, the job raises with the loader's first error (the runner records `error`), and no
    auto-match runs. The existing admin endpoints and the loader/matcher behaviour for them do not change.
S3. Validation record, stored in `rbjob_result["validation"]`:
    `{"date": "<YYYYMMDD loader date>", "files": {"price_guide": {"status", "rows"}, "singles": {...},
    "nonsingles": {...}}, "price_rows": N, "products_today": N, "new_products": N}`, read from
    `rbcm_load_history` rows of the loader date and from the tables (`new_products` = product ids of the
    loader date that do not exist on any earlier date). Status per file is the history status
    (`success`/`skipped`). The job fails (`error`) with message `Validation failed: no price rows for <date>`
    when `price_rows == 0`, or `Validation failed: <file> missing for <date>` when a file has no history row.
S4. Clear cases are linked automatically, nothing else:
    - the loader's existing exact-name rule (exactly one card whose name equals the product name, written by
      the loader with `match_type='auto'`, confidence 1.0) — unchanged;
    - from `auto_match(dry_run=True)`, only pairs from a group with **exactly one** unmapped product and
      **exactly one** free candidate card (no ignored pair, no slot conflict) are written, with
      `match_type='auto'`, confidence 0.7 (the matcher's value). Count in `rbjob_result["auto_match"] =
      {"linked": N, "proposed": N, "review": N}`.
S5. Review list in `rbjob_result["review"]` (D-F4-10): every other unmapped single of the loader date, as
    `{"product_id", "name", "expansion_id", "reason", "candidates": [{"set", "id", "name"}]}` with
    `reason` in `no_candidates` | `ambiguous` (several products or several candidates in the group) |
    `conflict` (slot already taken or duplicated) | `ignored_pair`; at most 200 items, plus
    `rbjob_result["review_total"]`. `flask jobs list` keeps one row per job (no new columns).
S6. Retry rule: `flask jobs enqueue <kind> --unless-succeeded-today`:
    - when a job of that kind finished with `success` on the current UTC date (`rbjob_finished_at`), it
      prints `Skipped: a '<kind>' job already succeeded today (job <id>).` and exits 0, writing nothing;
    - otherwise it behaves exactly like `enqueue` (same messages and exit codes, including the
      `already queued or running` exit 1).
    Without the option, `enqueue` is unchanged (test that every F4-a message and exit code still holds).
S7. systemd: `docs/systemd/riftbound-daily.service` keeps `flask jobs enqueue daily_prices`;
    `riftbound-daily-retry.service` gets `ExecStart=… flask jobs enqueue daily_prices --unless-succeeded-today`;
    both lose the "Install with F4-b" comment; same user/paths as `riftbound-jobs.service`. Runbook
    (`ops-runbook.md` → "Scheduled jobs"): install both timers, check with `flask jobs list`, read the result
    (`venv/bin/flask jobs show <id>` is NOT added; document a one-liner reading `rbjob_result` through
    `flask shell` instead), what the review list means, and rollback (disable both timers).
S8. Tests (no network): handler success path with the loader mocked to write known rows (or `_download_json`
    returning small fixtures under `tests/fixtures/cardmarket/`); loader failure → job `error` and no
    auto-match; validation failures (no price rows, file missing); clear-case linking writes only the
    one-to-one pairs; review reasons and the 200 cap + total; unknown param → error; the S6 option (skip,
    enqueue, active job) and the unchanged plain `enqueue`; migration round trip 0007↔0008 + drift; systemd
    template assertions updated.
S9. Docs: `AGENTS.md` (kind list, CLI option), `docs/knowledge/state.md` (F4-b row, next unit F2-a),
    `docs/requirements/README.md`, `docs/requirements/F4/README.md` F4-b row unchanged except "done".
    Line endings preserved. Lanes green (pytest; frontend untouched).

## After merge (gentle-shell, on the server, with the owner's go-ahead)

Backup, `flask db upgrade` (0008), `flask db check`, restart, install `riftbound-daily` and
`riftbound-daily-retry` services+timers adapted to the host (as for `riftbound-jobs`), run once by hand:
`flask jobs enqueue daily_prices` and read the result a few minutes later.

## Open questions

none

## Log

- L1 (owner, 2026-10-24): "continua tu ya con lo que hay planificado"
- L2 (gentle-shell): "clear cases" = the loader's exact-name rule plus one-product/one-candidate matcher
  groups; everything the matcher pairs by price order inside larger groups goes to the review list. This is
  the conservative reading of "clear cases only" and can be widened later by the planner from the review data.
- L3 (gentle-shell): "today" is the UTC date, the same convention as the loader (`clock.utcnow()`); 06:30
  and 08:00 Europe/Madrid always fall on the same UTC day.
- L4 (gentle-shell): the price guide keeps loading every day even when its hash is unchanged (existing
  loader rule); F4-R4's "skip when hashes did not change" applies to the product files only, as today.
