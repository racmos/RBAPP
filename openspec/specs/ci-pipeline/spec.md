# ci-pipeline Specification

Source: change f0-foundation (archived 2026-10-19); updated by change f1-app-shell (archived 2026-10-22)

> Tags: `[a]`..`[e]` = delivery unit of change f0-foundation. `[GH-CI]` = only observable in GitHub Actions; `[PG-CI]` = runs in the PostgreSQL CI job; `[MANUAL]` = review. Untagged scenarios are pytest-testable (workflow YAML parsed with PyYAML; file-system checks). Also holds the repo-hygiene and documentation requirements of unit e, which the proposal did not assign to a capability.
>
> F1 Tags: `[a]`..`[g]` = delivery unit of change f1-app-shell. `[GH-CI]` = only observable in GitHub Actions. Untagged scenarios are pytest-testable (workflow YAML parsed with PyYAML; file-system checks). CI-1 (no app secrets) and CI-6 (least privilege) keep applying to the new steps: the artifact upload needs no write permission.

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

On push to `main` and on pull requests to `main`, CI MUST install `requirements.txt` and run `pytest` with coverage. Any failing test MUST fail the job. Every test in the suite MUST pass. (amended 2026-10-22, M-a)

#### Scenario: Green run [GH-CI]
- GIVEN a PR branch
- WHEN CI runs
- THEN the test job passes on Python 3.12 and reports coverage

### Requirement: CI-4 PostgreSQL migrations job [e]

A CI job MUST start a PostgreSQL service (major version at least 16, SHOULD match the dev major, 18) and: (1) `flask db upgrade head` on an empty DB; (2) `flask db check` clean; (3) `downgrade base` then `upgrade head`. The job MUST fail on any step failure.

The baseline data migration was verified when F0 was archived (2026-10-19); the PostgreSQL-marked tests were removed by M-a. A future unit that needs PostgreSQL-only behaviour adds `postgres`-marked tests and re-adds the `pytest -m postgres` step. (amended 2026-10-22, M-a)

The `migrations-pg` job (service `postgres:18`) is delivered with unit b, not e, so the `[PG-CI]` scenarios of units b to d run in CI from unit b onward (R9). The database URL is defined inline in the `run:` commands, not in an `env:` block, which keeps CI-1 true.

#### Scenario: Migration steps [PG-CI]
- GIVEN the PostgreSQL service
- WHEN the job runs the three steps
- THEN all pass (amended 2026-10-22, M-a)

#### Scenario: Workflow shape
- GIVEN `ci.yml`
- WHEN parsed
- THEN a job with a `postgres` service exists and its steps include `flask db upgrade`, `flask db check` and `flask db downgrade`

### Requirement: CI-5 Frontend job [e]

(The heading is kept verbatim so the archive step can match and replace the F0 block; the job is no longer a placeholder after unit a, and the archive MAY rename it to "Frontend job".)

The `frontend` job MUST run `npm ci`, lint, typecheck, `vitest run` and build with the Node version from `.nvmrc`, and those steps MUST NOT be skipped (they are no longer guarded by `hashFiles('frontend/package.json')`, because `frontend/package.json` now exists). After a successful build the job MUST upload `frontend/dist` as a workflow artifact named `frontend-dist`. From unit f onward a manifest check step MUST verify that the built `manifest.webmanifest` exists and that its `name` is "Rift Manager", `id` is `/riftbound/`, `scope` is `/riftbound/` and `start_url` is `/riftbound/app/`, and the job MUST fail on mismatch. A failure in any step MUST fail the workflow. (amended 2026-10-22, M-a)

#### Scenario: Frontend steps run
- GIVEN `frontend/package.json` exists
- WHEN CI runs [GH-CI]
- THEN the `frontend` job executes install, lint, typecheck, test and build (none skipped) and is green

#### Scenario: Job shape
- GIVEN `ci.yml`
- WHEN parsed
- THEN the frontend job has steps for `npm ci`, lint, typecheck, `vitest run` and build, none of them with an `if` referencing `hashFiles('frontend/package.json')`, and Node comes from `.nvmrc`

#### Scenario: Artifact uploaded
- GIVEN a green frontend build
- WHEN the job finishes [GH-CI]
- THEN an artifact named `frontend-dist` containing `index.html` is available

#### Scenario: Artifact step declared
- GIVEN `ci.yml`
- WHEN parsed
- THEN the frontend job uses `actions/upload-artifact` with `name: frontend-dist` and `path: frontend/dist`, and the workflow still grants only `contents: read`

#### Scenario: Manifest check
- GIVEN a built `dist/manifest.webmanifest` with `name` "Riftbound Manager"
- WHEN the manifest check step runs [GH-CI]
- THEN the job fails; with the correct values it passes

#### Scenario: Placeholder test rewritten
- GIVEN `tests/test_ci_workflows.py`
- WHEN pytest runs after unit a
- THEN the former "does not need a frontend directory" assertion no longer exists, a test asserts that `frontend/package.json` exists and the job shape above, and the suite is green

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

### Requirement: CI-9 Frontend repository hygiene [a]

`frontend/dist/`, `node_modules/` and `.vite/` MUST remain ignored by git (CI-7) and `package-lock.json` MUST be committed. The `frontend-dist` artifact MUST NOT contain `.map` files with embedded secrets or `.env` files. The Python test lane MUST NOT require Node (HOST tests use a temporary dist).

#### Scenario: Ignored and locked
- GIVEN the repository
- WHEN `git check-ignore frontend/dist` runs and the tree is listed
- THEN `dist` is ignored and `frontend/package-lock.json` is tracked

#### Scenario: No Node in pytest
- GIVEN a runner without Node
- WHEN `pytest` runs
- THEN the SPA hosting tests pass using a temporary dist
