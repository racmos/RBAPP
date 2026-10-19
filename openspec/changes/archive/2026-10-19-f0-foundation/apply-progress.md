# Apply Progress: f0-foundation

**Mode**: Strict TDD (runner `venv/bin/python -m pytest`) · **Artifact store**: openspec (Engram unavailable, so this file replaces the `apply-progress` observation)
**Written**: 2026-10-19, after verify (see `verify-report.md`, W2). The per-task evidence (RED/GREEN notes, failure reasons, mutation checks) lives in the `_(done ...)_` notes of `tasks.md`; this file is the index into it.

Suite growth, default lane (passed): baseline 93 -> unit a 249 -> unit b 397 -> unit c 690 -> unit d 957 -> unit e 1181 (+1 in the pre-archive fixes = 1182). The PostgreSQL lane (`-m postgres`, 30 tests) adds on top: 1211 with the PG lane before the pre-archive fixes. Skips in the default lane are all PG-lane tests when `TEST_POSTGRES_URL` is unset.

## Summary table

| Unit | PR | Tasks (total / done) | Passed after the unit | Open |
|---|---|---|---|---|
| 0 prerequisites | n/a | 8 / 5 (0.1, 0.3, 0.6, 0.7, 0.8) | n/a | 0.2, 0.4, 0.5 (optional user decisions) |
| a config and secrets | #11 | 25 / 24 | 249 | 1.24 (manual `python run.py` check) |
| b Alembic, legacy drop, integer quantity | #12 | 36 / 35 (+1 skipped, 2.35) | 397 | none |
| c admin authz and data exposure | #13 | 39 / 39 | 690 (686 at the 3.35 checkpoint, final count after review fixes) | none |
| d CSRF, login protection, sessions, cache | #14 | 34 / 33 | 957 | 4.31 (deferred follow-up after archive) |
| e API v1, CI, docs, cleanup | #15 | 22 / 21 | 1181 | 5.20 (deferred follow-up after archive) |

## Unit a (PR #11): config and secrets
- Done: 1.1 to 1.23, 1.25 (CFG-1..7, SESS-2, SESS-3, CI-1, IMG-1, PRC-1).
- Evidence: CHAR first (tasks 1.3 to 1.6, 1.14) in `tests/test_card_images.py`, `tests/test_pricing.py`, `tests/test_cardmarket_matcher.py`; RED 1.8 to 1.13, 1.15 in `tests/test_config.py`, `tests/test_run_entry.py`, `tests/test_ci_workflows.py`; GREEN 1.16 to 1.22 name the RED they turn green.
- Deviations: R13 (denylist stored as sha256 digests so CFG-1's literal scan passes), R15 (`.env` read when `RB_ENV` is unset), R8 (`run:app` kept, `wsgi.app` alias). 1.24 left to the user.

## Unit b (PR #12): Alembic baseline, legacy tables, integer quantity
- Done: 2.1 to 2.34, 2.36 (MIG-1..9, QTY-1..4). 2.35 skipped on purpose (downgrade is covered by `test_migrations_pg` in CI).
- Evidence: SPIKE 2.3 (`test_batch_fk_change_sqlite`) passed first run, so no create-copy-rename helper was needed; RED/GREEN pairs in `tests/test_migrations.py` (layout, 0001, 0002, 0003, drift guard, round trip), `tests/test_collection_quantity.py`, `tests/test_migrations_pg.py` (PG lane, 14 tests at this unit, run on a throw-away PostgreSQL 16.2; PG 18 in CI).
- Deviations: the `migrations-pg` CI job (PostgreSQL 18 service) was pulled forward into this unit (orchestrator decision). R6 applied (pre-flight 1..9999 plus `CHECK rbcollection_quantity_chk`). 2.23: nothing was forced in the baseline tests, only 3 assertions were tightened. Dev rollout 2.34 done by the user (stamp 0001, upgrade, counts unchanged).

## Unit c (PR #13): admin authorization and data exposure
- Done: 3.0 to 3.38 (ACL-1..8, IMG-2, IMG-3, PRC-2, DECK-1..4, PROF-1..3).
- Evidence: RED files `tests/test_access_control.py`, `tests/test_authz_matrix.py`, `tests/test_admin_cli.py`, `tests/test_cardmarket_urls.py`, `tests/test_pricing.py`, `tests/test_card_images.py`, `tests/test_deck_viewing.py`, `tests/test_profile.py`, `tests/test_migrations.py::TestUserAdminFlags`; PG lane `TestUserAdminFlags` and `TestSchemaComments` (mutation check with 0004a disabled turned 6 PG tests red). 3.32 is the documented non-RED case (`test_update_password` input adaptation; the real RED is in `test_profile.py`).
- Deviations: R1 (`is_blocked` column + `User.is_active` property), R2 (`promote`/`demote` canonical, `make-admin`/`revoke-admin` aliases), R5 (falsy price = missing), R7 (viewer C tested by id), R14 (JSON 401 left to unit e). Extra revision `0004a_schema_comments` (task 3.0) so that `flask db check` is clean on dev. Test-infra fix in `tests/conftest.py` (`g._login_user` leak between two clients). 14 baseline tests moved to `admin_client`, none weakened.

## Unit d (PR #14): CSRF, login protection, sessions, landing cache
- Done: 4.1 to 4.30, 4.32, 4.33, 4.34 (CSRF-1..5, LOGIN-1..9, SESS-1, LAND-1). 4.30 and 4.32 were closed by user verification after the merge; 4.31 is deferred.
- Evidence: `tests/test_clock.py` (collection error first), `tests/test_migrations.py::TestLoginProtection` (all red first on the missing revision), `tests/test_session_cookies.py`, `tests/test_csrf.py`, `tests/test_templates_csrf.py`, `tests/test_csrf_js.py` (real `csrf.js` under Node, mutation-checked), `tests/test_login_protection.py`, `tests/test_captcha.py` (payloads solved with the real `altcha` library), `tests/test_landing_cache.py`, `tests/test_nginx_config_doc.py`; PG lane `TestLoginProtection` (8 tests; mutation check without the savepoint fails with `InFailedSqlTransaction`). 4.7 is the second documented non-RED case (cookie tests green once config existed).
- Deviations: R3 (count-based escalation, no `lockout_level`), R4 (blocked = invalid credentials), R11 (ALTCHA 5 min), R12 (landing cache 300 s). altcha 2.3.0 exposes PoW v1 as `*_v1` functions and the vendored widget 2.3.0 speaks v1, so the service uses those. Pre-existing tests edited only where the new columns forced it (table count 14 -> 15, two tests now read at head); no assertion weakened.

## Unit e (PR #15): API v1, CI, docs, cleanup
- Done: 5.1 to 5.19, 5.21, 5.22 (API-1..8, CI-2..8). 5.20 (user review of README/AGENTS prose) is a deferred follow-up.
- Evidence: `tests/test_api_v1.py` (written first: collection failed on the missing `wants_json`, API tests 404ed), `tests/test_error_negotiation.py` (37), `tests/test_authz_matrix.py` (six P rows, one U row, R14 JSON 401 for every U/A rule), `tests/test_ci_workflows.py` (25 of 52 red first), `tests/test_docs.py` (77, red before the docs were rewritten). CI evidence for 5.19: PR #15 `test`, `migrations-pg` (PG 18), `frontend` green; `main` after merge green.
- Deviations: R9 (DB URL inline in `run:`), R10 (`hashFiles` at step level, so the `frontend` job runs green with Node steps skipped instead of being skipped). Jinja register moved to the shared limit scope `register` so form and API share one budget. 5.14 removed `package.json`, `package-lock.json`, `diagnose.py`, `docs/riftbound-landing.service` after a reference grep.

## Pre-archive fixes (this change set, after verify)
- W5: `tests/test_api_v1.py::TestEnvelope::test_the_blueprint_handler_answers_an_unhandled_exception` raises `ValueError('secret detail')` from the real `api_v1.health` endpoint (view function swapped with `monkeypatch.setitem`) and spies on `app.api.v1.unexpected_error_response`, the name only the blueprint handler uses (the app-level handler holds its own reference, so it cannot satisfy the spy). It also asserts the generic 500 envelope, no exception text or class name in the body, and the text is logged. RED by mutation: with `@api_v1.errorhandler(Exception)` commented out the test fails (the `ValueError` escapes the blueprint, the spy has no call); restored, the file passes (59 passed). Coverage of `app/api/v1/__init__.py` lines 22 to 24 is now exercised.
- W3: delta specs under `specs/` updated to the as-built wording (R1, R2, R3, R4, R5, R6, R7, R8, R9, R10, R11, R12, R13, R15, `0004a_schema_comments`, PG lane in unit b) with one-line "As built" notes; requirement IDs unchanged.
- W4: stale ticks closed in `tasks.md` (0.3, 0.7, 0.8, 4.32, 5.19, 5.22); 4.31 and 5.20 stay open as deferred follow-ups; a "Deployment notes (dev)" section was added.
- W2: this file.

## Still open after apply (none blocks archive)
0.2 (decision on committing `openspec/`), 0.4 and 0.5 (optional user actions; 0.4 stays recommended because the old values remain in git history), 1.24 (manual `run.py` check), 4.31 and 5.20 (deferred follow-ups after archive). Verify suggestions S2 to S5 are not part of this change.
