# Archive Report: f0-foundation

**Change**: f0-foundation (roadmap phase F0 "Base", delivery units a-e)
**Archive date**: 2026-10-19
**Artifact store**: openspec
**Verdict (verify-report.md)**: PASS WITH WARNINGS (0 CRITICAL, 5 WARNING, 5 SUGGESTION). No CRITICAL issue, so archiving is allowed.
**Status**: archived and closed. Folder move to `openspec/changes/archive/2026-10-19-f0-foundation/` is done by the orchestrator (`git mv`) after this report.

---

## 1. Delivery

| Unit | Scope (from the delta specs) | PR | Branch |
|---|---|---|---|
| a | Config from env, `RB_ENV`, fail-fast validation, CI secrets removed, `run.py` debug off, `.env.example` | #11 | not recorded in inputs |
| b | Alembic baseline (`riftbound` schema), legacy table backup and drop, `rbcol_quantity` integer, `migrations-pg` job | #12 | not recorded in inputs |
| c | `is_admin` / `is_blocked`, admin guard and authorization matrix, `price` tools locked down, Cardmarket URL allow-list, deck viewing, profile | #13 | feat/f0c-admin-authz |
| d | CSRF, cookie flags, login lockout, rate limits, ALTCHA, landing feed cache | #14 | feat/f0d-csrf-login |
| e | API v1 (`/riftbound/api/v1`), JSON error negotiation, CI and docs, repo hygiene | #15 | feat/f0e-api-v1 |

All five PRs are merged to `main` (verification run at `1fd086f`). CI on PR #15 and on `main` after the merge is green (`test`, `migrations-pg` on PostgreSQL 18, `frontend` placeholder).

## 2. Verification evidence (from verify-report.md)

- Default lane: 1181 passed, 30 skipped (the skips are the PostgreSQL tests when `TEST_POSTGRES_URL` is unset).
- PostgreSQL lane (`-m postgres`): 30 passed. Total 1211 / 1211 passing.
- Specs: 14 capabilities, 74 requirements, 184 scenarios. 178 of 184 scenarios have passing evidence, 2 are PARTIAL (API-1 unhandled exception via blueprint handler, CI-5 wording), 4 are MANUAL-pending (see follow-ups). 0 failing, 0 untested.
- `bandit -r app/ -ll`: 0 medium/high.
- Verify warnings W2 to W5 are recorded as addressed before archive in `state.yaml`. W1 (open manual checks) is accepted as follow-up below. W3 (spec sync with as-built decisions) is resolved by this archive, see section 3.

## 3. Specs merged into source of truth

`openspec/specs/` was empty (only `.gitkeep`), so each delta spec became the main spec for its domain. The delta specs only contained `ADDED Requirements`, so there was no MODIFIED or REMOVED merge and no destructive delta to warn about (config rule `archive`).

| Domain | Main spec | Requirements | Scenarios | Unit(s) |
|---|---|---|---|---|
| access-control | `openspec/specs/access-control/spec.md` | 8 (ACL-1..ACL-8) | 16 | c |
| api-v1 | `openspec/specs/api-v1/spec.md` | 8 (API-1..API-8) | 22 | e |
| app-config | `openspec/specs/app-config/spec.md` | 7 (CFG-1..CFG-7) | 16 | a |
| card-images | `openspec/specs/card-images/spec.md` | 3 (IMG-1..IMG-3) | 10 | a, c |
| ci-pipeline | `openspec/specs/ci-pipeline/spec.md` | 8 (CI-1..CI-8) | 11 | a, b, e |
| collection-quantity | `openspec/specs/collection-quantity/spec.md` | 4 (QTY-1..QTY-4) | 12 | b |
| csrf-protection | `openspec/specs/csrf-protection/spec.md` | 5 (CSRF-1..CSRF-5) | 14 | d |
| db-migrations | `openspec/specs/db-migrations/spec.md` | 9 (MIG-1..MIG-9) | 20 | b |
| deck-viewing | `openspec/specs/deck-viewing/spec.md` | 4 (DECK-1..DECK-4) | 10 | c |
| landing-feeds | `openspec/specs/landing-feeds/spec.md` | 1 (LAND-1) | 5 | d |
| login-protection | `openspec/specs/login-protection/spec.md` | 9 (LOGIN-1..LOGIN-9) | 21 | d |
| price-resolution | `openspec/specs/price-resolution/spec.md` | 2 (PRC-1..PRC-2) | 11 | a, c |
| session-security | `openspec/specs/session-security/spec.md` | 3 (SESS-1..SESS-3) | 7 | a, d |
| user-profile | `openspec/specs/user-profile/spec.md` | 3 (PROF-1..PROF-3) | 9 | c |
| **Total** | 14 domains | **74** | **184** | |

Merge rules applied to every main spec:
- Requirement IDs, titles, requirement text and all scenarios are kept as in the delta. No requirement was added or dropped.
- `## ADDED Requirements` is replaced by a plain `## Requirements` section.
- A header line `Source: change f0-foundation (archived 2026-10-19)` is added.
- The "As built" notes (R-references and D-references) are folded into the requirement text as plain sentences. Where the as-built wording differs from the original requirement (ACL-1 `is_blocked` vs `is_active`, ACL-6 aliases, LOGIN-8 TTL 5 min, LAND-1 TTL 300 s, PRC-1 zero-as-missing, CI-4 job location), the main spec states the as-built behavior and keeps the D/R reference for traceability.

Redactions made for the "no secrets, private IPs or hostnames" rule (scenario meaning unchanged):
- CFG-1: the legacy default key literal and the legacy database host IP are now described in words, not written out. The scan still checks for them.
- CFG-3: the legacy default key used in the weak-key example is described in words.
- ACL-7: the foreign-host example IP is replaced by the documentation address `192.0.2.1`. The scenario still tests a non-https foreign host.

## 4. Archive contents (moved by orchestrator)

Folder to archive: `openspec/changes/f0-foundation/` → `openspec/changes/archive/2026-10-19-f0-foundation/`

- `proposal.md`, `design.md`, `tasks.md` (164 items: 151 complete, 1 skipped, 12 open manual/bookkeeping items per verify-report section 1)
- `specs/` (14 delta spec files, kept as the audit record)
- `exploration.md`, `dev-schema-snapshot.txt`, `apply-progress.md`, `verify-report.md`, `archive-report.md`, `state.yaml`

The archive is an audit trail: the delta files stay there unchanged. Only the main specs were written.

## 5. Open follow-ups carried forward

| # | Item | Type | Status / what is needed |
|---|---|---|---|
| F-1 | 4.31: Nginx `limit_req` burst test (LOGIN-7 live layer) and LOGIN-5 timing sample | MANUAL | Pending the Nginx repoint to the app port. Code and docs paths are automated and green. |
| F-2 | 4.32: SESS-1 cookie flags over HTTPS behind Nginx | MANUAL | Same pending Nginx repoint as F-1. Listed by verify-report section 1 (not in the original carry-forward list, added here for completeness). |
| F-3 | 5.20: CI-8 README/AGENTS prose review sign-off | MANUAL | Prose already checked against code (verify-report section 5.3). User sign-off pending. |
| F-4 | 0.2: decision on tracking `openspec/` in git | Optional, USER | Files are already tracked; decision not ticked. |
| F-5 | 0.5: `TEST_POSTGRES_URL` for local `-m postgres` runs | Optional, USER | Not set locally. The CI `migrations-pg` job covers it. |
| F-6 | 1.24: live `python run.py` check | Optional, MANUAL | Failure message verified; live run is the user's check. |
| F-7 | 0.4: secret rotation | USER, recommended | Done in part: the app now connects with a dedicated database role, and `SECRET_KEY` was rotated on 2026-10-19. Still pending with the user: the superuser database password rotation. Old values remain in git history, so keep this item open until the superuser password is rotated. |
| F-8 | Verify S2: tighten loose status assertions | Suggestion | `test_templates_csrf.py` (`status_code in (200, 404)`) and `test_login_protection.py` (`in (200, 302)`). |
| F-9 | Verify S3: assert each authorization class (P, U, A) has at least one rule | Suggestion | In `test_authz_matrix.py`. |
| F-10 | Verify S4: low coverage of legacy modules (`price.py`, `cardmarket_loader.py`, `riot_scraper.py`) | Suggestion | Pre-existing. Add characterization tests when F1 or later touches them. |
| F-11 | Verify S5: state the 5th-failure response explicitly in the login spec | Suggestion | Not applied: LOGIN-2 is unchanged. The 5th wrong password answers invalid credentials and sets the lock; the 6th attempt gets the locked response. Consider stating this in LOGIN-2 in a later change. |

Verify W5 / S1 (blueprint-level API error handler not exercised by a test) is covered by the pre-archive fixes recorded in `state.yaml`. It was not re-verified in this archive step.

## 6. Next phase

Next roadmap phase: **F1 "Estructura app"** (Vite + React + TypeScript PWA, tokens, i18n, login/register in React, Nginx + HTTPS). See `openspec/roadmap.md` section 5. Start it as a new change with `/sdd-new` (the roadmap says one change folder per phase under `openspec/changes/<fase>/`, with its own branch and PR). Roadmap section 8 lists the open questions for F1 (domain and server for HTTPS).

## 7. Traceability

- Artifact store: openspec only. Engram was unavailable for this run, so no `mem_save` was made and no observation IDs exist. The file paths above are the traceability record.
- Specs were not changed in the delta files.
- `state.yaml`: `archive: done`.
