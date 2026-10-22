# Archive Report: f1-app-shell

**Change**: f1-app-shell (roadmap phase F1 "App shell", delivery units a-g)
**Archive date**: 2026-10-22
**Artifact store**: openspec
**Verdict (verify-report.md)**: 67 requirements: 64 PASS, 1 PASS (manual), 2 DEFERRED (FAUTH-11, PWA-9), 0 FAIL. No defects.
**Status**: archived and closed. Folder moved with `git mv` to `openspec/changes/archive/2026-10-22-f1-app-shell/` in unit F1-close (`docs/requirements/F1/F1-close.md`).

---

## 1. Delivery

| Unit | Scope | PR | Branch |
|---|---|---|---|
| planning | exploration, proposal, delta specs, design, tasks | #17 | `docs/f1-planning` |
| a | frontend toolchain, tokens, background, brand SVG, CI frontend job | #20 | `feat/f1a-frontend-toolchain` |
| b | `spa_bp` serving `frontend/dist` at `/riftbound/app/` | #18 | `feat/f1b-spa-hosting` |
| c | migration `0006_user_prefs`, `GET`/`PATCH /me/prefs`, remember-me 30 days, API error codes | #19 | `feat/f1c-api-prefs` |
| fix | portrait background (map rotated 90 degrees) | #21 | `fix/f1-bg-portrait` |
| d | API client, router, login/register with ALTCHA, i18n ES/EN | #22 | `feat/f1d-frontend-auth` |
| e | app shell, navigation, "Más" sheet, Home hub, Interface page, Jinja rename and "Nueva app" link | #23 | `feat/f1e-app-shell` |
| f | PWA: manifest, icons, service worker, update toast, install item, offline shell, self-destroying rollback | #24 | `feat/f1f-pwa` |
| g | CSP report-only (`SPA_CSP`), axe sweep, precache de-duplication, deterministic Toast test | #26 | `feat/f1g-hardening` |

`tasks.md` names the branches `feat/f1-a` .. `feat/f1-g`; the real names are the ones in the table above.
`state.yaml` said `apply: pending` until this archive; it now records every phase as done.

## 2. Verification evidence (from verify-report.md)

- Verified commit: `c2a7fe7` (merge of PR #26).
- Lanes run in F1-close: pytest 1694 passed / 41 skipped (PostgreSQL-only tests skip on SQLite); vitest 1189 passed; lint, typecheck, build and `check:dist` clean.
- 67 requirement rows, every cited test checked with grep (none missing).
- Spec text amended before the merge where the code was right (verify-report.md, "Spec amendments"): I18N-4, PWA-3, PWA-4, DS-2, DS-5, PREF-6, SHELL-3, FAUTH-7. CI-5 needed no extra amendment: the F1 delta already describes the real frontend job, and the merge replaced the F0 placeholder text.

## 3. Specs merged into source of truth

Rules (same as the F0 archive): ADDED capabilities become new `openspec/specs/<capability>/spec.md` files; MODIFIED requirements replace the matching requirement block of the main spec; ADDED requirements inside an existing capability are appended; there were no REMOVED requirements. Delta headings (`## ADDED/MODIFIED Requirements`) become `## Requirements`, the `(Previously: ...)` notes of the MODIFIED requirements are dropped (they stay in this archive), and a `Source:` line names the change. CI-5 is renamed "Frontend job" (it is no longer a placeholder), as the delta allowed.

| Capability | Main spec | Change | F1 requirements | Scenarios (delta) | Main spec after merge |
|---|---|---|---|---|---|
| api-v1 | `openspec/specs/api-v1/spec.md` | MODIFIED API-1, API-4, API-5; ADDED API-9 | 4 | 21 | 9 requirements, 34 scenarios |
| ci-pipeline | `openspec/specs/ci-pipeline/spec.md` | MODIFIED CI-5; ADDED CI-9 | 2 | 8 | 9 requirements, 17 scenarios |
| session-security | `openspec/specs/session-security/spec.md` | MODIFIED SESS-1 | 1 | 9 | 3 requirements, 12 scenarios |
| app-shell | `openspec/specs/app-shell/spec.md` | new (SHELL-1..10) | 10 | 25 | 10 / 25 |
| design-system | `openspec/specs/design-system/spec.md` | new (DS-1..10) | 10 | 27 | 10 / 27 |
| frontend-auth | `openspec/specs/frontend-auth/spec.md` | new (FAUTH-1..11) | 11 | 26 | 11 / 26 |
| i18n | `openspec/specs/i18n/spec.md` | new (I18N-1..5) | 5 | 12 | 5 / 12 |
| pwa | `openspec/specs/pwa/spec.md` | new (PWA-1..9) | 9 | 22 | 9 / 22 |
| spa-hosting | `openspec/specs/spa-hosting/spec.md` | new (HOST-1..7) | 7 | 15 | 7 / 15 |
| ui-preferences | `openspec/specs/ui-preferences/spec.md` | new (PREF-1..8) | 8 | 22 | 8 / 22 |
| **Total** | 7 new + 3 modified capabilities | 62 ADDED + 5 MODIFIED | **67** | **187** | |

After the merge `openspec/specs/` holds 21 capabilities and 136 requirements (74 from F0 + 62 added by F1).
Checks: each of the 67 F1 requirement IDs appears exactly once as a `### Requirement:` heading under
`openspec/specs/` (grep count, 0 mismatches); no `ADDED`, `MODIFIED` or `REMOVED` marker remains there.

## 4. Deferred items (owner checks)

| Task | Requirement | Where |
|---|---|---|
| 4.41 | FAUTH-11 | owner: sign in in the app, open `/riftbound/` (Jinja), still signed in; sign out there, back in the app it shows the login screen |
| 6.26, 7.4 | PWA-9 | owner, Lighthouse (Chromium installability errors: none, live 2026-10-21) |
| 6.28 | PWA-6, PWA-9 | owner, iPhone Safari to test later |
| 6.28b | PWA-6 | owner, Mac to test later |
| 6.32 | PWA-4 | owner, observe the update prompt at the next deploy of a new build (verified locally in Chromium) |
| 6.34 | PWA-5 | not run on dev on purpose: it uninstalls the worker on the owner's devices (verified locally in Chromium) |
| 7.5 | — (unit g) | owner, CSP report-only console review after the F1-g deploy |

These are listed in `docs/knowledge/state.md` → "Pending checks". None blocks the archive: every requirement
with a deferred device check also has passing automated tests, except FAUTH-11 and PWA-9, whose only
scenarios are manual.

## 5. After this archive

`openspec/` is read-only history plus the merged contract in `openspec/specs/`. New work is specified in
`docs/requirements/` (see `docs/knowledge/specs-index.md`); a requirement that changes a contract in
`openspec/specs/` must say which requirement it amends.
