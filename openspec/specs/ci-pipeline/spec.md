# ci-pipeline Specification

Source: change f0-foundation (archived 2026-10-19)

> Tags: `[a]`..`[e]` = delivery unit of change f0-foundation. `[GH-CI]` = only observable in GitHub Actions; `[PG-CI]` = runs in the PostgreSQL CI job; `[MANUAL]` = review. Untagged scenarios are pytest-testable (workflow YAML parsed with PyYAML; file-system checks). Also holds the repo-hygiene and documentation requirements of unit e, which the proposal did not assign to a capability.

## Requirements

### Requirement: CI-1 No application secrets in CI [a]

Workflows MUST NOT pass `DATABASE_URL`, `SECRET_KEY` or `FLASK_ENV` (nor `secrets.*` values for them) to the test job; tests self-configure.

#### Scenario: Workflow scan
- GIVEN `.github/workflows/*.yml`
- WHEN parsed
- THEN no `env` block (workflow, job or step) defines those names and no `secrets.DATABASE_URL`/`secrets.SECRET_KEY` appears

### Requirement: CI-2 Single pinned Python and tooling [e]

CI and security workflows MUST use Python 3.12, a `.python-version` file MUST say `3.12`, and bandit MUST be version-pinned.

#### Scenario: Versions
- GIVEN the workflows and `.python-version`
- WHEN parsed
- THEN every `python-version` is `'3.12'`, the file reads `3.12`, and the bandit install line has `==<version>`

### Requirement: CI-3 Test job [e]

On push to `main` and on pull requests to `main`, CI MUST install `requirements.txt` and run `pytest` with coverage. Any failing test MUST fail the job. The 93 baseline tests plus new tests MUST pass.

#### Scenario: Green run [GH-CI]
- GIVEN a PR branch
- WHEN CI runs
- THEN the test job passes on Python 3.12 and reports coverage

### Requirement: CI-4 PostgreSQL migrations job [e]

A CI job MUST start a PostgreSQL service (major version at least 16, SHOULD match the dev major, 18) and: (1) `flask db upgrade head` on an empty DB; (2) `flask db check` clean; (3) `downgrade base` then `upgrade head`; (4) upgrade to the baseline, seed legacy rows (text quantities such as `'12'`, rows in `old1_rbusers`/`old_rbdecks`), then upgrade to head and verify the data. The job MUST fail on any step failure.

The `migrations-pg` job (service `postgres:18`) is delivered with unit b, not e, so the `[PG-CI]` scenarios of units b to d run in CI from unit b onward (R9). The database URL is defined inline in the `run:` commands, not in an `env:` block, which keeps CI-1 true.

#### Scenario: Migration steps [PG-CI]
- GIVEN the PostgreSQL service
- WHEN the job runs the four steps
- THEN all pass, including the `USING` cast of `rbcol_quantity` and the legacy backup file creation

#### Scenario: Workflow shape
- GIVEN `ci.yml`
- WHEN parsed
- THEN a job with a `postgres` service exists and its steps include `flask db upgrade`, `flask db check` and `flask db downgrade`

### Requirement: CI-5 Frontend placeholder job [e]

A frontend job MUST run only when `frontend/package.json` exists (guarded by `hashFiles`) and then run install (`npm ci`), lint, typecheck, `vitest run` and build with a pinned Node version (`.nvmrc`). While `frontend/` is absent the workflow MUST still succeed, with the job's Node steps skipped.

GitHub does not allow `hashFiles` in a job-level `if`, so the guard is a step-level `if: ${{ hashFiles('frontend/package.json') != '' }}` on every Node step (R10). The `frontend` job therefore runs and ends green with its Node steps skipped; it is not reported as a skipped job.

#### Scenario: No frontend yet
- GIVEN no `frontend/package.json`
- WHEN CI runs [GH-CI]
- THEN the `frontend` job is green with every Node step skipped and the workflow is green

#### Scenario: Guard present
- GIVEN `ci.yml`
- WHEN parsed
- THEN the `if` of the frontend job's Node steps references `hashFiles('frontend/package.json')`

### Requirement: CI-6 Least-privilege permissions [e]

Every workflow MUST declare `permissions:` explicitly: `contents: read` by default; `contents: write` only for the job that creates a release.

#### Scenario: Permissions
- GIVEN each workflow
- WHEN parsed
- THEN top-level `permissions` exists, `ci.yml` and `security.yml` grant only `contents: read`, and only the release job has `contents: write`

### Requirement: CI-7 Repository hygiene [e]

`package.json`, `package-lock.json` and `diagnose.py` MUST be removed. `.gitignore` MUST include `node_modules/`, `frontend/dist/` and `.vite/`.

#### Scenario: Files gone
- GIVEN the repo after unit e
- WHEN listed
- THEN none of the three files exist and the `.gitignore` entries are present

### Requirement: CI-8 Docs match reality [e]

`README.md` MUST document setup, environment variables, running, tests, migrations (`flask db`), the admin CLI and deployment. `AGENTS.md` MUST state the real stack versions (Flask 3.1.0, SQLAlchemy 2.0.36, Pydantic 2.10.5, pytest 8.3.4), the real structure (landing, services, api, migrations, `.github`, `openspec`), the `rbcm_*` tables, roles and CSRF rules, the API envelope, Alembic workflow and the production command (`gunicorn ... run:app`, 3 workers). It SHOULD NOT list skills that do not exist. Stale landing docs (`docs/riftbound-landing.service`, Nginx `/` to 8001) SHOULD be updated to the current topology.

#### Scenario: Docs review [MANUAL]
- GIVEN the final repo
- WHEN `README.md` and `AGENTS.md` are reviewed against the checklist above
- THEN every item is present and no stated version, count or command is wrong

#### Scenario: Versions grep
- GIVEN `AGENTS.md`
- WHEN searched
- THEN it contains `3.1.0`, `2.0.36`, `2.10.5` and `8.3.4` and does not list `fastapi-pro`
