# F1-close: Record F1 results, verify against the F1 specs and archive the change

| Field | Value |
|---|---|
| Phase / unit | F1 / close |
| Branch | `chore/f1-close` (from up-to-date `main`) |
| Depends on | PR #24 merged (done). F1-g merged first if the owner chose to do it (see Open questions). |
| Size forecast | ~600-900 changed lines, almost all Markdown moved or merged under `openspec/` (no application code) |
| Risk | `Risk: item 3 (rewrites openspec/specs, the contract later requirements are checked against)` |
| TDD | Not applicable to the Markdown work. Run the full lanes once at the end: `venv/bin/pytest`; `cd frontend && npm run lint && npm run typecheck && npx vitest run && npm run build && npm run check:dist` |
| Save as | `docs/requirements/F1/F1-close.md` (already in the repo) |

## Objective

Close phase F1 the same way F0 was closed: every task of `openspec/changes/f1-app-shell/tasks.md` is
either checked with evidence or explicitly deferred, a verification report maps the F1 requirements to
tests or manual results, and the F1 delta specs become part of `openspec/specs/` (the reference contract
for F2 onwards). After this, `openspec/` is a read-only archive plus the merged contract.

## Read first

- `AGENTS.md`, `docs/knowledge/conventions.md`, `docs/knowledge/state.md`
- The F0 precedent: `git show --stat 8944e18` (commit "chore(openspec): archive f0-foundation; main specs
  as source of truth") and `openspec/changes/archive/2026-10-19-f0-foundation/{verify-report.md,archive-report.md,state.yaml}`.
  Follow the same structure and conventions for the merge of ADDED / MODIFIED requirements.
- `openspec/changes/f1-app-shell/` (proposal, design, `specs/<capability>/spec.md`, `tasks.md`, `state.yaml`)
- `openspec/specs/` (14 capabilities from F0)

## Scope

In:
- Tick or annotate the open tasks of `openspec/changes/f1-app-shell/tasks.md` with the evidence below.
- Write `verify-report.md` for F1.
- Merge the F1 delta specs into `openspec/specs/` and archive the change folder.
- Update `docs/knowledge/state.md` and `docs/knowledge/specs-index.md`.

Out:
- Any application code change. If verification finds a real defect, do not fix it here: list it in the
  verify report under "Defects" and in `state.md` "Follow-ups" so the planner writes a fix requirement.
- Unit g work (that is `F1-g-hardening.md`).

## Specs

S1. Every unchecked task in `openspec/changes/f1-app-shell/tasks.md` ends in exactly one of these states,
    with its evidence written in the task's parentheses (same style as the checked tasks):
  - checked `[x]` with evidence, or
  - left unchecked and prefixed `DEFERRED (<where>)`, for example `DEFERRED (owner, iPhone not available yet)`.
S2. Evidence to record (owner results of 2026-10-21 and facts already established):
  - 0.5, 0.6: checked — F1 units deployed after each merge; units branched from updated `main`.
  - 1.39 (logo trace) and 1.50 / 5.41 (background default 100, blur, darkening): checked — "owner: the
    logo is fine; the only complaint was the zoom, fixed in unit a/e; default 100 kept" (adjust to the
    exact wording of the owner's confirmation recorded in Open questions).
  - 4.41: FAUTH-11 cross-app session — checked only if the owner confirms the manual check listed in
    "After merge"; otherwise `DEFERRED (owner)`.
  - 4.42, 5.43, 6.35: checked — PR checkpoints merged as PRs #22, #23 and #24.
  - 5.42: checked — deployed on dev after PR #23; Jinja pages show "Rift Manager" and the "Nueva app" link.
  - 6.5: checked — "favicon: simplified mark approved by the owner on 2026-10-21".
  - 6.8 and 6.27: checked — "Android Chrome install OK: name, icon (maskable) and standalone window".
  - 6.29: checked — "desktop install OK in Chrome and Edge".
  - 6.33: checked — "remember-me: still signed in after closing the installed app until the next day".
  - 6.25: checked — "frontend job green on PR #24".
  - 6.30 and 6.31: checked — "automated live check 2026-10-21 (Playwright against the HTTPS dev URL),
    19/19: worker scope /riftbound/app/, Jinja page not controlled, offline deep link opens the shell
    with the banner, banner removed online".
  - 6.26: `DEFERRED (owner, Lighthouse)` unless F1-g recorded Lighthouse results; note "Chromium
    installability errors: none (live, 2026-10-21)".
  - 6.28: `DEFERRED (owner, iPhone Safari to test later)`; add a line for macOS: `DEFERRED (owner, Mac to test later)`.
  - 6.32: `DEFERRED (owner, observe the update prompt at the next deploy of a new build; verified locally in Chromium)`.
  - 6.34: `DEFERRED (not run on dev on purpose: it uninstalls the worker on the owner's devices; verified locally in Chromium)`.
  - Unit 7 (7.1-7.7): checked with F1-g evidence if F1-g was merged; otherwise every task
    `DEFERRED (F1-g not done; CSP enforcing is planned for F12)`.
S3. `openspec/changes/f1-app-shell/verify-report.md` exists and contains: date, commit verified, test
    counts from the full lanes run in this unit, a table with one row per F1 requirement ID across all
    capabilities in `openspec/changes/f1-app-shell/specs/` (ID, title, evidence: test file::test name or
    manual task number, status PASS / PASS (manual) / DEFERRED / FAIL), a "Defects" section (may be
    "none") and a "Deferred" section listing every DEFERRED item.
  - Known spec/code mismatches to resolve in the report (amend the spec text when the code is right, or list
    as a defect): I18N-4 says the key is `errors.<code>`, the code uses `errors:code.<code>`; PWA-3 says "both"
    background images, the build precaches three (1280, 1920, portrait); F0 CI-5 still describes the
    placeholder frontend job; `state.yaml` says `apply: pending`; `tasks.md` names branches `feat/f1-a`..
    while the real ones are `feat/f1a-frontend-toolchain`..`feat/f1f-pwa` (note it in the archive report).
  - Each test reference must exist: check with `grep -rn` (backend `tests/`, frontend `frontend/src`,
    `frontend/scripts`); a requirement without a test and without a manual result is FAIL, not PASS.
S4. Delta specs merged into `openspec/specs/` following the F0 precedent:
  - ADDED capabilities become new `openspec/specs/<capability>/spec.md` files.
  - MODIFIED requirements replace the matching requirement blocks in the existing capability spec; ADDED
    requirements inside an existing capability are appended; REMOVED ones are deleted.
  - No delta markers (ADDED/MODIFIED/REMOVED headings) remain in `openspec/specs/`.
  - Every requirement ID of the F1 deltas appears exactly once under `openspec/specs/` (check with a grep
    count and report it).
S5. The change folder is moved with `git mv` to `openspec/changes/archive/<YYYY-MM-DD>-f1-app-shell/`
    (date of the commit) with `archive-report.md` (what was merged where, counts, deferred items) and
    `state.yaml` updated (`apply: done`, `verify: done`, `archive: done`, date).
S6. `openspec/roadmap.md` gets one line under its title: "Superseded on 2026-10-21 by
    `docs/knowledge/roadmap.md` (Claude Project + gentle-shell workflow); kept for history."
S7. `docs/knowledge/state.md`: F1 row becomes "Done" with the PR number placeholder of this unit, the
    "Pending checks" table keeps only the DEFERRED owner checks, and the Units table marks F1-close done.
    `docs/knowledge/specs-index.md` lists the F1 capabilities under `openspec/specs/` (no longer as deltas).
S8. Line endings of every touched file are preserved (check `git diff --stat` and `git ls-files --eol`
    on touched files before committing).

## API / data contract

none

## UI

none

## Acceptance criteria

- [ ] AC1 No `- [ ]` task in the archived `tasks.md` lacks a `DEFERRED (...)` prefix (S1, S2): `grep -n '^- \[ \]' .../tasks.md | grep -v DEFERRED` prints nothing.
- [ ] AC2 `verify-report.md` has one row per F1 requirement ID and every cited test exists (S3).
- [ ] AC3 Requirement ID counts: each F1 ID appears once in `openspec/specs/`; no ADDED/MODIFIED/REMOVED markers there (S4).
- [ ] AC4 `openspec/changes/f1-app-shell/` no longer exists; the archive folder has `archive-report.md`, `verify-report.md` and the updated `state.yaml` (S5).
- [ ] AC5 Full lanes green (no code changed, but tests read docs: `tests/test_docs.py`, `tests/test_frontend_contracts.py`).
- [ ] AC6 `docs/knowledge/state.md`, `docs/knowledge/specs-index.md` and `openspec/roadmap.md` updated (S6, S7).

## Delivery

- Commits: one for tasks + verify report, one for the spec merge + archive move, one for docs/knowledge.
- Push and PR when the owner says so. PR title: `chore(openspec): close and archive F1 app shell`.
  PR body: summary, counts (requirements PASS / manual / deferred / fail), list of deferred owner checks.

## After merge

- No deploy needed (documentation only).
- Owner checks still open after this unit (copy them into the PR body):
  1. iPhone Safari: "Más" → "Instalar app", follow the 3 steps; icon without black corners, name "Rift Manager", opens full screen.
  2. Mac: install from Safari ("Añadir al Dock") or Chrome; own window, correct icon.
  3. FAUTH-11: sign in in the app, open `/riftbound/` (Jinja) — still signed in; sign out there, go back to
     the app — it shows the login screen.
  4. Update prompt at the next deploy of a new frontend build: toast "Nueva versión disponible." with
     "Actualizar"; no reload by itself.

## Open questions

- CONFIRM: is F1-g done before this unit (recommended: yes, it is small and closes unit 7) or deferred?
- CONFIRM: the owner's exact confirmation for 1.39 / 1.50 / 5.41 (logo trace OK, background default 100
  with the current blur and darkening OK).
