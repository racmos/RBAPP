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
| M-c | `M/M-c-hygiene.md` | Done (#<PR>). |
| F13 | `F13/README.md` | Phase spec only (Riot sync + catalog admin; added by M-b). |
| F14 | `F14/README.md` | Phase spec only (Products; added by M-b). |
| F15 | `F15/README.md` | Phase spec outline (Rules app; added by M-b; specified when the phase starts). |
| F2-* | `F2/F2-*.md` | Drafts written before 2026-10-22; they still need the planner's rewrite before hand-over (see `F2/README.md` → Decisions already taken and Open decisions). |

Phases F3-F15 have a phase spec only (`F<n>/README.md`; F13 Riot sync + catalog admin, F14 Products, F15
Rules app were added by M-b); their unit requirements are written when the phase starts, after the owner
answers its open decisions. Maintenance unit M-d (card images out of git) has no requirement yet.

## How to hand one over

```text
Implementa el requerimiento docs/requirements/F1/F1-g-hardening.md.
Trabaja en un worktree nuevo desde origin/main (rama indicada en el documento); no cambies de rama en el
checkout desplegado. TDD estricto. Al terminar: todos los lanes en verde, docs y docs/knowledge/state.md
actualizados, y un resumen de cierre con S# → tests.
```
