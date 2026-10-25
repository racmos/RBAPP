# F13-f: Catalog admin UI — sets, cards, Riot sync panel

| Field | Value |
|---|---|
| Phase / unit | F13 / f — batch 1, unit 7 |
| Branch | `feat/f13f-catalog-admin-ui` (from the F13-e branch) |
| Depends on | F13-a, b, d, e (stack) |
| Size forecast | ~650 authored lines |
| Risk | `Risk: none` |
| TDD | ON (strict). Runner: `cd frontend && npx vitest run` (MSW handlers for the admin API) |
| Sources | F13 phase spec ("UI", F13-R27-R29), `decisions-2026-10-25.md` (D-F13-14, 15, 21) |

## Objective

The owner manages sets (with release date), cards and images, and starts and follows the Riot sync from the
new admin area, on desktop first and usable on the phone.

## Read first

- `frontend/src/admin/` (F13-a), `frontend/src/api/client.ts`, `frontend/src/api/endpoints.ts`
- `frontend/src/components/ui/` (Modal/Sheet, ConfirmDialog, Select, Input, Field, Switch, Badge, Toast,
  EmptyState, ErrorState, Skeleton, PageHeader), `frontend/src/test/msw/handlers.ts`
- `docs/api.md` → Admin API (F13-b/d/e shapes)

## Specs

S1. Client: `request` accepts a `FormData` body (no JSON `Content-Type`, the browser sets the boundary; CSRF
    header as for any POST). Endpoints in `endpoints.ts`: `listAdminSets`, `createAdminSet`, `patchAdminSet`,
    `deleteAdminSet`, `listAdminCards`, `createAdminCard`, `patchAdminCard`, `deleteAdminCard`,
    `uploadAdminCardImage`, `startRiotSync`, `listAdminJobs`, `getAdminJob`. Query keys under `['admin', …]`;
    every mutation invalidates `['admin']`.
S2. `Pagination` (`src/components/ui/Pagination.tsx`): `nav` with `aria-label` `common:pagination.label`, buttons
    `common:pagination.prev` / `common:pagination.next` (disabled at the ends) and the text
    `common:pagination.page`; props `page`, `pages`, `onChange`. (F2-h reuses it.)
S3. Admin nav (`adminNav.ts`) appends `sets` → `/admin/sets`, `cards` → `/admin/cards`, `riot` → `/admin/riot`.
S4. `/admin/sets` (`SetsPage`): `PageHeader` with button `admin:sets.new`.
    - ≥ 1240: table (`<caption>` `admin:sets.caption`, sortable headers with `aria-sort` on code, name and
      release date; client-side sort) with columns code, name, release date (`formatDate`), cards
      (`admin:sets.cardsValue` = "{{count}} / {{declared}}", declared `—` when null), window (`Badge` with
      `admin:window.<value>`), next run (`formatDate` with time, `—` when null), actions (Edit, Delete as icon
      buttons with accessible names `admin:sets.edit` / `admin:sets.delete` + code). Row click opens the editor
      in a right drawer (`Sheet` side right, 420 px).
    - ≥ 1600: the editor is a persistent right panel instead of a drawer (empty state `admin:sets.pickOne`).
    - < 860: one card per set (code + name, release date, window badge) with an actions menu; the editor opens
      in a bottom `Sheet`.
S5. `SetEditor`: fields code (`admin:sets.fields.id`, disabled with hint `admin:sets.idLocked` when the set has
    cards), name, release date (`<input type="date">`, required), declared count (number 0-999, optional); the
    help text `admin:sets.windowHelp`; buttons save / cancel. Validation errors from the API shown per field
    (`translateDetail`); 409 codes shown with `translateError` in a `FormAlert`. Success → toast
    `admin:sets.saved`.
S6. Delete set: `ConfirmDialog` title `admin:sets.confirmDelete.title` ("{{id}}"), body
    `admin:sets.confirmDelete.body`; `set_in_use` shows its translated error.
S7. `/admin/cards` (`CardsAdminPage`): filters bar — set `Select` (`admin:cards.filters.allSets` + every set),
    rarity `Select` (`admin:cards.filters.allRarities` + the raw values Common, Uncommon, Rare, Epic, Showcase),
    type text, search text (debounced
    300 ms), `Switch` `admin:cards.filters.missingImage`; filters live in the URL search string. Button
    `admin:cards.new`. `Pagination` (S2), page size `Select` 50/100/200 on desktop.
    - ≥ 1240: table with image (40 px wide, `alt=""`), set, number, name, type, rarity, a `Badge`
      `admin:cards.noImage` when `image` is empty; row click → `CardEditor` drawer (420 px); ≥ 1600 persistent
      panel.
    - < 860: list rows (image, name, `SET · #id`, rarity) → editor in a bottom `Sheet`.
S8. `CardEditor`: set and card id (editable only when creating; hint `admin:cards.keyLocked` otherwise), name
    (required), domain, type, tags, energy, power, might (0-99), ability (`textarea`, 6 rows), rarity, artist,
    image URL; each with the label key `admin:cards.fields.<field>` and the raw-value hints
    `admin:cards.hints.domain|type|tags`. Image block: preview (`image_src`), file input
    `admin:cards.image.upload` (`accept="image/png,image/jpeg,image/webp"`), hint `admin:cards.image.hint`;
    upload → toast `admin:cards.image.uploaded`. Delete button with `ConfirmDialog`
    (`admin:cards.confirmDelete.*`); `card_in_use` shown translated.
S9. `/admin/riot` (`RiotPage`):
    - "Sets en ventana activa" (`admin:riot.activeTitle`): from `GET /admin/overview` `riot.active_sets`, each with
      window badge and next run; empty → `admin:riot.noActive`.
    - "Sincronizar ahora": optional set multi-select (checkbox list in a `Sheet` on mobile, inline on desktop,
      label `admin:riot.pickSets`, hint `admin:riot.allSetsHint`) and primary button `admin:riot.syncNow`.
      On 202 → `JobStatus` for that job; `job_running` → translated error.
    - `JobStatus` (`src/admin/JobStatus.tsx`): polls `GET /admin/jobs/<id>` every 3 s while `queued` or
      `running` (stops on `success`/`error` and on unmount); shows `admin:job.status.<status>`, times, and for
      `riot_sync` results one line per set with `admin:riot.summary` (interpolated counts) and, when
      `proposed > 0`, a link `admin:riot.reviewChanges` to `/admin/riot/changes?set=<id>` (route of F13-g; until
      then the link may 404 — acceptable inside the stack); `error` shows the job message.
    - "Últimas ejecuciones" (`admin:riot.recentTitle`): last 10 `riot_sync` jobs (date, trigger
      `admin:riot.trigger.<schedule|manual>`, status badge, one-line summary
      `admin:riot.recentSummary`); a row opens its `JobStatus` in a `Modal`.
S10. Every screen: skeletons while loading, `ErrorState` with retry, `EmptyState` (`admin:sets.empty`,
     `admin:cards.empty`), offline → buttons and inputs disabled with `common:offline.editDisabled`
     (`useOnline`). Axe clean. `useDocumentTitle` per page.

## UI strings

| Key | ES | EN |
|---|---|---|
| `admin:nav.sets` | Sets | Sets |
| `admin:nav.cards` | Cartas | Cards |
| `admin:nav.riot` | Riot | Riot |
| `admin:window.pre_release` | Antes de la salida | Before release |
| `admin:window.post_release` | Recién salido | Just released |
| `admin:window.monthly` | Mensual | Monthly |
| `admin:window.none` | Sin empezar | Not started |
| `admin:sets.title` | Sets | Sets |
| `admin:sets.subtitle` | Alta, fecha de salida y estado de sincronización. | Creation, release date and sync status. |
| `admin:sets.caption` | Sets del catálogo | Catalog sets |
| `admin:sets.new` | Nuevo set | New set |
| `admin:sets.edit` | Editar {{id}} | Edit {{id}} |
| `admin:sets.delete` | Borrar {{id}} | Delete {{id}} |
| `admin:sets.cardsValue` | {{count}} / {{declared}} | {{count}} / {{declared}} |
| `admin:sets.columns.id` | Código | Code |
| `admin:sets.columns.name` | Nombre | Name |
| `admin:sets.columns.releaseDate` | Salida | Release |
| `admin:sets.columns.cards` | Cartas | Cards |
| `admin:sets.columns.window` | Ventana | Window |
| `admin:sets.columns.nextRun` | Próxima sincronización | Next sync |
| `admin:sets.columns.actions` | Acciones | Actions |
| `admin:sets.fields.id` | Código | Code |
| `admin:sets.fields.name` | Nombre | Name |
| `admin:sets.fields.releaseDate` | Fecha de salida | Release date |
| `admin:sets.fields.declaredCount` | Cartas anunciadas | Announced cards |
| `admin:sets.idLocked` | El código no se puede cambiar porque el set ya tiene cartas. | The code cannot change because the set already has cards. |
| `admin:sets.windowHelp` | La sincronización empieza 21 días antes de la salida (08:00 y 14:00), sigue una vez al día durante 14 días después y luego una vez al mes. | Sync starts 21 days before release (08:00 and 14:00), runs once a day for 14 days after it and then once a month. |
| `admin:sets.saved` | Set guardado. | Set saved. |
| `admin:sets.pickOne` | Elige un set para editarlo. | Pick a set to edit it. |
| `admin:sets.empty` | Todavía no hay sets. | There are no sets yet. |
| `admin:sets.confirmDelete.title` | ¿Borrar el set {{id}}? | Delete set {{id}}? |
| `admin:sets.confirmDelete.body` | Solo se puede borrar un set sin cartas. Esta acción no se puede deshacer. | Only a set without cards can be deleted. This cannot be undone. |
| `admin:cards.title` | Cartas | Cards |
| `admin:cards.subtitle` | Datos e imágenes del catálogo. | Catalog data and images. |
| `admin:cards.caption` | Cartas del catálogo | Catalog cards |
| `admin:cards.new` | Nueva carta | New card |
| `admin:cards.empty` | Ninguna carta coincide con los filtros. | No card matches the filters. |
| `admin:cards.noImage` | Sin imagen | No image |
| `admin:cards.filters.allSets` | Todos los sets | All sets |
| `admin:cards.filters.allRarities` | Todas las rarezas | All rarities |
| `admin:cards.filters.type` | Tipo | Type |
| `admin:cards.filters.search` | Buscar por nombre o número | Search by name or number |
| `admin:cards.filters.missingImage` | Solo sin imagen | Missing image only |
| `admin:cards.filters.pageSize` | Por página | Per page |
| `admin:cards.columns.image` | Imagen | Image |
| `admin:cards.columns.set` | Set | Set |
| `admin:cards.columns.number` | Nº | No. |
| `admin:cards.columns.name` | Nombre | Name |
| `admin:cards.columns.type` | Tipo | Type |
| `admin:cards.columns.rarity` | Rareza | Rarity |
| `admin:cards.fields.set_id` | Set | Set |
| `admin:cards.fields.card_id` | Número | Number |
| `admin:cards.fields.name` | Nombre | Name |
| `admin:cards.fields.domain` | Dominio | Domain |
| `admin:cards.fields.type` | Tipo | Type |
| `admin:cards.fields.tags` | Etiquetas | Tags |
| `admin:cards.fields.energy` | Energía | Energy |
| `admin:cards.fields.power` | Poder | Power |
| `admin:cards.fields.might` | Fuerza | Might |
| `admin:cards.fields.ability` | Habilidad | Ability |
| `admin:cards.fields.rarity` | Rareza | Rarity |
| `admin:cards.fields.artist` | Artista | Artist |
| `admin:cards.fields.image_url` | URL de la imagen en la galería | Gallery image URL |
| `admin:cards.hints.domain` | Como en la galería, separados por espacios: Fury Chaos | As in the gallery, separated by spaces: Fury Chaos |
| `admin:cards.hints.type` | Como en la galería: Champion Unit | As in the gallery: Champion Unit |
| `admin:cards.hints.tags` | Separadas por comas. | Separated by commas. |
| `admin:cards.keyLocked` | El set y el número no se pueden cambiar. | The set and number cannot change. |
| `admin:cards.saved` | Carta guardada. | Card saved. |
| `admin:cards.image.upload` | Subir imagen | Upload image |
| `admin:cards.image.hint` | PNG, JPG o WebP de hasta 2 MB. | PNG, JPG or WebP up to 2 MB. |
| `admin:cards.image.uploaded` | Imagen actualizada. | Image updated. |
| `admin:cards.confirmDelete.title` | ¿Borrar {{name}}? | Delete {{name}}? |
| `admin:cards.confirmDelete.body` | Solo se puede borrar una carta que no esté en colecciones ni mazos. | Only a card that is not in collections or decks can be deleted. |
| `admin:riot.title` | Sincronización con Riot | Riot sync |
| `admin:riot.subtitle` | La galería oficial se consulta según la fecha de salida de cada set. | The official gallery is read according to each set's release date. |
| `admin:riot.activeTitle` | Sets en ventana activa | Sets in an active window |
| `admin:riot.noActive` | Ningún set está cerca de su salida. | No set is close to its release. |
| `admin:riot.pickSets` | Sets a sincronizar | Sets to sync |
| `admin:riot.allSetsHint` | Sin selección se sincronizan todos los sets. | With no selection every set is synced. |
| `admin:riot.syncNow` | Sincronizar ahora | Sync now |
| `admin:riot.summary` | {{set}}: {{inserted}} nuevas · {{applied}} aplicadas · {{proposed}} propuestas · {{unchanged}} sin cambios | {{set}}: {{inserted}} new · {{applied}} applied · {{proposed}} proposed · {{unchanged}} unchanged |
| `admin:riot.reviewChanges` | Revisar cambios | Review changes |
| `admin:riot.recentTitle` | Últimas ejecuciones | Recent runs |
| `admin:riot.recentSummary` | {{sets}} sets · {{inserted}} nuevas · {{proposed}} propuestas | {{sets}} sets · {{inserted}} new · {{proposed}} proposed |
| `admin:riot.trigger.schedule` | Programada | Scheduled |
| `admin:riot.trigger.manual` | Manual | Manual |
| `admin:job.status.queued` | En cola | Queued |
| `admin:job.status.running` | En curso | Running |
| `admin:job.status.success` | Terminado | Finished |
| `admin:job.status.error` | Error | Error |
| `common:pagination.label` | Paginación | Pagination |
| `common:pagination.prev` | Anterior | Previous |
| `common:pagination.next` | Siguiente | Next |
| `common:pagination.page` | Página {{page}} de {{pages}} | Page {{page}} of {{pages}} |

## Acceptance criteria

- [ ] AC1 `client.test.ts`: `FormData` body keeps the CSRF header and has no JSON content type (S1).
- [ ] AC2 `Pagination.test.tsx`: disabled ends, labels, `onChange` (S2).
- [ ] AC3 `SetsPage.test.tsx`: table at 1280, cards at 390, persistent panel at 1700, create/edit/delete flows with API errors (`already_exists`, `set_in_use`), id lock hint (S4-S6).
- [ ] AC4 `CardsAdminPage.test.tsx`: filters in the URL, pagination, editor create/edit, image upload (FormData sent), delete with `card_in_use` (S7, S8).
- [ ] AC5 `RiotPage.test.tsx` + `JobStatus.test.tsx`: active sets, sync start, polling with fake timers until success, summary lines, `job_running`, recent runs (S9).
- [ ] AC6 States and offline disabling on every page; axe clean; parity test green (S10).
- [ ] AC7 Full lanes green; `docs/frontend.md` (admin pages) and `state.md`.

## Delivery

PR title: `feat(admin): sets, cards and Riot sync screens (F13 unit f)`. Screenshots at 390, 1280 and 1700 px in
the PR body (D-F13-14).

## After merge

Deploy (frontend build). Manual (owner): create a test set with a date in three weeks, see its window
"Antes de la salida"; edit a card's artist; upload an image; "Sincronizar ahora" for one set and watch the job finish.

## Open questions

none
