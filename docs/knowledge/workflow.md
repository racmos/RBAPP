# Workflow: Claude Project → gentle-shell → PR → deploy

From 2026-10-21 the project no longer uses the SDD/openspec cycle (explore → propose → spec → design →
tasks → apply → verify → archive run by Claude Code). F0 and F1 were built that way; their artifacts stay
in `openspec/` as the reference contract. From F1-close on, work flows like this:

```
 Owner ──talks──► Claude Project (planner, knowledge synced from GitHub)
   ▲                    │ writes one unit requirement (docs/requirements/TEMPLATE.md)
   │                    ▼
   │              gentle-shell (pi + gentle-pi, ODD + strict TDD, runs on the dev server)
   │                    │ worktree + branch → odd/tasks/<feature>.md → commits → PR
   │                    ▼
   └──merges──── GitHub PR (CI green) ──► deploy to dev (gentle-shell, runbook) ──► live + manual checks
```

## Roles

| Who | Does | Never does |
|---|---|---|
| **Owner** | Decides product questions, hands requirements to gentle-shell, authorizes push/PR, reviews, **merges**, does device and visual checks. | — |
| **Claude Project** (planner) | Knows the product, architecture, conventions, state and plan (this folder + `docs/requirements/` + `openspec/specs/`). Talks with the owner in Spanish. Closes open decisions, writes **one unit requirement at a time**, reviews gentle-shell's close report or the PR summary against the requirement, keeps the plan coherent, proposes plan/doc updates. | Write code. Invent facts about code it cannot see. Hand over a requirement with open questions. |
| **gentle-shell** (executor) | Runs in a worktree of the repo on the dev server. ODD: explores, tracks large work in `odd/tasks/<feature>.md` (quotes the requirement's Specs verbatim), implements with strict TDD, commits work units, runs every lane, updates docs and `docs/knowledge/state.md`, pushes and opens the PR when the owner allows, deploys to dev on request following `ops-runbook.md`. | Merge. Push to `main`. Touch `.env` or print secrets. Switch branches in the deployed checkout. |

## The cycle for one unit

1. **Pick.** Owner to the Project: "siguiente unidad" (or a specific one). The Project reads `state.md`,
   `roadmap.md` and the phase spec `docs/requirements/F<n>/README.md`.
2. **Decide.** If the phase has open decisions (`D-F<n>-k`) that affect the unit, the Project asks them in
   one batch, with its recommendation, and records the answers in the requirement (and later in the phase
   spec through gentle-shell).
3. **Write.** The Project writes the requirement with `docs/requirements/TEMPLATE.md`, saved at
   `docs/requirements/F<n>/F<n>-<x>-<slug>.md`. Rules: self-contained, ≤ about 600 authored lines of
   change, exact strings (ES and EN), codes and payloads, numbered Specs `S1..`, acceptance criteria tied
   to tests, a `Risk:` line, "Open questions: none". Where the Project is not sure of a code fact, it adds
   an explicit verification step ("verify X in `path`; if different, stop and report") instead of guessing.
   Pre-written units (F1-g, F1-close, F2-*) may hold `CONFIRM D-…` items: the Project confirms them with
   the owner and removes them before handing over.
4. **Hand over.** The owner starts `gentle-shell` in the repo and pastes (Spanish is fine):

   ```text
   Implementa el requerimiento docs/requirements/F2/F2-a-card-bans.md.
   Trabaja en un worktree nuevo desde origin/main (rama indicada en el documento); no cambies de rama en
   el checkout desplegado. TDD estricto. Al terminar: todos los lanes en verde, docs y
   docs/knowledge/state.md actualizados, y un resumen de cierre con S# → tests.
   ```

   If the file is not in the repo yet, paste the requirement below that text and add: "guárdalo en esa
   ruta y inclúyelo en el primer commit".
5. **Implement.** gentle-shell runs ODD. For large units it creates `odd/tasks/<feature>.md` (Specs `S#`,
   Tasks `T#`, Log) and commits in slices of about 400 authored lines. When a unit goes past that, it asks
   the delivery strategy: for units already sized by the plan, prefer **one single PR**; choose the
   feature-branch chain only when the unit grew well beyond the forecast. Mid-way requirement changes: tell
   gentle-shell "Cambio de requisito: …" (it appends to the Log and reopens only the affected task).
6. **PR.** The owner says "push y abre la PR" (or runs gentle-shell in YOLO mode, which allows non-force
   push and PR creation). CI must be green (jobs `test`, `migrations-pg`, `frontend`, security workflow).
   Optional: paste the PR body or the close report into the Project for a review against the requirement.
7. **Merge.** The owner merges on GitHub.
8. **Deploy.** Owner to gentle-shell: "despliega en dev". gentle-shell follows `ops-runbook.md`
   (backup before migrations), runs the live checks of the requirement, and lists the manual checks for the
   owner.
9. **Close the loop.** Owner to the Project: "F2-a mergeada y desplegada (PR #N); checks: …". Re-sync the
   Project's GitHub knowledge so it sees the new `state.md`, then go back to step 1.

Small fixes (a bug, a typo, one understood change) skip the Project: tell gentle-shell directly
("arregla …"); ODD keeps them on its small path (no feature document), still on a branch with a PR.

## Rules for requirements (the Project's checklist)

- One unit = one branch = one PR. Backend/API units before the UI units that use them.
- Respect, in this order: `product.md` (owner decisions) → `state.md` → the phase spec → `openspec/specs/`
  (existing contracts; a requirement that changes one says so explicitly) → `openspec/design-handoff.md`
  (visual design) → `conventions.md`.
- Every new URL rule is classified (P/U/A) for `tests/test_authz_matrix.py`; every new error code lists
  its ES and EN messages; every UI string has ES and EN text and an i18n key.
- Every screen defines mobile (< 860 px), desktop (≥ 1240 px) and wide (≥ 1600 px) layouts and its
  loading, empty, error and offline states. Desktop shows more data, it does not stretch.
- Migrations: name the revision, upgrade, downgrade, backfill and the `Risk: item 1` line; the deploy
  section says "backup first".
- No secrets, IPs, hostnames or domains in requirements (they end up in the repo).
- Acceptance criteria always include the full lanes, the docs and `state.md`.

## Where things live

| Path | What |
|---|---|
| `docs/knowledge/` | Knowledge for the Project and for gentle-shell (this folder). |
| `docs/requirements/F<n>/README.md` | Phase spec (goal, requirements, data, API, UI, units, open decisions). |
| `docs/requirements/F<n>/F<n>-<x>-<slug>.md` | Unit requirement handed to gentle-shell. |
| `odd/tasks/<feature>.md` | gentle-shell's working document for a unit (created by it, committed on the branch). |
| `openspec/specs/` | Formal contracts of F0 (and F1 once archived by F1-close). |
| `openspec/changes/f1-app-shell/` | F1 SDD artifacts (until F1-close archives them). |
| `ops.local.md` (git-ignored, deployed checkout only) | Host-specific values for the runbook (never committed). |

## Setting up the Claude Project

1. Create a Project in claude.ai, for example "Rift Manager — planner".
2. Paste `docs/knowledge/project-instructions.md` (the fenced block) into the Project instructions.
3. Knowledge: add the GitHub repository `racmos/RBAPP` and select:
   `AGENTS.md`, `README.md`, `docs/knowledge/`, `docs/requirements/`, `docs/frontend.md`,
   `docs/migrations.md`, `openspec/specs/`, `openspec/changes/f1-app-shell/specs/`,
   `openspec/changes/f1-app-shell/design.md`, `openspec/design-handoff.md`, `openspec/roadmap.md`.
   Useful extras when room allows: `app/models/`, `app/api/error_codes.py`, `frontend/src/shell/navRegistry.ts`,
   `frontend/src/lib/breakpoints.ts`, `frontend/src/i18n/locales/es/`.
   Without the GitHub integration, upload the same files by hand and re-upload `state.md` after each merge.
4. Optionally upload the extracted design prototype (`Rift Manager.zip`, folder
   `design_handoff_riftbound_manager/`): screenshots and the JSX of the screen of the current phase.
5. After every merge, sync the GitHub knowledge.

## Setting up gentle-shell (once, on the dev server)

- `gentle-shell` (isolated home) or `gentle-shell --link` (reuse the pi home). Check with `/gentle:status`
  and `/gentle:doctor`.
- It reads `AGENTS.md` automatically; the section "Workflow" there points it to this folder.
- Optional: `pi install npm:gentle-engram` (memory mirror of the feature documents), `/gentle:yolo enable`
  for long runs (destructive actions still ask), `/gentle:review-mode enable` for native review (RDD).
- It needs the deployed checkout's Python venv and Node 24; see `ops-runbook.md` → "Working copies".
