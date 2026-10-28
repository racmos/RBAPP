# F14-a: Product catalog data — `rbproducts` reshaped, refreshed after each daily load

| Field | Value |
|---|---|
| Phase / unit | F14 / a — batch 1, unit 27 |
| Branch | `feat/f14a-product-catalog-data` (from the F3-i branch) |
| Depends on | F4-b (main), F4-c, F13-a (stack) |
| Size forecast | ~450 authored lines |
| Risk | `Risk: item 1 (reshapes rbproducts: primary key change) + item 3 (step chained to the daily load)` |
| TDD | ON (strict). Runner: `venv/bin/pytest` |
| Sources | F14 phase spec (F14-R1, data model, D-F14-1…3, 13), `decisions-2026-10-25.md` |

## Objective

Every sealed Riftbound product Cardmarket lists (boxes, cases, sleeves, …) is in one product catalog with its
Cardmarket id, name, category, product kind and set, kept up to date after each daily price load. Nothing is
shown yet (F14-b…f).

## Read first

- `app/models/cardmarket.py` (`RbcmProduct`, `RbProducts`, `RbcmExpansion`), `app/services/cardmarket_loader.py`
  (non-singles file), `app/routes/domains/price.py` (Jinja product upsert/search: must keep working)
- `app/jobs/daily_prices.py` (F4-c chaining), `app/jobs/value_snapshot.py`, `migrations/versions/` (latest)

## Specs

S1. Preflight on the dev database (read only; paste the output in the PR): 
    (a) `SELECT rbprd_category_name, count(DISTINCT rbprd_id_product) FROM riftbound.rbcm_products WHERE rbprd_type = 'nonsingle' GROUP BY 1 ORDER BY 2 DESC;`
    (b) `SELECT rbpdt_type, count(*) FROM riftbound.rbproducts GROUP BY 1;`
    (c) `SELECT rbpdt_id_product, count(*) FROM riftbound.rbproducts GROUP BY 1 HAVING count(*) > 1;`
    (d) for the latest `rbprc_date`, how many non-single products have a non-null, non-zero `rbprc_avg7`,
        `rbprc_trend`, `rbprc_low` (three counts).
    If (c) returns rows, stop (BATCH-1 R7a): the key change would lose data.
S2. Migration `00NN_products_catalog` on `rbproducts`:
    - primary key becomes (`rbpdt_id_product`) (`rbproducts_pkey`); `rbpdt_id_set` becomes nullable (the set
      when the expansion is mapped);
    - new columns: `rbpdt_category TEXT NULL`, `rbpdt_kind VARCHAR(16) NULL` CHECK IN (`booster`, `box`, `case`,
      `bundle`, `starter`, `sleeves`, `accessory`, `other`) (`rbproducts_kind_chk`), `rbpdt_kind_locked BOOLEAN
      NOT NULL DEFAULT false`, `rbpdt_set_locked BOOLEAN NOT NULL DEFAULT false`, `rbpdt_hidden BOOLEAN NOT NULL
      DEFAULT false`, `rbpdt_listed BOOLEAN NOT NULL DEFAULT true`, `rbpdt_updated_at TIMESTAMP NULL`;
    - `rbpdt_type` (`single`/`nonsingle`) is kept as is; only `nonsingle` rows are products (D-F14-13);
    - downgrade restores the old key and drops the columns (fails clearly if a NULL `rbpdt_id_set` exists;
      documented).
S3. Kind mapping (`app/services/products.py`, `kind_for(category) -> str`), case-insensitive, first rule that
    matches wins: contains `case` → `case`; `booster box` or `display` → `box`; `booster` → `booster`;
    `bundle` or `gift` → `bundle`; `starter` or `deck` (but not `deck box`) → `starter`; `sleeve` →
    `sleeves`; `deck box`, `playmat`, `binder`, `accessor`, `dice`, `token` → `accessory`; anything else →
    `other`. A unit test covers every category of the S1(a) output (add them to the test with their expected
    kind); a category that ends in `other` is listed in the PR for the owner.
S4. `refresh_products(date) -> dict`: from `rbcm_products` rows of `date` with `rbprd_type = 'nonsingle'`:
    insert new ids (name, category, kind, set from `rbcm_expansions.rbexp_rbset_id` of the expansion or NULL,
    `listed = true`, `rbpdt_type = 'nonsingle'`); update name, category and `listed = true` of existing ones, and
    kind / set unless locked; mark `listed = false` for `nonsingle` products not in that date; never delete;
    `rbpdt_updated_at` on change. Returns `{"date", "new", "updated", "not_listed", "total"}`.
S5. Kind `products_refresh` (`app/jobs/products_refresh.py`, timeout 600 s, optional param `date`
    `YYYYMMDD`, default the latest `rbcm_products` date), migration `00NN_jobs_products_refresh` extends
    `ck_rbjobs_kind`/`JOB_KINDS`; `daily_prices` success queues it after `value_snapshot` (same rule as F4-c S4;
    result `queued` lists both).
S6. The Jinja product endpoints (`/cardmarket-upsert-product`, searches, details) keep working with the new key
    (adapt queries that used the composite key); their behaviour for the admin is unchanged.
S7. Docs: `AGENTS.md` (table shape, kind), runbook (`flask jobs enqueue products_refresh`), `state.md`.

## Acceptance criteria

- [ ] AC1 Migration round trip and drift; key change keeps existing rows; downgrade refusal with a NULL set (S2).
- [ ] AC2 `tests/test_products_kind.py`: rules and every preflight category (S3).
- [ ] AC3 `tests/test_products_refresh.py`: new, updated, locked kind/set untouched, not listed, singles ignored, never deleted (S4).
- [ ] AC4 `tests/test_products_refresh_job.py`: kind, params, chaining after `daily_prices` (S5).
- [ ] AC5 Jinja product endpoints still work (S6); full lanes green; docs (S7).

## Delivery

PR title: `feat(products): product catalog in rbproducts refreshed after the daily load (F14 unit a)`. PR body:
the S1 output and the category → kind table.

## After merge

**Backup first** (`products_catalog`, `jobs_products_refresh`). Deploy; `flask jobs enqueue products_refresh` and
read the counts.

## Open questions

none

## Log

- L1 (implementer): the 0019 upgrade also refuses (nothing changed) when a product id is in more than one row, a guard for S1(c); dev has none.
- L2 (implementer): `refresh_products` sets `rbpdt_type = 'nonsingle'` on an existing row whose id is in the day's non-singles (for example one created by hand in Jinja with a NULL type), otherwise it would never count as a product.
- L3 (implementer): a date with no non-single rows raises `NothingToRefresh` (the job fails, nothing changes) instead of unlisting the whole catalog.
- L4 (implementer): counts: `updated` = existing rows of the file that changed; `not_listed` = every non-single product missing from the date; `total` = non-single rows after the refresh.
- L5 (implementer): the Jinja upsert with an existing product id and another set moves that one row to the new set (before, the composite key created a second row); it does not lock the set.
- L6 (parent): S1 preflight results are in state.md; categories ending in `other`: 'Riftbound Riftbound Box Sets', 'RB Set'. At the latest load `avg7` is zero for every non-single, so F14-b prices will use trend/low fallbacks unless this changes.
