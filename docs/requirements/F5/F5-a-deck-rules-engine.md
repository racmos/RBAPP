# F5-a: Deck rules engine (Python) + rule values

| Field | Value |
|---|---|
| Phase / unit | F5 / a (PR A of F5; F5-b, the TypeScript port, runs the same cases) |
| Branch | `feat/f5ab-deck-rules` (from `main` `1cde14f`) |
| Depends on | F2 done (bans per mode, `name_key`, `parse_type`, `/meta/game`) |
| Size forecast | ~600 authored lines + the generated cases file (tests and docs included) |
| Risk | `Risk: item 3 (the shared cases file and the issue codes/params are a contract F5-b, F5-d and the UI consume)` |
| TDD | ON (strict). Runner: `venv/bin/pytest` (backend only; no frontend change) |
| Save as | `docs/requirements/F5/F5-a-deck-rules-engine.md` |

## Objective

The deck rules of the game live once in the backend, as pure functions any later unit can call: the
rule values are served by `/meta/game`, a v2 deck can be validated per game mode with machine-readable
issues that say what is wrong and what each section is missing, the editor can ask whether a card may
be added or moved, the hard limits are listed for the decks API, and the prototype's deck operations
(legend and champion choice, auto runes) are ported with their known bugs fixed. A shared JSON cases
file fixes the behaviour for the TypeScript port.

## Read first

- `AGENTS.md`, `docs/knowledge/conventions.md`, `docs/knowledge/product.md` → "Game rules"
- `docs/requirements/F5/README.md` (F5-R1..R4, R6, R9, D-F5-7, D-F5-8)
- `openspec/design-handoff.md` §5.1-5.5, §7.6 (L9)
- `app/schemas/game_domain.py`, `app/services/catalog.py` (`parse_type`, `card_summary`),
  `app/services/bans.py` (`name_key`, `ban_map`), `app/services/riot_scraper.py` (`full_name`:
  legends store the bare name, the champion is in the tags)
- `docs/requirements/F5/samples/deck-export-text-1.txt` (the owner's real deck)

## Scope

In:
- `DECK_RULES` and `rules.deck` in `GET /meta/game`
- `app/services/deck_rules.py` (pure functions, no Flask, no database)
- `tests/fixtures/deck_rules_cases.json` + `tests/test_deck_rules_cases.py`, `tests/test_deck_rules.py`

Out (do not do, even if tempting):
- The TypeScript port (F5-b), the v2 tables and Pydantic content model (F5-c), the decks API and
  `deck_limit_exceeded` (F5-d), import/export parsers (F5-e), deck value
- No migration, no new route, no new HTTP error code

## Specs

S1. `app/schemas/game_domain.py` `DECK_RULES = {main_size: 39, total_with_champion: 40, runes: 12,
  battlefields: 3, sideboard: 10, copies_max: 3, workbench_max: 100}` (that key order). `GET /meta/game`
  returns `rules: {deck: DECK_RULES}`; nothing else of the payload changes. The engine reads every
  value from `DECK_RULES` (a changed value changes the rules).

S2. Inputs. `deck` = content v2 `{"v": 2, "legend": ref|null, "champion": ref|null, "main": [line],
  "runes": [line], "battlefields": [ref], "sideboard": [line], "workbench": [line]}`, `ref = {set,
  id}`, `line = {set, id, qty}`; a missing zone is empty. `cards` = `{(set_id, card_id): card}` with
  the `CardSummary` fields `name`, `type`, `supertype` (str|null), `domains`, `tags` (extra keys are
  ignored, so `card_summary` output works). `bans` = `{name: [modes]}`, names compared with
  `name_key` (keys normalised too). A referenced card missing from `cards` raises
  `deck_rules.UnknownCard((set, id))`; an unknown mode, zone or move raises `ValueError`. No function
  mutates its inputs; operations return a new deck.

S3. Names (D-F5-7). Printings of one `name_key` are one card. `name_sort_key(name) = (name_key(name),
  name)`, compared in code-point order (no locale collation): space < `'` < `,`; "Élan" sorts after
  "Zed"; ties by the raw name ("REBUKE" < "Rebuke", "Zhonya's" < "Zhonya’s"). `sort_names(names)`
  sorts with it. Wherever a function reports a name it is the first occurrence in zone order
  legend, champion, battlefields, main, sideboard, runes, workbench.

S4. Card classes. Token: supertype words contain `Token`, or type `Token` (a bare "Token").
  Champion Unit: supertype words contain `Champion` and type `Unit`. Signature: supertype words contain
  `Signature`. Colours of a card: its domains without `Colorless`. Rune colour: `domains[0]`.
  Identity: the legend's colours (empty without a legend). Two cards share a tag when any tag is equal
  (exact strings, region tags included: prototype `shareTag`).

S5. Zone types (owner, 2026-11-04). Legend slot: 1 card of type `Legend`. Champion slot: 1 Champion
  Unit sharing a tag with the legend. Main deck and sideboard: never `Legend`, `Rune` or
  `Battlefield`. Battlefields: 3 distinct `Battlefield` cards. Runes: 12 `Rune` cards of the legend's
  colours. Workbench: any card. A card of the wrong type is a soft `validate` issue
  (`card_off_identity`, `reason: "type"`): an incomplete or wrong deck can still be stored and
  imported; `can_add` / `can_move` refuse it. Type mismatches are **not** hard limits.

S6. `validate(deck, cards, bans, mode) -> {legal, issues: [{code, params}], completeness}`. `legal`
  is true only with no issue at all. Issues come in this code order, then by `name_sort_key` of
  `params.name`, then zone order of `params.zone`; one issue per code + name + zone. The workbench
  counts only for `copies_over` and `workbench_over`. `completeness` =
  `{legend, champion, main, runes, battlefields, sideboard}` each `{have, need, missing}` with
  `missing = max(0, need - have)` (needs 1, 1, 39, 12, 3, 10); `have` counts every card in the section,
  fitting or not (battlefields: entries).

S7. Issue codes and params (`size(have, need) = {have, need, missing: max(0, need-have), over:
  max(0, have-need)}`):

  | Code | When | Params |
  |---|---|---|
  | `legend_missing` | no legend | `{have: 0, need: 1, missing: 1}` |
  | `champion_missing` | no champion | `{have: 0, need: 1, missing: 1}` |
  | `champion_tag` | legend present, champion is a Champion Unit (not a token) with no tag in common | `{name}` |
  | `main_size` | Σ main qty ≠ 39 (the champion apart) | `size(have, 39)` |
  | `runes_count` | Σ runes qty ≠ 12 | `size(have, 12)` |
  | `rune_off_identity` | legend present, a `Rune` whose colour is not an identity colour | `{name}` |
  | `battlefields_count` | battlefield entries ≠ 3 | `size(have, 3)` |
  | `battlefields_duplicate` | two battlefields with one `name_key` | `{name}` |
  | `sideboard_size` | Σ sideboard qty ≠ 10 (under: soft, missing N; over: also a hard limit) | `size(have, 10)` |
  | `copies_over` | a name over 3 copies in main + sideboard + workbench + champion | `{name, count, max: 3}` |
  | `workbench_over` | more than 100 distinct names in the workbench | `{count, max: 100}` |
  | `card_off_identity` | a non-token card that does not fit its zone | `{name, zone, reason}` |
  | `token_in_deck` | a token in any zone but the workbench | `{name, zone}` |
  | `banned` | a card (any zone but the workbench) whose name is banned in `mode` | `{name, mode}` |

  `card_off_identity.reason`: `type` (S5; legend, champion, main, sideboard, battlefields, runes zones,
  always checked), `tag` (a Signature card in main / sideboard sharing no tag with the legend) or
  `domain` (a main / sideboard card with a colour outside the identity; a two-domain card needs both).
  Without a legend only `type` is checked (no `tag`, `domain`, `rune_off_identity`, `champion_tag`).
  The champion's colour is not checked (prototype `champFilter`). A card in the legend slot that is not
  a Legend still acts as the identity.
  - Example: the owner's deck (`docs/requirements/F5/samples/deck-export-text-1.txt`) →
    `{legal: true, issues: [], completeness: {... all missing 0}}`; with `bans {"Zhonya’s Hourglass":
    ["2v2"]}` in 2v2 → `banned {name: "Zhonya's Hourglass", mode: "2v2"}`.
  - Example: legend + 23 main + 6 runes + 2 battlefields + 4 sideboard → `champion_missing`,
    `main_size {have 23, need 39, missing 16, over 0}`, `runes_count {6, 12, 6, 0}`,
    `battlefields_count {2, 3, 1, 0}`, `sideboard_size {4, 10, 6, 0}`.

S8. `can_add(deck, cards, card, zone)` (zone `main|sideboard|workbench|runes|battlefields`) →
  `{ok: true}` or `{ok: false, code, params}`, the first failing check, params describing the deck
  after the add: token outside the workbench → `token_in_deck`; wrong type (S5) → `card_off_identity`
  (`reason: "type"`); runes: no legend → `legend_missing`, off colour → `rune_off_identity`, 13th →
  `runes_count size(13, 12)`; battlefields: same name → `battlefields_duplicate`, 4th →
  `battlefields_count size(4, 3)`; main / sideboard / workbench: 4th copy of the name (champion and
  workbench included) → `copies_over {name, count: 4, max: 3}`; 11th sideboard card →
  `sideboard_size size(11, 10)`; 101st distinct workbench name → `workbench_over {count: 101, max:
  100}`. Colour, Signature tag and the 39-card size are soft: allowed.

S9. `can_move(deck, cards, card, from, to)` (zones `main|sideboard|workbench`, different, the printing
  must be in `from`) → same result shape. Token to main / sideboard → `token_in_deck`; wrong type →
  `card_off_identity`; workbench → main / sideboard when main + sideboard + champion already hold 3 →
  `copies_over` (prototype rule kept); into the workbench when it already holds 3 of the name →
  `copies_over`; into a full sideboard → `sideboard_size`; a new name into a workbench of 100 names →
  `workbench_over`.

S10. `hard_limit_violations(deck, cards) -> [{rule, max, name?}]` (the future `deck_limit_exceeded`
  params, F5-R9), in this order: `copies` (`max 3`, one per name, by `name_sort_key`), `sideboard`
  (`max 10`), `workbench` (`max 100` distinct), `battlefields` (`max 3` entries), `runes` (`max 12`),
  `token` (`max 0`, one per name outside the workbench, by `name_sort_key`). Nothing else is hard: sizes
  not reached, identity, types, duplicates, missing legend/champion, bans.

S11. `apply_legend(deck, cards, legend|null) -> {ok: true, deck} | refusal`. A token → `token_in_deck
  {zone: legend}`; a non-Legend → `card_off_identity {zone: legend, reason: type}`. Otherwise the legend
  is set, runes whose colour is not a new identity colour are removed, the champion is removed when it
  shares no tag with the new legend (always when the legend is removed); main, sideboard, battlefields
  and workbench are untouched (design-handoff §5.1 (d)).

S12. `apply_champion(deck, cards, champion|null) -> {ok: true, deck} | refusal`. `null` clears it.
  Checks in order: token → `token_in_deck {zone: champion}`; not a Champion Unit → `card_off_identity
  {zone: champion, reason: type}`; no legend → `legend_missing`; no shared tag → `champion_tag {name}`.
  Then, while main + sideboard + workbench copies of its name + 1 > 3, one copy is removed: main, then
  sideboard, then workbench; inside a zone from the printing line with the most copies (first on ties);
  a line at 0 is removed (§5.1 (c)). The previous champion no longer counts.

S13. `auto_runes(deck, cards) -> deck` (design-handoff §5.3, L10: it balances by colour demand). No
  legend or no identity colour → the deck unchanged. `demand[c]` = Σ main qty of cards whose domains
  include `c` + 1 when the champion's domains include `c` (sideboard, legend and runes do not count).
  `total = Σ demand`; `total == 0` → `floor(12 / n)` each; else `max(1, floor(demand[c] / total * 12 +
  0.5))` (evaluated in that order; never Python `round`). `order` = colours sorted by runes descending,
  stable. While the sum > 12: `order[i % n]` loses 1 if above 1; while < 12: `order[i % n]` gains 1; `i`
  counts every step, at most 200. All runes are replaced, in identity order, each colour with the rune
  printing already in the deck for it, else the first `Rune` of that colour in `cards` order; a colour
  with no rune card is left out before computing.
  - Examples: demand `[5, 19]` → `[3, 9]`; one colour → 12; two colours, no demand → 6/6; `[1, 100]` →
    `[1, 11]`; `[7, 3]` → `[8, 4]`; three colours `[2, 2, 3]` → `[3, 3, 6]`.

S14. `deck_domains(deck, cards)` = union of the colours of legend, champion and main deck, in `DOMAINS`
  order, unknown domains after them by `name_sort_key`.

S15. Shared cases `tests/fixtures/deck_rules_cases.json` (plain JSON, UTF-8, no NaN):
  `{"catalog": [card], "cases": [case]}`; card `{set, id, name, type, supertype, domains, tags}`; case
  `{id, description, op, mode?, deck, catalog, bans?, args, expected}` where `catalog` is the ordered
  list of `"<set>-<id>"` keys the engine receives. `op` ∈ `validate` (mode, bans), `can_add` (`args
  {card, zone}`), `can_move` (`args {card, from, to}`), `auto_runes`, `apply_legend` (`args {legend}`),
  `apply_champion` (`args {champion}`), `deck_domains`, `hard_limits`, `sort_names` (`args {names}`,
  `deck: null`). `tests/test_deck_rules_cases.py` runs every case (pytest id = case id) and guards the
  file: unique ids, known ops, resolvable keys, every issue code expected at least once, every hard rule
  at its boundary. Node reads it with `JSON.parse(fs.readFileSync(path, 'utf8'))`.

## API / data contract

`GET /meta/game` `data.rules` = `{deck: DECK_RULES}` (additive; `docs/api.md`). No migration, no new
route, no new error code.

## UI

none

## Acceptance criteria

- [x] AC1 S1: `tests/test_game_domain.py::test_deck_rules_values`, `tests/test_api_meta_game.py::test_shape_order_and_extras`
- [x] AC2 S3-S15: `tests/test_deck_rules_cases.py` (143 cases: validate 48, can_add 29, can_move 9,
  auto_runes 16, hard_limits 16, apply_champion 12, apply_legend 7, deck_domains 4, sort_names 2)
- [x] AC3 S2 (errors, purity, values from `DECK_RULES`, `CardSummary` input): `tests/test_deck_rules.py`
- [x] AC4 Full backend lane green: `venv/bin/pytest` (no frontend change)
- [x] AC5 `docs/knowledge/state.md`, `docs/api.md`, `AGENTS.md`, F5 `README.md` updated

## Delivery

- Conventional Commits. Push and PR only when the owner says so; PR A of F5 together with F5-b. PR
  title: `feat(decks): deck rules engine and shared cases (F5 units a, b)`. Never merge.

## After merge

- Backend restart only (no migration). Live check: `GET /riftbound/api/v1/meta/game` has
  `data.rules.deck.sideboard == 10`.

## Log

- L1 (agent): the functions take `cards` (and `can_add` the deck, card and zone) because pure
  functions need the catalog subset: `can_add(deck, cards, card, zone)`, `apply_legend(deck, cards,
  legend)`, `apply_champion(deck, cards, champion)`, `deck_domains(deck, cards)`.
- L2 (agent): added beyond F5-R2, needed by the editor and F5-e: `can_move` (§5.5 `onDeckMoveName`),
  `sort_names` / `name_sort_key` (D-F5-7), `completeness`, `copies`, `identity`; ops `can_move` and
  `sort_names` in the cases.
- L3 (owner 2026-11-04 → agent): sized issues carry `size(have, need)`; `legend_missing` /
  `champion_missing` carry `{have: 0, need: 1, missing: 1}`; `copies_over {name, count, max}` and
  `workbench_over {count, max}` keep the F5-R19 shape. Refusals of `can_add` / `can_move` /
  `apply_*` use the same codes and params (describing the deck after the change).
- L4 (owner 2026-11-04 → agent): a card of the wrong type for its zone is `card_off_identity` with
  `reason: "type"` (no new code, F5-R2 list kept); `reason` also tells a Signature tag (`tag`) from a
  colour (`domain`) mismatch, so the UI can explain why. Not a hard limit (R9 lists only copies,
  sideboard over 10, workbench, battlefields over 3, runes over 12, tokens).
- L5 (owner 2026-11-04): the sideboard must be 10: under 10 is a soft `sideboard_size` with `missing`,
  over 10 is also the hard limit `sideboard` (the README said "max 10").
- L6 (agent): without a legend only type rules are checked (no colour, tag, rune colour or champion tag
  issues: `legend_missing` already explains it); `can_add` to runes answers `legend_missing`.
- L7 (agent, prototype): the champion's colour is not checked, and "share a tag" means any tag
  (`["Blitzcrank", "Zaun"]` shares "Zaun" with a "Zaun" legend). If region tags make this too loose,
  that is an owner rule change for both engines.
- L8 (agent): `copies_over` counts the workbench (fixes prototype bug L9). The prototype's move rule
  (workbench → main / sideboard blocked when main + sideboard + champion hold 3) is kept in
  `can_move` even though the unified count already prevents it in a valid deck.
- L9 (agent): issue order is deterministic (code order, name, zone) rather than the prototype's
  insertion order, so both engines agree; bans apply to every zone but the workbench (legend, champion,
  battlefields, runes, sideboard included), once per name.
- L10 (agent): `auto_runes` picks the deck's existing rune printing per colour, else the first in
  `cards` order (F5-d must pass the catalog in natural order); colours without a rune card are skipped.
  The loop counter `i` is shared by both loops (only one of them ever runs).
- L11 (agent): `deck_domains` uses `DOMAINS` order (the prototype used insertion order).
- L12 (agent): `apply_champion` removes copies until the champion fits (one in a valid deck), from the
  printing with the most copies in the zone; `apply_legend` refuses tokens and non-Legends.
- L13 (agent, deviation from the hand-off): the cases file has one shared top-level `catalog` and each
  case lists the keys of its subset (ordered), instead of repeating the cards inline: inline catalogs
  made the file 1.1 MB; this keeps it about 400 KB and every case still says exactly which cards the
  engine gets.
- L14 (agent, for F5-e): the catalog stores legends with the bare name (`riot_scraper.full_name`), so
  the owner's "Riven, The Exile" is the legend "The Exile" with tag "Riven"; the shared cases model it
  that way. The export/import "Legend" line is `<tag>, <name>`.
- L15 (agent, for F5-b): `name_key` uses Python `casefold()`; JS `toLocaleLowerCase('en')` differs only
  for a few characters (ß, ligatures, final sigma) that no case uses; a Node check of the
  `sort_names-collation` case with `toLocaleLowerCase('en')` + `<` matched.

## Open questions

none
