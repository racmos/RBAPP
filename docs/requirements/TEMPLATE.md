# <ID>: <short title>

<!--
Template for one unit of work handed to gentle-shell (pi + gentle-pi, ODD workflow).
One requirement = one feature branch = one PR (gentle-shell may chain PR slices when it
grows past ~400 authored lines). gentle-shell copies the "Specs" of this document verbatim
into odd/tasks/<feature>.md, so write exact strings, codes, payloads and examples here:
anything not written down will be invented or asked.
Delete these comments before handing it over. "Open questions" must be empty.
-->

| Field | Value |
|---|---|
| Phase / unit | F<n> / <letter> |
| Branch | `feat/f<n><letter>-<slug>` (from up-to-date `main`) |
| Depends on | <merged PRs or units, or "none"> |
| Size forecast | ~<N> authored lines (tests and docs included) |
| Risk | `Risk: none` or `Risk: item <1-6> (<reason>)` (gentle-shell Task Size list: 1 data/migrations, 2 security/auth, 3 contracts others consume, 4 concurrency, 5 delivery/CI/deps, 6 no test would catch it) |
| TDD | ON (strict). Runners: `venv/bin/pytest` (backend), `cd frontend && npx vitest run` (frontend) |
| Save as | `docs/requirements/F<n>/F<n>-<x>-<slug>.md` (commit this document verbatim in the first commit if it is not in the repo yet) |

## Objective

<One paragraph: the outcome for the user, not the implementation.>

## Read first

- `AGENTS.md` (project rules: they apply to every line of this unit)
- `docs/knowledge/conventions.md`
- <specific code paths, specs in `openspec/specs/<capability>/spec.md`, design notes>

## Scope

In:
- <bullets>

Out (do not do, even if tempting):
- <bullets>

## Specs

<!-- Numbered, testable, verbatim-quotable. Use MUST/SHOULD. Include exact UI copy in ES and EN,
exact error codes, status codes, payload shapes, boundaries and examples. One behaviour per item. -->

S1. <Requirement.>
  - Example: Given <state>, when <action>, then <observable result>.
S2. ...

## API / data contract

<!-- Endpoints (method, path, auth P/U/A, request, response envelope `{success,data,meta}`, error codes),
migrations (revision name, up/down, data backfill), model changes. Write "none" if none. -->

## UI

<!-- Screens, routes under /riftbound/app/, mobile (<860 px) vs desktop (>=1240 / >=1600) layout,
states (loading, empty, error, offline), exact strings ES/EN (i18n keys), a11y notes. "none" if none. -->

## Acceptance criteria

- [ ] AC1 <verifiable check, tied to a test or a command> (S1)
- [ ] ACn Full lanes green: `venv/bin/pytest`; `cd frontend && npm run lint && npm run typecheck && npx vitest run && npm run build && npm run check:dist`
- [ ] ACn `docs/knowledge/state.md` updated (what changed, PR number placeholder, new follow-ups)
- [ ] ACn `AGENTS.md` / `docs/*.md` updated where this unit changes structure, commands, endpoints or conventions

## Delivery

- Conventional Commits; commit messages end with the attribution lines the session supplies.
- Push and PR only when the user says so. PR title: `<type>(<scope>): <summary> (F<n> unit <x>)`.
  PR body: summary, specs → tests map (S# → test file::name), manual checks for the user, rollback.
- Never merge. The user merges.

## After merge (user asks gentle-shell, or does it)

- Deploy to dev with `docs/knowledge/ops-runbook.md` (backup first when there is a migration).
- Live checks: <URLs and expected results>.
- Manual checks for the user: <device or visual checks, or "none">.

## Open questions

none
