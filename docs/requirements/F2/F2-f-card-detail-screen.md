# F2-f: Card detail screen

| Field | Value |
|---|---|
| Phase / unit | F2 / f |
| Branch | `feat/f2f-card-detail-screen` (stacked on the previous unit's branch, `docs/requirements/BATCH-1.md` R1) |
| Depends on | F2-d (detail API) and F2-e (atoms) merged |
| Size forecast | ~650 authored lines (tests and docs included) |
| Risk | `Risk: none` |
| TDD | ON (strict). Runners: `venv/bin/pytest` (backend, untouched), `cd frontend && npx vitest run` (frontend) |
| Save as | `docs/requirements/F2/F2-f-card-detail-screen.md` (commit this document verbatim in the first commit if it is not in the repo yet) |

## Objective

A user can open any card at `/riftbound/app/cards/<set>/<id>` and see everything about it: the art, its
Cardmarket prices and trend, the rules text with game symbols, attributes, in which mode it is banned and
why, their own copies, other printings, related cards and the decks of theirs that use it. On a phone it
is a full screen; on desktop it is built to open as a large modal over the catalog (the catalog itself
arrives in F2-h), with 2 columns from 860 px and 3 columns from 1240 px.

## Read first

- `AGENTS.md`, `docs/knowledge/conventions.md`, `docs/frontend.md`
- `docs/requirements/F2/README.md` (F2-R17, R20, R25, R26; D-F2-5)
- `docs/api.md` → `CardDetail`, `CardMini` (F2-d)
- `openspec/design-handoff.md` §2.3 (ability grammar), §3.5 (card modal), §3.13 (layout matrix), §7.4 A4/A20
- `frontend/src/app/routes.tsx`, `src/api/{client,endpoints,types}.ts`, `src/components/ui/Modal.tsx` (+ tests),
  `src/components/card/*` (F2-e), `src/shell/legacyRoutes.ts`, `src/lib/useMediaQuery.ts`, `src/lib/breakpoints.ts`,
  `src/test/msw/handlers.ts`, `src/test/viewport.ts`, `src/test/renderApp.tsx`, `frontend/eslint.config.js`

## Scope

In:
- Folder `frontend/src/catalog/` (page-level, like `account/`): `CardsLayout`, `CardDetailRoute`, `CardDetailView`
  and its sections, `useCardDetail`.
- `getCard` endpoint and the `CardDetail` family of types.
- `AbilityText` + `parseAbility` in `src/components/card/`.
- `Modal` `size` prop.
- Routes `/cards` (layout, `Outlet` only for now) and `/cards/:setId/:cardId`.

Out (do not do, even if tempting):
- The catalog list and the nav flip (F2-h). The price chart (F2-g leaves a slot here). Editing collection
  lines, wishlist, deck actions (F3/F5). Offline caching (F2-j).

## Specs

S1. Types (`src/api/types.ts`) mirror `docs/api.md`: `CardMini`, `CardPriceDetail` (`date`, `product_id`,
    `columns`, `foil_product_id`, `foil_columns`), `BanInfo` (`mode`, `since`, `reason`), `MyLine`, `InDeck`,
    `CardDetail = CardSummary & {...}`. Endpoint `getCard(setId, cardId, signal?)` in `src/api/endpoints.ts`
    calls `request<CardDetail>('/cards/' + encodeURIComponent(setId) + '/' + encodeURIComponent(cardId))`.

S2. `useCardDetail(setId, cardId)` (`src/catalog/queries.ts`): TanStack Query key
    `['cards', 'detail', setId, cardId]`, `staleTime` 5 minutes, no retry on 404.

S3. ESLint: `catalog` joins `FOLDERS` and the `shell`/`account` boundary group (may import everything below,
    never `app`). The boundary test gets one case.

S4. Routes (inside the shell, lazy): `{path: '/cards', Component: CardsLayout, children: [{path: ':setId/:cardId', Component: CardDetailRoute}]}`.
    `CardsLayout` renders `<Outlet context={{presentation: 'page'}} />` only (F2-h replaces it with the
    catalog, which passes `presentation: 'modal'` and `siblings`). `/cards` alone renders nothing yet beyond
    the layout (F2-h adds the index); it is not linked anywhere in this unit.

S5. Outlet context type (exported from `src/catalog/context.ts`):
    `{presentation: 'page' | 'modal'; siblings?: {setId: string; cardId: string}[]; onClose?: () => void}`.
  - `page` → `CardDetailView` inside the page: back button (`common:actions.back`) that goes back in
    history when the previous entry is in the app, otherwise to `/cards`.
  - `modal` → the same view inside `Modal` with `size="xl"`, `title` = card name; closing (Esc, ×,
    backdrop) calls `onClose`.

S6. Prev/next (only when `presentation === 'modal'` and `siblings` contains the card): two icon buttons
    (`cards:detail.nav.prev` / `next`) and the ←/→ keys (ignored while focus is in an input, select or
    textarea) navigate with `replace: true` to the previous/next sibling, keeping the location state;
    disabled at the ends.

S7. `CardDetailView` content, in this order on mobile (one column):
    1. `CardImage size="full" priority` (max 260 px wide, centred).
    2. Eyebrow `cards:detail.eyebrow` (`{{set}} · #{{number}}` with the set name and `card_id`), `h1` (page) or
       the modal's `h2` with the name, `RarityDot showLabel`, `DomainPips`, type line = translated supertype
       and type joined with ` · ` (`Campeón · Unidad`), tags as links to `/cards?tag=<tag>`.
    3. Bans: `BanBadge` + one line per `ban_info` item (`cards:detail.bans.line` with the mode and
       `formatDate(since)`, plus `cards:detail.bans.reason` when there is a reason); not banned →
       `cards:detail.bans.none`.
    4. Prices panel (`cards:detail.prices.title`): "Mercado" = `formatMoney(price.market)` large, with
       `cards:detail.prices.sourceLine` (source translated by `cards:detail.prices.source.<market_source>`);
       "Mín." = `price_detail.columns.low`; "Media 30 d" = `price_detail.columns.avg30`; "Mercado foil" =
       `price.market_foil` only when `foilable`; trend chips 7 d and 30 d (`PriceTag`-style, with their
       accessible text); footer `cards:detail.prices.asOf` with `formatDate(price.as_of)`. `price` null →
       `cards:detail.prices.none` only. Missing single values show `—`.
    5. An empty `<div data-slot="price-chart" />` (F2-g fills it).
    6. Text panel (`cards:detail.text.title`) with `AbilityText` (S9).
    7. Attributes (`cards:detail.attributes.*`): energy, power, might, type, rarity, domains, artist as a
       `<dl>`; null → `—`.
    8. My copies (`cards:detail.mine.title`): total via `cards:detail.mine.total` (plural) and one row per
       `my_lines` item (`cards:detail.mine.line`, a `Foil` badge when foil, `cards:detail.mine.selling` with
       `formatMoney(sell_price)` or `sellingNoPrice`); none → `cards:detail.mine.none`. Link
       `cards:detail.mine.manage` to `legacyHref('collection')` (plain `<a>`, full navigation).
    9. Other printings (`cards:detail.printings.title`, only when there is more than one): a horizontal list of
       links to each printing's detail (`CardImage size="thumb" decorative`, `set_id · #card_id`, rarity
       dot, `formatMoney(market)` or `—`); the current one has `aria-current="page"` and no link.
    10. Related (`cards:detail.related.title`): grid of up to 12 links (thumb + name); none → `related.none`.
    11. In my decks (`cards:detail.decks.title`): rows `<name> — cards:detail.decks.qty` linking to
        `legacyHref('decks') + '/view/' + deck_id` (plain `<a>`); none → `decks.none`.

S8. Layout by width (CSS Modules, widths only from `breakpoints.ts`; the page is capped at `--maxw`):
  - < 860: one column as S7.
  - 860-1239: two columns `minmax(220px, 280px) 1fr`: left = image + prices; right = the rest in S7 order.
  - ≥ 1240: three columns `280px 1fr 1fr`: A = image + prices + chart slot; B = header block (2), bans,
    text, attributes, my copies; C = printings, related, decks. In `modal` presentation the modal is
    `size="xl"`; in `page` presentation the same grid sits in the page.

S9. `parseAbility(text)` (`src/components/card/parseAbility.ts`, pure) and `AbilityText` (design-handoff §2.3):
  - Step 1: split on `/(\([^()]*\))/g`; parenthesised parts become `{kind: 'reminder', children}` whose inner
    text (without the parentheses kept as text around it) goes through step 2.
  - Step 2: split on `/(:rb_[a-z0-9_]+:|\[[^\]]+\])/g`: `[X]` → `{kind: 'keyword', text: 'X'}` (`[>]`,
    `[Assault 2]`, `[Level 16]` included); `:rb_energy_N:` → `{kind: 'energy', value: N}`; `:rb_exhaust:` →
    `{kind: 'exhaust'}`; `:rb_might:` → `{kind: 'might'}`; `:rb_rune_<fury|calm|mind|body|chaos|order>:` →
    `{kind: 'rune', domain: 'Fury'…}`; `:rb_rune_rainbow:` → `{kind: 'rune', domain: 'rainbow'}`; any other
    `:rb_x:` → `{kind: 'keyword', text: 'x'}`; the rest → `{kind: 'text', text}`.
  - Rendering: keyword pill (accent tint, 12 px/800, no brackets); energy circle with the number and sr-only
    `cards:ability.energy` (count); exhaust and might as inline SVG (gold) with sr-only
    `cards:ability.exhaust` / `might`; rune dot in the domain colour (rainbow = conic gradient of the six
    colours) with sr-only `cards:ability.rune` (translated domain) or `runeAny`; reminder in italic
    `--muted-2`. `null`/empty → `cards:ability.empty` in muted text.
  - Examples: `"[Accelerate] When I attack, deal 2."` → keyword + text; `"Pay :rb_energy_2: (then :rb_exhaust:)"`
    → text, energy 2, text, reminder[text, exhaust]; `":rb_power:"` → keyword `power`.

S10. `Modal` gets `size?: 'md' | 'lg' | 'xl'` (default `md` = today's width, so no existing dialog changes):
     `lg` = `min(960px, 100%)`, `xl` = `min(1200px, 100%)`; below 680 px every size is full screen as today.

S11. States: loading → skeleton of the S8 grid (`aria-busy`, label `cards:detail.loading`); 404 →
     `EmptyState` `cards:detail.notFound.title` / `body` with a link `notFound.action` to `/cards`; other
     errors → `ErrorState` (message from `translateError`) with retry; `useDocumentTitle(name)` once loaded.

## API / data contract

Consumes `GET /riftbound/api/v1/cards/{set_id}/{card_id}` (F2-d). No backend change.

## UI

Route: `/riftbound/app/cards/:setId/:cardId`. Layouts S8; states S11; MSW handler for the detail with a
fixture `cardDetail` added to `src/test/fixtures/cards.ts` (the `champion` card with 3 printings, 2 related,
a ban in 1v1 with reason, two `my_lines` (one foil, one selling at 1.50) and one deck).

Strings — `cards.json` (add under `detail` and `ability`):

| Key | es | en |
|---|---|---|
| `detail.eyebrow` | {{set}} · #{{number}} | {{set}} · #{{number}} |
| `detail.loading` | Cargando carta | Loading card |
| `detail.notFound.title` | Carta no encontrada | Card not found |
| `detail.notFound.body` | Puede que el enlace sea antiguo o que la carta ya no exista. | The link may be old or the card may no longer exist. |
| `detail.notFound.action` | Ir al catálogo | Go to the catalog |
| `detail.nav.prev` / `detail.nav.next` | Carta anterior / Carta siguiente | Previous card / Next card |
| `detail.bans.line` | {{mode}}: baneada desde el {{date}} | {{mode}}: banned since {{date}} |
| `detail.bans.reason` | Motivo: {{reason}} | Reason: {{reason}} |
| `detail.bans.none` | Legal en 1v1 y 2v2 | Legal in 1v1 and 2v2 |
| `detail.prices.title` | Precios | Prices |
| `detail.prices.market` / `marketFoil` / `low` / `avg30` | Mercado / Mercado foil / Mín. / Media 30 d | Market / Foil market / Low / 30-day avg. |
| `detail.prices.sourceLine` | Según {{source}} | Based on the {{source}} |
| `detail.prices.source.avg7` / `avg7_foil` / `low` / `low_foil` | la media de 7 días / la media de 7 días foil / el precio mínimo / el precio mínimo foil | 7-day average / 7-day foil average / lowest price / lowest foil price |
| `detail.prices.asOf` | Precios de Cardmarket a {{date}} | Cardmarket prices as of {{date}} |
| `detail.prices.none` | Esta carta aún no tiene precio en Cardmarket. | This card has no Cardmarket price yet. |
| `detail.prices.trend7` / `trend30` | 7 días / 30 días | 7 days / 30 days |
| `detail.text.title` | Texto | Text |
| `detail.attributes.title` | Atributos | Attributes |
| `detail.attributes.energy` / `power` / `might` / `type` / `rarity` / `domains` / `artist` / `tags` | Energía / Poder / Fuerza / Tipo / Rareza / Dominios / Artista / Etiquetas | Energy / Power / Might / Type / Rarity / Domains / Artist / Tags |
| `detail.mine.title` | Mis copias | My copies |
| `detail.mine.total_one` / `_other` | Tienes {{count}} copia / Tienes {{count}} copias | You have {{count}} copy / You have {{count}} copies |
| `detail.mine.none` | Todavía no tienes esta carta. | You don't have this card yet. |
| `detail.mine.line` | {{qty}}× · {{condition}} · {{language}} | {{qty}}× · {{condition}} · {{language}} |
| `detail.mine.selling` / `sellingNoPrice` | En venta a {{price}} / En venta | For sale at {{price}} / For sale |
| `detail.mine.manage` | Gestionar en la colección | Manage in the collection |
| `detail.printings.title` | Otras versiones | Other printings |
| `detail.related.title` / `related.none` | Relacionadas / No hay cartas relacionadas. | Related cards / No related cards. |
| `detail.decks.title` | En mis mazos | In my decks |
| `detail.decks.qty_one` / `_other` | {{count}} copia / {{count}} copias | {{count}} copy / {{count}} copies |
| `detail.decks.none` | No está en ningún mazo tuyo. | Not in any of your decks. |
| `ability.energy` | {{count}} de energía | {{count}} energy |
| `ability.exhaust` / `ability.might` | agotar / fuerza | exhaust / might |
| `ability.rune` / `ability.runeAny` | runa de {{domain}} / runa de cualquier dominio | {{domain}} rune / rune of any domain |
| `ability.empty` | Sin texto | No text |

a11y: one `h1` (page) or the modal title as `h2`; sections are `section` + `h2`/`h3`; focus moves to the
modal title on open and returns to the opener on close (existing Modal behaviour); prev/next buttons have
names; links to Jinja pages are plain anchors.

## Acceptance criteria

- [ ] AC1 `src/components/card/parseAbility.test.ts`: every S9 rule and example, nested reminder content, unknown rune colour, empty input.
- [ ] AC2 `src/components/card/AbilityText.test.tsx`: rendering and sr-only texts in es and en.
- [ ] AC3 `src/catalog/CardDetailView.test.tsx`: S7 sections with the fixture; price null; foil market only when foilable; ban lines with and without reason; my copies variants; printing `aria-current`; legacy hrefs for collection and deck.
- [ ] AC4 `src/catalog/CardDetailRoute.test.tsx`: page at 390 px; page grid at 1280 px (3 columns class); modal presentation via a test layout with siblings → ←/→ and buttons, disabled ends, Esc calls `onClose`; S11 states (loading, 404, error + retry).
- [ ] AC5 `src/components/ui/Modal.test.tsx`: `size` classes; default unchanged (S10).
- [ ] AC6 `src/app/routes.test.tsx`: `/cards/OGN/79` renders the detail; axe clean for page (390, 1280) and modal.
- [ ] AC7 ESLint boundary case for `catalog` (S3).
- [ ] AC8 Full lanes green: `venv/bin/pytest`; `cd frontend && npm run lint && npm run typecheck && npx vitest run && npm run build && npm run check:dist`
- [ ] AC9 `docs/knowledge/state.md` updated (what changed, PR number placeholder, new follow-ups)
- [ ] AC10 `docs/frontend.md` ("Catalog" section: routes, presentation context, where sections live); `AGENTS.md` frontend tree lists `catalog/`.

## Delivery

- Conventional Commits; commit messages end with the attribution lines the session supplies.
- Suggested slices: (1) types + endpoint + `parseAbility`/`AbilityText` + Modal size, (2) view sections, (3) route + layouts + states.
- Push and PR only when the user says so. PR title: `feat(catalog): card detail screen (F2 unit f)`.
  PR body: summary, specs → tests map (S# → test file::name), screenshots at 390, 1024 and 1440 px, manual
  checks, rollback (revert; route not linked from the nav yet).
- Never merge. The user merges.

## After merge (user asks gentle-shell, or does it)

- Deploy to dev with `docs/knowledge/ops-runbook.md` (frontend build only).
- Live checks: `<URL>/riftbound/app/cards/<a real set>/<a real id>` signed in → the detail renders with
  prices; `<URL>/riftbound/app/cards/NOPE/1` → "Carta no encontrada".
- Manual checks for the user: open three real cards on the phone and on desktop (a champion with printings,
  a common foil, a Basic Rune) and check prices against Cardmarket, the symbols in the rules text and the
  "Mis copias" numbers against the Jinja collection.

## Open questions

none — the CONFIRM items of the draft (D-F2-5) are answered in
`docs/knowledge/decisions-2026-10-25.md`; batch rules in `docs/requirements/BATCH-1.md` (G1-G12) apply.
