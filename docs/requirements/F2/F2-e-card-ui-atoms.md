# F2-e: Card UI atoms — image, placeholder, domain pips, rarity, ban badge, price tag

| Field | Value |
|---|---|
| Phase / unit | F2 / e |
| Branch | `feat/f2e-card-ui-atoms` (stacked on the previous unit's branch, `docs/requirements/BATCH-1.md` R1) |
| Depends on | F2-b merged (contract `CardSummary` in `docs/api.md`). No backend call is made in this unit |
| Size forecast | ~500 authored lines (tests and docs included) |
| Risk | `Risk: none` |
| TDD | ON (strict). Runners: `venv/bin/pytest` (backend, untouched), `cd frontend && npx vitest run` (frontend) |
| Save as | `docs/requirements/F2/F2-e-card-ui-atoms.md` (commit this document verbatim in the first commit if it is not in the repo yet) |

## Objective

The app gets the small building blocks every card screen reuses (catalog, detail, collection, decks): the
card image at the right 352×492 ratio with a designed fallback when the image is missing, the domain pips,
the rarity dot, the per-mode ban badge and the price with its trend — all accessible, translated, and
matching the prototype's look with the F1 tokens.

## Read first

- `AGENTS.md`, `docs/knowledge/conventions.md`, `docs/frontend.md`
- `docs/requirements/F2/README.md` (F2-R25, R26, R28; D-F2-12)
- `docs/api.md` → `CardSummary` (F2-b)
- `openspec/design-handoff.md` §1.11-1.12 (semantic and domain/rarity colours, glyph risk), §2.1 (DomainPips,
  RarityDot, CardArt, money/pct), §2.2 (placeholder algorithm), §7.4 A10/A14 (contrast, title-only meaning)
- `frontend/src/components/ui/Badge.tsx`, `Icon.tsx`, `icons.ts`; `frontend/src/lib/format.ts`,
  `contrast.ts`; `frontend/src/styles/tokens.css` + `tokens.test.ts`; `frontend/src/i18n/resources.ts`,
  `parity.test.ts`; `frontend/eslint.config.js` + `src/test/eslint-boundaries.test.ts`; `src/dev/KitchenSink.tsx`

## Scope

In:
- `frontend/src/components/card/`: `CardImage`, `CardArtPlaceholder`, `DomainPips`, `RarityDot`, `BanBadge`,
  `PriceTag`, `index.ts`.
- `frontend/src/api/types.ts`: `CardSummary` and its parts (types only).
- `frontend/src/lib/`: `color.ts` (`shadeHex`), `domains.ts` (colours), `formatPct` in `format.ts`.
- Tokens for domain and rarity colours; `enums` and `cards` i18n namespaces; `useEnumLabel`.
- ESLint boundary for `src/components/card/**` and `src/components/charts/**`.
- Shared test fixtures `frontend/src/test/fixtures/cards.ts`. Kitchen sink entries.

Out (do not do, even if tempting):
- Endpoints, queries, pages (F2-f+). `AbilityText` (F2-f). Charts (F2-g). Thumbnail generation (F2-l).

## Specs

S1. Types in `frontend/src/api/types.ts` mirror `docs/api.md` exactly: `GameMode = '1v1' | '2v2'`,
    `CardBans = Record<GameMode, boolean>`, `CardOwned = {total: number; foil: number}`, `CardPrice` (`market`,
    `market_source`, `market_foil`, `market_foil_source`, `trend_7d_pct`, `trend_30d_pct`, `as_of`; numbers
    and strings nullable as in the contract) and `CardSummary` (every key of the contract; `price: CardPrice | null`).

S2. `frontend/src/test/fixtures/cards.ts` exports six `CardSummary` fixtures used by this and later units:
    `champion` (two domains Fury+Chaos, Rare, price with trends, banned in 1v1), `foilCommon` (one domain,
    Common, `foilable: true`, `market_foil` set), `basicRune` (type Rune, supertype Basic, `foilable: false`),
    `token` (supertype Token, `card_id` `t01`, `number: null`), `noImage` (`image_src: null`), `noPrice`
    (`price: null`).

S3. Colours: `tokens.css` adds `--domain-fury #e7504a`, `--domain-calm #33b27b`, `--domain-mind #4f86e6`,
    `--domain-body #e08a36`, `--domain-chaos #a45cc8`, `--domain-order #d8b84a`, `--domain-colorless #8aa3ad`,
    `--rarity-common #9fb6bf`, `--rarity-uncommon #4fb6a5`, `--rarity-rare #4f86e6`, `--rarity-epic #a45cc8`,
    `--rarity-showcase #e0a93a`, and `--green-text #5fe0a8` (positive text, design-handoff §1.11; the
    existing `--red-text` is the negative one) inside the existing tokens layer; the contrast test covers
    `--green-text` on `--panel` (≥ 4.5:1). `src/lib/domains.ts` exports the same hex
    values (`DOMAIN_COLORS`, `RARITY_COLORS`) for SVG and gradients; a test asserts the CSS and TS values are
    equal. Unknown domain → colorless; unknown rarity → common colour.

S4. `shadeHex(hex, amount)` in `src/lib/color.ts`: each channel `clamp(v + amount * 2.55, 0, 255)`, rounded,
    returned as `#rrggbb`; accepts only `#rrggbb` (throws otherwise). Examples: `shadeHex('#000000', 100)` →
    `#ffffff`; `shadeHex('#e7504a', 0)` → `#e7504a`.

S5. `formatPct(value, lang)` in `src/lib/format.ts`: `Intl.NumberFormat(locale, {style: 'percent',
    minimumFractionDigits: 1, maximumFractionDigits: 1, signDisplay: 'exceptZero'})` of `value / 100`.
    Examples: `formatPct(10, 'en')` → `+10.0%`; `formatPct(-3.14, 'es')` → `-3,1 %` (with the locale's
    non-breaking space; compare with `Intl` output in the test, not a literal).

S6. i18n:
  - Namespace `enums` (`locales/{es,en}/enums.json`, registered in `resources.ts` and `NAMESPACES`) with the
    keys and texts of the UI section. Missing values fall back to the raw value through
    `useEnumLabel()` (`src/i18n/enumLabel.ts`, exported from `@/i18n`): `label('domain', 'Fury')` →
    `t('enums:domain.Fury', {defaultValue: 'Fury'})`.
  - Namespace `cards` with the keys of the UI section (F2-f adds more).

S7. `CardImage` props: `card` (`name`, `image_src`, `image_thumb_src`, `domains`, `type`, `supertype`,
    `energy`, `might`), `size: 'thumb' | 'tile' | 'full'`, `decorative?: boolean`, `priority?: boolean`,
    `className?`.
  - Wrapper keeps `aspect-ratio: 352 / 492`, radius 11 px, `container-type: inline-size`.
  - `<img>` source: `image_thumb_src` for `thumb`/`tile` when present, otherwise `image_src`; `full` always
    `image_src`. Attributes `width="352" height="492"`, `decoding="async"`, `loading="lazy"` unless
    `priority`; `alt` = card name, or `""` when `decorative`. CSS `width: 100%; height: auto; object-fit: cover`.
  - `image_src` null, or the image fires `error` → `CardArtPlaceholder` in the same box (no layout shift).
    After a thumb error the component tries `image_src` once before the placeholder.

S8. `CardArtPlaceholder` (design-handoff §2.2, ratio 352/492): background from the domain colours — two or
    more domains → `linear-gradient(150deg, d0 0%, d0 42%, d1 58%, d1 100%)` (first two only); one →
    `radial-gradient(120% 130% at 30% 12%, shadeHex(d0, 38), shadeHex(d0, -30))`; none → the colorless
    colour as the single domain; top gloss and inner frame as §2.2; the first domain's glyph (SVG, S9) at
    62 % size, opacity .16, rotated −8°, bottom-right; the translated type (supertype + type, upper case) top
    left; an energy circle when `energy` is not null; a might square (gold ring) when `might` is not null;
    the name at the bottom. It is `role="img"` with `aria-label` = card name (no role, `aria-hidden`, when
    decorative). Text sizes use `cqi` units with a 22 px cap so they scale with the tile.

S9. `DomainPips` props `domains: string[]`, `size?: number` (default 20), `className?`.
  - One 20×20 pip per domain (radius 6), background = domain colour, glyph = an inline SVG (24×24 viewBox)
    per domain replacing the prototype characters: Fury triangle, Calm eight-petal asterisk, Mind crescent,
    Body four-point star, Chaos burst, Order six-point star, Colorless diamond outline; unknown → circle.
  - Glyph ink = whichever of `#ffffff` and `#06222c` has the higher contrast with the pip colour
    (`lib/contrast.ts`); a test asserts ≥ 3:1 for all seven domains.
  - The group is `role="img"` with `aria-label` = translated names joined with
    `Intl.ListFormat(locale, {type: 'conjunction'})` (es: `Furia y Caos`; en: `Fury and Chaos`); pips are
    `aria-hidden`. Empty list → renders nothing.

S10. `RarityDot` props `rarity: string`, `showLabel?: boolean`. A 9 px dot in the rarity colour plus, when
     `showLabel`, the translated rarity text; without the label the dot is `role="img"` with
     `aria-label` = `t('cards:rarityLabel', {rarity})` (es `Rareza: Rara`, en `Rarity: Rare`).

S11. `BanBadge` props `bans: CardBans`, `variant?: 'full' | 'compact'` (default `full`). No ban → renders
     nothing. `full` → `Badge tone="danger"` with `t('cards:ban.full', {modes})` where `modes` are the banned
     modes joined with `Intl.ListFormat` (es `Baneada en 1v1 y 2v2`, en `Banned in 1v1 and 2v2`).
     `compact` → `warning` icon + the modes joined with ` · ` (`1v1 · 2v2`) and the full sentence as
     visually hidden text (`sr-only`).

S12. `PriceTag` props `price: CardPrice | null`, `foil?: boolean`, `trend?: '7d' | '30d' | null` (default
     `'7d'`), `size?: 'sm' | 'md' | 'lg'`.
  - Amount = `formatMoney(foil ? market_foil : market, lang)`; when missing → `t('cards:price.none')`
    (es `Sin precio`, en `No price`) in muted text.
  - Trend chip (when the chosen trend is a number): up/down arrow icon + `formatPct`; colour `--green-text` (up) or
    `--red-text` (down); accessible text (sr-only) `t('cards:trend.up' | 'down' | 'flat', {value, days})`.
  - Example (es, champion fixture): `1,21 €` and `+10,0 %` with sr-only `Sube un 10,0 % en 7 días`.

S13. ESLint: `frontend/eslint.config.js` adds a boundary for `src/components/card/**` and
     `src/components/charts/**`: they may import `@/lib`, `@/i18n`, `@/components/ui` and **types** from
     `@/api` only; never `auth`, `prefs`, `pwa`, `shell`, `account`, `app` or feature folders.
     `src/test/eslint-boundaries.test.ts` gets a failing and a passing case; a small test asserts every
     `@/api` import under `src/components/card` is `import type`.

S14. `/_kitchen` (dev only) shows each atom with the S2 fixtures, including the placeholder for the six
     fixtures and BanBadge in both variants.

## API / data contract

none (types only, S1).

## UI

Atoms only; no route. Visual reference: design-handoff §2.1-2.2. Every atom works at 390 px and inside
desktop tables; nothing here depends on breakpoints.

Strings — `enums.json`:

| Key | es | en |
|---|---|---|
| `domain.Fury` / `Calm` / `Mind` / `Body` / `Chaos` / `Order` / `Colorless` | Furia / Calma / Mente / Cuerpo / Caos / Orden / Incoloro | Fury / Calm / Mind / Body / Chaos / Order / Colorless |
| `type.Legend` / `Unit` / `Spell` / `Gear` / `Rune` / `Battlefield` | Leyenda / Unidad / Hechizo / Equipo / Runa / Campo de batalla | Legend / Unit / Spell / Gear / Rune / Battlefield |
| `supertype.Champion` / `Signature` / `Token` / `Basic` | Campeón / Distintiva / Ficha / Básica | Champion / Signature / Token / Basic |
| `rarity.Common` / `Uncommon` / `Rare` / `Epic` / `Showcase` | Común / Infrecuente / Rara / Épica / Showcase | Common / Uncommon / Rare / Epic / Showcase |
| `mode.1v1` / `mode.2v2` | 1v1 / 2v2 | 1v1 / 2v2 |

Strings — `cards.json`:

| Key | es | en |
|---|---|---|
| `rarityLabel` | Rareza: {{rarity}} | Rarity: {{rarity}} |
| `ban.full` | Baneada en {{modes}} | Banned in {{modes}} |
| `price.none` | Sin precio | No price |
| `trend.up` | Sube un {{value}} en {{days}} días | Up {{value}} in {{days}} days |
| `trend.down` | Baja un {{value}} en {{days}} días | Down {{value}} in {{days}} days |
| `trend.flat` | Sin cambios en {{days}} días | No change in {{days}} days |
| `foil` | Foil | Foil |

(`value` is passed without its sign: `formatPct(Math.abs(x))` minus the `+`.)

a11y: images have names or are decorative; pips/rarity/ban never rely on colour or `title` alone; trend has
text; contrast of every text ≥ 4.5:1 and every glyph ≥ 3:1 on its background.

## Acceptance criteria

- [ ] AC1 `src/components/card/CardImage.test.tsx`: source choice per size, attributes, alt/decorative, error → retry full → placeholder, null image → placeholder (S7).
- [ ] AC2 `src/components/card/CardArtPlaceholder.test.tsx`: gradient rule for 2/1/0 domains, type text translated, energy/might presence (S8).
- [ ] AC3 `src/components/card/DomainPips.test.tsx`: aria-label in es and en, glyph contrast ≥ 3:1 for all 7, unknown domain, empty (S9).
- [ ] AC4 `RarityDot`, `BanBadge`, `PriceTag` tests with the S10-S12 examples in both languages.
- [ ] AC5 `src/lib/color.test.ts`, `src/lib/format.test.ts` (`formatPct`), `src/lib/domains.test.ts` (CSS = TS colours), `src/i18n/enumLabel.test.ts` (fallback to raw value) (S3-S6).
- [ ] AC6 `src/components/card/axe.test.tsx`: the six fixtures rendered with every atom, no axe violations.
- [ ] AC7 ESLint boundary cases and the type-only import check (S13); parity test green with `enums` and `cards`.
- [ ] AC8 Full lanes green: `venv/bin/pytest`; `cd frontend && npm run lint && npm run typecheck && npx vitest run && npm run build && npm run check:dist`
- [ ] AC9 `docs/knowledge/state.md` updated (what changed, PR number placeholder, new follow-ups)
- [ ] AC10 `docs/frontend.md` gains a short "Card components" section (atoms, where they live, the boundary); `AGENTS.md` frontend tree lists `components/card/`.

## Delivery

- Conventional Commits; commit messages end with the attribution lines the session supplies.
- Push and PR only when the user says so. PR title: `feat(frontend): card UI atoms (F2 unit e)`.
  PR body: summary, specs → tests map (S# → test file::name), kitchen-sink screenshots at 390 px and
  1280 px, manual checks, rollback (revert; nothing uses the atoms yet).
- Never merge. The user merges.

## After merge (user asks gentle-shell, or does it)

- Deploy to dev with `docs/knowledge/ops-runbook.md` (frontend build only; no restart needed).
- Live checks: none (no screen uses the atoms yet; `/_kitchen` exists only in `npm run dev`).
- Manual checks for the user: review the kitchen-sink screenshots in the PR (placeholder look, pip glyphs,
  ban badge wording).

## Open questions

none — the CONFIRM items of the draft (D-F2-12) are answered in
`docs/knowledge/decisions-2026-10-25.md`; batch rules in `docs/requirements/BATCH-1.md` (G1-G12) apply.
