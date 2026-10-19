# Delta for ci-pipeline

> Tags: `[a]`..`[g]` = delivery unit of change f1-app-shell. `[GH-CI]` = only observable in GitHub Actions. Untagged scenarios are pytest-testable (workflow YAML parsed with PyYAML; file-system checks). CI-1 (no app secrets) and CI-6 (least privilege) keep applying to the new steps: the artifact upload needs no write permission.

## MODIFIED Requirements

### Requirement: CI-5 Frontend placeholder job [e]

(The heading is kept verbatim so the archive step can match and replace the F0 block; the job is no longer a placeholder after unit a, and the archive MAY rename it to "Frontend job".)

The `frontend` job MUST run `npm ci`, lint, typecheck, `vitest run` and build with the Node version from `.nvmrc`, and those steps MUST NOT be skipped (they are no longer guarded by `hashFiles('frontend/package.json')`, because `frontend/package.json` now exists). After a successful build the job MUST upload `frontend/dist` as a workflow artifact named `frontend-dist`. From unit f onward a manifest check step MUST verify that the built `manifest.webmanifest` exists and that its `name` is "Rift Manager", `id` is `/riftbound/`, `scope` is `/riftbound/` and `start_url` is `/riftbound/app/`, and the job MUST fail on mismatch. A failure in any step MUST fail the workflow. The test that previously asserted that `frontend/package.json` does NOT exist MUST be rewritten to assert the opposite and the new job shape; it MUST NOT be deleted without a replacement.
(Previously: a placeholder job whose Node steps were guarded by `hashFiles('frontend/package.json')` and skipped while `frontend/` was absent; no artifact; no manifest check.)

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

## ADDED Requirements

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
