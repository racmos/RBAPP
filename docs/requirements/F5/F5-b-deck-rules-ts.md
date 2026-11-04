# F5-b: Deck rules library (TypeScript)

| Field | Value |
|---|---|
| Phase / unit | F5 / b (PR A of F5 together with F5-a) |
| Branch | `feat/f5b-deck-rules-ts` (stacked on `feat/f5ab-deck-rules`, PR #91) |
| Depends on | F5-a (Python engine, `DECK_RULES` in `/meta/game`, shared cases) |
| Size forecast | ~500 authored lines (tests and docs included) |
| Risk | `Risk: item 3 (the library must match the Python engine and the shared cases; the editor of F5-h consumes it)` |
| TDD | ON (strict). Runner: `cd frontend && npx vitest run` (frontend only; no backend change) |
| Save as | `docs/requirements/F5/F5-b-deck-rules-ts.md` |

## Objective

The deck editor can check a deck while the user edits it, without a round trip: the same rules as the
backend engine (validation with issues and completeness, add and move checks, hard limits, legend and
champion choice, auto runes, deck domains, name order) as pure TypeScript functions, proven equal to the
Python engine by running every shared case. The server stays authoritative.

## Read first

- `AGENTS.md` (Frontend), `docs/frontend.md`
- `docs/requirements/F5/F5-a-deck-rules-engine.md` (S1-S15, L1-L15), `docs/requirements/F5/README.md`
  (F5-R3, F5-R4, D-F5-7, D-F5-8)
- `app/services/deck_rules.py` (the reference), `tests/test_deck_rules_cases.py`,
  `tests/fixtures/deck_rules_cases.json`
- `openspec/design-handoff.md` §5.1-5.5, `frontend/eslint.config.js`

## Scope

In:
- `frontend/src/decks/rules/` (types, constants, the functions, barrel) and its tests
- `GameMeta.rules.deck` typed in `frontend/src/api/types.ts`
- ESLint: the `decks` folder and the purity boundary of `decks/rules`

Out (do not do, even if tempting):
- Any backend change, the cases file or the Python engine (a disagreement is reported, not edited)
- UI screens (F5-h), API calls, i18n strings (no user-visible text)

## Specs

S1. `frontend/src/decks/rules/` ports every public function of `app/services/deck_rules.py` with the
  same behaviour, issue order and params: `validate(deck, cards, bans, mode, rules)` →
  `{legal, issues, completeness}`, `completeness(deck, rules)`, `canAdd(deck, cards, card, zone, rules)`,
  `canMove(deck, cards, card, from, to, rules)`, `hardLimitViolations(deck, cards, rules)`,
  `applyLegend(deck, cards, legend)`, `applyChampion(deck, cards, champion, rules)`,
  `autoRunes(deck, cards, rules)`, `deckDomains(deck, cards, rules)`, `sortNames(names)`, plus `nameKey`,
  `compareNames`, `copies`, `identity`, `isToken`, `isChampionUnit`. `ISSUE_CODES`, `HARD_RULES`,
  `ZONE_ORDER`, `ADD_ZONES`, `MOVE_ZONES` equal the Python tuples.
S2. Rule values are never hardcoded: the functions take a `RulesContext {deck: DeckRules, modes,
  domains}`; `rulesFromMeta(meta)` builds it from `GET /meta/game` (`null` without `rules.deck`).
  `DEFAULT_RULES` (the backend values) is used only by tests.
S3. `cards` is a `Map` keyed by `cardKey({set, id})` (`makeCards`); any `CardSummary` is a valid card.
  An unknown card throws `UnknownCard` with `ref = [set, id]`; an unknown mode, zone or move, or a card
  not in the `from` zone, throws `RangeError` with the Python message (`unknown game mode: ffa`,
  `unknown zone: legend`, `unknown move: main -> main`, `card not in sideboard`).
S4. Pure: no input is mutated (frozen inputs work), the result shares no object with the inputs, and
  `decks/rules` imports nothing but its sibling modules (no React, api, lib, package, `node:` or DOM).
S5. Names (D-F5-7): `nameKey` = `name_key` with `toLocaleLowerCase('en')` for `casefold()` and Python's
  whitespace set; order by `(nameKey, name)` in code-point order (not UTF-16 units, no
  `localeCompare`). `autoRunes` uses `Math.floor(x + 0.5)`.
S6. `frontend/src/decks/rules/cases.test.ts` runs every case of `tests/fixtures/deck_rules_cases.json`
  (read with `fs`, never imported into the bundle; test name = case id), with the Python runner's card
  resolution, and guards the file: unique ids, well-formed cases, the Python runner's `OPS` all handled
  and present, the Python `ISSUE_CODES` and `HARD_RULES` in order, every code and hard rule expected,
  and the number of cases run equals the number in the file.

## API / data contract

none (frontend only). `GameMeta.rules` is typed `{deck?: DeckRuleValues; [key]: unknown}`.

## UI

none

## Acceptance criteria

- [x] AC1 S1, S5, S6: `src/decks/rules/cases.test.ts` (143 cases: validate 48, can_add 29, can_move 9,
  auto_runes 16, hard_limits 16, apply_champion 12, apply_legend 7, deck_domains 4, sort_names 2; all
  pass, no divergence from Python)
- [x] AC2 S2-S5: `src/decks/rules/rules.test.ts` (purity, errors, values from the context, defaults equal
  `game_domain.py`, `DEFAULT_RULES` only in tests, `CardSummary` input, names)
- [x] AC3 S4: `src/test/eslint-boundaries.test.ts` (F5-b tests)
- [x] AC4 Frontend lanes green: `npm run lint && npm run typecheck && npx vitest run && npm run build &&
  npm run check:dist`
- [x] AC5 `docs/frontend.md`, `docs/knowledge/state.md`, `AGENTS.md`, F5 `README.md` updated

## Delivery

- Conventional Commits, one commit for this unit. Push and PR only when the owner says so; PR A of F5
  together with F5-a. Never merge.

## After merge

- Nothing to deploy beyond the frontend build (no screen uses the library until F5-h).

## Log

- L1 (agent): the functions take an explicit `rules: RulesContext` (Python reads module constants); it
  carries `modes` (unknown mode check) and `domains` (`deckDomains` order) too. `applyLegend` and
  `sortNames` read no value and take none.
- L2 (agent): `GameMeta.rules.deck` is optional in the type because existing tests outside this unit
  type a `GameMeta` with `rules: {}`; the server always sends it and the default MSW handler now does.
- L3 (agent): `deckDomains` orders by the context's `domains`; `/meta/game` lists `DOMAINS` and then
  extra data values sorted by `str.lower`, so a domain outside `DOMAINS` present in the meta keeps the
  meta position (Python sorts it by `name_sort_key`). Only data outside the game tuples differs.
- L4 (agent): `casefold()` vs `toLocaleLowerCase('en')`: they differ for `ß` (→ `ss`), ligatures (`ﬁ` →
  `fi`), final sigma (`ς` vs `σ`) and a few others; no catalog name in the cases uses them. Python's
  `split()` whitespace (adds `\x1c-\x1f`, `\x85`; not `\ufeff`) is reproduced exactly.
- L5 (agent): the shared-cases loader lives in `src/test/deckRulesCases.ts` (also used by the purity
  test); the ESLint purity rule exempts `*.test.ts` in `decks/rules`.

## Open questions

none
