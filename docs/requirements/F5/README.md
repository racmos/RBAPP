# F5: Decks v2 — phase spec
Status: planned · Depends on: F2 (bans per mode, `/meta/game`, card DTO, `CardCombobox`, charts), F3 (collection lines, wishlist) · Source: roadmap §3 (rules), §5 (F5), design-handoff §3.7 (list, workspace, modals), §3.12, §3.13, §5.1-5.5 (rules, parser, auto-runes, export, edit operations), §6 (1, 2, 22-25, 33), §7.2 V3, §7.3 D2/D5, §7.5 R9, §7.6 L9-L11/L15, §9 (F5), §10-8, `docs/knowledge/product.md` "Game rules", "Users, accounts and security"

## Goal

Decks move to the v2 format (legend, chosen champion, main deck, runes, battlefields, sideboard, workbench)
with the game rules implemented once in Python and once in TypeScript against the same test cases, every
existing deck migrated automatically, an editor that never lets the user exceed a hard limit and explains
why, legality per game mode (1v1/2v2, bans by name), text import/export (own, riftdecks and Piltover
Archive formats), deck vs collection (missing cards, cost, add to wishlist), version history with diff,
private-by-default decks with a public read-only link, and an opening-hand simulator. Desktop shows list |
editor | analysis panel.

## Current state

| Area | What exists today |
|---|---|
| Model | `RbDeck` (`rbdecks`, `app/models/deck.py`): `id` PK, `rbdck_user` (username FK), `rbdck_name`, `rbdck_seq` (version number; UNIQUE user+name+seq; each save inserts a row with the next seq), `rbdck_snapshot`, `rbdck_description`, `rbdck_mode` (default `1v1`), `rbdck_format` (`Standard`), `rbdck_max_set`, `rbdck_ncards`, `rbdck_orden`, `rbdck_cards` JSON `{"main": [{"set", "id", "qty"}], "sideboard": [...]}` — legend, champion, runes and battlefields all sit in `main`. |
| Routes (Jinja + flat JSON, U) | `GET /riftbound/deck` (list with filters; legend found by type in `main`), `GET /deck/api/legends`, `GET /deck/view/<id>`, `/view/<name>`, `/view/<name>/<seq>`, `GET /deck/versions/<name>`, `POST /deck/save` (`DeckSave` schema). Contract `openspec/specs/deck-viewing/spec.md` (DECK-1..4): have/missing from the viewer's collection; name routes scoped to the viewer; every signed-in user can open any deck by id. |
| Rules | None on the server. The prototype's rules live in the client (design-handoff §5.1-5.5) with known bugs (L9 workbench ignored in copies, sideboard 8, silent no-ops). |
| F2 | Ban table + `card_bans`, `GET /bans`, `name_key`, `is_base`, `parse_type` (supertype Token/Champion/Signature), `/meta/game` with `rules: {}`, `CardCombobox` with `filters`, `PriceChart`, `Sparkline`. F3 | wishlist API, collection quantities per printing. |
| Frontend | Nav entry `decks` is `legacy` (`/riftbound/deck`). |

## Scope

In: rule values + engine (Python) + TS library + shared cases; v2 data model + migration of existing decks;
decks API (CRUD, versions, diff, legality); import/export; deck vs collection; visibility + share link +
public page; hand simulator; editor UI (mobile, desktop, wide); offline read of decks; nav flip.

Out: deck statistics across events (F8), deck comments/likes, public deck browsing/search (no public index
of decks), tournament formats beyond 1v1/2v2.

## Decisions already taken (product.md "Game rules", binding)

- 1 Legend, 1 chosen Champion, 39 main-deck cards (40 counting the champion); exactly 12 runes, only of the
  legend's domains; 3 distinct battlefields (not counted); sideboard 10; max 3 copies per **name** across
  main + sideboard + workbench + chosen champion (printings of a name are the same card); workbench ≤ 100
  distinct names, excluded from export, value and legality; the champion must share a tag with the legend;
  changing the legend purges incompatible runes and champion (not the main deck).
- Game modes 1v1 and 2v2 only; bans per mode by name (F2 table); the UI says why a deck is not legal in its mode.
- Rule values live in the backend and are served through `/meta/game` (`rules.deck`); never hardcoded in the UI.
- Port the prototype's deck logic as is except where these rules differ (product.md F5); JS `Math.round` vs
  Python `round` trap (design-handoff §5.3): implement `floor(x + 0.5)`.
- Private by default; owner can mark public or generate a read-only share link (product.md). Until F5 every
  signed-in user can see every deck (DECK-1 note) — F5 changes that.
- New tables reference `rbusers.id`; migrations take the next free revision numbers.

## Requirements

### Rules
- **F5-R1** `app/schemas/game_domain.py` gains `DECK_RULES = {main_size: 39, total_with_champion: 40, runes: 12, battlefields: 3, sideboard: 10, copies_max: 3, workbench_max: 100, opening_hand: <D-F5-6>}`; `/meta/game` returns them under `rules.deck`. (F5-a)
- **F5-R2** `app/services/deck_rules.py`: pure functions `validate(deck, cards, bans, mode) -> {legal, issues[{code, params}]}`, `can_add(deck, card, zone) -> ok | {code, params}`, `auto_runes(deck, cards)`, `apply_legend(deck, legend)`, `apply_champion(deck, champion)`, `deck_domains`. Issue codes: `legend_missing`, `champion_missing`, `champion_tag`, `main_size`, `runes_count`, `rune_off_identity`, `battlefields_count`, `battlefields_duplicate`, `sideboard_size`, `copies_over`, `workbench_over`, `card_off_identity`, `token_in_deck`, `banned` (params `{name, mode}`). (F5-a)
- **F5-R3** Shared cases in `tests/fixtures/deck_rules_cases.json` (input deck + catalog subset + mode → expected issues / operation result) covering design-handoff §5.1 (a)-(i), the §5.3 auto-runes examples (`[5,19] → [3,9]`, 1 colour → 12, 2 colours without cards → 6/6, `[1,100] → [1,11]`, `[7,3] → [8,4]`) and collation of names (`localeCompare` vs Python: D-F5-7). pytest and vitest both run every case. (F5-a, F5-b)
- **F5-R4** `frontend/src/decks/rules/` implements the same functions in TS (used for instant feedback; the server stays authoritative). (F5-b)

### Data
- **F5-R5** New tables (D-F5-1): `rbdeckheads` (`rbdkh_id`, `user_id` FK `rbusers.id`, `name` ≤ 80, `mode` CHECK IN GAME_MODES, `visibility` CHECK IN ('private','public'), `share_slug` VARCHAR(24) UNIQUE NULL, `current_version_id`, `legacy_name`, timestamps; UNIQUE (user, name)) and `rbdeckversions` (`rbdkv_id`, `deck_id` FK CASCADE, `seq`, `content` JSON v2, `note` ≤ 200, `created_at`; UNIQUE (deck, seq)). (F5-c)
- **F5-R6** Content v2 JSON: `{"v": 2, "legend": {"set","id"} | null, "champion": {"set","id"} | null, "main": [{"set","id","qty"}], "runes": [...], "battlefields": [{"set","id"}] (≤ 3), "sideboard": [...], "workbench": [...]}`; validated by a Pydantic model; printings kept. (F5-c)
- **F5-R7** Migration of every `rbdecks` row: group by (user, name) → one head (mode from the latest row) + one version per row (seq kept); cards routed by type: first Legend → legend; first Champion-supertype unit sharing a tag with the legend → champion (others stay in main); Battlefield → battlefields (first 3 distinct, rest → workbench); Rune → runes; tokens → workbench; the rest → main; old `sideboard` → sideboard (overflow > 10 → workbench). Unknown card ids are kept in a `dropped[]` list in the version note and reported by the migration. `rbdecks` is not modified. Downgrade drops the new tables. (F5-c)

### API (all U unless noted)
- **F5-R8** `GET /decks` (mine: name, mode, visibility, legend/champion `CardMini`, domains, counts per zone, `legal{1v1, 2v2}` with issue codes, value, updated_at), `POST /decks`, `GET /decks/{id}` (current content expanded with `CardMini`s + legality for both modes), `PATCH /decks/{id}` (name, mode, visibility), `PUT /decks/{id}/content` (saves the draft = current version; hard limits rejected), `POST /decks/{id}/versions` (snapshot as a new version, D-F5-3), `GET /decks/{id}/versions`, `GET /decks/{id}/diff?a=&b=`, `DELETE /decks/{id}`. Only the owner; another user's id → 404. (F5-d)
- **F5-R9** Hard limits enforced by `PUT …/content` (and every operation): copies per name > 3, sideboard > 10, workbench > 100 distinct, battlefields > 3, runes > 12, a token anywhere but the workbench → 400 `deck_limit_exceeded` with `params {rule, max, name?}`. Soft rules (sizes not reached, identity, bans) never block saving; they are issues. (F5-d)
- **F5-R10** `POST /decks/import/preview {text, format?: auto|rbapp|riftdecks|piltover}` → `{deck_preview, warnings[{line, text, reason_code}]}` (parser of design-handoff §5.2 adapted: dynamic set prefixes, base printing preferred, explicit id respected, nothing dropped silently); `POST /decks/import {text, format, name?}` creates a deck; `GET /decks/{id}/export?format=text|riftdecks|piltover` (§5.4 for `text`). (F5-e)
- **F5-R11** `GET /decks/{id}/vs-collection` → `{missing[{card: CardMini, need, have}], cost_eur, owned_value}` (copies counted per name across printings, as DECK-1); `POST /decks/{id}/missing-to-wishlist` adds the missing names to the F3 wishlist (merges quantities; `already_exists` never raised here). (F5-f)
- **F5-R12** `POST /decks/{id}/share` → `{slug, url}` (22 url-safe random chars), `DELETE /decks/{id}/share`; `GET /public/decks/{slug}` (**P**, no session needed, rate-limited 60/min/IP) returns the read-only deck (no owner username unless the deck is public — D-F5-4). (F5-g)
- **F5-R13** Legacy Jinja deck pages: after F5-c they read the new tables read-only (or show a banner "Este mazo se edita en la nueva app") and `POST /deck/save` is disabled with a JSON 410 + message (D-F5-2). DECK-1..3 behaviour preserved for viewing. (F5-c)

### UI
- **F5-R14** `/decks` (nav `decks` → `spa`): mobile = deck list (name, pips, mode, legality badges 1v1/2v2, main n/39, value) and the workspace as its own screen `/decks/:id` with collapsible sections in the §3.7.1 order; limits shown as disabled controls with the reason (tooltip + `aria-describedby`), undo toast for removals. (F5-h)
- **F5-R15** Desktop ≥ 1240: list | editor (2 internal columns); wide ≥ 1600: list | editor | sticky analysis panel (energy/power curves, `Donut` by type and domain, value own vs to complete, legality per mode with explanations, missing cards, hand simulator, versions). (F5-i)
- **F5-R16** Import/export modals with format tabs, paste/drag-and-drop, per-line preview; versions list and side-by-side diff (added/removed/changed per zone). (F5-j)
- **F5-R17** Public page `/riftbound/app/d/:slug` outside the auth guard (read-only deck, legality, curves, export text, "Abrir en Rift Manager" for signed-in users); hand simulator: draw `opening_hand` cards from the 39-card main (seeded, "Nueva mano", mulligan per D-F5-6). (F5-k)

### Offline / i18n / a11y / security
- **F5-R18** Read cache `rb-api-decks` (NetworkFirst) for `GET /decks*`; editing disabled offline. (F5-l)
- **F5-R19** Namespace `decks`; every issue code translated with its params (`decks:issue.copies_over` = "«{{name}}» tiene {{count}} copias (máx. {{max}})."). (F5-h..k)
- **F5-R20** Public endpoint exposes no user data beyond D-F5-4; slugs unguessable; revoking a slug makes the old URL 404 immediately. Authz matrix: everything U except `api_v1.public_deck` P. (F5-g)

## Data model changes

| Change | Migration (next free numbers) | Backfill / downgrade | Risk |
|---|---|---|---|
| `rbdeckheads`, `rbdeckversions` | `00NN_decks_v2` | Data migration from `rbdecks` (F5-R7) with a dry-run CLI `flask decks migrate --dry-run` that prints the routing per deck before the real upgrade; downgrade drops the new tables (old table untouched) | High (item 1): routing heuristics on real data; run the dry-run on a copy of the dev DB and have the owner review it |

## API

| Method | Path | Auth | Unit |
|---|---|---|---|
| GET/POST | `/decks` | U | F5-d |
| GET/PATCH/DELETE | `/decks/{id}` | U | F5-d |
| PUT | `/decks/{id}/content` | U | F5-d |
| GET/POST | `/decks/{id}/versions` | U | F5-d |
| GET | `/decks/{id}/diff?a=&b=` | U | F5-d |
| POST | `/decks/import/preview`, `/decks/import` | U | F5-e |
| GET | `/decks/{id}/export?format=` | U | F5-e |
| GET | `/decks/{id}/vs-collection` | U | F5-f |
| POST | `/decks/{id}/missing-to-wishlist` | U | F5-f |
| POST/DELETE | `/decks/{id}/share` | U | F5-g |
| GET | `/public/decks/{slug}` | P | F5-g |

New error codes: `deck_limit_exceeded` (400, `params {rule, max, name?}`), `already_exists` (409, deck name
taken by the same user; shared with F3/F4), `import_format_unknown` (400, shared with F3). Legality issues
are **not** HTTP errors: they are `issues[{code, params}]` in the payload, translated in `decks.json`.

## UI

| Route | Mobile < 860 | Desktop ≥ 1240 | Wide ≥ 1600 |
|---|---|---|---|
| `/decks` | Deck list + "Nuevo" / "Importar" | list 1/3 + editor 2/3 | list \| editor \| analysis |
| `/decks/:id` | Workspace screen, collapsible sections, sticky summary bar (main n/39, runes n/12, legality) | editor with 2 internal columns (A: legend + main; B: champion, battlefields, sideboard, runes, curves, workbench) | + analysis panel |
| `/decks/:id/versions` | list + diff stacked | diff side by side | same |
| `/d/:slug` (public) | read-only deck | 2 columns | 3 columns |

Components to port/build (design-handoff §9 F5): `DeckCard`, `DeckWorkspace`, `CollapsibleSection`, `MiniCurve`,
variant strip (printing chips), `CardRow` with `Stepper` and move actions, `ImportModal`/`ExportModal`,
`DeckDiff`, `HandSimulator`, `Donut` (built here, reused by F6). States: loading, empty ("Aún no tienes
mazos" + Nuevo/Importar), error, offline read-only, 404 for slugs.

## Units

| ID | Title | Depends on | Size | Risk | Summary |
|---|---|---|---|---|---|
| F5-a | Deck rules engine (Python) + rule values | F2 done | ~600 | item 3 | `DECK_RULES` in `/meta/game`, `deck_rules.py`, shared cases JSON + pytest runner |
| F5-b | Deck rules library (TS) | F5-a | ~500 | item 3 | `frontend/src/decks/rules/`, vitest runner over the same cases |
| F5-c | Deck v2 data + migration | F5-a | ~600 | items 1, 3 | Tables, Pydantic content, routing migration + dry-run CLI, Jinja read-only switch |
| F5-d | Decks API | F5-c | ~600 | items 3, 4 | CRUD, content save with hard limits, versions, diff, legality both modes |
| F5-e | Import/export API | F5-d | ~550 | items 3, 6 | Parsers (rbapp + riftdecks + Piltover; samples needed), preview warnings, export formats |
| F5-f | Deck vs collection | F5-d, F3-f | ~350 | item 3 | Missing/cost per name, missing to wishlist |
| F5-g | Visibility, share link, public endpoint | F5-d | ~400 | item 2 | Slugs, public read endpoint with rate limit, authz P |
| F5-h | Decks UI mobile | F5-b, F5-d | ~650 | none | List, workspace screen, editing with limits and reasons, nav flip |
| F5-i | Decks UI desktop/wide + analysis | F5-h | ~650 | none | Columns, analysis panel, `MiniCurve`, `Donut` |
| F5-j | Import/export + versions UI | F5-e, F5-h | ~550 | none | Modals, preview, versions, diff |
| F5-k | Public deck page + hand simulator | F5-g, F5-i | ~500 | item 2 | `/d/:slug` outside the guard, simulator |
| F5-l | Offline decks | F5-i | ~250 | items 5, 6 | `rb-api-decks` cache, purge, disabled edits |

## Open decisions

| ID | Question | Options | Recommendation | Blocks |
|---|---|---|---|---|
| D-F5-1 | Storage of v2 decks | (a) new head + version tables; (b) keep `rbdecks` rows with v2 JSON | (a): a deck can be renamed without breaking its history, ownership uses the user id, visibility/slug live once per deck; `rbdecks` stays as the untouched legacy source until F11 | F5-c |
| D-F5-2 | Jinja deck pages after the migration | read-only on new tables / keep writing old table / redirect to the app | Read-only on the new tables with a banner; `POST /deck/save` answers 410 | F5-c |
| D-F5-3 | When is a new version created? | every save / explicit "Guardar versión" / daily | Autosave updates the current version (debounced 1 s); "Guardar como versión" (with an optional note) snapshots; import creates version 1 | F5-d |
| D-F5-4 | What does a public link show? | — | Deck name, content, legality, value; owner's username only when visibility = public (a share link of a private deck is anonymous) | F5-g |
| D-F5-5 | Import sample files | — | Owner sends 2-3 exported decks from riftdecks and Piltover Archive before F5-e | F5-e |
| D-F5-6 | Opening hand rules | — | Owner confirms the official opening hand size and mulligan rule; stored in `DECK_RULES.opening_hand` / `mulligan` | F5-a, F5-k |
| D-F5-7 | Name collation for sorting/export | Python `casefold` vs JS `localeCompare` | Both sides sort by `casefold()` / `toLocaleLowerCase('en')` + code-point order (no locale collation) so shared cases agree | F5-a, F5-b |
| D-F5-8 | Shared cases location | `tests/fixtures/` / `frontend/` / `shared/` | `tests/fixtures/deck_rules_cases.json`, read by vitest through `fs` with a path relative to the repo | F5-a, F5-b |
| D-F5-9 | Decks visible to other users after F5 | — | Only the owner (plus public/shared links); the DECK-1 "any signed-in user by id" behaviour ends (spec amendment recorded in F5-d) | F5-d |

## Risks and notes

- **Migration heuristics** (item 1) are the biggest risk: legacy decks may have several legends, champions
  without a shared tag, more than 3 battlefields, tokens. Nothing is dropped silently: overflow goes to the
  workbench and unresolved ids are listed. Dry-run first, owner review, backup.
- **Two rule implementations** can diverge; the shared JSON cases are the contract and run in CI on both
  sides. The server is authoritative.
- `Donut` and `MiniCurve` are built here and reused by F6 (F6 must not rebuild them).
- Bans change over time: legality is computed on read, never stored.
- The public route is the first SPA route outside the auth guard; the service worker navigation fallback
  already covers `/riftbound/app/*`.
- F8 links "deck played" to `rbdeckheads.id` (and optionally a version id).
