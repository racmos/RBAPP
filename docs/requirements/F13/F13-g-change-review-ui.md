# F13-g: Change review UI, overview completed, hand-off from the Jinja Riot section

| Field | Value |
|---|---|
| Phase / unit | F13 / g — batch 1, unit 8 |
| Branch | `feat/f13g-change-review-ui` (from the F13-f branch) |
| Depends on | F13-e, F13-f (stack) |
| Size forecast | ~450 authored lines |
| Risk | `Risk: none` |
| TDD | ON (strict). Runner: `cd frontend && npx vitest run`; `venv/bin/pytest` for the Jinja banner |
| Sources | F13 phase spec (F13-R21-R25, UI), `decisions-2026-10-25.md` (D-F13-15, 16) |

## Objective

The owner reviews what the monthly sync found — card, field, old value and new value — and approves or rejects
it one by one or in bulk; the overview and the admin navigation show how many changes are waiting.

## Read first

- `frontend/src/admin/` (F13-a/f), `docs/api.md` → change endpoints (F13-e)
- `app/templates/price.html` (Riot section), `docs/knowledge/ops-runbook.md`

## Specs

S1. Route `/admin/riot/changes` (`ChangesPage`); admin nav appends `changes` with label
    `admin:nav.changesCount` (count = `overview.riot.pending_changes`, plain `admin:nav.changes` when 0).
S2. Filters (in the URL): status `SegmentedControl` (`pending` default, `approved`, `rejected`, `all`), set
    `Select`, field `Select` (`admin:changes.field.<field>` for the 12 synced fields), search (debounced 300 ms).
    `Pagination` (F13-f) with 50 per page.
S3. ≥ 1240: table (`<caption>` `admin:changes.caption`) with a selection checkbox column (only `pending` rows;
    header checkbox selects the visible pending rows, named `admin:changes.selectPage`), card (40 px image,
    name, `SET · #id`), field, change (`ValueDiff`), detected (`formatDate`), actions (Approve, Reject; names
    `admin:changes.approveOne` / `rejectOne` + card name). A bulk bar appears with a selection:
    `admin:changes.selected` (plural), buttons `admin:changes.approveSelected` / `rejectSelected`, each behind a
    `ConfirmDialog` (`admin:changes.confirm.approve` / `reject`, plural with the count, body
    `admin:changes.confirm.body`). After a bulk call a toast `admin:changes.bulkResult` (counts per outcome;
    stale and decided rows stay visible with their new status after the refetch).
S4. ≥ 1600: a right panel shows the selected row: card image (tile size), and `ValueDiff` side by side (old |
    new) for long text fields (`rbcar_ability`, `rbcar_tags`).
S5. < 860: one card per change (image, name, field, `ValueDiff` stacked), with Approve/Reject buttons; bulk
    selection hidden (D-F13-15).
S6. `ValueDiff` (`src/admin/ValueDiff.tsx`): props `oldValue`, `newValue`, `layout` (`inline` | `stacked` |
    `side`); empty/NULL shown as `admin:changes.empty`; old value struck through with the visually-hidden prefix
    `admin:changes.old`, new value with prefix `admin:changes.new` (colour is never the only signal).
S7. Single actions call approve/reject; `change_stale` and `change_decided` show the translated error in a toast
    and refetch. `warnings` containing `image_download_failed` → toast `admin:changes.imageWarning`.
S8. Overview completed: a second KPI band "Riot" with pending changes (link to `/admin/riot/changes`), last sync
    (status badge + date + trigger, or `admin:overview.noSync`), placeholder sets (list of codes with link to
    `/admin/sets`, or nothing), active sets count (link to `/admin/riot`).
S9. Jinja hand-off: the Riot section of `app/templates/price.html` shows at its top a notice (Spanish only, like
    the page) "La sincronización con Riot se gestiona ahora en la nueva administración." with a link "Abrir"
    to `/riftbound/app/admin/riot`. Test with the Flask client that the admin page renders it.
S10. States as G6 of `BATCH-1.md`; empty `admin:changes.emptyPending` for `pending`, `admin:changes.emptyOther`
     otherwise. Axe clean.
S11. Docs: `AGENTS.md` (admin area complete for the catalog), `docs/frontend.md`, runbook ("How to review Riot
     changes"), `docs/requirements/F13/README.md` status line "Implemented in batch 1", `state.md` (F13 phase row).

## UI strings

| Key | ES | EN |
|---|---|---|
| `admin:nav.changes` | Cambios | Changes |
| `admin:nav.changesCount` | Cambios ({{count}}) | Changes ({{count}}) |
| `admin:changes.title` | Cambios de Riot | Riot changes |
| `admin:changes.subtitle` | Cambios detectados en la revisión mensual de la galería. | Changes found by the monthly gallery check. |
| `admin:changes.caption` | Cambios detectados | Detected changes |
| `admin:changes.status.pending` | Pendientes | Pending |
| `admin:changes.status.approved` | Aprobados | Approved |
| `admin:changes.status.rejected` | Rechazados | Rejected |
| `admin:changes.status.all` | Todos | All |
| `admin:changes.columns.card` | Carta | Card |
| `admin:changes.columns.field` | Campo | Field |
| `admin:changes.columns.change` | Cambio | Change |
| `admin:changes.columns.detected` | Detectado | Detected |
| `admin:changes.columns.actions` | Acciones | Actions |
| `admin:changes.field.rbcar_name` | Nombre | Name |
| `admin:changes.field.rbcar_domain` | Dominio | Domain |
| `admin:changes.field.rbcar_type` | Tipo | Type |
| `admin:changes.field.rbcar_tags` | Etiquetas | Tags |
| `admin:changes.field.rbcar_energy` | Energía | Energy |
| `admin:changes.field.rbcar_power` | Poder | Power |
| `admin:changes.field.rbcar_might` | Fuerza | Might |
| `admin:changes.field.rbcar_ability` | Habilidad | Ability |
| `admin:changes.field.rbcar_rarity` | Rareza | Rarity |
| `admin:changes.field.rbcar_artist` | Artista | Artist |
| `admin:changes.field.image_url` | URL de la imagen | Image URL |
| `admin:changes.field.image` | Fichero de imagen | Image file |
| `admin:changes.allFields` | Todos los campos | All fields |
| `admin:changes.search` | Buscar carta | Search card |
| `admin:changes.old` | Antes: | Before: |
| `admin:changes.new` | Ahora: | Now: |
| `admin:changes.empty` | (vacío) | (empty) |
| `admin:changes.selectPage` | Seleccionar los pendientes de esta página | Select the pending ones on this page |
| `admin:changes.selected_one` | {{count}} cambio seleccionado | {{count}} change selected |
| `admin:changes.selected_other` | {{count}} cambios seleccionados | {{count}} changes selected |
| `admin:changes.approveOne` | Aprobar el cambio de {{name}} | Approve the change of {{name}} |
| `admin:changes.rejectOne` | Rechazar el cambio de {{name}} | Reject the change of {{name}} |
| `admin:changes.approve` | Aprobar | Approve |
| `admin:changes.reject` | Rechazar | Reject |
| `admin:changes.approveSelected` | Aprobar seleccionados | Approve selected |
| `admin:changes.rejectSelected` | Rechazar seleccionados | Reject selected |
| `admin:changes.confirm.approve_one` | ¿Aplicar {{count}} cambio? | Apply {{count}} change? |
| `admin:changes.confirm.approve_other` | ¿Aplicar {{count}} cambios? | Apply {{count}} changes? |
| `admin:changes.confirm.reject_one` | ¿Rechazar {{count}} cambio? | Reject {{count}} change? |
| `admin:changes.confirm.reject_other` | ¿Rechazar {{count}} cambios? | Reject {{count}} changes? |
| `admin:changes.confirm.body` | Los cambios que ya no coincidan con la carta se marcarán como desfasados y no se aplicarán. | Changes that no longer match the card are reported as stale and not applied. |
| `admin:changes.bulkResult` | Aprobados: {{approved}} · Rechazados: {{rejected}} · Desfasados: {{stale}} · Ya decididos: {{decided}} | Approved: {{approved}} · Rejected: {{rejected}} · Stale: {{stale}} · Already decided: {{decided}} |
| `admin:changes.imageWarning` | Cambio aplicado, pero la imagen nueva no se pudo descargar. | Change applied, but the new image could not be downloaded. |
| `admin:changes.emptyPending` | No hay cambios pendientes. | There are no pending changes. |
| `admin:changes.emptyOther` | No hay cambios con estos filtros. | No changes match these filters. |
| `admin:overview.riotTitle` | Riot | Riot |
| `admin:overview.kpi.pendingChanges` | Cambios pendientes | Pending changes |
| `admin:overview.kpi.activeSets` | Sets en ventana activa | Sets in an active window |
| `admin:overview.kpi.lastSync` | Última sincronización | Last sync |
| `admin:overview.noSync` | Todavía no se ha sincronizado. | No sync yet. |
| `admin:overview.placeholderSets` | Sets creados por la sincronización (ponles nombre y fecha): {{codes}} | Sets created by the sync (give them a name and date): {{codes}} |

## Acceptance criteria

- [ ] AC1 `ChangesPage.test.tsx`: filters in the URL, pagination, table at 1280 with selection and bulk confirm, panel at 1700, cards at 390 without bulk, single approve/reject with stale/decided toasts, image warning (S1-S7).
- [ ] AC2 `ValueDiff.test.tsx`: three layouts, empty values, accessible prefixes (S6).
- [ ] AC3 `OverviewPage.test.tsx` (extend): Riot band with and without data (S8); nav count in `AdminLayout` (S1).
- [ ] AC4 `tests/test_jinja_riot_notice.py`: the notice and link render for an admin (S9).
- [ ] AC5 States, axe, parity green; full lanes green; docs and `state.md` (S10, S11).

## Delivery

PR title: `feat(admin): Riot change review, overview and Jinja hand-off (F13 unit g)`. Screenshots at 390, 1280
and 1700 px.

## After merge

Deploy. Manual (owner): with at least one pending change (a monthly sync on a set without date produces them),
approve one, reject one, bulk-approve two.

## Open questions

none

## Log

- L1 (implementer): no product deviations. The detail panel shows the last selected pending
  change (checkbox-driven) instead of opening on row click, so keyboard users get the same content
  without nested interactive elements; no separate modal on small screens, as the cards already carry
  the full actions inline. `common:actions.delete` was added alongside save/cancel for the admin
  confirm dialogs.
