# F2-k: Card combobox and global card search

| Field | Value |
|---|---|
| Phase / unit | F2 / k |
| Branch | `feat/f2k-card-combobox` (from up-to-date `main`) |
| Depends on | F2-c (list API), F2-e (atoms), F2-h (catalog routes) merged |
| Size forecast | ~450 authored lines (tests and docs included) |
| Risk | `Risk: none` |
| TDD | ON (strict). Runners: `venv/bin/pytest` (backend, untouched), `cd frontend && npx vitest run` (frontend) |
| Save as | `docs/requirements/F2/F2-k-card-combobox.md` (commit this document verbatim in the first commit if it is not in the repo yet) |

## Objective

A reusable, keyboard- and screen-reader-friendly card picker that searches the server as you type (it will
be used to add cards to the collection in F3 and to pick legend/champion/cards in F5), and on desktop a
"Buscar cartas" box in the topbar that jumps straight to any card from any screen.

## Read first

- `AGENTS.md`, `docs/knowledge/conventions.md`, `docs/frontend.md`
- `docs/requirements/F2/README.md` (F2-R21, R26; D-F2-14)
- `openspec/design-handoff.md` §2.1 `CardPicker` → `CardCombobox`, §3.2 (desktop topbar), §7.4 A5
- WAI-ARIA 1.2 combobox pattern (editable combobox with list autocomplete)
- `frontend/src/catalog/{queries,params}.ts`, `src/api/endpoints.ts::listCards`, `src/components/card/*`,
  `src/shell/Topbar.tsx` (+ css, tests), `src/lib/breakpoints.ts`, `src/lib/useMediaQuery.ts`

## Scope

In:
- `src/catalog/CardCombobox.tsx` (+ css, tests), exported from `src/catalog/index.ts`.
- Topbar global search at ≥ 1240 px and the `/` shortcut.

Out (do not do, even if tempting):
- Recent searches, fuzzy matching, search of decks/collection. Any backend change.

## Specs

S1. `CardCombobox` props: `label` (visible or `hideLabel`), `onSelect(card: CardSummary)`, `filters?:
    Partial<CardListParams>` (passed to the API, e.g. `{base_only: true, exclude_supertype: ['Token']}`),
    `placeholder?`, `autoFocus?`, `clearOnSelect?` (default true), `id?`.

S2. Search: after 2 or more characters (trimmed), debounced 250 ms, `listCards({...filters, q, per_page: 20,
    sort: 'name'})`; previous request aborted; results cached by TanStack Query (key from the params). Fewer than
    2 characters → list closed, no request.

S3. ARIA 1.2: input `role="combobox"`, `aria-expanded`, `aria-controls` = listbox id, `aria-autocomplete="list"`,
    `aria-activedescendant` = active option id; popup `role="listbox"`; each option `role="option"` with
    `aria-selected` for the active one. Keys: ↓/↑ move (wrap), Home/End within the list when open, Enter
    selects the active option, Esc closes (second Esc clears the text), Tab closes without selecting. Mouse:
    `pointerdown` on an option selects it (no blur race). Clicking outside closes.

S4. Option content: `CardImage size="thumb" decorative` (32 px wide), name, `set_id · #card_id`, translated
    type, `DomainPips size={14}`, `formatMoney(price.market)` or `—`. Up to 20 options; when `meta.total` >
    20, a non-selectable last row `cards:combobox.more` (count).

S5. States inside the popup (announced through a polite live region): loading `cards:combobox.loading`, no
    results `cards:combobox.empty` (with the query), error `cards:combobox.error`, offline
    `cards:combobox.offline` (no request is made while `useOffline()` is true and nothing is cached).

S6. Global search: `Topbar` renders a `CardCombobox` (label hidden, `cards:combobox.globalLabel`, placeholder
    `cards:combobox.globalPlaceholder`, width 280 px) only at ≥ 1240 (`up('xl')`). Selecting a card navigates
    to `/cards/<set>/<id>` (state `fromCatalog: true`, so at ≥ 860 it opens as a modal over the catalog).
    Pressing `/` anywhere except in an editable field focuses it (`preventDefault`); the input shows a `/`
    key hint (`aria-hidden`).

S7. Popover layer uses `--z-popover`; inside a `Modal` it stays visible (it is rendered within the dialog).

## API / data contract

Consumes `GET /cards?q=&per_page=20&sort=name&…`. No backend change.

## UI

Mobile < 860: the combobox is full width where a feature places it (no global search in the topbar; the
catalog has its own search). Desktop ≥ 1240: topbar box between the nav and the account menu; popup
420 px wide, max height 60 dvh. Strings — `cards.json`:

| Key | es | en |
|---|---|---|
| `combobox.globalLabel` | Buscar cartas | Search cards |
| `combobox.globalPlaceholder` | Buscar cartas… | Search cards… |
| `combobox.loading` | Buscando… | Searching… |
| `combobox.empty` | No hay cartas que coincidan con «{{query}}». | No cards match "{{query}}". |
| `combobox.error` | No se pudo buscar. Inténtalo de nuevo. | The search failed. Try again. |
| `combobox.offline` | La búsqueda necesita conexión. | Search needs a connection. |
| `combobox.more` | y {{count}} más: afina la búsqueda | and {{count}} more: refine your search |
| `combobox.results_one` / `_other` | {{count}} resultado / {{count}} resultados | {{count}} result / {{count}} results |

## Acceptance criteria

- [ ] AC1 `src/catalog/CardCombobox.test.tsx`: 2-character threshold, debounce (fake timers), abort of the previous request, filters passed through, option content, "more" row (S1, S2, S4).
- [ ] AC2 Same file: keyboard (↓/↑ wrap, Home/End, Enter, Esc twice, Tab), pointer selection, outside click, ARIA attributes and live-region texts for every S5 state (S3, S5).
- [ ] AC3 `src/shell/Topbar.test.tsx`: global search only at ≥ 1240; selecting navigates to the detail; `/` focuses it except inside inputs (S6).
- [ ] AC4 Axe: combobox open with results, empty and error; topbar at 1280 px.
- [ ] AC5 Full lanes green: `venv/bin/pytest`; `cd frontend && npm run lint && npm run typecheck && npx vitest run && npm run build && npm run check:dist`
- [ ] AC6 `docs/knowledge/state.md` updated (what changed, PR number placeholder, new follow-ups)
- [ ] AC7 `docs/frontend.md`: "CardCombobox" usage (props, filters for F3/F5).

## Delivery

- Conventional Commits; commit messages end with the attribution lines the session supplies.
- Push and PR only when the user says so. PR title: `feat(catalog): card combobox and topbar search (F2 unit k)`.
  PR body: summary, specs → tests map (S# → test file::name), screenshots, manual checks, rollback (revert).
- Never merge. The user merges.

## After merge (user asks gentle-shell, or does it)

- Deploy to dev with `docs/knowledge/ops-runbook.md` (frontend build only).
- Live checks: at 1280 px the topbar shows "Buscar cartas"; typing two letters lists cards.
- Manual checks for the user: use the topbar search only with the keyboard (`/`, type, arrows, Enter) and
  with a screen reader if available (NVDA/VoiceOver announce the number of results and the active card).

## Open questions

- CONFIRM D-F2-14: global search in the topbar from 1240 px, `/` shortcut.
