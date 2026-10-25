# F3-a: Collection data — purchase price, copies to sell, playset size and "keep a playset"

| Field | Value |
|---|---|
| Phase / unit | F3 / a — batch 1, unit 18 |
| Branch | `feat/f3a-collection-data` (from the F2-k branch) |
| Depends on | F2 batch units (stack) |
| Size forecast | ~450 authored lines |
| Risk | `Risk: item 1 (migration with backfill on users' collection rows) + item 3 (line contract consumed by F3-b…, F7)` |
| TDD | ON (strict). Runner: `venv/bin/pytest` |
| Sources | F3 phase spec (F3-R1…R4, R26, R27, data model), `decisions-2026-10-22.md` (D-F3-1), `decisions-2026-10-25.md` (D-F3-9…12) |

## Objective

The collection rows gain an optional purchase price and a "copies to sell" count; the legacy "S" selling
value disappears; each user gets a playset size (3 by default) and a "keep a playset" mark per card name. The
Jinja collection keeps working and keeps the new count coherent.

## Read first

- `app/models/collection.py`, `app/models/prefs.py`, `app/schemas/prefs_domain.py`
- `app/routes/domains/collection.py` (every write route listed in S6; `export_csv`)
- `migrations/versions/0009_card_bans.py` (frozen `name_key` copy, seed pattern), `tests/migration_helpers.py`
- `app/services/bans.py` (`name_key`)

## Specs

S1. Preflight (before writing any migration code): run on the dev database, read only, and paste the output
    in the PR: `SELECT rbcol_selling, count(*) FROM riftbound.rbcollection GROUP BY 1;` and
    `SELECT count(*) FROM riftbound.rbcollection WHERE rbcol_playset IS NOT NULL;`. If a query fails or shows
    `rbcol_quantity < 1` rows, stop (BATCH-1 R7a).
S2. Migration `00NN_collection_selling`:
    - add `rbcol_purchase_price NUMERIC(10,2) NULL` with CHECK `rbcol_purchase_price IS NULL OR
      rbcol_purchase_price >= 0` (`rbcollection_purchase_price_chk`);
    - add `rbcol_sell_qty INTEGER NOT NULL DEFAULT 0`;
    - data: `rbcol_selling = 'S'` → `'Y'` (D-F3-11); then `rbcol_sell_qty` = `max(0, qty − playset)` when
      `rbcol_playset` is not NULL, else `qty` when `rbcol_selling = 'Y'`, else 0;
    - CHECK `rbcol_sell_qty BETWEEN 0 AND rbcol_quantity` (`rbcollection_sell_qty_chk`); `rbcollection_selling_chk`
      becomes `IN ('Y', 'N')`;
    - the migration logs `rows S->Y: n` (print or `op` logger);
    - downgrade: drop both columns and their CHECKs, restore the selling CHECK with `'S'` (rows stay `Y`;
      documented).
S3. Migration `00NN_playset` (`down_revision` = S2):
    - `rbuserprefs.rbprf_playset_size SMALLINT NULL` with CHECK `rbprf_playset_size BETWEEN 1 AND 9`
      (`rbuserprefs_playset_size_chk`); NULL means 3;
    - table `rbkeepplayset`: `rbkps_user_id INTEGER NOT NULL` FK `rbusers.id` ON DELETE CASCADE
      (`rbkeepplayset_user_fk`), `rbkps_name_key VARCHAR(200) NOT NULL`, `rbkps_created_at TIMESTAMP NOT NULL`
      default now; PK (`rbkps_user_id`, `rbkps_name_key`) (`rbkeepplayset_pkey`);
    - seed (D-F3-12): one row per (user id, `name_key(card name)`) for every collection row with
      `rbcol_playset` NOT NULL (join `rbusers.username = rbcol_user`, `rbcards` for the name), duplicates
      collapsed; `name_key` is a frozen copy of `app.services.bans.name_key` with a test that keeps both equal;
    - downgrade drops the table and the column.
S4. Models: `RbCollection` gains `rbcol_purchase_price` (`Numeric(10, 2)`), `rbcol_sell_qty` and the named
    CHECKs; `RbUserPrefs` gains `rbprf_playset_size`; new `RbKeepPlayset` (`app/models/playset.py`). The
    column comment of `rbcol_playset` says "Deprecated (F3-a): read only by the Jinja collection; dropped in F11".
S5. `app/services/collection_rules.py`: `legacy_sell_qty(qty, playset, selling) -> int` (S2 rule);
    `kept_copies(lines) -> int` = Σ (`qty − sell_qty`); `playset_size(prefs_row | None) -> int` (NULL → 3).
S6. Legacy coherence (F3-R4): after each Jinja write that changes quantity, selling or playset —
    `add`, `update_quantity`, `update_selling`, `update_playset`, `bulk_apply`, `import_csv` — the touched rows get
    `rbcol_sell_qty = legacy_sell_qty(...)` in the same transaction. `export_csv` uses `rbcol_sell_qty` as the
    quantity (rows with 0 skipped), everything else byte-identical (test against a fixture produced by the
    current code before the change).
S7. Docs: `AGENTS.md` (tables/columns, "rbcol_playset is deprecated"), `docs/knowledge/state.md` (remove the
    `rbcol_selling = 'S'` known issue; F3-a row; pending check "backup first, two migrations").

## Acceptance criteria

- [ ] AC1 `tests/test_collection_data_migration.py`: seeded rows of every kind (S, Y, N, with and without playset) → expected `selling` and `sell_qty`; CHECKs reject negative price and `sell_qty > qty`; downgrade/upgrade round trip and drift for both revisions (S2, S3).
- [ ] AC2 `tests/test_playset_seed.py`: seed rows per user and name, duplicates collapsed, frozen `name_key` equals the service one (S3).
- [ ] AC3 `tests/test_collection_rules.py`: S5 functions (S5).
- [ ] AC4 `tests/test_collection_legacy_routes.py`: each S6 route keeps `sell_qty` coherent; `export_csv` byte-identical except the quantity source (S6).
- [ ] AC5 Full lanes green; docs and `state.md` (S7).

## Delivery

PR title: `feat(collection): purchase price, copies to sell and playset data (F3 unit a)`. PR body: the S1 output
and the migration's `rows S->Y` count on a copy of the dev data if available.

## After merge

**Backup first.** Deploy (`collection_selling`, `playset`), `flask db check`. Live: the Jinja collection still
lists, edits and exports.

## Open questions

none
