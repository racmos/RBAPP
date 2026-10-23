# M-a: Test reset — remove the old suites, keep the authorization matrix and a startup smoke test

| Field | Value |
|---|---|
| Phase / unit | M (maintenance, outside the phases) / a |
| Branch | `chore/m-a-test-reset` (from up-to-date `main`) |
| Depends on | F1 closed (PRs #26 and #27 merged) — done |
| Size forecast | ~250 authored lines (two smoke test files, CI edit, docs). Deletions are not counted (~45 backend and ~85 frontend test files). |
| Risk | `Risk: item 5 (CI and test lanes change) + item 6 (removing the old suites removes their safety net: a regression in code they covered would not be caught)` |
| TDD | Not applicable to the deletions. The two smoke files characterize existing behaviour; prove they are not vacuous (S4). Runners: `venv/bin/pytest`, `cd frontend && npx vitest run`. |
| Save as | `docs/requirements/M/M-a-test-reset.md` (already in the repo) |

## Objective

Owner decision of 2026-10-22: the existing test suites were written for the old SDD cycle and are not kept.
From now on every unit writes the tests for what it builds (strict TDD stays). Only two guards survive:
the authorization matrix (every URL rule classified public / signed-in / admin, the most valuable check
while registration is open) and a startup smoke test in each lane, so CI still proves the app boots.
CI keeps every non-test check (lint, typecheck, build, `check:dist`, migrations round trip, bandit).

## Read first

- `docs/knowledge/decisions-2026-10-22.md` (owner decisions; the test reset is the first unit)
- `AGENTS.md` (sections "Testing", "Adding a New Route", "Database Changes"), `docs/knowledge/conventions.md`
- `.github/workflows/ci.yml`, `pytest.ini`, `tests/conftest.py`, `tests/test_authz_matrix.py`
- `tests/test_run_entry.py::…::test_app_is_an_alias_of_application` (S2 copies its environment setup)
- `frontend/vite.config.ts` (`test.include`), `frontend/src/test/` (`renderApp.tsx`, `msw/`, `setup.ts`),
  `frontend/src/auth/LoginPage.test.tsx` (S3 copies its setup) — read these BEFORE deleting anything
- `openspec/specs/ci-pipeline/spec.md` (CI-3, CI-4, CI-5)

## Scope

In:
- Delete the old backend and frontend test files; keep the test infrastructure.
- Two smoke test files; CI adjustment; spec amendment; docs and `state.md`.

Out (do not do, even if tempting):
- Any change to application code. If a smoke test fails, stop and report: do not "fix" the app here.
- Editing `docs/requirements/F2/…` to `F12/…` (the planner rewrites each requirement before handing it over).
- Editing `openspec/changes/archive/**` (history).
- Deleting `tests/conftest.py`, helpers, fixtures or `frontend/src/test/` helpers (future units reuse them).

## Specs

S1. Record the baseline first: run `git rev-parse origin/main` when creating the branch and keep the SHA;
    it is "the last commit with the old suites" used in S7 and S9.
S2. Backend. After this unit, `git ls-files 'tests/test_*.py'` lists exactly:
    `tests/test_authz_matrix.py` and `tests/test_smoke.py`.
  - Delete every other `tests/test_*.py`.
  - Keep unchanged: `tests/__init__.py`, `tests/conftest.py`, `tests/auth_helpers.py`,
    `tests/migration_helpers.py`, `tests/snapshot_utils.py`, `tests/fixtures/`, `pytest.ini` (keep the
    `postgres` marker for future tests).
  - `tests/test_authz_matrix.py` stays byte-identical and green. Verify first that it imports only from
    `tests.conftest` and uses only conftest fixtures (`app`, `client`, `authenticated_client`, `admin_client`,
    `spa_app`, `make_user`); if it needs anything from a file being deleted, stop and report.
  - New `tests/test_smoke.py` with exactly these two tests:
    - `test_the_app_starts_and_reports_healthy`: with the `app` and `client` fixtures,
      `GET /riftbound/api/v1/health` → status 200, JSON `success` is `true`, `data.status == "ok"`,
      `data.db == "ok"`.
    - `test_the_wsgi_entry_point_builds_the_app`: same environment setup as
      `test_run_entry.py::…::test_app_is_an_alias_of_application` (`clean_env`, `RB_ENV=development`,
      `DATABASE_URL=sqlite:///:memory:`); `runpy.run_path` of `wsgi.py` → `application` is a `Flask`
      instance and `app is application`.
S3. Frontend. After this unit, the only Vitest file is `frontend/src/app/smoke.test.tsx`:
    `git ls-files 'frontend/*.test.ts' 'frontend/scripts/*.test.ts' 'frontend/src/**/*.test.ts' 'frontend/src/**/*.test.tsx'`
    prints exactly that path.
  - Delete every other `*.test.ts` / `*.test.tsx` (this includes `frontend/pwa-options.test.ts`,
    `frontend/scripts/check-dist.test.ts`, `frontend/scripts/icons.test.ts`, `src/i18n/parity.test.ts`
    and the `*.test.ts` files inside `src/test/`).
  - Keep every non-test file of `frontend/src/test/` (setup, MSW handlers, `renderApp`, stubs, helpers),
    `vite.config.ts` test settings, `scripts/check-dist.mjs` and `scripts/icons.mjs`.
  - `smoke.test.tsx`, one test `the app boots on the login screen`: render the app at
    `/riftbound/app/login` with the same helper, providers and MSW handlers the current
    `src/auth/LoginPage.test.tsx` uses (signed-out session); assert that the field labelled "Usuario"
    (`auth.json` → `login.username`, Spanish is the default test language — verify in `src/test/setup.ts`
    or `src/test/i18n.tsx`; if the test language is English, use "Username" from the `en` catalog) and the
    button "Entrar" are visible.
S4. Not vacuous: before committing, break each smoke test once on purpose (for example, request
    `/riftbound/api/v1/healthz`; render `/riftbound/app/does-not-exist`), watch it fail, revert. Say so in
    the PR body, with the failure line.
S5. CI (`.github/workflows/ci.yml`):
  - `test` job: unchanged (`pytest` with coverage runs the authorization matrix and the backend smoke tests).
  - `migrations-pg` job: keep the step "Migrations round trip (upgrade, check, downgrade to base, upgrade)";
    delete the step "PostgreSQL tests" (`pytest -m postgres` would select no test and exit with code 5).
    Update the job comment accordingly.
  - `frontend` job: unchanged (`npx vitest run` runs the frontend smoke test; lint, typecheck, build,
    `check:dist` and the self-destroying worker check stay).
  - `security.yml`: unchanged.
S6. Amend `openspec/specs/ci-pipeline/spec.md`, each change marked "(amended 2026-10-22, M-a)":
  - CI-3: replace "The 93 baseline tests plus new tests MUST pass." with "Every test in the suite MUST pass."
  - CI-4: keep (1)–(3); remove (4) (seed legacy rows and verify after upgrade). Add: "The baseline data
    migration was verified when F0 was archived (2026-10-19); the PostgreSQL-marked tests were removed by
    M-a. A future unit that needs PostgreSQL-only behaviour adds `postgres`-marked tests and re-adds the
    `pytest -m postgres` step."
  - CI-5: delete the last sentence ("The test that previously asserted … without a replacement.").
S7. Test policy. Add this paragraph verbatim as the first paragraph of AGENTS.md → "Testing" and of
    `docs/knowledge/conventions.md` → its testing section (create the section if there is none), with
    `<sha>` replaced by the S1 value:

    > **Test policy (since 2026-10-22, unit M-a).** The pre-existing suites were removed. Only
    > `tests/test_authz_matrix.py` (every URL rule classified P/U/A) and the startup smoke tests
    > (`tests/test_smoke.py`, `frontend/src/app/smoke.test.tsx`) remain. Strict TDD still applies: every
    > unit writes the tests for the behaviour it adds or changes. When a unit touches an area whose old
    > guard was removed, it re-creates that guard in its smallest form: a migration → a round-trip and
    > model/schema drift test for that revision (`tests/migration_helpers.py`); new UI strings → the ES/EN
    > parity test; a new error code → the backend/frontend catalog test; a new legacy link → the
    > legacy-routes check against the Flask `url_map`; a new pinned version → the pin check. The last
    > commit with the old suites is `<sha>`; recover any file with `git show <sha>:<path>`.

S8. Remove references to deleted test files. In `AGENTS.md`, `README.md`, `docs/knowledge/*.md` (except
    history lines in `state.md`), `docs/frontend.md`, `docs/migrations.md`, `docs/requirements/TEMPLATE.md`,
    `docs/requirements/README.md`, `docs/knowledge/workflow.md` and `docs/knowledge/project-instructions.md`:
    every sentence that names a deleted test file keeps its rule and drops the file name, or becomes
    "the unit adds a test for it" (S7). Mentions of `tests/test_authz_matrix.py` stay.
  - Check: `grep -rnE "tests/test_[a-z_]+\.py|[A-Za-z/_.-]+\.test\.tsx?" AGENTS.md README.md docs/knowledge docs/frontend.md docs/migrations.md docs/requirements/TEMPLATE.md docs/requirements/README.md`
    prints only `test_authz_matrix.py`, `test_smoke.py`, `smoke.test.tsx` and `state.md` history lines.
  - `docs/knowledge/specs-index.md`: add one line: "Test file names cited in `openspec/specs/` and in the
    archive are historical evidence; the files were removed by M-a (2026-10-22). The requirement text still
    binds."
  - `docs/requirements/README.md`: set the M-a row to "Done (#<PR>)".
S9. `docs/knowledge/state.md`:
  - "Units" table: row `M-a | done | chore/m-a-test-reset / #<PR> | Old suites removed; kept authz matrix + smoke tests; baseline <sha>`.
  - Replace the test counts line of "Live on dev" with the new counts (pytest and vitest) and the baseline SHA.
  - "Known issues": remove the two flaky-test entries (Toast and `states.test.tsx`).
  - "Follow-ups": add "Guards to re-create when their area is touched: see the test policy (AGENTS.md → Testing)".
S10. Every touched file keeps its line endings (`git ls-files --eol` on touched files; AGENTS.md and README.md are CRLF).

## API / data contract

none

## UI

none

## Acceptance criteria

- [ ] AC1 `git ls-files 'tests/test_*.py'` prints exactly `tests/test_authz_matrix.py` and `tests/test_smoke.py`; infrastructure files of S2 still present (S2).
- [ ] AC2 The S3 `git ls-files` command prints exactly `frontend/src/app/smoke.test.tsx`; `frontend/src/test/` helpers still present (S3).
- [ ] AC3 Smoke tests proven non-vacuous, failure lines in the PR body (S4).
- [ ] AC4 Full lanes green: `venv/bin/pytest`; `cd frontend && npm run lint && npm run typecheck && npx vitest run && npm run build && npm run check:dist`. Record counts and durations in the PR.
- [ ] AC5 CI green on the PR: `test`, `migrations-pg` (round trip only), `frontend`, security workflow (S5).
- [ ] AC6 `ci-pipeline` spec amended; test policy paragraph in AGENTS.md and conventions.md; the S8 grep is clean; `specs-index.md` and `docs/requirements/README.md` updated (S6-S8).
- [ ] AC7 `docs/knowledge/state.md` updated (S9); line endings preserved (S10).

## Delivery

- Conventional Commits, suggested slices: (1) smoke tests (green before deleting anything);
  (2) delete backend tests + CI step; (3) delete frontend tests; (4) spec amendment + docs + state.md.
- Push and PR when the owner says so. PR title: `chore(tests): reset the test suites, keep authz matrix and smoke tests (M-a)`.
  PR body: summary, baseline SHA, files kept, counts before/after (before: pytest 1694 passed / 41 skipped, vitest 1189, per `state.md`), lane durations, S4 proof, rollback (`git revert` of the merge restores the suites).
- Never merge.

## After merge

- No deploy needed (no application change). Optionally redeploy to confirm nothing changed:
  `/riftbound/api/v1/health` answers 200.
- Manual checks for the owner: none.

## Open questions

none
