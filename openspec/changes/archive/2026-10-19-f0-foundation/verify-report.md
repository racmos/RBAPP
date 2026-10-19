# Verification Report: f0-foundation

**Change**: f0-foundation (roadmap F0 "Base", units a-e, PRs #11-#15 merged to `main` at `1fd086f`)
**Artifact store**: openspec
**Mode**: Strict TDD (runner `venv/bin/python -m pytest`)
**Date**: 2026-10-19
**Verdict**: **PASS WITH WARNINGS** (0 CRITICAL, 5 WARNING, 5 SUGGESTION)

Scope of this verification: read-only on code. The dev DB was not touched and `.env` was not loaded (`RB_ENV=testing`, set by `tests/conftest.py`). A throw-away PostgreSQL 16.2 (pgserver, scratchpad) was used for `-m postgres` and stopped afterwards.

---

## 1. Completeness

| Metric | Value |
|---|---|
| Tasks total | 164 |
| Complete `[x]` | 151 |
| Skipped `[-]` | 1 (2.35 optional downgrade rehearsal; covered by `test_migrations_pg` in CI) |
| Open `[ ]` | 12 |
| Specs | 14 capabilities, 74 requirements, 184 scenarios |

### Open tasks (all MANUAL / USER / bookkeeping; no core implementation task is open)

| Task | Kind | Real state |
|---|---|---|
| 0.2 | USER decision | `openspec/` is already tracked in git for the proposal/design/tasks files; decision never ticked |
| 0.3 | USER | `.env` and `/etc/riftbound/riftbound.env` exist and dev runs from them (dev rollout done in 2.34/3.37/4.33); tick is stale |
| 0.4 | USER, optional | Rotate DB password and `SECRET_KEY`; firewall port 8000. Still recommended: old values stay in git history |
| 0.5 | USER, optional | `TEST_POSTGRES_URL` for local `-m postgres`. Not set; the CI job covers it (and I ran it, see 3.2) |
| 0.7 | USER | Done in practice (3.37: racmos promoted, 403/200 confirmed). Tick is stale |
| 0.8 | USER | Done in practice (PRs #11-#15 merged). Tick is stale |
| 1.24 | MANUAL | `python run.py` binds 127.0.0.1 without debugger and fails clearly with no env. I re-checked the failure message (section 3.5); the live `run.py` check is still the user's |
| 4.31 | MANUAL, pending CT 102 nginx repoint | Nginx `limit_req` burst test (LOGIN-7) and LOGIN-5 timing sample |
| 4.32 | MANUAL, pending CT 102 nginx repoint | Secure/HttpOnly/Lax cookie and strict Referer behind HTTPS (SESS-1) |
| 5.19 | GH-CI | Evidence now exists (section 3.3): PR #15 `test`, `migrations-pg`, `frontend` all SUCCESS; push to `main` after merge SUCCESS. Safe to tick |
| 5.20 | MANUAL | CI-8 README/AGENTS review. I checked the prose claims below (section 5.3); the user's sign-off is still pending |
| 5.22 | Process | This report is the success-criteria walk (section 6). Tick after the orchestrator accepts it |

---

## 2. Build and Tests Execution

**Build**: n/a (Python, no build step). Config/app import smoke checks in 3.5.

**Tests (default lane)**: `RB_ENV=testing venv/bin/python -m pytest -q --cov=app --cov-report=term-missing -rs`
```
1181 passed, 30 skipped in 209.22s   (exit 0)
```
The 30 skips are all `tests/test_migrations_pg.py` ("TEST_POSTGRES_URL is not set"). No other skip/xfail exists in the suite apart from three guarded conditional skips (`node` missing, running as root, no PG URL).

**Tests (PostgreSQL lane)**: throw-away PostgreSQL 16.2, DB `rbtest`, `TEST_POSTGRES_URL` set:
```
pytest -m postgres  ->  30 passed, 1181 deselected in 15.20s
```
Together: 1211 / 1211 pass. PostgreSQL 18 (dev major) is covered by the `migrations-pg` CI job (green on PR #15).

**Coverage** (informational, no threshold configured): total **75 %** (3384 stmts, 850 missed).

**Security scan**: `bandit -r app/ -ll` (bandit 1.9.4, same pin as `security.yml`): 0 medium/high; 3 low.

**Linter / type checker**: not configured in the project (per `openspec/config.yaml`). Skipped.

---

## 3. Strict TDD Verification

### 3.1 TDD Compliance

| Check | Result | Details |
|---|---|---|
| TDD evidence reported | WARNING | There is no `apply-progress` artifact in openspec (Engram off). The equivalent evidence lives as per-task notes in `tasks.md`: 46 `RED`, 59 `GREEN`, 5 `CHAR` tasks, each GREEN names the RED it turns green, and many notes state the failure reason ("failed first on the missing revision", "collection error first", "25 of 52 were red first", mutation checks). No formal "TDD Cycle Evidence" table. See W2 |
| All tasks have tests | OK | Every implementation task in units a-e is paired with a test file that exists and passes |
| RED confirmed (tests exist) | OK | All referenced test files exist (34 files, 1211 tests) |
| GREEN confirmed (tests pass now) | OK | 1181 pass default lane, 30 pass PG lane |
| Triangulation adequate | OK | Mostly parametrized/multi-case (e.g. escalation table 5..12 and 40, 11 invalid register cases, 7 bad set ids). Single-case tasks are 1:1 with single-scenario requirements |
| Honest non-RED cases | OK | 3.32 (`test_update_password` adaptation) and 4.7 (cookie tests green once config existed) are documented as not-RED with the real RED located elsewhere |
| Safety net for modified files | OK | Baseline edits are listed per task (2.23, 3.12, 3.32, 4.5, 4.28, 5.5) and none weakens an assertion |

### 3.2 Test layer distribution

| Layer | Tests | Files | Tools |
|---|---|---|---|
| Unit (pure functions, services, config, clock, workflow/YAML/doc scans, JS under Node) | ~330 | test_config, test_clock, test_pricing (part), test_cardmarket_urls, test_captcha (part), test_csrf_js, test_ci_workflows, test_docs, test_nginx_config_doc, test_run_entry, test_landing_cache, test_card_images (part) | pytest, node |
| Integration (Flask test client + in-memory SQLite, Alembic up/down, CLI runner) | ~850 | all route, API, CSRF, login, migration, profile, deck, quantity, authz tests | pytest-flask, flask test client, `app.test_cli_runner()` |
| Integration (real PostgreSQL) | 30 | test_migrations_pg | pytest `-m postgres` |
| E2E (browser) | 0 | not available | none; covered by user MANUAL checks (4.30 done, 4.32 pending) |
| **Total** | **1211** | **34** | |

### 3.3 Changed-file coverage (default lane; PG-only code is exercised by the PG lane)

| File | Line % | Uncovered | Rating |
|---|---|---|---|
| `app/__init__.py` | 96 | 102, 106, 184-187 | Excellent |
| `app/errors.py` | 97 | 53, 115 | Excellent |
| `app/security.py`, `app/api/v1/auth.py`, `app/api/v1/meta.py`, `app/routes/auth.py`, `app/routes/domains/profile.py`, `app/cli/users.py`, `app/services/pricing.py`, `app/services/card_images.py`, `app/utils/clock.py`, models (except deck) | 100 | none | Excellent |
| `app/services/auth.py` | 96 | 168-172 | Excellent |
| `app/services/captcha.py` | 99 | 138 | Excellent |
| `app/api/responses.py` | 92 | 18 | Excellent |
| `app/routes/domains/sets.py` | 91 | 24, 26, 69, 71 | Acceptable |
| `app/schemas/validators.py` | 92 | 65-67, 119, 127-128, 150-152, 164, 182-187, 198-201, 233, 423 | Acceptable |
| `app/api/v1/__init__.py` | 70 | 22-24 (blueprint-level error handler body never executed) | Low (see W5) |
| `app/models/deck.py` | 70 | `to_dict`/helper methods, pre-existing | Low |
| `app/routes/domains/{cards,collection,deck}.py` | 76 / 74 / 75 | pre-existing untouched paths (bulk ops, search filters, deck builder helpers) | Low |
| `app/routes/domains/price.py` | 48 | Cardmarket load/match tool paths, pre-existing; the F0 changes (guard, URL allow-list) are covered | Low |
| `app/services/cardmarket_loader.py` | 34 | network download/parse paths, pre-existing; `validate_override_url` fully covered | Low |
| `app/services/riot_scraper.py` | 45 | live scraping paths, pre-existing; F0 image-write change covered | Low |
| `app/cli/schema.py` | 28 | PostgreSQL-only; covered by the 30 `-m postgres` tests | n/a |

Average is dominated by pre-existing, untouched legacy modules. Every line introduced by F0 is covered except `api/v1/__init__.py:22-24`. Informational only.

### 3.4 Assertion quality audit

Scanned all test files added or changed by F0 (plus baseline files for weak patterns).
- Tautologies (`assert True`, `1 == 1`): 0.
- Assertion-free tests / tests that never call production code: 0 found.
- Ghost loops: loops over `app.url_map` / marker lists are guarded by size assertions (`len(rules) == 23`, `len(rules) > 60`, `len(post_rules) > 20`, `test_both_protected_classes_were_checked`) or by `parametrize`. The authz-matrix per-class helper does not itself assert non-emptiness per class, but completeness tests make an empty class impossible.
- Loose status assertions: `status_code in (200, 404)` (`test_templates_csrf.py:73`, deliberately includes the `no-such-page` path), `in (200, 302)` (`test_login_protection.py:335`, followed by row-count and flash assertions), `in (302, 401)` for anonymous (spec allows both), `in (400, 415)` (spec-ambiguous). All are paired with value assertions. Pre-existing `is not None` smoke assertions are in baseline cardmarket tests only.
- Mock-heavy: `test_landing_cache.py` patches raw fetchers by design (spec requires counting calls); mocks do not outnumber behavioral assertions.

**Assertion quality**: 0 CRITICAL, 0 WARNING, 2 SUGGESTION (S2, S3).

---

## 4. Spec Compliance Matrix (behavioral, requirement to evidence)

Result key: OK = a test that exercises the scenario passed in this run; PG = test is in the `-m postgres` lane, passed in this run and in CI on PG 18; CI = verified in GitHub Actions; MAN-DONE = manual, completed by the user per tasks.md (not re-verified by me); MAN-PENDING = open manual task; PARTIAL = see warning.

Evidence files are under `/home/racmos/RBAPP/tests/`.

### app-config (unit a)
| Req | Scenarios | Evidence | Result |
|---|---|---|---|
| CFG-1 | literals gone; values from env | `test_config.py::TestNoCredentialsInTree` (legacy literals, scan coverage); `TestCreateApp::test_values_come_from_the_environment`; `git grep` for the three literals outside tests/openspec: 0 hits (re-run by me) | OK |
| CFG-2 | unset=production; unknown value | `TestResolveEnv`, `TestCreateApp::test_unset_rb_env_is_production`, `test_unknown_rb_env_raises_listing_allowed_values`; I confirmed the message: `allowed values: development, testing, production` | OK |
| CFG-3 | missing key; weak keys (incl. 31 chars, no echo); missing DB URL; test contract | `TestValidateSettings`, `TestCreateApp::{test_production_without_secret_key_raises, test_weak_secret_keys_raise_without_echoing_the_value, test_production_without_database_url_raises, test_test_contract_is_unchanged, test_validation_runs_after_overrides_*}` | OK |
| CFG-4 | development loads .env; production ignores .env | `TestDotenvGating` (8 tests incl. unset RB_ENV per R15) | OK |
| CFG-5 | SQLite options; PG client_encoding | `TestEngineOptions`, `TestEngineAndProxyViaApp` | OK |
| CFG-6 | example file safe; service unit [MANUAL] | `TestNoCredentialsInTree::test_env_example_*`, `TestServiceUnit` (EnvironmentFile, no literals, `run:app`, rotation advice). Service-unit review is automated | OK |
| CFG-7 | default one hop; trust disabled | `TestEngineAndProxyViaApp::{test_default_trusts_one_forwarded_hop, test_zero_hops_ignores_the_header}` | OK |

### db-migrations (unit b)
| Req | Scenarios | Evidence | Result |
|---|---|---|---|
| MIG-1 | upgrade on SQLite; on PG [PG-CI] | `test_migrations.py::TestBaselineVersioning` (version in `riftbound`, 16 tables, default schema untouched), `TestDriftGuard::test_every_model_table_exists_and_nothing_else`; `test_migrations_pg.py` (only `riftbound` created, none in `public`) | OK / PG |
| MIG-2 | structure; CHECKs enforced; matches PG [PG-CI] | `TestBaselineMatchesSnapshot`, `TestBaselineSpecScenarios` (indexes, partial index, no extra FKs, CHECKs reject/accept); PG snapshot diff test | OK / PG |
| MIG-3 | stamp keeps data [MANUAL] | tasks 2.34 (user: stamped 0001, upgraded, counts unchanged 306/4/3/1298) | MAN-DONE |
| MIG-4 | backup then drop; path ignored; missing deck warning; unwritable aborts; downgrade restores | `TestBackupThenDrop`, `TestLayout::test_backup_path_is_git_ignored`, `TestMissingDeckWarning`, `TestAbortsLeaveEverythingIntact::test_unwritable_backup_directory_aborts_before_any_drop`, `TestDowngradeRestores`. I confirmed no backup is tracked (`git ls-files` shows no `instance/`) | OK |
| MIG-5 | FK target at head; orphan aborts | `TestDecksUserForeignKey`, `TestAbortsLeaveEverythingIntact::test_orphan_deck_owner_aborts_naming_the_user` | OK |
| MIG-6 | clean drift SQLite; guard catches drift; clean on PG [PG-CI] | `TestDriftGuard` (6 tests incl. extra column named, type change); PG `flask db check` tests | OK / PG |
| MIG-7 | round trip | `TestRoundTrip` (2 tests) + PG up/down/up | OK / PG |
| MIG-8 | layout; no implicit create | `TestLayout` (4 tests) | OK |
| MIG-9 | runbook [MANUAL] | `TestRunbook` (mentions, safe order) | OK |

### collection-quantity (unit b)
| Req | Scenarios | Evidence | Result |
|---|---|---|---|
| QTY-1 | data preserved; pre-flight aborts; downgrade; PG cast [PG-CI] | `TestQuantityDataIsConverted`, `TestQuantityPreflight`, `TestQuantityDowngrade`; PG USING-cast tests | OK / PG |
| QTY-2 | asc/desc numeric | `test_collection_quantity.py::TestNumericSort` | OK |
| QTY-3 | sequential adds; concurrent [MANUAL]; export arithmetic | `TestAtomicMerge::{test_sequential_adds_*, test_a_concurrent_write_between_read_and_update_is_not_lost, test_export_subtracts_the_playset_arithmetically}`, `TestNoTextQuantityLeftovers` (code-review item automated) | OK |
| QTY-4 | mixed input; overwrite; bad body; scoped to caller | `TestImportCsv`, `TestImportCsvBadBody` | OK |

### access-control (unit c)
| Req | Scenarios | Evidence | Result |
|---|---|---|---|
| ACL-1 | existing users after upgrade; no self-promotion | `test_migrations.py::TestUserAdminFlags`; `test_access_control.py::TestNoSelfPromotion`. Column is `is_blocked` + property `User.is_active` per R1/D10 (spec text says `is_active`; see W3) | OK |
| ACL-2 | session cut; blocked + correct password == wrong password | `test_access_control.py` part 1; `test_login_protection.py` (R4) | OK |
| ACL-3 | non-admin catalog 403; price tools 403 with no outbound request; admin passes | `test_access_control.py` (`len(rules)==23`, `requests.Session.request` recorder) | OK |
| ACL-4 | non-admin pages; admin pages | `test_access_control.py` (markers, listeners, price link) | OK |
| ACL-5 | enforcement per class; unclassified rule fails | `test_authz_matrix.py` (76 rules classified exactly once, stale/double entries fail naming the rule, JSON 401 for protected rules) | OK |
| ACL-6 | promote (twice); unknown user | `test_admin_cli.py` (24 tests; canonical `promote`/`demote`, aliases `make-admin`/`revoke-admin` per R2) | OK |
| ACL-7 | foreign host rejected; allowed host accepted | `test_cardmarket_urls.py` (48 tests, `requests.get` never called on rejection) | OK |
| ACL-8 | baseline intact | full suite: the 93 original tests and the 14 moved to `admin_client` all pass | OK |

### card-images (units a, c)
| Req | Scenarios | Evidence | Result |
|---|---|---|---|
| IMG-1 | promo set; regular/PROK; no image | `test_card_images.py::{TestImageSrc, TestImageFolder, TestCardImageFolder}` | OK |
| IMG-2 | traversal rejected; via filename; lands where image_src reads; fallback; limits | `TestUpload` (13 tests incl. CWD independence, symlink escape, exactly 2 MB) | OK |
| IMG-3 | promo from scraper; fallback | `TestScraper` | OK |

### deck-viewing (unit c)
| Req | Scenarios | Evidence | Result |
|---|---|---|---|
| DECK-1 | another user's deck; viewer owns none; owner | `test_deck_viewing.py` DECK-1 group (R7: C by id) | OK |
| DECK-2 | viewer owns one; none -> 404; unknown | DECK-2 group | OK |
| DECK-3 | two versions; other user's hidden | DECK-3 group | OK |
| DECK-4 | removed routes 404 and absent from url_map; save still works | DECK-4 group | OK |

### user-profile (unit c)
| Req | Scenarios | Evidence | Result |
|---|---|---|---|
| PROF-1 | taken (409, unchanged); own; free; commit-time IntegrityError | `test_profile.py` (27 tests) | OK |
| PROF-2 | correct / wrong / missing current password; email only; baseline adapted | `test_profile.py`, `test_routes.py::test_update_password` | OK |
| PROF-3 | anonymous; invalid email | `test_profile.py` | OK |

### price-resolution (units a, c)
| Req | Scenarios | Evidence | Result |
|---|---|---|---|
| PRC-1 | 7 chain scenarios | `test_pricing.py::TestResolvePriceChain::test_chain` (table-driven) + 0/None edge tests (R5) | OK |
| PRC-2 | deck matches collection; showcase/low; latest wins; unmapped | `TestDeckPrices`, `TestLatestPriceForCard`, `TestNoOtherPriceRule` (grep) | OK |

### csrf-protection (unit d)
| Req | Scenarios | Evidence | Result |
|---|---|---|---|
| CSRF-1 | no token; header token; multipart; no expiry (2 h); forged | `test_csrf.py` (33 tests; PUT/PATCH/DELETE via a throw-away route since the app has none) | OK |
| CSRF-2 | browser form -> HTML 400 | `test_csrf.py` | OK |
| CSRF-3 | meta tag on every page; login with token; wrapper [MANUAL] | `test_templates_csrf.py` (37), `test_csrf_js.py` (real `csrf.js` under Node, 14); wrapper in a real browser: 4.30 | OK / MAN-DONE |
| CSRF-4 | POST logout; GET 405; nav markup | `test_csrf.py`, `test_templates_csrf.py::TestLogoutControl` | OK |
| CSRF-5 | default on in production; env kill switch | `test_session_cookies.py`, `test_csrf.py` | OK |

### login-protection (unit d)
| Req | Scenarios | Evidence | Result |
|---|---|---|---|
| LOGIN-1 | existing users | `test_migrations.py::TestLoginProtection` (+ PG) | OK / PG |
| LOGIN-2 | 5th failure locks, 6th refused; expiry; no extension | `test_login_protection.py` service + route level (Retry-After integer, 429, no session) | OK |
| LOGIN-3 | escalation; cap | escalation table (5 to 12, 40) | OK |
| LOGIN-4 | reset; session survives | `test_login_protection.py` | OK |
| LOGIN-5 | same response + one hash check (mocked counter); timing [MANUAL] | `test_login_protection.py` (hash check on every path); timing sample is part of 4.31 | OK / MAN-PENDING (timing) |
| LOGIN-6 | unlock CLI | `test_login_protection.py` (CLI) | OK |
| LOGIN-7 | login burst; register cap; Nginx layer [MANUAL] | `TestRateLimits` (12 tests); `test_nginx_config_doc.py` (map + `limit_req` + per-worker note); live burst test is 4.31 | OK / MAN-PENDING (live nginx) |
| LOGIN-8 | missing payload; valid; replay & expiry; tampered | `test_captcha.py` (35 tests, payloads solved with the real `altcha` lib); PG replay path | OK / PG |
| LOGIN-9 | invalid fields; legacy username; duplicate | `test_login_protection.py` | OK |

### session-security (units a, d)
| Req | Scenarios | Evidence | Result |
|---|---|---|---|
| SESS-1 | production cookie; development cookie; remember config; HTTPS behind Nginx [MANUAL] | `test_session_cookies.py` (32 tests) | OK / MAN-PENDING (4.32) |
| SESS-2 | defaults; explicit opt-in | `test_run_entry.py` | OK |
| SESS-3 | rotated key | `test_session_security.py` | OK |

### api-v1 (unit e)
| Req | Scenarios | Evidence | Result |
|---|---|---|---|
| API-1 | unknown path + browser Accept; wrong method; unhandled exception | `test_api_v1.py`; the unhandled-exception test registers its route on the app, not on the blueprint, so the blueprint handler is unexercised | OK, OK, PARTIAL (W5) |
| API-2 | healthy; DB down -> 503 | `test_api_v1.py` | OK |
| API-3 | altcha; none | `test_api_v1.py` | OK |
| API-4 | anonymous; logged in | `test_api_v1.py` | OK |
| API-5 | success; 5 wrong then 429; missing fields; CSRF | `test_api_v1.py` | OK |
| API-6 | logout; anonymous 401 | `test_api_v1.py` | OK |
| API-7 | created; duplicate 409; captcha missing | `test_api_v1.py` | OK |
| API-8 | browser 404 HTML; `*/*` JSON; no Accept 302; JSON client 401 | `test_error_negotiation.py` (37); I also ran these four requests by hand against an in-memory app and got the same results | OK |

### ci-pipeline (units a, b, e)
| Req | Scenarios | Evidence | Result |
|---|---|---|---|
| CI-1 | workflow scan | `test_ci_workflows.py::TestNoApplicationSecretsInCi` | OK |
| CI-2 | versions | `TestPinnedTooling` | OK |
| CI-3 | green run [GH-CI] | `TestTestJob`; `gh run list`: CI Pipeline success on PR #15 and on `main` after merge | OK / CI |
| CI-4 | migration steps [PG-CI]; workflow shape | `TestMigrationsJobShape`, `TestMigrationsPostgresJob`; `migrations-pg` job SUCCESS on PR #15 (PG 18) | OK / CI |
| CI-5 | no frontend yet [GH-CI]; guard present | `TestFrontendPlaceholderJob`; `frontend` check SUCCESS. The job is not "skipped": its steps are (step-level `hashFiles`, per R10) | PARTIAL (W3, accepted by R10) |
| CI-6 | permissions | `TestLeastPrivilege` | OK |
| CI-7 | files gone | `TestRepositoryHygiene`; I confirmed `package.json`, `package-lock.json`, `diagnose.py` are not tracked | OK |
| CI-8 | docs review [MANUAL]; versions grep | `test_docs.py` (77 tests: versions equal `requirements.txt`, tree paths exist, env vars, gunicorn command equals the service unit); prose checked by me in 5.3 | OK / MAN-PENDING (5.20 sign-off) |

### landing-feeds (unit d)
| Req | Scenarios | Evidence | Result |
|---|---|---|---|
| LAND-1 | hit; expiry; independent; public; TTL 0 | `test_landing_cache.py` (27 tests; TTL default 300 per R12) | OK |

**Compliance summary**: 178 / 184 scenarios compliant with passing evidence (this includes 5 PG-CI scenarios proven in the PG lane and CI, and 3 MANUAL scenarios already done or automated); **2 PARTIAL** (API-1 unhandled exception, CI-5 no-frontend wording); **4 MANUAL pending** (LOGIN-5 timing, LOGIN-7 live Nginx burst, SESS-1 HTTPS behind Nginx, CI-8 review sign-off); 0 failing; 0 untested.

---

## 5. Correctness, Coherence and extra checks

### 5.1 Coherence with design.md (D1-D22) and Reconciliation R1-R15

| Decision | Followed? | Notes |
|---|---|---|
| D1/D2 env + fail-fast (R13, R15) | Yes | `ConfigError(RuntimeError)`; digests for the denylist; I confirmed `RB_ENV=production` with no env and `RB_ENV=staging` fail with clear messages |
| D3-D9 Alembic layout, baseline, backup, cast | Yes | revisions `0001`, `0002`, `0003`, `0004`, `0004a`, `0005`; legacy SQL under `migrations/legacy_sql/`; `instance/` ignored |
| D10 `is_blocked` + `is_active` property (R1) | Yes | spec wording differs, see W3 |
| D11 `promote/demote` + aliases (R2) | Yes | |
| D12 pricing (R5: falsy = missing) | Yes | |
| D13 images | Yes | `card_image_folder`, `card_image_path` (realpath + commonpath) |
| D14 CSRF, no expiry, API not exempt | Yes | no `csrf.exempt` anywhere in `app/` |
| D15 lockout (R3 count-based, R4 blocked==invalid) | Yes | orchestrator decisions followed; no `lockout_level` column |
| D16 ALTCHA + `rbcaptcha_used` (R11: 5 min) | Yes | altcha 2.3.0 PoW v1 API, widget vendored with sha256 recorded |
| D17 clock, D18 `wants_json`, D19 deck lookups | Yes | |
| D20 PG lane | Yes | `postgres` marker; DB name must contain `test` |
| D21 pins | Yes | resolved with no pin changes |
| D22 landing cache (R12: 300 s) | Yes | design says 900 s; R12 overrides |
| PG lane moved to unit b (orchestrator decision) | Yes | `migrations-pg` job on `postgres:18` |
| R8 `run:app` + `wsgi.app` alias | Yes | |
| R9 DB URL inline in `run:` | Yes | |
| R10 `hashFiles` at step level | Yes | CI-5 wording deviates, accepted |
| R14 JSON 401 only from unit e | Yes | |

### 5.2 Dead or untested production code
`app/api/v1/__init__.py:_any_error` (blueprint-level `Exception` handler) is never executed in the suite; the app-level handlers produce the same envelope, so behavior is correct today, but the blueprint handler is unproven.

### 5.3 CI-8 prose claims (manual item 5.20), checked by me against code
README/AGENTS state: lockout 5 failures / 15 min doubling to 24 h (`config.py`: 5 / 15 / 1440, OK); ALTCHA 5 min (`ALTCHA_EXPIRE_SECONDS=300`, OK); landing cache 300 s (OK); `gunicorn --workers 3 ... run:app` (matches `docs/riftbound.service`, enforced by test); admin CLI list (`promote|demote|block|unblock|set-password|list|unlock` + aliases, matches `app/cli/users.py`); `python run.py` on `127.0.0.1:5000` (OK). No wrong version, count or command found. Rate limits `10/minute;50/hour` and `5/hour` are in `app/services/auth.py` constants and tested.

---

## 6. Proposal Success Criteria walk (task 5.22)

| Criterion | Status | Evidence |
|---|---|---|
| No credentials in code; start outside dev/test without env fails clearly | OK | grep 0 hits; `RB_ENV=production` no env -> `ConfigError: SECRET_KEY is missing; DATABASE_URL is missing`; `staging` -> lists allowed values |
| `flask db upgrade head` builds schema on empty SQLite and PG; dev stamped + upgraded; drift clean; legacy dropped with backup; FK -> `rbusers(username)` | OK (dev part user-verified) | SQLite tests + 30 PG tests (PG 16.2 here, PG 18 in CI); dev rollout per 2.34, 3.37, 4.33 (not re-verified; dev DB untouched by design) |
| `rbcol_quantity` integer, numeric sort | OK | `TestNumericSort`, migration 0003 |
| Authorization matrix classifies every URL rule; non-admin 403 on set/card changes and all `price/*`; traversal rejected | OK | `test_authz_matrix.py` (76 rules), `test_access_control.py`, `TestUpload` |
| Shared deck uses viewer's collection; removed deck routes 404; duplicate email 4xx | OK | `test_deck_viewing.py`, `test_profile.py` (409) |
| Missing CSRF token -> 400; 6th failed login locks (Retry-After); register without ALTCHA rejected | OK | `test_csrf.py`, `test_login_protection.py`, `test_captcha.py` |
| `/api/v1/health` 200 `{success,data}`; protected API call without session -> JSON 401; browser 404 -> HTML | OK | `test_api_v1.py`, `test_error_negotiation.py`; also reproduced by hand |
| CI green on Python 3.12 incl. PG job; 93 baseline + new tests pass; strict TDD per unit | OK, with W2 | `gh`: PR #15 `test`, `migrations-pg`, `frontend` SUCCESS; main push SUCCESS; 1211/1211 pass |

---

## 7. Issues

### CRITICAL (must fix before archive)
None.

### WARNING (should fix / decide)
- **W1. Manual verification still open for four spec scenarios.** LOGIN-7 live Nginx burst and LOGIN-5 timing sample (4.31), SESS-1 Secure cookie and Referer check behind HTTPS (4.32), both blocked on the CT 102 Nginx repoint to port 5000; CI-8 review sign-off (5.20); also 1.24 and the optional 0.4/0.5. The code and docs paths are automated and green; only the live-environment confirmation is missing. They do not block archive if the user accepts them as follow-ups.
- **W2. No formal apply-progress / "TDD Cycle Evidence" artifact.** In openspec mode the evidence is embedded in `tasks.md` notes (46 RED, 59 GREEN, 5 CHAR, each GREEN names its RED; failure reasons recorded). A strict reading of Strict TDD verify would escalate this to CRITICAL. I rated it WARNING because every referenced test exists, passes, is mutation- or red-checked where noted, and the process was auditable. The orchestrator may prefer to write a short `apply-progress.md` summary before archive.
- **W3. Specs are not synced with the as-built decisions.** Delta specs still say `is_active` column (ACL-1, ACL-2; built as `is_blocked` + property, R1), `make-admin`/`revoke-admin` as canonical (ACL-6; built as aliases, R2), `wsgi`-related text, CI-5 "job skipped" (the job runs green with Node steps skipped, R10), LAND-1 and the PRC header 0 semantics. `openspec/specs/` is empty, so archive should merge the deltas with the as-built wording (R1-R15 applied) to avoid a main spec that contradicts the code.
- **W4. Stale checkboxes in `tasks.md`.** 0.3, 0.7, 0.8 are done in practice; 5.19 now has CI evidence (PR #15 and `main`); 5.22 is this report. State file said `apply: in_progress` and `verify: pending`.
- **W5. Blueprint-level API error handler is unexercised.** The API-1 "unhandled exception" test raises from a route added to the app, so `app/api/v1/__init__.py:_any_error` (lines 22-24) is dead in tests. Behavior is right because the app-level handler gives the same envelope, but the scenario says "an API route" and the blueprint handler could regress unnoticed.

### SUGGESTION
- **S1.** Add one test that registers the raising route on the `api_v1` blueprint (or drop the blueprint handler if redundant) to close W5.
- **S2.** Tighten the loose assertions `status_code in (200, 404)` in `test_templates_csrf.py:73` (split the `no-such-page` case from the real pages) and `in (200, 302)` in `test_login_protection.py:335`.
- **S3.** In `test_authz_matrix.py` assert that each of P/U/A has at least one rule, so a future misclassification cannot make a class vacuous.
- **S4.** Coverage of legacy modules (`price.py` 48 %, `cardmarket_loader.py` 34 %, `riot_scraper.py` 45 %) is low but pre-existing; schedule characterization tests when F1+ touches them.
- **S5.** Keep recommending 0.4 (rotate the DB password and `SECRET_KEY`; firewall port 8000) since the old values remain in public git history; open design question 1 (5th failed attempt answers INVALID, the 6th LOCKED) is consistent with the spec scenarios and the success criterion but could be stated explicitly in the main spec at archive.

---

## 8. Verdict

**PASS WITH WARNINGS.** 1211/1211 tests pass (1181 default lane + 30 on PostgreSQL), CI is green on PR #15 and on `main` (test, migrations-pg on PG 18, frontend), bandit shows no medium/high issues, and every one of the 74 requirements has passing evidence. No CRITICAL issue. Before archive: sync the specs with R1-R15 (W3), optionally write an apply-progress summary (W2), tick the stale tasks (W4), and let the user close or defer the Nginx-dependent manual checks 4.31/4.32 and the CI-8 sign-off 5.20 (W1).
