# Requirements

Inputs for gentle-shell. The cycle is described in `docs/knowledge/workflow.md`.

- `TEMPLATE.md` — format of a unit requirement (one unit = one branch = one PR).
- `F<n>/README.md` — phase spec: goal, current state, requirements `F<n>-R#`, data, API, UI, units, open
  decisions `D-F<n>-#`. The planner writes unit requirements from it.
- `F<n>/F<n>-<x>-<slug>.md` — unit requirement handed to gentle-shell. It must have "Open questions: none"
  before it is handed over; drafts with `CONFIRM D-…` items are confirmed with the owner first.

## Ready or drafted

| Unit | File | State |
|---|---|---|
| F1-g | `F1/F1-g-hardening.md` | Ready (optional unit; recommended before F1-close). |
| F1-close | `F1/F1-close.md` | Ready after two CONFIRM items. |
| F2-* | `F2/F2-*.md` | Drafts with CONFIRM items (see `F2/README.md` → Open decisions). |

Phases F3-F12 have a phase spec only; their unit requirements are written when the phase starts, after the
owner answers its open decisions.

## How to hand one over

```text
Implementa el requerimiento docs/requirements/F1/F1-g-hardening.md.
Trabaja en un worktree nuevo desde origin/main (rama indicada en el documento); no cambies de rama en el
checkout desplegado. TDD estricto. Al terminar: todos los lanes en verde, docs y docs/knowledge/state.md
actualizados, y un resumen de cierre con S# → tests.
```
