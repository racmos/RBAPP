# Requirements

Inputs for gentle-shell. The cycle is described in `docs/knowledge/workflow.md`.

- `TEMPLATE.md` — format of a unit requirement (one unit = one branch = one PR).
- `F<n>/README.md` — phase spec: goal, current state, requirements `F<n>-R#`, data, API, UI, units, open
  decisions `D-F<n>-#`. The planner writes unit requirements from it.
- `F<n>/F<n>-<x>-<slug>.md` — unit requirement handed to gentle-shell. It must have "Open questions: none"
  before it is handed over; drafts with `CONFIRM D-…` items are confirmed with the owner first.
- `M/M-<x>-<slug>.md` — maintenance units outside the phases (tests, hygiene, plan updates).

Phase order: `docs/knowledge/roadmap.md`. Phase IDs are identifiers, not order. The owner decisions of
2026-10-22 are folded into the phase specs (M-b); the record of the answers is
`docs/knowledge/decisions-2026-10-22.md`.

## Ready or drafted

| Unit | File | State |
|---|---|---|
| F1-g | `F1/F1-g-hardening.md` | Done (#26). |
| F1-close | `F1/F1-close.md` | Done (#27). |
| M-a | `M/M-a-test-reset.md` | Done (#29). |
| M-b | `M/M-b-plan-update.md` | Done (#30). |
| M-c | `M/M-c-hygiene.md` | Done (#31). |
| F4-a | `F4/F4-a-job-runner.md` | Done (#32). |
| F4-b | `F4/F4-b-daily-prices.md` | Done (#33). |
| F2-a | `F2/F2-a-card-bans.md` | Done (#34). |
| M-d | `M/M-d-card-images-out-of-git.md` | Implemented, in review (#37). |
| F13-a | `F13/F13-a-admin-foundation.md` | Implemented, in review (#38). |
| F13-b | `F13/F13-b-catalog-admin-api.md` | Implemented, in review (#39). |
| F13-c | `F13/F13-c-riot-sync-engine.md` | Implemented, in review (#40). |
| F13-d | `F13/F13-d-riot-sync-schedule.md` | Implemented, in review (#41). |
| F13 | `F13/README.md` | Phase spec only (Riot sync + catalog admin; added by M-b). |
| F14 | `F14/README.md` | Phase spec only (Products; added by M-b). |
| F15 | `F15/README.md` | Phase spec outline (Rules app; added by M-b; specified when the phase starts). |
| **Batch 1** | `BATCH-1.md` | **Ready (2026-10-25)** — 32 units run autonomously in order: M-d, F13-a…g, F2-b…i + F2-k, F3-a/b, F4-c, F3-c/d/e/g/h/i, F14-a…f. Decisions in `docs/knowledge/decisions-2026-10-25.md`. |
| F2-j, F2-l | `F2/F2-j-*.md`, `F2/F2-l-*.md` | Drafts, deferred to batch 2. |

Batch 1 (`BATCH-1.md`) lists the unit requirements written on 2026-10-25 for M-d, F13, F2, F3, F4-c and F14.
The other phases have a phase spec only; their unit requirements are written when the phase starts.

## How to hand one over

```text
Implementa el requerimiento docs/requirements/F1/F1-g-hardening.md.
Trabaja en un worktree nuevo desde origin/main (rama indicada en el documento); no cambies de rama en el
checkout desplegado. TDD estricto. Al terminar: todos los lanes en verde, docs y docs/knowledge/state.md
actualizados, y un resumen de cierre con S# → tests.
```
