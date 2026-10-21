# F2-a: Per-mode card bans — table, CLI, read API

| Field | Value |
|---|---|
| Phase / unit | F2 / a |
| Branch | `feat/f2a-card-bans` (from up-to-date `main`) |
| Depends on | F1 units a-f merged (done). F1-close recommended first, not required |
| Size forecast | ~550 authored lines (tests and docs included) |
| Risk | `Risk: items 1 and 3 (new table + data backfill migration 0007; the ban service and GET /bans are consumed by F2-b/c/d, F5 legality and F10 admin)` |
| TDD | ON (strict). Runners: `venv/bin/pytest` (backend), `cd frontend && npx vitest run` (frontend, untouched here) |
| Save as | `docs/requirements/F2/F2-a-card-bans.md` (commit this document verbatim in the first commit if it is not in the repo yet) |

## Objective

The owner can ban a card **name** separately for the 1v1 and the 2v2 game mode from the server shell, and
every signed-in client can read the current bans. A ban covers every printing of the name. This replaces the
single, unreliable `rbcar_banned` flag (the Riot scraper resets it to `N` on every run) as the only source of
truth, so the catalog (F2), deck legality (F5) and the admin UI (F10) all read the same table.

## Read first

- `AGENTS.md` (project rules: they apply to every line of this unit)
- `docs/knowledge/conventions.md`, `docs/knowledge/product.md` → "Game rules" (bans per mode, by name)
- `docs/requirements/F2/README.md` (phase spec: F2-R1, R2, R3, R5, R10, R14, R27; D-F2-2, D-F2-3)
- `app/models/card.py`, `app/models/prefs.py` + `app/schemas/prefs_domain.py` (pattern: domain tuples shared
  by schema and CHECK, `sql_in`), `migrations/versions/0006_user_prefs.py` (migration style), `tests/test_migrations.py::TestUserPrefs0006`
- `app/cli/users.py`, `app/cli/__init__.py` (CLI pattern), `tests/test_admin_cli.py`
- `app/api/v1/me.py`, `app/api/v1/__init__.py`, `app/api/responses.py`, `app/api/error_codes.py`
- `app/routes/domains/cards.py` (`search_banned` filter), `app/templates/cards.html` (Banned column, badge,
  add/edit modals), `app/services/riot_scraper.py` (step 5 rewrites `rbcar_banned`)
- `tests/test_authz_matrix.py`, `tests/test_docs.py::TestAgentsStructure::test_every_table_is_named`

## Scope

In:
- `app/schemas/game_domain.py` with `GAME_MODES`.
- Model `RbCardBan` (`app/models/ban.py`), migration `0007_card_bans` with backfill.
- `app/services/bans.py` (normalization, reads, add/remove).
- `flask bans list|add|remove` (`app/cli/bans.py`).
- `GET /riftbound/api/v1/bans` (`app/api/v1/bans.py`).
- Jinja catalog: Banned column/badge/filter read the ban table; the admin add/edit modals lose the banned field.
- Docs.

Out (do not do, even if tempting):
- Exposing bans on card payloads (`CardSummary.bans`: F2-b/F2-c), deck legality (F5), any admin web UI for
  bans (F10).
- Dropping or rewriting `rbcar_banned`, or changing the scraper (F11 drops the column).
- `validate_query` refactor (F2-c).

## Specs

S1. `app/schemas/game_domain.py` exists with `GAME_MODES = ('1v1', '2v2')` and a module docstring saying it is
    the single source of game enumerations (F2-b adds domains, types, rarities; F5 adds deck rule values).
    `RbCardBan`'s CHECK is built from it with `sql_in` (import it from `app.schemas.prefs_domain`).

S2. `name_key(name: str) -> str` in `app/services/bans.py`: replace `’` (U+2019) and `‘` (U+2018) with `'`,
    `casefold()`, split on whitespace and join with one space (this also trims).
  - Example: `name_key("  Kai’Sa,   Daughter of the Void ")` → `"kai'sa, daughter of the void"`.
  - Example: `name_key("JINX, Loose Cannon") == name_key("jinx, loose cannon")`.

S3. Table `riftbound.rbcardbans` (model `RbCardBan`, `app/models/ban.py`, imported in `app/models/__init__.py`):

    | Column | Type | Null | Notes |
    |---|---|---|---|
    | `rbban_id` | Integer | no | PK, autoincrement |
    | `rbban_name_key` | String(200) | no | `name_key` of the banned name |
    | `rbban_name` | String(200) | no | display name (catalog spelling when the name exists) |
    | `rbban_mode` | String(3) | no | CHECK `rbcardbans_mode_chk`: `rbban_mode IN ('1v1', '2v2')` |
    | `rbban_since` | Date | no | date the ban applies from |
    | `rbban_reason` | String(500) | yes | free text |
    | `rbban_created_at` | DateTime | no | `default=clock.utcnow`, `server_default=now()` |

    Constraints: PK `rbcardbans_pkey`; UNIQUE (`rbban_name_key`, `rbban_mode`) named
    `rbcardbans_name_mode_key`. Table comment: `Bans by card name and game mode (F2).` Every column has a
    short English `comment`.

S4. Migration `migrations/versions/0007_card_bans.py`, `revision = '0007_card_bans'`,
    `down_revision = '0006_user_prefs'`.
  - Upgrade creates the table exactly as S3 (so `flask db check` reports no drift) and then backfills: for
    every distinct `rbcar_name` of `riftbound.rbcards` whose `upper(trim(rbcar_banned))` is `S` or `Y`,
    insert one row per mode (`1v1`, `2v2`) with `rbban_name_key` = the key, `rbban_name` = that name,
    `rbban_since` = the migration date (UTC), `rbban_reason` = `Migrated from rbcar_banned`. Names with the
    same key are inserted once per mode (first by `rbcar_name` order).
  - The backfill uses a **frozen copy** of `name_key` inside the migration file (migrations must not import
    app code); a test asserts the frozen copy and the service function agree on the S2 examples.
  - Downgrade drops the table. `rbcar_banned` is never modified by upgrade or downgrade.
  - The docstring states: no data loss on upgrade; downgrade loses the bans added after the upgrade.

S5. Reads in `app/services/bans.py` (no Flask request objects):
  - `ban_map() -> dict[str, dict[str, BanEntry]]`: all bans keyed by `name_key`, then mode. `BanEntry` is a
    frozen dataclass `(name: str, mode: str, since: date, reason: str | None)`.
  - `card_bans(name, bans=None) -> dict[str, bool]`: always both modes, e.g. `{'1v1': False, '2v2': True}`.
    `bans` lets callers pass a preloaded `ban_map()` (one query per request, never one per card).
  - `ban_info(name, bans=None) -> list[dict]`: `[{'mode': '1v1', 'since': '2026-09-01', 'reason': None}]`,
    ordered by `GAME_MODES` order, ISO dates.
  - `list_bans(mode=None) -> list[BanEntry]`: ordered by mode (GAME_MODES order), then `name_key`.

S6. Writes in `app/services/bans.py` (commit inside; raise on invalid input, never print):
  - `add_ban(name, modes, since=None, reason=None, force=False) -> list[tuple[str, str]]` returns one
    `(mode, status)` per requested mode with status `added`, `updated` or `unchanged`.
    - The name must match at least one `rbcards.rbcar_name` by `name_key`; otherwise raise
      `UnknownCardName(name)` unless `force=True`.
    - `rbban_name` = the catalog spelling of the first match (ordered by set id, card id), or `name.strip()`
      when forced.
    - Existing row for (key, mode): when `since` or `reason` is given and differs → update them → `updated`;
      otherwise → `unchanged`. New row: `since` defaults to `clock.utcnow().date()` → `added`.
    - `reason` longer than 500 characters raises `ValueError('reason too long')`; an empty or whitespace-only
      reason is stored as NULL.
  - `remove_ban(name, modes) -> list[tuple[str, str]]` with status `removed` or `absent`. It matches by
    `name_key` only (works for forced names that are not in the catalog).

S7. CLI group `flask bans` (`app/cli/bans.py`, registered in `app/cli/__init__.py`; help text
    `Manage card bans per game mode (1v1, 2v2).`). `--mode` takes `1v1`, `2v2` or `all` (= both, in
    GAME_MODES order) and is required for `add` and `remove`. Exact output lines (one per mode):
  - `flask bans list [--mode 1v1|2v2]` → `<mode>  <since YYYY-MM-DD>  <name>` and, when there is a reason,
    `  — <reason>` appended. No bans → `No bans.` Exit 0.
  - `flask bans add NAME --mode M [--since YYYY-MM-DD] [--reason TEXT] [--force]` →
    `Banned '<name>' in <mode> since <since>.` / `Updated the ban of '<name>' in <mode>.` /
    `'<name>' is already banned in <mode>.` Exit 0. Unknown name without `--force` → exit 1 with
    `Error: No card named '<NAME>' in the catalog (use --force to ban it anyway).` and nothing written.
    Reason over 500 characters → exit 1 with `Error: The reason must be at most 500 characters.`
    Bad date → click's usage error (exit 2).
  - `flask bans remove NAME --mode M` → `Unbanned '<name>' in <mode>.` / `'<NAME>' was not banned in <mode>.`
    Exit 0.
  - Example: `flask bans add "jinx, loose cannon" --mode all --reason "Too strong"` on a catalog with
    `Jinx, Loose Cannon` → two lines `Banned 'Jinx, Loose Cannon' in 1v1 since 2026-10-21.` and the same for
    2v2; running it again → `'Jinx, Loose Cannon' is already banned in 1v1.` (and 2v2).

S8. `GET /riftbound/api/v1/bans` (U), view function `list_bans` in `app/api/v1/bans.py` (endpoint
    `api_v1.list_bans`), imported in `app/api/v1/__init__.py`.
  - Optional query `mode` ∈ `1v1`, `2v2`. Any other value → 400:
    `{"success": false, "error": "Validation Error", "message": "Invalid query parameters", "code": "validation_error", "details": [{"field": "mode", "message": "mode must be 1v1 or 2v2", "type": "literal_error", "code": "invalid_value"}]}`
    (built with `fail(...)`; F2-c later moves this onto `validate_query` with the same body).
  - 200 body (ordered as `list_bans`): see the API section. `printings` lists every catalog card with the
    same `name_key` as `{set_id, card_id}`, ordered by set id then card id; `[]` for a forced name.
  - Anonymous → JSON 401 (existing handler). No CSRF needed (GET).

S9. Jinja catalog (`GET /riftbound/card`) reads bans from the table (D-F2-2):
  - The table's "Banned" cell and the grid badge show the modes where the card's name is banned, joined with
    `, ` (`1v1, 2v2`), or `—` / `ALLOWED` when none. Badge text when banned: `BANNED 1v1, 2v2`.
  - Filter `search_banned=S` → only cards whose name is banned in at least one mode; `N` → only cards whose
    name is banned in no mode. Implement by computing the matching raw `rbcar_name` values in Python from
    `ban_map()` and filtering `RbCard.rbcar_name.in_(...)` (an empty list matches nothing).
  - The admin add and edit modals no longer show the banned select and their JavaScript no longer sends
    `rbcar_banned` (the schemas keep accepting it; the column keeps its value).

S10. Docs: `AGENTS.md` (CRLF preserved) lists `rbcardbans` in "Database Naming", `ban.py` under models,
     `bans.py` under services, `app/cli/bans.py` and `GET /bans` in "API v1", and one sentence in "Roles and
     Authorization": bans are changed only by `flask bans` until F10. `docs/knowledge/ops-runbook.md` →
     "Service operations" gains the three `flask bans` commands. Model comment on `rbcar_banned`:
     `Deprecated (F2): bans live in rbcardbans; removed in F11.` (Python comment only, not the column
     comment, so no migration is needed).

## API / data contract

Migration `0007_card_bans` (up: create + backfill; down: drop). Model and endpoint:

```http
GET /riftbound/api/v1/bans?mode=1v1
```
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "name": "Jinx, Loose Cannon",
        "mode": "1v1",
        "since": "2026-09-01",
        "reason": "Too strong",
        "printings": [{"set_id": "OGN", "card_id": "79"}, {"set_id": "OGNX", "card_id": "257"}]
      }
    ]
  }
}
```

Authz: `api_v1.list_bans` → `U` in `tests/test_authz_matrix.py`. No new error code.

## UI

None in the React app. Jinja catalog changes only as S9.

## Acceptance criteria

- [ ] AC1 `tests/test_card_bans.py`: `name_key` examples (S2); `ban_map`, `card_bans`, `ban_info`, `list_bans` order (S5); `add_ban`/`remove_ban` statuses, catalog spelling, `UnknownCardName`, `force`, reason limits, default `since` with `frozen_clock` (S6).
- [ ] AC2 `tests/test_migrations.py::TestCardBans0007`: chains after `0006_user_prefs`; columns, types, nullability, names of PK/UNIQUE/CHECK; CHECK rejects `3v3`; UNIQUE rejects a duplicate (key, mode); backfill of `S` and `y ` names into both modes (and a name with two printings once per mode); `rbcar_banned` unchanged; downgrade drops the table; models equal the schema at head (S3, S4).
- [ ] AC3 `tests/test_bans_cli.py`: every exact output line and exit code of S7, including `--mode all`, idempotency and the unknown-name error leaving the table empty.
- [ ] AC4 `tests/test_api_bans.py`: 200 shape and order, `mode` filter, invalid `mode` 400 body, anonymous 401, printings including a promo printing and `[]` for a forced name (S8).
- [ ] AC5 `tests/test_authz_matrix.py` classifies `api_v1.list_bans` as U and passes.
- [ ] AC6 `tests/test_routes.py` (or a new `tests/test_cards_jinja_bans.py`): Banned cell/badge text and `search_banned=S|N` from the ban table; the add/edit modals have no `rbcar_banned` control (S9).
- [ ] AC7 `flask db upgrade` on a copy of the dev schema then `flask db check` → no drift; `flask db downgrade -1` then upgrade again → clean (record in the PR).
- [ ] AC8 Full lanes green: `venv/bin/pytest`; `cd frontend && npm run lint && npm run typecheck && npx vitest run && npm run build && npm run check:dist`
- [ ] AC9 `docs/knowledge/state.md` updated (F2-a done, PR placeholder, follow-ups: none expected)
- [ ] AC10 `AGENTS.md` and `docs/knowledge/ops-runbook.md` updated as S10; `tests/test_docs.py` green.

## Delivery

- Conventional Commits; commit messages end with the attribution lines the session supplies.
- Suggested slices: (1) game_domain + model + migration + migration tests, (2) service + CLI, (3) API + Jinja + docs.
- Push and PR only when the user says so. PR title: `feat(bans): per-mode card bans table, CLI and read API (F2 unit a)`.
  PR body: summary, specs → tests map (S# → test file::name), manual checks for the user, rollback
  (`flask db downgrade -1` loses bans added since; `rbcar_banned` untouched).
- Never merge. The user merges.

## After merge (user asks gentle-shell, or does it)

- Deploy to dev with `docs/knowledge/ops-runbook.md` — **backup first** (migration `0007`), then
  `flask db upgrade`, `flask db check`, restart.
- Live checks:
  - `venv/bin/flask bans list` → `No bans.` or the migrated names (if any card had `rbcar_banned = 'S'`).
  - Signed-in `GET <URL>/riftbound/api/v1/bans` → 200 `{"success": true, "data": {"items": [...]}}`;
    anonymous → 401 JSON.
- Manual checks for the user: ban a real card with `flask bans add "<name>" --mode 1v1 --reason test`, open
  the Jinja catalog and see `BANNED 1v1` on every printing; `flask bans remove "<name>" --mode 1v1` and see
  it gone.

## Open questions

- CONFIRM D-F2-2: backfill `rbcar_banned` `S`/`Y` as banned in **both** modes with reason
  `Migrated from rbcar_banned`, and switch the Jinja catalog to the ban table (S4, S9).
- CONFIRM D-F2-3: `GET /bans` is for signed-in users (U).
