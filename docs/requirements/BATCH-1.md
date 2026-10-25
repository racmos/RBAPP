# Batch 1 — functional sketch (autonomous run)

Owner mandate (2026-10-25): "Todos los requisitos más acotados para que invente o improvise lo menos
posible, menos pausas; mergeas varias PRs seguidas y poder presentar un boceto funcional lo antes posible.
Debe ser totalmente autónomo y después ya iremos revisando módulo a módulo."

The implementer (Claude Code or gentle-shell) runs every unit below, in order, **without asking the owner
between units**: one branch and one PR per unit, PRs stacked, the owner merges them in order whenever he
wants. The decisions that would normally stop the run are already taken in
`docs/knowledge/decisions-2026-10-25.md`.

Precedence for this batch (owner authorization of 2026-10-25): where `AGENTS.md` → "Workflow" says that push
and PR creation are the owner's decision, that every branch starts from `origin/main`, or that any
contradiction stops the work, this file wins: the implementer **pushes each branch and opens each PR by
itself**, stacks the branches (R1) and stops only in the cases of R7. Merging and deploying stay with the
owner.

## Units, in order

| # | Unit | Requirement | Migration | Notes |
|---|---|---|---|---|
| 1 | M-d | `M/M-d-card-images-out-of-git.md` | none | Server step before deploy (copy images). |
| 2 | F13-a | `F13/F13-a-admin-foundation.md` | `admin_audit` | First frontend unit: re-creates the ES/EN parity test. |
| 3 | F13-b | `F13/F13-b-catalog-admin-api.md` | none | Introduces `already_exists`, `set_in_use`, `card_in_use`. |
| 4 | F13-c | `F13/F13-c-riot-sync-engine.md` | `card_changes`, `jobs_riot_sync` | |
| 5 | F13-d | `F13/F13-d-riot-sync-schedule.md` | none | Two timers on the server. |
| 6 | F13-e | `F13/F13-e-riot-sync-api.md` | none | |
| 7 | F13-f | `F13/F13-f-catalog-admin-ui.md` | none | |
| 8 | F13-g | `F13/F13-g-change-review-ui.md` | none | |
| 9 | F2-b | `F2/F2-b-game-meta-card-dto.md` | `price_product_date_idx` | Read-only DB queries first (D-F2-1). |
| 10 | F2-c | `F2/F2-c-cards-list-api.md` | none | |
| 11 | F2-d | `F2/F2-d-card-detail-api.md` | none | |
| 12 | F2-e | `F2/F2-e-card-ui-atoms.md` | none | |
| 13 | F2-f | `F2/F2-f-card-detail-screen.md` | none | |
| 14 | F2-g | `F2/F2-g-price-chart.md` | none | |
| 15 | F2-h | `F2/F2-h-catalog-page.md` | none | Nav `cards` → app. |
| 16 | F2-i | `F2/F2-i-catalog-desktop-wide.md` | none | |
| 17 | F2-k | `F2/F2-k-card-combobox.md` | none | |
| 18 | F3-a | `F3/F3-a-collection-data.md` | `collection_selling`, `playset` | Data backfill on the dev data. |
| 19 | F3-b | `F3/F3-b-collection-read-api.md` | none | |
| 20 | F4-c | `F4/F4-c-value-snapshots.md` | `value_snapshots`, `jobs_value_snapshot` | |
| 21 | F3-c | `F3/F3-c-collection-write-api.md` | none | |
| 22 | F3-d | `F3/F3-d-collection-export-api.md` | none | |
| 23 | F3-e | `F3/F3-e-collection-import-api.md` | `import_previews` | RBAPP format only. |
| 24 | F3-g | `F3/F3-g-collection-ui-mobile.md` | none | Nav `collection` → app. |
| 25 | F3-h | `F3/F3-h-collection-ui-desktop.md` | none | |
| 26 | F3-i | `F3/F3-i-import-export-ui.md` | none | |
| 27 | F14-a | `F14/F14-a-product-catalog-data.md` | `products_catalog`, `jobs_products_refresh` | |
| 28 | F14-b | `F14/F14-b-products-read-api.md` | none | |
| 29 | F14-c | `F14/F14-c-owned-products-api.md` | `user_products`, `snapshot_products_value` | |
| 30 | F14-d | `F14/F14-d-products-admin.md` | none | |
| 31 | F14-e | `F14/F14-e-products-ui-mobile.md` | none | Nav `products` (new). |
| 32 | F14-f | `F14/F14-f-products-ui-desktop.md` | none | |

Paths are relative to `docs/requirements/`. "Migration" lists the revision names in order; the numbers are
taken at implementation time (rule G3).

## Run protocol

R1. Setup: `git fetch origin`. Work in a worktree outside the deployed checkout (never switch branches in
    the deployed checkout). Unit 1 branches from `origin/main`; every next unit branches from the previous
    unit's branch (a linear stack). Branch names are the ones in each requirement.
R2. Per unit, in this order: read the requirement, this file, `docs/knowledge/decisions-2026-10-25.md` and
    the requirement's "Read first"; implement with strict TDD (AGENTS.md → Testing); run every lane
    (`venv/bin/pytest`; `cd frontend && npm run lint && npm run typecheck && npx vitest run && npm run build
    && npm run check:dist`); update the docs the requirement names and `docs/knowledge/state.md` (G9);
    commit (Conventional Commits, slices of about 400 authored lines); push; open the PR (R3); commit
    "docs(state): record PR #N for <unit>" on the same branch and push; start the next unit at once.
R3. Every PR targets `main`. Title from the requirement. Body: summary; "Stacked on #<previous PR> —
    merge in order" (except unit 1); S# → test map; deviations (G8); manual checks; deploy notes
    (migrations, server steps); rollback. Never merge.
R4. CI: after opening each PR, check the CI of the open PRs of the batch (`gh pr checks`). When one fails,
    fix it on its branch, push, then bring the fix into every later branch with `git merge` (no rebase,
    no force push) and push them. A unit may only start when the previous unit's lanes are green locally.
R5. When the owner merges PRs meanwhile, continue stacking; if `main` gains a commit the stack does not
    have, `git merge origin/main` into the current branch and resolve.
R6. Deploying is **not** part of the run. When the owner says "despliega", deploy what is merged on `main`
    with `docs/knowledge/ops-runbook.md` (backup first; every pending migration in order; the server steps
    listed in the merged PRs, in order).
R7. Stop the whole run and report to the owner only when: (a) a migration would fail or lose data on the
    dev database (preflight query result); (b) a change would weaken authentication, authorization or CSRF;
    (c) CI cannot be made green after two honest attempts; (d) a product question appears that neither the
    requirement, the phase spec, `decisions-2026-10-22.md`, `decisions-2026-10-25.md` nor `product.md`
    answers **and** a wrong guess would be expensive to undo (schema, public contract, deleting data). Any
    other uncertainty: take the reading closest to the phase spec and the existing code patterns, record it
    as a deviation (G8) and continue.
R8. At the end (or at a stop): post one summary for the owner — table unit → PR → CI → deviations count;
    the ordered server steps for the deploy; the owner's manual checks of every unit; what batch 2 contains
    (`decisions-2026-10-25.md` → "Deferred").

## Global rules (they override older text in the drafts)

G1. Tests (owner 2026-10-22, M-a): every unit writes its own tests; a test file named in a requirement that
    does not exist is created; guards removed by M-a are re-created in their smallest form when a unit
    touches their area (AGENTS.md → Testing). Nothing in the tests reaches the internet.
G2. Every new URL rule is classified in `tests/test_authz_matrix.py` (P/U/A). Admin rules: `A`.
G3. Migrations: revision ids `00NN_<name>` take the next free number on the stack at implementation time and
    chain to the current head (numbers written in older drafts, such as `0008_price_product_date_idx`, are
    placeholders). Each migration is reversible, has a round-trip and drift test (`tests/migration_helpers.py`),
    and its PR says "backup first".
G4. Error codes: each new code goes to `app/api/error_codes.py`, both `frontend/src/i18n/locales/{es,en}/errors.json`
    (`code.<value>`) and `tests/test_error_catalogs.py`. A code is introduced once (the first unit that needs it).
G5. i18n: every UI string has ES and EN text under an i18n key; ES is the source. F13-a re-creates
    `frontend/src/i18n/parity.test.ts` (keys, `{{placeholders}}` and plural forms equal in both languages, using
    `src/i18n/parity.ts`); every later unit keeps it green. Spanish copy: "tú", sentence case, no exclamation marks.
    Plurals: requirements list `_one` and `_other`; Spanish also needs `_many` (same text as `_other`), as in
    `auth.json` (`countdown_many`). English keeps `_one` and `_other`.
G6. Layouts: every screen works at mobile (< 860 px), desktop (≥ 1240 px) and wide (≥ 1600 px) as its
    requirement says; desktop shows more data, it never just stretches. Every screen has loading, empty,
    error and offline states (offline: read what is cached, every edit control disabled with the hint
    `common:offline.editDisabled`, added by F13-a: "Necesitas conexión para hacer cambios." / "You need a
    connection to make changes."). Axe has no violations on new screens.
G7. Card images: after M-d every image URL is `/riftbound/media/cards/<folder>/<file>`; image paths in older
    drafts (`/riftbound/static/images/cards/…`) mean that URL.
G8. Deviations: when the code differs from what a requirement assumes, follow the requirement's own
    "verify … if different" instruction; when it has none, take the reading closest to the phase spec,
    append a line `L<n> (implementer): …` to the requirement's "## Log" section (create it at the end of the
    document) and list it in the PR body under "Deviations".
G9. `docs/knowledge/state.md`: each unit adds or updates its row in "Units" (status "in review (#N)"; the
    owner's merge makes it done), its phase row in "Phases", "Pending checks" for its server steps and
    "Follow-ups"/"Known issues" when it creates or closes one. `docs/requirements/README.md`: the unit's row.
G10. No secrets, IPs, hostnames or domains in code, docs or tests. Line endings of touched files preserved
     (AGENTS.md and README.md are CRLF).
G11. "Open questions" sections that still contain `CONFIRM` lines in older drafts are answered by
     `decisions-2026-10-25.md`; do not stop on them.
G12. Out of scope for the whole batch: everything listed as deferred in `decisions-2026-10-25.md`; removing
     Jinja pages or legacy routes; changing `product.md` rules.
G13. Read-only queries on the dev database (F2-b S1, F3-a S1, F14-a S1): run them with the app's
     `DATABASE_URL` (`flask shell` or `psql`). If the implementer has no access to that database, do not stop:
     write "Preflight not run (no database access)" in the PR, keep the requirement's defaults, and make the
     migration itself check the dangerous condition and abort with a clear message (F3-a: any
     `rbcol_quantity < 1`; F14-a: duplicate `rbpdt_id_product`). The owner's deploy (backup first) then
     surfaces it. Likewise, when the official `es-es` gallery cannot be read (F2-e, D-F2-12), use the draft's
     Spanish names and list them in the PR.

## Owner checks after the batch

Each PR lists its own manual checks. The sketch to present: sign in → Cartas (catalog, filters, card detail
with price chart) → Colección (add, edit, playset warning, export, import RBAPP) → Productos (catalog, owned,
total) → Administración (sets with release date, cards, Riot sync now, change review).
