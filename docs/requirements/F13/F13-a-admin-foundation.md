# F13-a: Admin foundation — admin API blueprint, audit log, admin layout and overview

| Field | Value |
|---|---|
| Phase / unit | F13 / a — batch 1, unit 2 |
| Branch | `feat/f13a-admin-foundation` (from the M-d branch) |
| Depends on | M-c, M-d (stack) |
| Size forecast | ~550 authored lines |
| Risk | `Risk: item 2 (new admin surface) + item 1 (new audit table)` |
| TDD | ON (strict). Runners: `venv/bin/pytest`, `cd frontend && npx vitest run` |
| Sources | `docs/requirements/F13/README.md` (F13-R1, R2, R3, R25, R27-R29), `docs/knowledge/decisions-2026-10-25.md` |

## Objective

The owner gets an "Administración" area inside the new app, guarded on the server and in the client, with
a first overview of the catalog. Every later admin unit (F13-b…g, F14-d, F10) plugs into the blueprint, the
audit helper and the layout built here.

## Read first

- `app/api/v1/__init__.py` (blueprint + error handler), `app/security.py` (`require_admin`),
  `app/api/responses.py`, `app/errors.py`, `app/__init__.py` (blueprint registration order)
- `app/models/prefs.py` (model conventions, named constraints), `migrations/versions/0009_card_bans.py`,
  `tests/migration_helpers.py`
- `frontend/src/app/routes.tsx`, `frontend/src/auth/guards.ts` (`requireAdmin`), `frontend/src/shell/navRegistry.ts`,
  `frontend/src/account/InterfacePage.tsx` (a page inside the shell), `frontend/src/i18n/resources.ts`,
  `frontend/src/i18n/parity.ts`, `frontend/src/test/renderApp.tsx`, `frontend/src/components/ui/`

## Scope

In: blueprint `api_admin`, `GET /admin/overview` (catalog block), table `rbadminaudit` + `app/services/audit.py`,
React `AdminLayout` + `AdminNav` + overview page, nav flip of `admin`, i18n namespace `admin`, the key
`common:offline.editDisabled`, the ES/EN parity test.
Out: any admin write endpoint (F13-b on), Riot counters on the overview (F13-e), audit screen (F10).

## Specs

S1. Blueprint `api_admin = Blueprint('api_admin', __name__, url_prefix='/riftbound/api/v1/admin')` in
    `app/api/admin/__init__.py`, with `before_request(require_admin)` and the same `errorhandler(Exception)`
    as `api_v1` (reuse the function, do not copy it). CSRF is not exempt. Routes register by importing their
    modules at the end of `__init__.py` (same pattern as `api_v1`). Registered in `app/__init__.py` next to
    `api_v1`. Anonymous → JSON 401 (`code: unauthenticated`); signed-in non-admin → JSON 403.
S2. `tests/test_authz_matrix.py`: add `'api_admin.*': 'A'`. The existing A-class tests already cover the
    401/403/200 shapes for every rule.
S3. `GET /admin/overview` (`api_admin.overview`) → `ok({"catalog": {"sets": int, "sets_without_release_date":
    int, "cards": int, "cards_without_image": int}})`. `cards_without_image` = cards whose `image` is NULL or
    empty. At most 4 SQL statements. F13-e adds a `riot` block; clients ignore unknown keys.
S4. Table `rbadminaudit` (migration `00NN_admin_audit`, schema `riftbound`), model `RbAdminAudit` in
    `app/models/audit.py`:
    `rbaud_id` BIGINT PK (Integer variant on SQLite, autoincrement); `rbaud_actor_id` INT NULL FK
    `rbusers.id` ON DELETE SET NULL (`rbadminaudit_actor_fk`); `rbaud_actor_username` VARCHAR(64) NOT NULL;
    `rbaud_action` VARCHAR(48) NOT NULL; `rbaud_target_type` VARCHAR(24) NOT NULL; `rbaud_target_id`
    VARCHAR(64) NULL; `rbaud_details` JSON NULL (JSONB on PostgreSQL); `rbaud_created_at` TIMESTAMP NOT NULL
    default `clock.utcnow()` / `now()`. Indexes `idx_rbadminaudit_created` (`rbaud_created_at`),
    `idx_rbadminaudit_target` (`rbaud_target_type`, `rbaud_target_id`). Downgrade drops the table (data loss
    documented in the migration docstring).
S5. `app/services/audit.py`:
    - `SYSTEM = object()` sentinel.
    - `record(action, target_type, target_id=None, details=None, actor=None) -> RbAdminAudit`: adds the row to
      the current session **without committing** (the caller's transaction commits it with the change).
      `actor=None` → `current_user` (must be authenticated, else `RuntimeError`); `actor=SYSTEM` →
      `actor_id` NULL, `actor_username` `'system'`.
    - `action` matches `^[a-z_]+(\.[a-z_]+)+$` (e.g. `set.create`, `riot.apply`), else `ValueError`.
    - `details` must be JSON-serialisable and ≤ 4096 bytes once serialised (UTF-8), else `ValueError`.
S6. Frontend admin area (`frontend/src/admin/`):
    - Route `/admin` inside the shell with `loader: requireAdmin(queryClient)`, `lazy` `AdminLayout`; index child
      → `OverviewPage`. A non-admin gets the existing behaviour of `requireAdmin` (the 404 view; unchanged).
    - `adminNav.ts`: ordered list `{id, to, labelKey}`; this unit has only `overview` → `/admin`. Each later
      unit appends its entry (`sets`, `cards`, `riot`, `changes`, `products`).
    - `AdminLayout`: ≥ 1240 px a left `nav` (220 px, `aria-label` = `admin:nav.label`) with `NavLink`s and the
      page in an `Outlet`; < 1240 px a `Select` labelled `admin:nav.label` at the top that navigates on change.
      < 860 px the layout shows the hint `admin:mobileHint` under the page title.
    - `OverviewPage`: `PageHeader` (`admin:overview.title`, subtitle `admin:overview.subtitle`); four KPI tiles
      (label + number) for the S3 counters; desktop 4 columns, mobile 2. States: skeleton tiles, `ErrorState`
      with retry, offline shows the last data (TanStack cache) with the `OfflineBanner` of the shell.
      Query key `['admin', 'overview']`, endpoint `getAdminOverview()` in `src/api/endpoints.ts`.
S7. Nav: `navRegistry.ts` entry `admin` becomes `{status: 'spa', to: '/admin'}` (same icon, placements,
    `adminOnly: true`). `price` stays legacy. `legacy-routes.json` unchanged.
S8. i18n: new namespace `admin` (both languages, added to `resources.ts`/`NAMESPACES`) with the keys below;
    `common:offline.editDisabled` added. Re-create `frontend/src/i18n/parity.test.ts`: for every namespace,
    ES and EN have the same keys, the same `{{placeholders}}` per key and the same plural suffixes.
S9. Docs: `AGENTS.md` (blueprint `api_admin`, table `rbadminaudit`, audit rule "every admin write records an
    audit row in the same transaction"), `docs/frontend.md` (admin area and how a unit adds an admin page),
    `docs/knowledge/state.md`.

## API / data contract

```json
GET /riftbound/api/v1/admin/overview
{"success": true, "data": {"catalog": {"sets": 9, "sets_without_release_date": 2, "cards": 1243, "cards_without_image": 4}}}
```

## UI

| Key | ES | EN |
|---|---|---|
| `admin:title` | Administración | Administration |
| `admin:nav.label` | Secciones de administración | Administration sections |
| `admin:nav.overview` | Resumen | Overview |
| `admin:mobileHint` | Más cómodo en un ordenador. | Easier on a computer. |
| `admin:overview.title` | Resumen | Overview |
| `admin:overview.subtitle` | Estado del catálogo y de la sincronización. | Catalog and sync status. |
| `admin:overview.kpi.sets` | Sets | Sets |
| `admin:overview.kpi.setsWithoutDate` | Sets sin fecha de salida | Sets without release date |
| `admin:overview.kpi.cards` | Cartas | Cards |
| `admin:overview.kpi.cardsWithoutImage` | Cartas sin imagen | Cards without image |
| `common:offline.editDisabled` | Necesitas conexión para hacer cambios. | You need a connection to make changes. |

Layouts: mobile < 860 (select navigation, 2-column KPIs, hint), desktop ≥ 1240 (left nav, 4-column KPIs),
wide ≥ 1600 (same as desktop with the KPI band capped at 1200 px and room on the right that F13-f uses for the
detail panel). `useDocumentTitle(admin:overview.title)`.

## Acceptance criteria

- [ ] AC1 `tests/test_admin_api.py`: overview counts on fixture data; anonymous 401 JSON, user 403 JSON, admin 200; statement count ≤ 4 (S1, S3).
- [ ] AC2 `tests/test_audit.py`: user actor, system actor, no commit by `record`, invalid action, oversized details, unauthenticated caller (S5).
- [ ] AC3 `tests/test_admin_audit_migration.py`: round trip and drift, FK `ON DELETE SET NULL` behaviour (S4).
- [ ] AC4 Authz matrix green with `api_admin.*` (S2).
- [ ] AC5 Vitest: `AdminLayout` (nav at 1280 px, select at 390 px, hint < 860), `OverviewPage` states (loading, data, error), route guarded for non-admins; axe clean; `parity.test.ts` green (S6-S8).
- [ ] AC6 Full lanes green; docs and `state.md` updated (S9).

## Delivery

PR title: `feat(admin): admin API blueprint, audit log, admin layout and overview (F13 unit a)`.

## After merge

Deploy (backup first: migration `admin_audit`). Live: as admin open `/riftbound/app/admin` → four counters;
as a normal user the "Administración" entry is not shown and the URL shows "Página no encontrada".

## Open questions

none

## Log

- L1 (implementer): no product deviations. Test-only: the admin Vitest suites raise the
  `findBy`/test timeouts (10 s/30 s) because the loaded page needs the session and the overview
  requests in sequence; the `findBy*` queries read the live DOM (the HydrateFallback `<main>` is
  replaced on load, so a `within()` captured before it resolves goes stale).
