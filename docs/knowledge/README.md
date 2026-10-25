# Knowledge base

Everything a planner (Claude Project) or an implementer (gentle-shell) needs to continue Rift Manager
without the history of past sessions. Synced into the Claude Project from GitHub; read by gentle-shell
through `AGENTS.md`.

| File | Read it for |
|---|---|
| [`product.md`](product.md) | What the app is and every owner decision (binding): architecture choices, game rules, scope by phase. |
| [`state.md`](state.md) | Current status: phases, units, what is live on dev, pending owner checks, follow-ups, known issues. Updated by every unit. |
| [`roadmap.md`](roadmap.md) | Phase order and dependencies, cross-phase contracts, units per phase, next steps. |
| [`workflow.md`](workflow.md) | The Claude Project → gentle-shell → PR → deploy cycle, roles, rules for requirements, project setup. |
| [`project-instructions.md`](project-instructions.md) | Text to paste into the Claude Project instructions. |
| [`architecture.md`](architecture.md) | How the system is built today: backend, API, data model, legacy Jinja pages, frontend, PWA, hosting, CI, tests. |
| [`conventions.md`](conventions.md) | Rules every change follows, known traps, definition of done. |
| [`specs-index.md`](specs-index.md) | Index of the formal contracts in `openspec/specs/` (F0 and F1, merged). |
| [`decisions-2026-10-25.md`](decisions-2026-10-25.md) | Planner decisions delegated by the owner for batch 1 (functional sketch): every open decision of M-d, F2, F3, F4-c, F13, F14 closed, and what is deferred to batch 2. Wins over the phase specs' open-decision tables. |
| [`decisions-2026-10-22.md`](decisions-2026-10-22.md) | Record of the owner's answers of 2026-10-22 and the agreed order. Folded into `product.md`, `roadmap.md`, `open-decisions.md` and the phase specs by M-b (#30). |
| [`open-decisions.md`](open-decisions.md) | Every product decision still open, by phase, with a recommendation. |
| [`ops-runbook.md`](ops-runbook.md) | Working copies, deploy, migrations with backup, rollback, service operations (generic; host values in the git-ignored `ops.local.md`). |

Related:

- `docs/requirements/` — `TEMPLATE.md`, phase specs `F<n>/README.md`, unit requirements `F<n>/F<n>-<x>-*.md`.
- `openspec/design-handoff.md` — inventory of the hi-fi design prototype (Spanish): tokens, components,
  screens, rules to port, gaps, open design decisions.
- `openspec/specs/` — formal requirement contracts (F0; F1 after F1-close).
- `docs/frontend.md`, `docs/migrations.md` — detailed frontend and migration guides.
