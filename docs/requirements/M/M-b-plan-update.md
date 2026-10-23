# M-b: Plan update — fold the decisions of 2026-10-22 into the plan documents

| Field | Value |
|---|---|
| Phase / unit | M (maintenance, outside the phases) / b |
| Branch | `docs/m-b-plan-update` (from up-to-date `main`) |
| Depends on | M-a merged (#29) — done |
| Size forecast | Documentation only (~600-900 authored lines across `docs/`). No code, no tests. |
| Risk | `Risk: none` for the application. Documentation only; the risk is plan incoherence, checked by S9. |
| TDD | Not applicable (documentation). Verification: S9 checks + `pytest` and `npx vitest run` stay green. |
| Written by | gentle-shell on the owner's instruction (2026-10-24), in place of the planner. |

## Objective

`docs/knowledge/decisions-2026-10-22.md` records the owner decisions and the agreed order and says unit M-b
"folds it in": "M-b Plan update: fold this file into `product.md`, `roadmap.md`, `open-decisions.md`, the
phase specs and `state.md`; add the new phase specs (Riot sync + catalog admin, Products, Rules app)."
After M-b, the plan documents agree with the decisions file and no longer need it to win over them.

## Specs

S1. `docs/knowledge/roadmap.md`: rewrite the phase table and the "Order" paragraph to the agreed order of
    `decisions-2026-10-22.md` (M-a … events). Add rows for the new phases F13, F14, F15 (S6) and for the
    maintenance units M-a (done), M-b, M-c, M-d. F5 loses the hand simulator / mulligan (F5-k moves after
    production). F8 moves after production and after F15; F11 loses the new landing (F11-a/b move with F8).
    F9 OAuth (F9-f) is done just before production. F10's catalog-admin and Riot-sync pieces
    (F10-a, F10-e, F10-f) move to F13; the rest of F10 stays. Update "Units per phase" accordingly.
    Remove the 2026-10-22 warning banner.
S2. `docs/knowledge/open-decisions.md`: remove the answered decisions (D-F2-1, D-F2-2, D-F2-12, D-F3-1,
    D-F4-1, D-F4-2, D-F5-6, D-F8-1, D-F10-6) and the "Answered on 2026-10-22" paragraph; add a one-line
    pointer saying where each answer now lives (phase spec "Decisions already taken"). Add open decisions
    for the new phases only where the decisions file leaves something open (each with a recommendation,
    same format "**ID** — question: *recommendation*").
S3. `docs/knowledge/product.md`: record every product decision of the decisions table (daily prices
    06:30 / retry 08:00 Europe/Madrid, auto-match clear cases + review list, the three "scraping" sources,
    Riot sync windows and approval table, bans per name and mode 1v1/2v2 from the official list, playset
    profile setting + per-card "keep a playset" warning, Products as a separate total, drop the legacy price
    CSV, Rules app, mulligan section, events after production, landing rebuilt with events, Google/Discord
    in F9 before production, history not rewritten, Spanish enum names from `es-es`, job runner built once
    in F4-a). Replace any statement that contradicts them.
S4. Existing phase specs `docs/requirements/F2/README.md` … `F12/README.md`: for each decision that touches
    the phase, move it to "Decisions already taken" (cite "owner, 2026-10-22"), remove it from "Open
    decisions", and adjust requirements, units, dependencies and scope that contradict it. Concretely at
    least: F2 (D-F2-1, D-F2-2, D-F2-12; bans initial data from the official list, `rbcar_banned` not a
    source), F3 (D-F3-1 playset; `rbcol_selling = 'S'` evaluated and removed in F3; CSV samples pending),
    F4 (D-F4-1 06:30 + retry 08:00, validation record; D-F4-2 auto-match; F4-a/F4-b run early, right after
    M-c; F4-c with F3), F5 (D-F5-6: F5-k split out, after production; deck export samples pending),
    F8 (D-F8-1: after production and after F15; upcoming-events calendar from the official site first),
    F9 (F9-f Google/Discord just before production; owner creates the OAuth apps with a guide),
    F10 (F10-a/e/f moved to F13; D-F10-6 legacy price CSV dropped; user admin still waits for F9),
    F11 (new landing moved with F8), F12 (images out of git moves to unit M-d; history not rewritten).
    Do not edit the F2 unit drafts (`F2/F2-*.md`) or `openspec/`.
S5. Each phase spec keeps its section layout (Goal, Current state, Scope, Decisions already taken,
    Requirements, Data model changes, API, UI, Units, Open decisions, Risks and notes).
S6. New phase specs with the same layout, written from the decisions file only (no invented product
    decisions; anything not decided goes to "Open decisions" with a recommendation):
    - `docs/requirements/F13/README.md` — Riot sync + catalog admin (admin foundation, sets with release
      date entered by hand, cards, Riot sync schedule: from 21 days before release at 08:00 and 14:00
      Europe/Madrid, from release for 14 days once a day, afterwards monthly; new cards always inserted;
      changes auto-applied inside the active windows, in the monthly run they go to an approval table with
      field, old value, new value, approve/reject; uses the F4-a job runner; pulls F10-a, F10-e, F10-f).
    - `docs/requirements/F14/README.md` — Products (sealed Cardmarket products: boxes, cases, sleeves, …;
      price and history; quantity owned; separate "products" total, not added to the collection value;
      after F3).
    - `docs/requirements/F15/README.md` — Rules app (after production, before events; select cards that
      interact; answers only from the official Core Rules, Tournament Rules and FAQ; stored queries returned
      when repeated; paid AI service per query; vector search; Obsidian-like linking; "Specified when the
      phase starts" — keep it a short outline with open decisions).
    Phase IDs are identifiers, not order; the order lives in `roadmap.md`.
S7. `docs/knowledge/decisions-2026-10-22.md`: replace the "wins over" sentence with "Folded into the plan
    documents by M-b (#<PR>); kept as the record of the owner's answers." `docs/knowledge/README.md`: update
    its row to match. `docs/knowledge/state.md` and `docs/knowledge/roadmap.md` lose their 2026-10-22
    warning banners.
S8. `docs/knowledge/state.md`: Phases table follows the new order (F13-F15 added, M units listed); "Plan
    change" section reduced to one line pointing to `roadmap.md`; Units table row
    `M-b | done | docs/m-b-plan-update / #<PR> | …`; next unit **M-c**. `docs/requirements/README.md`: rows
    for M-b (Done) and the new phase folders; the F2 drafts row says they still need the planner's rewrite.
S9. Coherence checks (record the outputs in the close report):
    - `grep -rn "D-F2-1\b\|D-F2-2\b\|D-F2-12\|D-F3-1\b\|D-F4-1\b\|D-F4-2\b\|D-F5-6\|D-F8-1\b\|D-F10-6" docs/knowledge docs/requirements/F*/README.md`
      shows them only in "Decisions already taken" sections, `decisions-2026-10-22.md`, or history.
    - `grep -rn "09:30" docs/knowledge docs/requirements/F*/README.md` prints nothing outside history.
    - Every phase in `roadmap.md` has a `docs/requirements/F<n>/README.md` and vice versa.
S10. Line endings preserved (all touched files are LF; check with `git ls-files --eol`). English only.

## Tasks

| ID | Specs | Route | Commit |
|---|---|---|---|
| T1 | S1, S2, S3, S7, S8 | worker A (`docs/knowledge/**`, `docs/requirements/README.md`) | |
| T2 | S4, S5 | worker B (`docs/requirements/F2/README.md` … `F12/README.md`) | |
| T3 | S6 | worker C (`docs/requirements/F13/**`, `F14/**`, `F15/**`) | |
| T4 | S9, S10 | parent: checks, lanes, commit, PR | |

## Log

- L1 (owner, 2026-10-24): "continua tu ya con lo que hay planificado"
- L2 (gentle-shell): no planner requirement existed for M-b; the owner chose to have gentle-shell proceed.
  The scope is taken verbatim from `decisions-2026-10-22.md` ("Agreed order", item 2). New phases get the
  identifiers F13 (Riot sync + catalog admin), F14 (Products), F15 (Rules app); mulligan stays F5-k inside
  the F5 spec, scheduled after production.
