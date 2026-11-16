# RESET: Production data reset (design, owner runbook, helper CLI requirement)

| Field | Value |
|---|---|
| Phase | Prerequisite of F12 (Production); runs after F9 (units a-e, h, i, j) and F11-f, before F9-f/F9-g and F12 |
| Decision | Owner, 2026-11-11: replaces "promote the dev database as is" (D-F12-6 option A keeps the server, not the data). Owner decisions on the details: 2026-11-12, section 13; **2026-11-15: keep only the Cardmarket load history** (Q4, Q5 now WIPE; Q2 `rbcardbans` kept by the agent, owner to confirm) |
| Parts | 1-8 design (this file); 9 helper CLI requirement (units RESET-a, RESET-b, to build later); 10-12 owner runbook, rehearsal, rollback; 13 owner decisions |
| Status | Design written 2026-11-12 (docs only, verified against `main` `80da5d2`, Alembic head `0028_legacy_schema_cleanup`); owner decisions applied 2026-11-12 (revised 2026-11-15; open again: Q2, section 13). No open questions then: the helper units can be handed over once F9-j is merged. **RESET-b built 2026-11-15** on `feat/reset-production-data` (from `main` `c078908`, head `0032_api_keys`; its own branch, not stacked on RESET-a / PR #148), implemented, not merged, not deployed: see "RESET-b as built". **Keep-list change 2026-11-15** on `feat/reset-keep-only-history` (from `main` `a0a432a`): `rbcm_ignored` and `rbproducts` become WIPE, implemented, not deployed |
| Placeholders | `<backup-file>`, `<backup dir>`, `<database>`, `<host>`, `<user>`, `<superuser>`, `<app role>`, `<server>`, `<service>`, `<service user>`, `<card images dir>`, `<product images dir>`, `<avatar dir>`, `<scratch dir>`, `<app e-mail>`, `<personal e-mail>`, `<URL>`. Real values live in `ops.local.md` (git-ignored) or in the owner's head; never in git, never in a chat |

## 1. Goal

Before production the dev database is cleaned so that production starts with a correct catalog, clean sets and
no test data, while the Cardmarket daily loads (the price history) are kept for later analysis:

- every application table is emptied **except** the Cardmarket load history (owner 2026-11-15: everything
  else was created while testing), the official ban list seeded by migration `0009` and the `daily_prices`
  job rows (section 13);
- the sets are created again from zero (same codes, values re-entered from the worksheet), **before** the
  catalog is downloaded again from the official Riot card gallery (`riot_sync` job);
- the Cardmarket mapping (expansion → set, product → card) is regenerated on the kept loads;
- only three accounts remain: `rbadmin` (admin, the owner's app e-mail), `racmos` (normal user, the owner's
  personal e-mail), `rbqa` (QA user); every other account is deleted. E-mails and passwords are typed at run
  time (prompt or environment variable), never written in git or in these docs;
- user data (collections, decks, locations, wishlists, owned products, price alerts, value snapshots,
  preferences, F9 profile, 2FA, API keys, sessions) is **lost on purpose**; the safety `pg_dump` is the only
  copy.

The owner runs every download and load by hand with section 10. Nothing here runs automatically.

## 2. Where it sits in the order

`F11-f` (migration `0028`, implemented) → F9 a → b → (c, d, h) → e → i → j → **RESET** → F9-f → F9-g → F12.
This is the order of `docs/requirements/F9/README.md` (owner decision Q13). Consequence: at reset time the head
is the last F9 revision before F9-f (planned `0032_api_keys`); `rboauthlinks` (`0033_oauth_links`, F9-f) does
not exist yet and F9-f must add it to the reset classification (RESET-b S2/S3 force it).

## 3. Inventory and classification

Source: `app/models/*.py`, `migrations/versions/0001`..`0028`, the F9 data model
(`docs/requirements/F9/README.md`). Schema `riftbound`, 30 application tables at head `0028` plus
`alembic_version`, plus 5 F9 tables before the reset and 1 after it.

Classes: **KEEP** (never touched), **WIPE** (every row deleted), **SPECIAL** (rows or columns partly kept,
rule given). "D-Q<n>" = owner decision of 2026-11-12 (section 13).

| # | Table | Holds | References (FK / soft) | Class | Why |
|---|---|---|---|---|---|
| 1 | `alembic_version` | migration head | — | KEEP | Tooling; the schema is not changed |
| 2 | `rbcm_price` | daily price guide rows, one per product and day | soft: product id | KEEP | The price history the owner wants to exploit (`cardmarket_loader._load_prices`) |
| 3 | `rbcm_products` | Cardmarket products per load date (singles and non-singles) | soft: expansion, category | KEEP | Part of each daily load (`_load_products`); the matcher, the load log and `products_refresh` read it |
| 4 | `rbcm_load_history` | one row per file and load (hash, rows, status) | — | KEEP | The load log (CM-a, `cardmarket_log`), "already loaded today" check |
| 5 | `rbcm_categories` | Cardmarket category lookup | — | KEEP | Pure Cardmarket data, upserted by every load |
| 6 | `rbcm_expansions` | Cardmarket expansion ids and names + `rbexp_rbset_id` mapping to our sets | soft → `rbset.rbset_id` | SPECIAL (D-Q1/Q3): rows kept, mapping cleared | The rows are Cardmarket data from the loads; the reset sets `rbexp_rbset_id` to NULL because the sets are wiped. Step 8 maps them again (CM-d), creating the sets at the same time |
| 7 | `rbcm_ignored` | products an admin ignored in the mappings browser | soft: product id + name | WIPE (D-Q4, 2026-11-15) | Test data of the matching workbench (wrong decisions included); the owner ignores products again in step 14 |
| 8 | `rbproducts` | sealed product catalog, kind/set locks, hidden, image name | soft `rbpdt_id_set` → set code (plain Text, **no FK**); `rbuserproducts` → here (RESTRICT) | WIPE (D-Q5, 2026-11-15) | Curation made while testing. Rebuilt by `products_refresh` from the next load (section 6.4); kinds, locks, hidden flags and uploaded images are **not** preserved. Deleted after `rbuserproducts` (section 3.1) |
| 9 | `rbcm_product_card_map` | product → card links (auto/manual, foil slot) | soft → `rbcards` (no FK) | WIPE | Owner decision: regenerate the mapping. No FK: deleting cards leaves these rows behind, so they are deleted explicitly |
| 10 | `rbset` | sets: name, `rbset_ncard`, release date | parent of `rbcards` (CASCADE) | WIPE (D-Q1) | The owner wants clean sets, created from zero in step 8 **before** the first Riot sync (section 6.2), with the values recorded in the worksheet |
| 11 | `rbcards` | card catalog | → `rbset` | WIPE | Rebuilt by `riot_sync` |
| 12 | `rbcardchanges` | Riot proposals and decisions | → `rbcards` CASCADE, → `rbjobs` SET NULL, → `rbusers.id` SET NULL | WIPE | Proposals against the old catalog |
| 13 | `rbcardbans` | bans by card name and mode (CLI only, seeded by `0009`) | none (keyed by `name_key`) | KEEP (D-Q2; agent 2026-11-15, owner to confirm) | Reference data, not test data: dev holds exactly the 25 rows the `0009` seed wrote (12 in 1v1, 13 in 2v2), identical to a fresh install; the seed never runs again, so wiping it would only force 25 `flask bans add`. Keyed by name, not card id, so it covers the new printings |
| 14 | `rbcardmarket` | legacy per-card price snapshots | → `rbcards` CASCADE | WIPE (D-Q11) | No route or service reads it (`docs/knowledge/architecture.md`); it would cascade away with the cards anyway |
| 15 | `rbusers` | accounts | parent of every user table | SPECIAL | Keep the `--keep-user` rows (reset `failed_login_count` = 0, `locked_until` = NULL; role, password, e-mail untouched); delete the others |
| 16 | `rbuserprefs` | interface prefs, playset size | → `rbusers.id` CASCADE | WIPE | User data |
| 17 | `rbkeepplayset` | "keep a playset" marks | → `rbusers.id` CASCADE | WIPE | User data |
| 18 | `rbcollection` | collection lines | → `rbcards` CASCADE, → `rbusers.username` **RESTRICT** | WIPE | User data; must go before any user row |
| 19 | `rbcollection_locations` | copies per location | → `rbcollection`, → `rblocations` (CASCADE) | WIPE | User data |
| 20 | `rblocations` | storage locations | → `rbusers.username` CASCADE | WIPE | User data |
| 21 | `rbdeckheads` | decks (incl. share slugs) | → `rbusers.id` CASCADE | WIPE | User data; every public share link stops working |
| 22 | `rbdeckversions` | deck versions | → `rbdeckheads` CASCADE | WIPE | User data |
| 23 | `rbwishlists` | wishlists | → `rbusers.id` CASCADE | WIPE | User data |
| 24 | `rbwishlistlines` | wanted cards | → `rbwishlists` CASCADE | WIPE | User data |
| 25 | `rbwishlistalerts` | price alerts | → `rbusers.id` CASCADE | WIPE | User data |
| 26 | `rbuserproducts` | owned sealed products | → `rbusers.id` CASCADE, → `rbproducts` RESTRICT | WIPE | User data |
| 27 | `rbvaluesnaps` | daily collection value per user | → `rbusers.id` CASCADE | WIPE | User data (history cannot be rebuilt; it is in the dump) |
| 28 | `rbimportpreviews` | 30-minute import previews | → `rbusers.id` CASCADE | WIPE | Transient |
| 29 | `rbcaptcha_used` | ALTCHA replay store | — | WIPE | Transient |
| 30 | `rbjobs` | job queue and results | → `rbusers.id` SET NULL | SPECIAL (D-Q6) | Keep finished `daily_prices` rows (the CM-a load log links each load day to its job); delete every other row; null `rbjob_requested_by` on kept rows |
| 31 | `rbadminaudit` | admin audit trail | → `rbusers.id` SET NULL | WIPE (D-Q7) + 1 row | Trail of dev actions on data that no longer exists (it stays in the dump); the reset writes one `data.reset` row as the first entry of the new trail |
| F9-a | `rbsessions` | server-side sessions | → `rbusers.id` CASCADE | WIPE | Everyone signs in again |
| F9-b | `rbuserprofile` | display name, bio, country, city, avatar file | → `rbusers.id` CASCADE | WIPE | User data (avatar files: section 5) |
| F9-d | `rbusermfa` | TOTP secret | → `rbusers.id` CASCADE | WIPE (D-Q8) | Kept accounts start without 2FA; re-enrol right after |
| F9-d | `rbrecoverycodes` | 2FA recovery codes | → `rbusers.id` CASCADE | WIPE (D-Q8) | Goes with `rbusermfa` |
| F9-h | `rbapikeys` | personal API key | → `rbusers.id` CASCADE | WIPE | User data |
| F9-f | `rboauthlinks` | Discord/Google links | → `rbusers.id` CASCADE | WIPE (added by F9-f) | Does not exist at reset time (section 2) |

Totals at reset time (`TABLE_POLICY`, 35 tables; 2026-11-15): KEEP 5 (`rbcm_price`, `rbcm_products`,
`rbcm_load_history`, `rbcm_categories`, `rbcardbans`; plus `alembic_version`, which is outside the metadata),
WIPE 27 (22 at head `0028` + 5 F9), SPECIAL 3 (`rbusers`, `rbjobs`, `rbcm_expansions`).

### 3.1 Delete order, soft references and sequences

- **Order**: children before parents. The helper deletes in reverse `db.metadata.sorted_tables` order, which
  puts `rbcollection_locations` → `rbcollection` and `rblocations` (both reference `rbusers.username`,
  `rbcollection` with RESTRICT) and every `rbusers.id` child before `rbusers`, `rbcardchanges` and
  `rbcardmarket` before `rbcards`, `rbcards` before `rbset`, and `rbuserproducts` before `rbproducts` (RESTRICT;
  proven by `tests/test_reset_cli.py::TestDeleteOrder` with SQLite foreign keys on, and on PostgreSQL by
  `tests/test_reset_pg.py`). It never relies on `ON DELETE` actions: every WIPE table is deleted explicitly
  (SQLite in the tests does not enforce foreign keys unless asked).
- **Soft references** (no FK) after the reset:
  - `rbcm_product_card_map` → `rbcards`: wiped too.
  - `rbcm_expansions.rbexp_rbset_id` → `rbset`: set to NULL by the reset (SPECIAL), mapped again in step 8.
  - `rbproducts.rbpdt_id_set` → set code: no longer a concern (2026-11-15): the table is wiped and
    `products_refresh` rebuilds it after the next load with the set of each expansion's new mapping
    (section 6.4). No product is set-locked after the reset, so P1 can only list a code if a set is deleted
    later.
- **Sequences** (PostgreSQL): every sequence owned by a column of a table the reset emptied restarts at 1;
  for the partly kept tables (`rbusers`, `rbjobs`) it restarts at `max(id) + 1`. Use `ALTER SEQUENCE …
  RESTART WITH n` inside the transaction (transactional on PostgreSQL 10 and later, so a rollback undoes it;
  RESET-b AC8 proves it on PostgreSQL 18, and if it does not hold the unit stops and reports), **never
  `setval`** (documented as not transactional: a rollback after `setval` would leave the sequence below kept
  ids). Sequences of kept tables (incl. `rbcm_expansions`) are not touched. `rbcardbans` (kept) owns the
  `rbban_id` sequence, which is therefore not touched; `rbproducts` and `rbcm_ignored` own no sequence (their
  keys are Cardmarket ids; checked in `tests/test_reset_pg.py`). Find them with
  `pg_get_serial_sequence('riftbound.<table>', '<column>')` (dev has legacy sequence names, for example on
  `rbusers.id`).

## 4. What stays, what is rebuilt, what is lost

Stays: the price history (`rbcm_price`, `rbcm_products`, `rbcm_load_history`, `rbcm_categories`), the
Cardmarket expansion rows (ids and names, without their mapping), the official ban list (the 25 rows of the
`0009` seed), the three accounts (with their current passwords until the owner sets new ones), the
`daily_prices` job history.

Rebuilt: the sets (step 8, values from the worksheet), the expansion → set mapping (step 8), the card catalog
and card images (`riot_sync`), the product → card links (Cardmarket load + auto-match + manual workbench),
the product catalog (`products_refresh` after the first load, step 14: only the non-singles of that load,
kinds from `kind_for`, sets from the new mapping), the ignored list (the owner ignores products again in
step 14).

**Lost on purpose** (only the dump of step 3 keeps them):

- all user content of every account: collections (incl. purchase prices and sale data), locations, decks,
  versions and share links, wishlists and alerts, owned products, playset marks, preferences, value history,
  F9 profile, avatars, 2FA, API keys, sessions; every account except the three;
- the sets (names, release dates, `rbset_ncard` such as VEN = 166) and the expansion → set mapping: the owner
  re-enters them from the worksheet (SQL A, SQL B); a set not re-created is gone;
- **hand work on the catalog**: card edits made in Admin → Cards, cards created by hand (Admin → Cards or the
  CM-c "create the missing card" form) that are not in the gallery, uploaded card images, every Riot change
  decision (the pending proposals, about 194 per the owner, and the approved/rejected/obsolete history).
  Because the rejected values are gone, the gallery value is stored again where the owner had kept a
  different one: the rehearsal diff (section 11) lists every such card (D-Q10);
- every Cardmarket product → card link (auto and manual);
- the ignored list (`rbcm_ignored`): test data with wrong decisions, so it is **not** recorded in the worksheet;
- the product catalog curation (`rbproducts`): kinds set by hand, kind/set locks, hidden flags, uploaded
  product images (the files are moved aside, section 5); products that are no longer in the latest load are
  not rebuilt. Not recorded either: the owner redoes what is wanted in Admin → Products after step 14;
- the audit trail and the job history except `daily_prices` (D-Q6, D-Q7); the legacy `rbcardmarket` rows
  (D-Q11).

## 5. Files on disk

| Directory | Written by | Plan |
|---|---|---|
| `CARD_IMAGES_DIR` | `riot_sync` (`_fetch_image`), admin image upload, `flask images import-legacy` | **Move aside and re-download everything** (D-Q9): `riot_sync` downloads an image only when the file is **missing** (`os.path.exists`), so a kept directory means nothing is re-downloaded. Move it to `<card images dir>.pre-reset-<date>` (do not delete it), create an empty one, let the sync download everything. Fallback for gaps: a second sync (it retries every missing file), then `flask images import-legacy --source <card images dir>.pre-reset-<date>` (copies only missing files, never overwrites) |
| `PRODUCT_IMAGES_DIR` | admin product image upload | **Move aside** (2026-11-15: follows `rbproducts`, now wiped, D-Q5): the rebuilt rows have no `rbpdt_image`, so the old files would only be orphans. Move it to `<product images dir>.pre-reset-<date>` and create an empty one; upload again in Admin → Products what is wanted |
| `AVATAR_DIR` (F9-c) | avatar upload | Move aside (the `rbuserprofile` rows are wiped) |

All three directories are moved aside in step 7 (never deleted) and archived in step 3.

## 6. How the catalog is rebuilt: findings in the code

### 6.1 Riot sync on an empty catalog (`app/services/riot_sync.py`)

- `sync()` without `sets` processes **every set code the gallery lists** (`gallery['set_codes']`); a set that
  exists only in `rbset` (for example a promo set ending in `X`) is not touched and keeps 0 cards.
- A card that is not stored is **always inserted** (`_process_set`: `RbCard(...)` for every gallery card not
  in `stored`), whatever the window. Windows only matter for existing cards (auto-apply around a release,
  proposals otherwise). So on an empty `rbcards` **nothing lands in `rbcardchanges`: zero approvals**. A
  second run right after must report only `unchanged` (an idempotence check, section 10 step 11).
- Each inserted card downloads its image when the file is missing; the summary counts
  `images.downloaded/existing/failed`. The whole run is one transaction committed at the end (one savepoint
  per set): with about 1,500 cards and images the run is long; the runner enforces the 1800 s timeout only
  when another `run-pending` starts (`expire_stale`), so during the reset the jobs run in the foreground
  through `riftbound-jobs.service` (it holds the `flock`) with the timer stopped.
- Audit rows `riot.insert` (and `set.create` for placeholders) are written with actor `system`.

### 6.2 Sets (`rbset`): why they are created before the first sync

What `_process_set` does for each gallery code, in this order:

1. `rs = RbSet.query.get(set_id)`; `ncard = rs.rbset_ncard if rs is not None else None`. The S15 rarity rule
   (`gallery_value`: above `ncard` → Showcase; at or below it a gallery "Showcase" never replaces the stored
   rarity) uses this `ncard` for the whole run.
2. No row → a **placeholder** is created: name = code, `rbset_outdat` NULL, `rbset_ncard` = number of gallery
   cards, audit `set.create`; `ncard` stays None for this run. A row with `rbset_ncard` NULL → the count is
   filled with the gallery's, and `ncard` also stays None for this run.
3. The window comes from `rbset_outdat` (`window_for`); new cards are inserted whatever the window, each field
   through `gallery_value(..., ncard=ncard)`.

So with `ncard` None at insert the rule is **skipped**: alt arts numbered at or below the real count are
stored with the gallery's "Showcase", which the owner's rule (ops-runbook "Comparison rules") forbids; fixing
the count later only turns them into proposals to approve. Riot gives no set names, release dates or card
counts. Hence the order of the runbook: **every set the gallery lists is created with its code, name, release
date and card count (step 8) before the first Riot sync (step 9)**; step 9 must then report
`placeholder_sets: []`.

Two existing ways to create a set, both with the same validation (`AdminSetCreate`: id 2-10 letters/digits,
upper-cased; name; release date required; declared count = `rbset_ncard`, optional but **required here**):

- **Preferred**: Admin → Cardmarket → Matching → Expansions → an expansion → "Map to a set…" → "Create a new
  set…" (CM-d, `PUT /admin/cardmarket/expansions/<id>` with `create_set`): creates the set and maps the
  expansion in one transaction, audited. Further expansions of the same set: "Map to a set…" the set just
  created.
- Admin → Sets → New set (`POST /admin/sets`), for a gallery set that has no Cardmarket expansion yet.

The set codes must equal the gallery codes exactly (the old `rbset_id` values in SQL A came from the gallery;
the rehearsal records `gallery.set_codes`, section 11). After the reset the Expansions tab has **no suggested
set** for any expansion (its suggestion counts product → card links, which are wiped): the owner maps them
from the worksheet (SQL B: old expansion id → set code), helped by the sample products, price range and
first-seen date the tab shows.

### 6.3 Cardmarket mapping

- The Cardmarket loader (`CardmarketLoader.run`, "Load now" / `daily_prices`) loads **today's** files and then
  runs its exact-name pass (`_update_product_card_map`: case-insensitive name equal to exactly one card →
  link, `match_type='auto'`, confidence 1.0) over the products of the latest date; `daily_prices` then links
  the clear matcher cases (`match_clear_cases`, confidence 0.7) and lists the rest for review, then queues
  `value_snapshot`, `products_refresh`, `price_alerts`.
- Admin → Cardmarket → Matching → Auto-match (`POST /admin/cardmarket/auto-match/preview|apply`) runs only
  the matcher clear cases (`classify_unmapped`) on the **latest kept load**, at most 200 per click
  (`max_groups` 1..200); it does **not** run the exact-name pass. So the first mapping step after the reset
  is a real load ("Load now"), then Auto-match until no clear case remains, then the manual workbench.
- The matcher prefers cards of the set its expansion is mapped to (`_get_expansion_to_set_map`, only mapped
  expansions): the expansion mapping restored in step 8 is what makes the clear cases clear, so step 8 comes
  before any load or auto-match.
- The ignored list is empty after the reset (2026-11-15): products ignored on dev show again in To link and
  are ignored again by hand in step 14.
- No re-download of past days is possible or needed: the kept `rbcm_products` / `rbcm_price` rows are
  untouched and prices reach the new cards through the new links (the canonical product is
  `MIN(id_product)`), so every card's price history goes back to the first kept load.

### 6.4 Products and the rest

- `products_refresh` (`app/services/products.py::refresh_products`) never deletes. On the empty `rbproducts`
  of the reset (2026-11-15) it **inserts** every non-single product of the load date it is given (the
  newest load), with `rbpdt_kind = kind_for(category)`, `rbpdt_id_set` = the set of its expansion's mapping
  (**NULL when the expansion is not mapped**), no lock, not hidden, no image. Products seen only in older
  loads are not inserted. So with step 8 first, the refresh queued by "Load now" gives every product its set
  at once; a load run before step 8 would leave every set NULL (harmless: the next refresh after the mapping
  fills it). A mapping added later → `venv/bin/flask jobs enqueue products_refresh` (or wait for the next
  daily load).
- `value_snapshot` writes no row (no collection); `price_alerts` creates none (no lines).
- Bans are keyed by `name_key` (`app/services/bans.py`): kept rows cover the new printings when the names
  match; `GET /bans` shows the `printings` each name matches.

### 6.5 Tools: exists vs missing

| Step | Exists today | Missing |
|---|---|---|
| Safety dump | `pg_dump` (ops-runbook "Riot sync" recheck section), `scripts/db_backup.py` (nightly naming, prunes after 14 days: not for this dump) | — |
| Count rows per table, wipe in FK order, keep users, clear the expansion mapping, reset sequences, one transaction, guards | nothing (hand SQL is forbidden: ops-runbook "Never") | **`flask reset production-data`** (RESET-b) |
| Create `rbadmin` / missing accounts | `POST /auth/register` (needs the app, ALTCHA, never admin) + `flask users promote` | **`flask users create`** (RESET-a) |
| Set passwords, roles | `flask users set-password|promote|demote|list` | — |
| Change a kept account's e-mail | Account → Profile (`PATCH /me/account`, signed in as that user) | — (no CLI needed) |
| 2FA re-enrol / reset | Planned before the reset: Account → Security (F9-j), `flask users reset-2fa` (F9-d) | — (comes with F9) |
| Sessions | Planned before the reset: `rbsessions`, `flask sessions purge`, `riftbound-sessions-purge.timer` (F9-a) | — (comes with F9) |
| Sets + expansion mapping | Matching → Expansions "Map to a set… / Create a new set…" (CM-d, set and mapping in one transaction); Admin → Sets (`POST`/`PATCH /admin/sets`) | — |
| Catalog download | `flask jobs enqueue riot_sync`, Admin → Riot (`POST /admin/riot/sync`) | — |
| Load + auto links | Admin → Cardmarket "Load now" (`POST /admin/cardmarket/load`), `flask jobs enqueue daily_prices` | — |
| Clear cases, review, manual links, ignore | Matching tabs `auto`, `link`, `linked`, `conflicts`, `ignored` | — |
| Products | `products_refresh` (queued by `daily_prices`, or `flask jobs enqueue products_refresh`), Admin → Products | — |
| Images fallback | `flask images import-legacy --source` | — |
| Run jobs in the foreground | `sudo systemctl start riftbound-jobs.service` (oneshot, holds the lock) | — |

## 7. Gaps → helper units

1. `flask users create <username> [--email <e>] [--admin]` (RESET-a).
2. `flask reset production-data` with dry run, guards, classification guard, one transaction (RESET-b).

Both in one branch and one PR (`feat/reset-helpers`, one commit per unit), **no migration**, built after
F9-j is merged so the F9 tables exist in the metadata. Requirements in section 9.

## 8. Risks

- Running against the wrong database (rehearsal shell vs dev): guarded by `--database`, `--env`, the
  `test`-name rule and the backup `dbname` check (RESET-b S5-S8); the other commands (`riot_sync`, users) have
  no such guard, so the rehearsal shell prints the database name first (section 11).
- A set missing or without a card count at the first sync: placeholder, Showcase rule skipped (section 6.2).
  Step 8 creates every gallery set with its count first; step 9 checks `placeholder_sets: []`.
- A set re-created with a code different from the gallery's: the sync makes a second, placeholder set. The
  codes come from the worksheet and the rehearsal's `gallery.set_codes`.
- Product curation lost (2026-11-15: `rbproducts` wiped): kinds, locks, hidden flags and images are redone by
  hand in Admin → Products after step 14; nothing restores them except the dump.
- A long sync or load killed midway: both are transactional (the sync per set inside one final commit, the
  load in one commit); re-running is safe.
- Hand edits silently replaced by gallery values: found by the rehearsal diff, fixed by hand after the sync.

---

## 9. Helper CLI requirement

The two units below follow `docs/requirements/TEMPLATE.md`. The owner's decisions (section 13) are folded in;
they are handed over once F9-j is merged.

### RESET-a: `flask users create`

| Field | Value |
|---|---|
| Phase / unit | RESET (F12 prerequisite) / a |
| Branch | `feat/reset-helpers` (from up-to-date `main`), commit 1 of 2 |
| Depends on | F9-b merged (optional e-mail, D-F9-1) |
| Size forecast | ~200 authored lines (tests and docs included) |
| Risk | `Risk: item 2 (creates accounts, incl. admins, from the server shell)` |
| TDD | ON (strict). Runner: `venv/bin/pytest` |
| Save as | this file, section "RESET-a" |
| Status | Built 2026-11-15 on `feat/reset-helper-cli` (implemented, not merged, not deployed) |

**Objective.** The owner creates the accounts that survive the reset from the server shell, admins included,
without the web app, the captcha or a password in the shell history.

**Read first.** `AGENTS.md`; `app/cli/users.py`; `app/services/auth.py::register_user`;
`app/schemas/validators.py::RegisterRequest`, `PASSWORD_MIN_LENGTH`, `PASSWORD_MAX_LENGTH`;
`tests/test_users_cli.py` (created by F9-a).

**Scope.** In: the `create` command, tests, docs. Out: changing other `flask users` commands; any route.

**Specs.**

S1. `flask users create USERNAME [--email EMAIL] [--admin]` creates one account through the existing
    `register_user` (same username, e-mail and duplicate rules, validated with `RegisterRequest`); it never
    re-implements them. Verify first that after F9-b `RegisterRequest` / `register_user` accept a missing
    e-mail; if they do not, stop and report.
S2. Password source: the environment variable `RB_NEW_PASSWORD` when set and non-empty; otherwise a hidden
    prompt `New password` and `Repeat the password` (the texts of `set-password`). Mismatch →
    `Error: The two passwords do not match; nothing was changed.` exit 1. Length outside
    `PASSWORD_MIN_LENGTH..PASSWORD_MAX_LENGTH` (prompt or variable) →
    `Error: The password must have 8 to 128 characters.` exit 1.
S3. Invalid username or e-mail → `Error: <message of the validator>` exit 1, nothing created. Existing
    username → `Error: Username already taken: '<username>'` exit 1; e-mail taken (ignoring case) →
    `Error: E-mail already taken.` exit 1 (the e-mail is never echoed).
S4. Success prints exactly `Created '<username>'.` or, with `--admin`, `Created '<username>' (admin).`;
    `--admin` sets `is_admin` in the same transaction. The output never contains the password, the hash or
    the e-mail.
S5. The account is created with `is_blocked` false, no lock, no session, no profile row.
S6. `flask users --help` lists `create`; AGENTS.md (Roles and Authorization), `docs/knowledge/architecture.md`
    (CLI list) and `docs/knowledge/ops-runbook.md` (Service operations) name it.

**Acceptance criteria.**

- [ ] AC1 `tests/test_users_cli.py`: create with `RB_NEW_PASSWORD` (login works through `POST /auth/login`),
      with prompt input twice, `--admin` sets `is_admin`, no `--email` stores NULL (S1, S2, S4, S5).
- [ ] AC2 Mismatch, short and long password, bad username, bad e-mail, duplicate username, duplicate e-mail in
      another case: exact message, exit 1, user count unchanged (S2, S3).
- [ ] AC3 The output of every case contains neither the password nor the e-mail (S4).
- [ ] AC4 PRESERVE: one test that `set-password` and `promote` behave as before.
- [ ] AC5 Lanes: `venv/bin/pytest`; `cd frontend && npm run lint && npm run typecheck && npx vitest run && npm run build && npm run check:dist`.
- [ ] AC6 `docs/knowledge/state.md`, AGENTS.md and the docs of S6 updated.

### RESET-b: `flask reset production-data`

| Field | Value |
|---|---|
| Phase / unit | RESET (F12 prerequisite) / b |
| Branch | `feat/reset-helpers`, commit 2 of 2 |
| Depends on | RESET-a; F9-a..e, F9-h, F9-i, F9-j merged (their tables in the metadata); F11-f; owner decisions of 2026-11-12 (section 13) |
| Size forecast | ~680 authored lines (tests and docs included) |
| Risk | `Risk: item 1 (deletes almost every row of the database) + item 6 (sequence behaviour exists only on PostgreSQL)` |
| TDD | ON (strict). Runners: `venv/bin/pytest`; `TEST_POSTGRES_URL=… venv/bin/pytest -m postgres` against a database whose name contains `test` |
| Save as | this file, section "RESET-b" |

**Objective.** One command empties the database for production, keeping exactly the tables, rows and columns
the owner chose, in one transaction, with a dry run by default and guards that make a run against the wrong
database, without a backup or with an unclassified table impossible.

**Read first.** This file sections 3-6; `AGENTS.md`; `app/cli/riot.py` (dry-run pattern),
`app/cli/jobs.py` (`_UsageFailure`, exit 2), `app/services/audit.py` (`record`, `SYSTEM`),
`app/models/__init__.py`, `app/models/cardmarket.py` (`RbcmExpansion`, `RbProducts`), `tests/conftest.py`,
`tests/migration_helpers.py` (`checked_test_database_url`), `scripts/db_backup.py` (`PG_DUMP` variable
pattern).

**Scope.** In: `app/services/data_reset.py` (classification + logic, no Flask request objects),
`app/cli/reset.py` (group `reset`, registered in `app/cli/__init__.py`), tests, docs. Out: any migration;
any route; deleting files on disk; touching a KEEP table. (Until 2026-11-15 also "touching
`rbproducts.rbpdt_id_set`"; the table is now wiped.)

**Specs.**

S1. Classification: `app/services/data_reset.py` defines `TABLE_POLICY: dict[str, str]` mapping every table
    of `db.metadata` in schema `riftbound` to `keep`, `wipe` or `special`, with the values of section 3.
    `alembic_version` is not in the metadata and is never touched. The only `special` tables are `rbusers`
    (S11), `rbjobs` (S12) and `rbcm_expansions` (S13); `rbset` is `wipe`. Since 2026-11-15 the only `keep`
    tables are `rbcm_price`, `rbcm_products`, `rbcm_load_history`, `rbcm_categories` and `rbcardbans`;
    `rbproducts` and `rbcm_ignored` are `wipe` (until then they and `rbcardbans` were `keep`).
S2. Guard test: the set of `TABLE_POLICY` keys equals the set of metadata tables (no missing, no stale key);
    the failure message names the tables. A later unit that adds a table must classify it (F9-f:
    `rboauthlinks` → `wipe`). AGENTS.md "Adding a New Model" gains the step "classify it in
    `app/services/data_reset.py::TABLE_POLICY`".
S3. Runtime guard: before anything else the command reflects the tables of schema `riftbound` in the
    database; any table other than `alembic_version` that is not in `TABLE_POLICY` →
    `Error: Unclassified tables: <a>, <b>. Classify them in app/services/data_reset.py; nothing was changed.`
    exit 1.
S4. Options: `--keep-user USERNAME` (repeatable, at least one, required), `--database NAME` (required),
    `--env VALUE` (required), `--backup PATH`, `--allow-test-db`, `--execute`, `--confirm PHRASE`. Without
    `--execute` it is a dry run. `--execute` without `--confirm`, or `--confirm` without `--execute` →
    usage error, exit 2: `Error: --execute needs --confirm "RESET <database>".` /
    `Error: --confirm is only used with --execute.` (`<database>` is the `--database` value). `--execute`
    without `--backup` → usage error, exit 2: `Error: --execute needs --backup PATH.` (as built).
S5. `--database` must equal the database name of the engine URL, else
    `Error: Connected to database '<actual>', not '<given>'; nothing was changed.` exit 1.
S6. `--env` must equal `RB_ENV` as the app reads it (unset = `production`), else
    `Error: RB_ENV is '<actual>', not '<given>'; nothing was changed.` exit 1.
S7. A database name containing `test` (case-insensitive) needs `--allow-test-db`, else
    `Error: Database '<name>' looks like a test database; add --allow-test-db for a rehearsal.` exit 1.
    `--allow-test-db` with a name without `test` →
    `Error: --allow-test-db is only for a database whose name contains "test".` exit 1.
S8. Backup (required with `--execute`; reported by the dry run when given): the path is a regular file,
    non-empty, modified less than 6 hours ago, and `pg_restore -l PATH` (executable from `PG_RESTORE`,
    default `pg_restore`) exits 0, its header line `;     dbname: <name>` equals the connected database,
    and its list has a `TABLE DATA riftbound rbcm_price` entry. Messages, exit 1, nothing changed:
    `Error: Backup file not found: <path>` · `Error: Backup file is empty: <path>` ·
    `Error: Backup file is older than 6 hours: <path>` · `Error: pg_restore cannot read the backup (<first
    stderr line>).` · `Error: The backup is of database '<x>', not '<name>'.` ·
    `Error: The backup has no data for riftbound.rbcm_price.` The one function that runs `pg_restore`
    (`read_backup_toc(path) -> str`) is what the tests replace. Verify the header format with the installed
    `pg_restore` first; if it differs, stop and report.
S9. The database revision (`alembic_version`) must be the single head of `migrations/versions/`, else
    `Error: The database is at <rev>, the code expects <head>; run flask db upgrade first.` exit 1.
S10. No job may be `queued` or `running`, else
    `Error: <n> job(s) queued or running; stop the timers and wait (flask jobs list).` exit 1.
S11. Users: rows whose `username` is in `--keep-user` stay with `failed_login_count = 0` and
    `locked_until = NULL` (every other column untouched: password hash, e-mail, `is_admin`, `is_blocked`);
    every other row is deleted. A `--keep-user` name that does not exist is reported on the `Users:` line as
    missing, not an error.
S12. Jobs: rows with `rbjob_kind = 'daily_prices'` and status `success` or `error` stay, with
    `rbjob_requested_by = NULL` when it pointed to a deleted user; every other row is deleted.
S13. Expansions: every `rbcm_expansions` row stays; the command sets `rbexp_rbset_id` to NULL on every row
    and changes no other column (`rbexp_id`, `rbexp_name` untouched, no row added or deleted).
S14. Every `wipe` table (incl. `rbset`, after `rbcards`) is emptied with explicit `DELETE`s in reverse
    `db.metadata.sorted_tables` order, never relying on `ON DELETE` actions; `keep` tables are never written;
    `special` tables only as S11-S13.
S15. Sequences (PostgreSQL only): as section 3.1, with `ALTER SEQUENCE … RESTART WITH n`, after the deletes
    and inside the same transaction; never `setval`; sequences of `keep` tables and of `rbcm_expansions` are
    not touched.
S16. Audit: after the deletes, one `rbadminaudit` row through `audit.record` with actor `SYSTEM`:
    action `data.reset`, target type `database`, target id = database name, details
    `{"deleted": {<table>: <rows>}, "cleared_expansion_mappings": <n>, "kept_users": [...],
    "missing_users": [...], "backup": "<file name only>"}`. No e-mail, hash, path or URL in it.
S17. One transaction: everything from S11 to S16 commits once. Before committing, the command re-reads every
    `keep` table (row count) and `rbcm_expansions` (row count and the set of `rbexp_id`) and compares them
    with what it read at the start; a difference → rollback and
    `Error: Kept table <t> changed during the reset; rolled back, nothing was changed.` exit 1. Any exception
    → rollback, `Error: Reset failed (<ExceptionClass>); rolled back, nothing was changed.` exit 1, traceback
    in the log only.
S18. Output (dry run and execute, counts only, no e-mails, no URLs, no secrets):
    ```
    Database: <name> at <revision>; RB_ENV <env>
    Backup: <file name>, <bytes> bytes, <n> TOC entries, <h> h old      (or: Backup: not given (needed for --execute))
    Users: keep <k> (<names>), delete <d>; missing: <names or ->
    <table>  <rows>  keep | delete <n> | delete <n>, keep <m> | keep <n>, mapping cleared <m>   (one line per table, metadata order)
    ```
    (`keep <n>, mapping cleared <m>` is the `rbcm_expansions` line, `<m>` = rows with a non-NULL mapping),
    then `Dry run: nothing was changed. Run again with --execute --confirm "RESET <name>".` or
    `Reset done: <n> rows deleted in <t> tables, <m> expansion mappings cleared; kept tables unchanged.`
    When no kept user is an admin it adds
    `No kept user is an admin: create one with flask users create <name> --admin.`
S19. The confirmation phrase is exactly `RESET <database name>`; any other value →
    `Error: The confirmation does not match; nothing was changed.` exit 1.
S20. The command touches no file on disk and no other schema.
S21. Docs: AGENTS.md (structure: `app/cli/reset.py`, `app/services/data_reset.py`; "Adding a New Model"
    step of S2), `docs/knowledge/architecture.md` (CLI list), `docs/knowledge/ops-runbook.md` ("Production
    data reset": pointer to section 10 of this file).

**API / data contract.** None (no route, no migration).

**UI.** None.

**Acceptance criteria.**

- [ ] AC1 `tests/test_data_reset_classification.py`: `TABLE_POLICY` keys equal the metadata tables and the
      message names a missing or stale table; the `special` set is exactly `rbusers`, `rbjobs`,
      `rbcm_expansions` (S1, S2).
- [ ] AC2 `tests/test_reset_cli.py` with a seeding helper that writes at least one row in **every**
      metadata table and asserts it did (so a new table also needs a seed): 3 users kept + 2 deleted, with
      collection/location rows on a deleted user (username FK), F9 rows, `daily_prices` and other jobs,
      audit rows, Riot changes, links, two sets, expansions mapped to them and one unmapped, products with
      `rbpdt_id_set` = those set codes (one set-locked) owned by users (`rbuserproducts`, RESTRICT).
- [ ] AC3 Dry run: exit 0, the S18 lines (incl. `keep <n>, mapping cleared <m>` for `rbcm_expansions`),
      every table's rows and every expansion mapping unchanged (S4, S18).
- [ ] AC4 Execute: every `wipe` table empty (incl. `rbset`, and since 2026-11-15 `rbproducts` and
      `rbcm_ignored`); every `keep` table identical row by row (full tuples compared before/after, non-empty);
      `rbcm_expansions` identical row by row **except** `rbexp_rbset_id`, which is NULL on every row; users and
      jobs as S11/S12; one `data.reset` audit row with the S16 details and no e-mail or hash in the whole
      output (S11-S14, S16, S18).
- [ ] AC5 Each refusal of S3-S10 and S19: exact message, exit code, all counts and every expansion mapping
      unchanged. `read_backup_toc` and the revision reader are replaced in these tests; one test on the
      `migration_app` fixture upgraded to head proves the real revision check passes (S3-S10, S19).
- [ ] AC6 Unclassified table: a table created in the test database outside the policy → S3 message, nothing
      changed (S3).
- [ ] AC7 Failure midway: a delete step patched to raise after some deletes → S17 message, all counts and
      mappings unchanged; a keep table (and, separately, an `rbcm_expansions` row) changed inside the
      transaction → S17 rollback message (S17).
- [ ] AC8 PostgreSQL (`-m postgres`, database name contains `test`; re-add the `pytest -m postgres` CI step
      as AGENTS.md "Testing" says): sequences of emptied tables give id 1 on the next insert, `rbusers` and
      `rbjobs` give `max + 1`, keep-table sequences unchanged, and a forced rollback leaves every sequence as
      it was (S15, S17).
- [ ] AC9 Lanes: `venv/bin/pytest`; `cd frontend && npm run lint && npm run typecheck && npx vitest run && npm run build && npm run check:dist`.
- [ ] AC10 `docs/knowledge/state.md` and the docs of S21 updated.

**RESET-b as built (2026-11-15).** Where the code settles what the text left open:

- Files: `app/services/data_reset.py` (`TABLE_POLICY`, guards, `read_backup_toc`, `build_plan`, `execute`),
  `app/cli/reset.py` (group `reset`), tests `tests/test_data_reset_classification.py` (AC1),
  `tests/test_reset_cli.py` (AC2-AC7 on SQLite; the seeding helper `seed_world` lives in
  `tests/reset_helpers.py`, shared with the PostgreSQL tests) and `tests/test_reset_pg.py` (AC8, `-m postgres`).
- Branch: `feat/reset-production-data`, separate from RESET-a (PR #148); the code does not use RESET-a (only
  the `No kept user is an admin` line names `flask users create`).
- Check order: usage (S4, exit 2) → unclassified tables (S3) → database (S5) → RB_ENV (S6) → test name (S7)
  → confirmation phrase (S19) → revision (S9) → active jobs (S10) → backup (S8). The dry run refuses a
  `--backup` that fails S8 the same way.
- S9 without an `alembic_version` table prints `The database is at no revision, the code expects <head>; …`.
- S8: the age limit is `>= 6 h` refused; the TOC entry count comes from the `;     TOC Entries: <n>` header
  line (format checked against pg_restore 18.6); `PG_RESTORE` unset or empty = `pg_restore`; an executable that
  cannot run gives `pg_restore cannot read the backup (cannot run <executable>).`
- S18: table lines in `db.metadata.sorted_tables` order (parents first), `<table>  <rows>  <action>` with two
  spaces; `<h>` with one decimal; `-` for an empty name list; `Users:` names in the order given (duplicates
  dropped); `Reset done: <n> rows deleted in <t> tables` counts the deleted rows of every `wipe` table plus
  `rbusers` and `rbjobs`, and `<t>` the tables with at least one row deleted; the `No kept user is an admin`
  line comes last (dry run and execute).
- S14/S15/S16 order inside the transaction: deletes (reverse `sorted_tables`; `rbjobs` before `rbusers`, so
  `rbjob_requested_by` is cleared for deleted users before they go), sequences, then the audit row (so the
  `data.reset` row gets id 1 on PostgreSQL), then the S17 re-check and the single commit. S16 `deleted` lists
  every `wipe` table plus `rbusers` and `rbjobs` (zeros included).
- S15: the sequences are found with `pg_get_serial_sequence` on every integer column of the `wipe` tables,
  `rbusers` and `rbjobs`; a column whose sequence is not owned by it (`pg_get_serial_sequence` → NULL) is
  skipped (its ids simply continue).
- S17: an unexpected exception is logged with `current_app.logger.exception` (on a terminal the Flask logger
  writes to stderr) and the `Error:` line names only the exception class.
- AC8 needs the CI step `pytest -m postgres` in the `migrations-pg` job (`TEST_POSTGRES_URL` = the job's
  `riftbound_test` database); without it the three PostgreSQL tests only skip.
- Keep-list change (2026-11-15, `feat/reset-keep-only-history`, owner decision "keep only the Cardmarket
  history"): only `TABLE_POLICY` changed (`rbcm_ignored`, `rbproducts` → `wipe`; `rbcardbans` stays `keep`,
  agent decision, owner to confirm, section 13 Q2). No other code path changed: the delete order (reverse
  `sorted_tables`) already puts `rbuserproducts` before `rbproducts`; the S17 re-check reads the 5 `keep`
  tables (row counts) plus the expansion ids; the S15 restart finds no sequence on the two new `wipe` tables.
  On the AC2 world the execute now reports `53 rows deleted in 29 tables` (was 50 in 27). Tests: the
  classification test pins KEEP 5 / SPECIAL 3 / WIPE 27; `TestDeleteOrder` also proves the RESTRICT of
  `rbuserproducts` → `rbproducts` with foreign keys on; the PostgreSQL test checks both tables own no sequence.

**Delivery.** Conventional Commits; PR title `feat(reset): production data reset helpers (RESET units a, b)`;
PR body: specs → tests map, the rehearsal of section 11 as the manual check, rollback = revert (the
commands change nothing until run). Never merge; the owner merges.

**After merge.** Deploy to dev (no migration, restart). Then the owner runs section 11 (rehearsal) and, on a
later day, section 10.

---

## 10. Owner runbook (the reset day)

Run every command **as the service user, from the deployed checkout** (ops-runbook "Working copies"), unless
it starts with `sudo`. Never paste a password into a command line: use the prompts. Keep a terminal log
without secrets for `state.md`.

### 10.0 Worksheet (fill it during the rehearsal, section 11; check it again in step 2)

| Item | Query or command | Before | After |
|---|---|---|---|
| Revision | `venv/bin/flask db current` | | (same) |
| Sets: code, name, release date, card count | SQL A below — **the values step 8 re-enters** | | after step 8: same rows for every set re-created |
| Old expansion mapping | SQL B below — **the mapping step 8 re-does** | | after step 8: same pairs |
| Riot gallery set codes | rehearsal job result `gallery.set_codes` (11.3) | | every code has a set in step 8 |
| Cards | `SELECT count(*) FROM riftbound.rbcards;` | (about 1,500, owner's figure) | |
| Links by type | `SELECT rbpcm_match_type, count(*) FROM riftbound.rbcm_product_card_map GROUP BY 1;` | | |
| Price rows, days | `SELECT count(*), count(DISTINCT rbprc_date), min(rbprc_date), max(rbprc_date) FROM riftbound.rbcm_price;` | | must be equal (+1 day after "Load now") |
| Product rows | `SELECT count(*) FROM riftbound.rbcm_products;` | | equal (+ today's files) |
| Load history rows | `SELECT count(*) FROM riftbound.rbcm_load_history;` | | equal (+3) |
| Expansions (mapped, total) | `SELECT count(*) FILTER (WHERE rbexp_rbset_id IS NOT NULL), count(*) FROM riftbound.rbcm_expansions;` | | after step 5: 0 and the same total; after step 8: as before (or the count left unmapped on purpose) |
| Products by kind | `SELECT rbpdt_kind, count(*) FROM riftbound.rbproducts GROUP BY 1;` | (115 on 2026-10-29) | after step 5: none (wiped); after step 14: the non-singles of that load, kinds from `kind_for` (curation not kept) |
| Products whose set does not exist (P1) | query P1 below | none | none at every step (`rbproducts` empty until step 14, then sets from the new mapping) |
| Bans | `venv/bin/flask bans list` (and `SELECT rbban_mode, count(*) FROM riftbound.rbcardbans GROUP BY 1;`) | 25 rows: 12 in 1v1, 13 in 2v2 (the `0009` seed) | the same 25 rows after step 5 and at the end (KEEP) |
| Riot sync time | from the job's start/finish | | |
| Restore time | measured in 11.1 | | |

SQL A (the hand-entered set data and the card count per set):

```sql
SELECT s.rbset_id, s.rbset_name, s.rbset_ncard, s.rbset_outdat,
       (SELECT count(*) FROM riftbound.rbcards c WHERE c.rbcar_rbset_id = s.rbset_id) AS cards
FROM riftbound.rbset s ORDER BY s.rbset_outdat NULLS LAST, s.rbset_id;
```

SQL B (which Cardmarket expansion maps to which set):

```sql
SELECT rbexp_id, rbexp_name, rbexp_rbset_id FROM riftbound.rbcm_expansions
WHERE rbexp_rbset_id IS NOT NULL ORDER BY rbexp_rbset_id, rbexp_id;
```

P1 (products whose set code has no `rbset` row; none at every step since `rbproducts` is wiped, 2026-11-15):

```sql
SELECT p.rbpdt_id_set, p.rbpdt_set_locked, count(*) FROM riftbound.rbproducts p
LEFT JOIN riftbound.rbset s ON s.rbset_id = p.rbpdt_id_set
WHERE p.rbpdt_id_set IS NOT NULL AND s.rbset_id IS NULL
GROUP BY 1, 2 ORDER BY 1, 2;
```

Run SQL with `psql -h <host> -U <user> -d <database>` (or `riftbound_reset_test` during the rehearsal). Keep
the SQL A and SQL B results at hand for step 8 (they hold no personal data).

Not recorded on purpose (owner 2026-11-15): the ignored products list (`rbcm_ignored`, erroneous test data:
the owner ignores again in step 14 what is not a card) and the product curation (`rbproducts` kinds,
kind/set locks, hidden flags, uploaded images): neither is restored; only the dump of step 3 keeps them. The
bans need no list either: `rbcardbans` is kept (the 25 seeded rows; section 13 Q2).

### 10.1 Preconditions (all must be true)

1. F9-a..e, F9-h, F9-i, F9-j and F11-f deployed on dev (with the F9-a timer `riftbound-sessions-purge.timer`
   installed; if it is not, drop it from the `systemctl` lines below); RESET-a/b merged and deployed;
   `venv/bin/flask db current` shows the head; `venv/bin/flask db check` → `No new upgrade operations detected.`
2. The rehearsal (section 11) passed on an earlier day and the worksheet "Before" column is filled, including
   SQL A, SQL B and the gallery set codes.
3. RESET-b built with the owner decisions of section 13.
4. A maintenance window of at least the rehearsal's total time plus the restore time; `rbqa` users and anyone
   else told.

### 10.2 Steps

**Step 1. Stop the writers.**

```bash
sudo systemctl stop riftbound-jobs.timer riftbound-daily.timer riftbound-daily-retry.timer \
    riftbound-riot-sync-am.timer riftbound-riot-sync-pm.timer riftbound-sessions-purge.timer
sudo systemctl stop <service>                      # the app; the proxy answers an error page meanwhile
venv/bin/flask jobs list --limit 5                 # nothing queued or running
```

Check: `systemctl list-timers 'riftbound-*' --no-pager` lists only `riftbound-backup.timer` (leave it; avoid a
window across 03:30). If a job is `running`, wait for it and list again.

**Step 2. Record "before" figures** (worksheet, same queries as in the rehearsal, SQL A and SQL B included;
they must match it, give or take the days loaded since).

**Step 3. Safety dump and file copies.** The dump is the only safety net for the data that is wiped.

```bash
pg_dump -h <host> -U <user> -d <database> -n riftbound -Fc \
    -f <backup dir>/riftbound_pre_reset_$(date +%Y%m%d_%H%M).dump
chmod 600 <backup dir>/riftbound_pre_reset_*.dump
pg_restore -l <backup-file> | head -5             # header: dbname: <database>
pg_restore -l <backup-file> | grep -c 'TABLE DATA riftbound'
tar -C <card images dir> -czf <backup dir>/card-images-pre-reset-$(date +%Y%m%d).tar.gz .
tar -C <product images dir> -czf <backup dir>/product-images-pre-reset-$(date +%Y%m%d).tar.gz .
tar -C <avatar dir> -czf <backup dir>/avatars-pre-reset-$(date +%Y%m%d).tar.gz .   # only if <avatar dir> exists
```

Check: the dump size is close to the last nightly one; the `TABLE DATA` count equals the number of tables
with rows; the archives exist. Copy the dump and the archives off the server (owner's usual place).
Never use `scripts/db_backup.py` for this one: it names files `riftbound_nightly_*` and deletes them after
14 days.

**Step 4. Dry run.**

```bash
venv/bin/flask reset production-data --keep-user rbadmin --keep-user racmos --keep-user rbqa \
    --database <database> --env <RB_ENV of the server> --backup <backup-file>
```

Check: `Users:` line (kept names; `missing` lists the accounts to create in step 6); exactly the 5 KEEP tables
(`rbcm_price`, `rbcm_products`, `rbcm_load_history`, `rbcm_categories`, `rbcardbans`) say `keep`;
`rbproducts` and `rbcm_ignored` say `delete <n>`; `rbset` says `delete <n>` (n = rows of SQL A);
`rbcm_expansions` says `keep <n>, mapping cleared <m>`
(m = rows of SQL B); `rbjobs` keeps only `daily_prices` rows; the counts match the worksheet; ends with
`Dry run: nothing was changed.` Any `Error:` → fix the cause (timers, revision, backup) and repeat; do not
continue.

**Step 5. Execute.**

```bash
venv/bin/flask reset production-data --keep-user rbadmin --keep-user racmos --keep-user rbqa \
    --database <database> --env <RB_ENV of the server> --backup <backup-file> \
    --execute --confirm "RESET <database>"
```

Check: `Reset done: … expansion mappings cleared; kept tables unchanged.`; run step 4 again: every WIPE table
shows `0` except `rbadminaudit` (`1  delete 1`: the `data.reset` row), `rbusers` shows only the kept rows, KEEP tables show the same counts as before, `rbcm_expansions`
shows `mapping cleared 0`. SQL checks:

```sql
SELECT username, is_admin, is_blocked FROM riftbound.rbusers ORDER BY 1;
SELECT rbaud_action, rbaud_actor_username FROM riftbound.rbadminaudit;   -- one row: data.reset, system
SELECT count(*) FROM riftbound.rbset;                                   -- 0
SELECT count(*) FILTER (WHERE rbexp_rbset_id IS NOT NULL), count(*) FROM riftbound.rbcm_expansions;  -- 0, same total
SELECT count(*) FROM riftbound.rbproducts;                              -- 0 (rebuilt in step 14)
SELECT count(*) FROM riftbound.rbcm_ignored;                            -- 0
```

`venv/bin/flask bans list` → the 25 rows of the worksheet (12 in 1v1, 13 in 2v2). P1 returns no rows.

**Step 6. Accounts.**

```bash
venv/bin/flask users create rbadmin --email <app e-mail> --admin   # only if step 4 listed it as missing; prompts the password
venv/bin/flask users create racmos --email <personal e-mail>        # only if missing
venv/bin/flask users set-password rbadmin                            # new passwords for the kept ones (prompt)
venv/bin/flask users set-password racmos
venv/bin/flask users set-password rbqa
venv/bin/flask users demote racmos                                   # racmos is a normal user
venv/bin/flask users promote rbadmin
venv/bin/flask users list                                            # three rows; rbadmin admin; nobody blocked or locked
```

`RB_NEW_PASSWORD` is only for scripts: if used, set it with `read -rs RB_NEW_PASSWORD; export
RB_NEW_PASSWORD` and `unset RB_NEW_PASSWORD` right after. A kept account with a wrong e-mail is fixed in the
app (Account → Profile, signed in as that account) after step 7.

**Step 7. Start the app and move the three image directories aside** (card images, product images, avatars;
section 5).

```bash
sudo mv <card images dir> <card images dir>.pre-reset-$(date +%Y%m%d)
sudo install -d -o <service user> -g <service user> -m 755 <card images dir>
sudo mv <product images dir> <product images dir>.pre-reset-$(date +%Y%m%d)   # only if it exists
sudo install -d -o <service user> -g <service user> -m 755 <product images dir>
sudo mv <avatar dir> <avatar dir>.pre-reset-$(date +%Y%m%d)          # only if it exists
sudo install -d -o <service user> -g <service user> -m 755 <avatar dir>
sudo systemctl start <service>
curl -s -o /dev/null -w '%{http_code}\n' <URL>/riftbound/api/v1/health   # 200
```

Check: sign in as `rbadmin` at `/riftbound/app/login`; Admin overview opens; Cards shows 0 cards and Admin →
Sets shows no set. Enrol 2FA on `rbadmin` now if wanted (Account → Security). The timers stay stopped until
step 15.

**Step 8. Sets and expansion mapping — before any Riot sync or load.** Every set the Riot gallery lists
(worksheet "gallery set codes") must exist, **with its card count**, before step 9 (section 6.2: a missing
set or a set without a count makes the sync skip the Showcase rarity rule for its cards).

1. Admin → Cardmarket → Matching → Expansions (`?tab=expansions`): every expansion shows as not mapped and
   none has a suggestion. For each set in SQL B, take its first expansion → "Map to a set…" → "Create a new
   set…" with the code (`rbset_id`, exactly as in SQL A), name, release date and card count (`rbset_ncard`)
   of SQL A. This creates the set and maps the expansion in one transaction. The other expansions of the
   same set (SQL B) → "Map to a set…" → that set.
2. Admin → Sets → New set for every gallery code that has no Cardmarket expansion yet (same four values;
   for a set new since the worksheet, the owner enters them).
3. Sets of SQL A that the owner does not want any more (old placeholders, promo sets with no gallery cards):
   do not create them. Their expansions stay unmapped (or are mapped to another set); their products get no
   set at the refresh of step 14.

Check: SQL A on the database → one row per set created, every gallery code present, every row with a name,
a release date and a card count (no NULL `rbset_ncard`); "Expansions (mapped, total)" back to the "Before"
value (or less, by the expansions left unmapped on purpose; Expansions tab "Not mapped only" shows exactly
those); P1 returns no rows (no product exists before step 14).

**Step 9. Riot sync.**

```bash
venv/bin/flask jobs enqueue riot_sync
sudo systemctl start riftbound-jobs.service       # runs it in the foreground; returns when done
venv/bin/flask jobs list --limit 3
venv/bin/flask shell <<< "import json; from app.models import RbJob; j = RbJob.query.filter_by(rbjob_kind='riot_sync').order_by(RbJob.rbjob_id.desc()).first(); print(j.rbjob_id, j.rbjob_status, j.rbjob_message); print(json.dumps(j.rbjob_result, indent=2, ensure_ascii=False))"
```

Check: status `success`; **`placeholder_sets` is `[]`** (a code listed there was missed in step 8: its cards
went in without the Showcase rule; complete that set in Admin → Sets with name, date and count, run the sync
again and approve the rarity proposals in Admin → Riot → Changes); `gallery.unparsed` as in the rehearsal; per
set `inserted` = the rehearsal's, `applied` 0, `proposed` 0, `unchanged` 0, `error` null, `images.failed` 0
(or few); `SELECT count(*) FROM riftbound.rbcardchanges;` → 0; SQL A shows the new card counts (worksheet
"After").

**Step 10. Images gap (only if `images.failed` > 0).** Run step 9 again (it downloads only missing files);
still failing → `venv/bin/flask images import-legacy --source <card images dir>.pre-reset-<date>` (copies
missing files, never overwrites). Check: `curl -sI <URL>/riftbound/media/cards/<folder>/<file>` → 200 for a
card of each set; the Cards page shows images.

**Step 11. Idempotence check.** Step 9 once more: every set `inserted` 0, `proposed` 0, `applied` 0,
`unchanged` = cards, `images.existing` = cards, `placeholder_sets` `[]`. Any proposal → stop and send the job
result to the planner (a compare rule is not stable).

**Step 12. Sets review.** Admin → Sets: every set has its name, release date and card count; no set is named
after its code (a placeholder); a set with 0 cards is either a set Riot does not list yet (keep it) or a
mistake (unmap its expansions in the Expansions tab, then delete it).

**Step 13. Soft links and bans.** SQL checks:

```sql
SELECT e.rbexp_id, e.rbexp_rbset_id FROM riftbound.rbcm_expansions e
LEFT JOIN riftbound.rbset s ON s.rbset_id = e.rbexp_rbset_id
WHERE e.rbexp_rbset_id IS NOT NULL AND s.rbset_id IS NULL;     -- expect no rows
```

Products: nothing to check yet (`rbproducts` is rebuilt by the load of step 14).

Bans (kept, not re-added): `venv/bin/flask bans list` shows the same 25 rows as the worksheet (12 in 1v1,
13 in 2v2); signed in, `GET /riftbound/api/v1/bans` → every item has a non-empty `printings` list (an empty
one = the name no longer matches a card: fix with `flask bans remove` / `add`).

**Step 14. Cardmarket mapping.**

1. Admin → Cardmarket → "Load now" (or `venv/bin/flask jobs enqueue daily_prices` then
   `sudo systemctl start riftbound-jobs.service`; the follow-ups `value_snapshot`, `products_refresh`,
   `price_alerts` run in the same call). Check (ops-runbook "Daily Cardmarket load" one-liner): `success`,
   `validation.price_rows` > 0, `auto_match.linked`, `review_total`; `queued` lists the three follow-ups;
   `products_refresh` `new` = `total` = the non-singles of today's file (the catalog is rebuilt from zero),
   `value_snapshot` 0 rows, `price_alerts` 0 alerts; P1 returns no rows; "Products by kind" filled in the
   worksheet "After".
2. Matching → Auto-match (`?tab=auto`): Preview, then "Apply clear cases" until `remaining_clear` is 0.
3. Matching → To link (`?tab=link`): link the rest by hand (suggestions, Link dialog), Ignore what is not a
   card (the ignored list starts empty); Conflicts tab empty at the end.
4. Check: SQL "Links by type" vs the worksheet; the Matching header counters; a card detail page shows a
   price chart that starts **before** the reset day (proof that the history is reachable).
5. Optional: Admin → Products: redo the product curation that is wanted (kinds, kind/set locks, hidden,
   images); the old one is not restored (section 4).

**Step 15. Re-enable the timers.**

```bash
sudo systemctl enable --now riftbound-jobs.timer riftbound-daily.timer riftbound-daily-retry.timer \
    riftbound-riot-sync-am.timer riftbound-riot-sync-pm.timer riftbound-sessions-purge.timer
systemctl list-timers 'riftbound-*' --no-pager
```

**Step 16. Final validation.**

- [ ] `venv/bin/flask db current` = head, `venv/bin/flask db check` clean.
- [ ] Admin overview: sets and cards as the worksheet "After"; Riot pending 0; Cardmarket last load today,
      unmapped expansions = only those left unmapped on purpose in step 8, unmatched = what is left on purpose.
- [ ] P1 returns no rows; the expansion soft-link query of step 13 returns no rows.
- [ ] `/riftbound/app/cards`: images, filters and prices; a card detail: price history before the reset day.
- [ ] `/riftbound/app/products`: prices and history (back to the first kept load); kinds as `kind_for` gives
      them (or as redone in step 14.5); the set filter shows set names; no product image until uploaded again.
- [ ] `venv/bin/flask bans list`: the 25 rows of the worksheet.
- [ ] As `racmos`: Collection, Decks, Locations, Wishlists are empty; adding a card, a deck and a wishlist line
      works; the line shows a price.
- [ ] `/riftbound/app/admin/audit`: first row `data.reset`, then the set creations, the mappings, the sync and
      the mapping rows.
- [ ] `/riftbound/app/admin/cardmarket`: the old load days are listed (their `daily_prices` jobs linked, D-Q6).
- [ ] Next morning: the 06:30 `daily_prices` job `success`; the 08:00 Riot sync `success`.
- [ ] Record in `docs/knowledge/state.md`: date, dump file name (no path), worksheet figures, open items.

Keep the dump, the archives and the `.pre-reset-<date>` directories until production has run for a while (the
owner decides when to delete them).

## 11. Rehearsal (an earlier day, on a copy)

Goal: run section 10.2 steps 4-14 on a copy of the real data, measure the times, fill the worksheet (SQL A,
SQL B and the gallery set codes included) and see what the re-download changes. Nothing here touches the dev
database or the dev image directories.

### 11.1 Prepare

```bash
pg_dump -h <host> -U <user> -d <database> -n riftbound -Fc -f <scratch dir>/rehearsal_source.dump
createdb -h <host> -U <superuser> -O <app role> riftbound_reset_test
time pg_restore -h <host> -U <superuser> -d riftbound_reset_test --no-owner --role=<app role> \
    <scratch dir>/rehearsal_source.dump                 # this is the restore time of section 12
mkdir -p <scratch dir>/card-images <scratch dir>/product-images <scratch dir>/avatars
```

### 11.2 A dedicated shell (every rehearsal command runs in it)

```bash
read -rs DATABASE_URL && export DATABASE_URL               # paste the URL of riftbound_reset_test; not echoed, not in the history
export CARD_IMAGES_DIR=<scratch dir>/card-images
export PRODUCT_IMAGES_DIR=<scratch dir>/product-images
export AVATAR_DIR=<scratch dir>/avatars
venv/bin/flask shell <<< "from app import db; print(db.engine.url.database)"   # must print riftbound_reset_test
```

**If it prints anything else, stop.** The environment overrides `.env` (`load_dotenv(override=False)`), but
`riot_sync`, `flask users` and the jobs have no database guard. Jobs run with `venv/bin/flask jobs
run-pending` in this shell, never with `systemctl` (the units use the real environment file).

### 11.3 Run

1. Worksheet "Before" with `psql … -d riftbound_reset_test` (SQL A, SQL B, P1 and the counts), and three
   files for later steps:
   ```
   \copy (SELECT rbcar_rbset_id, rbcar_id, rbcar_name, rbcar_type, rbcar_rarity, rbcar_domain, rbcar_energy, rbcar_power, rbcar_might, rbcar_tags FROM riftbound.rbcards ORDER BY 1, 2) TO '<scratch dir>/cards_before.csv' CSV HEADER
   \copy (SELECT rbset_id, rbset_name, rbset_ncard, rbset_outdat FROM riftbound.rbset ORDER BY 1) TO '<scratch dir>/sets_before.csv' CSV HEADER
   \copy (SELECT rbexp_id, rbexp_rbset_id FROM riftbound.rbcm_expansions WHERE rbexp_rbset_id IS NOT NULL ORDER BY 1) TO '<scratch dir>/expansions_before.csv' CSV HEADER
   ```
2. Dump the scratch database (the backup check wants a dump of the database it resets):
   `pg_dump -h <host> -U <user> -d riftbound_reset_test -n riftbound -Fc -f <scratch dir>/rehearsal.dump`
3. Step 4 and step 5 with `--database riftbound_reset_test --allow-test-db --backup <scratch dir>/rehearsal.dump`;
   check `rbset` 0, `rbproducts` 0, `rbcm_ignored` 0, mappings 0, bans 25, P1 no rows.
4. Step 6 (users).
5. Step 8, either way:
   - **In the UI** (rehearses the real step, measures its time): in the rehearsal shell run
     `venv/bin/python run.py` (loopback only, debug off), reach it with `ssh -L 5000:127.0.0.1:5000 <server>`,
     sign in as `rbadmin` and do step 8 as written (if signing in fails over the tunnel, use the shortcut).
   - **Shortcut** (scratch database only, never on dev): put the old sets and mapping back with `psql … -d
     riftbound_reset_test`:
     ```
     \copy riftbound.rbset (rbset_id, rbset_name, rbset_ncard, rbset_outdat) FROM '<scratch dir>/sets_before.csv' CSV HEADER
     CREATE TEMP TABLE exp_before (rbexp_id integer, rbexp_rbset_id text);
     \copy exp_before FROM '<scratch dir>/expansions_before.csv' CSV HEADER
     UPDATE riftbound.rbcm_expansions e SET rbexp_rbset_id = b.rbexp_rbset_id FROM exp_before b WHERE e.rbexp_id = b.rbexp_id;
     ```
   Then fill any NULL `rbset_ncard` in the scratch copy as step 8 requires.
6. Step 9 with `venv/bin/flask jobs enqueue riot_sync && time venv/bin/flask jobs run-pending`, then steps 10,
   11. Record `gallery.set_codes` in the worksheet; compare with `sets_before.csv`: codes the gallery lists
   that were not in `rbset` (to create on the real day) and old sets the gallery does not list (to keep or
   drop, step 8.3). `placeholder_sets` must be `[]` with the step 8 sets; a code listed there must be added to
   the real-day list.
7. `\copy` the cards query to `cards_after.csv`; compare:
   `diff <(sort <scratch dir>/cards_before.csv) <(sort <scratch dir>/cards_after.csv)` and the keys only
   (`cut -d, -f1,2 … | sort | comm -3 - -`). Expected differences: cards that were not in the gallery (hand-made,
   promo) disappear; cards the owner edited by hand or whose proposals were rejected now show the gallery
   value. Write the list down: these are the hand fixes to redo after the real reset (D-Q10).
8. Step 14 without the UI: `venv/bin/flask jobs enqueue daily_prices && venv/bin/flask jobs run-pending`, then
   ```bash
   venv/bin/flask shell <<< "from app.services import cardmarket_matching as m; r = m.preview(); print(r['date'], r['clear'], r['doubtful'], r['review_total'])"
   venv/bin/flask shell <<< "from app import db; from app.services import cardmarket_matching as m; r = m.apply(200); db.session.commit(); print(r['linked'], r['remaining_clear'], r['doubtful'])"
   ```
   (repeat the second line until `remaining_clear` is 0). Compare "Links by type" with the dev figures: this is
   the manual linking left for the real day. P1 must return no rows after the load.
9. Fill the worksheet "After", the sync and load times, the restore time.

### 11.4 What to compare (pass criteria)

- KEEP counts identical before/after the reset (the 5 tables, bans 25); WIPE tables 0 (incl. `rbset`,
  `rbproducts`, `rbcm_ignored`); `rbcm_expansions` same rows, 0 mappings; three users; `rbproducts` rebuilt
  by the load with sets from the new mapping (P1 no rows).
- After step 8: SQL A and SQL B equal to the "Before" values for every set re-created.
- Riot sync `success`, `placeholder_sets: []`, no proposals, second run all `unchanged`.
- Cards per set close to the dev catalog; every difference explained by the diff of 11.3 step 7.
- Clear-case links + remaining review: a manual workload the owner accepts.
- Total time (reset + step 8 + sync + load + auto-match) fits the planned window.

### 11.5 Clean up

`dropdb -h <host> -U <superuser> riftbound_reset_test`; delete `<scratch dir>` (its CSVs hold card, set and
mapping data only; the dumps hold user data: delete them or keep them as private as the nightly backups).

## 12. Rollback and failures

**Full rollback** (any time before real users write production data; after that, a restore loses their
work):

```bash
sudo systemctl stop <service> riftbound-jobs.timer riftbound-daily.timer riftbound-daily-retry.timer \
    riftbound-riot-sync-am.timer riftbound-riot-sync-pm.timer riftbound-sessions-purge.timer
pg_restore -h <host> -U <user> -d <database> --clean --if-exists --single-transaction <backup-file>
sudo mv <card images dir> <card images dir>.reset-failed-$(date +%Y%m%d)
sudo mv <card images dir>.pre-reset-<date> <card images dir>
sudo mv <product images dir> <product images dir>.reset-failed-$(date +%Y%m%d)
sudo mv <product images dir>.pre-reset-<date> <product images dir>
sudo mv <avatar dir> <avatar dir>.reset-failed-$(date +%Y%m%d)
sudo mv <avatar dir>.pre-reset-<date> <avatar dir>
venv/bin/flask db current && venv/bin/flask db check
sudo systemctl start <service>
sudo systemctl enable --now riftbound-jobs.timer riftbound-daily.timer riftbound-daily-retry.timer \
    riftbound-riot-sync-am.timer riftbound-riot-sync-pm.timer riftbound-sessions-purge.timer
```

The restore brings back the sets, the expansion mapping and every wiped row (product catalog and ignored list
included). It takes about the restore time
measured in 11.1 plus a minute. Check: the worksheet "Before" figures (SQL A and SQL B included).

**A step fails midway**

| Step | Effect of a failure | What to do |
|---|---|---|
| 1-4 | Nothing changed | Fix the cause, repeat; restart the app and timers if the window is abandoned |
| 5 | One transaction: rolled back, `nothing was changed` | Read the message, fix, repeat step 4 |
| 6 | Each command is its own transaction | Repeat the failed command; `flask users list` |
| 7 | Directories only | Move them back if abandoning |
| 8 | Each set creation / mapping is one audited transaction (CM-d creates set + mapping together or nothing) | Redo the failed one in the screen (Undo toasts undo a mapping); do **not** start step 9 until every gallery set exists with its count |
| 9-11 | Sync: each set in a savepoint, one commit at the end; a set with `error` is not written | Repeat step 9 (inserts only what is missing); a gallery failure (`gallery fetch failed`) → try later; a non-empty `placeholder_sets` → step 9 check |
| 12-13 | Single admin writes, audited | Redo in the screen |
| 14 | Load is one transaction (`error` = nothing written); auto-match apply commits per click | Repeat "Load now" (same day: prices replaced, products skipped when unchanged); continue the matching where it stopped |
| 15-16 | — | Re-enable the timers in any case before leaving |

Abandoning after step 5 but before production users: full rollback, or stay on the reset data and finish
another day — but never let a timer run a Riot sync before step 8 is complete (keep
`riftbound-riot-sync-am/pm.timer` stopped until then; the daily load may run once step 8 is done).

## 13. Owner decisions (2026-11-12, revised 2026-11-15)

Revision of 2026-11-15 (owner): **the reset wipes everything except the Cardmarket load history**
(`rbcm_price`, `rbcm_products`, `rbcm_load_history`, `rbcm_categories`); everything else was created while
testing (wrong mappings, test data, even real-looking data). The SPECIAL tables stay as they were (Q1/Q3, Q6,
the `--keep-user` accounts). Q2, Q4, Q5 and Q10 below are rewritten; the other rows are unchanged.

| # | Decision | Effect in this plan |
|---|---|---|
| Q1 | **Wipe `rbset`**: the sets are created from zero (clean sets) | `rbset` WIPE; sets re-created in step 8, **before** the first Riot sync, from SQL A (code, name, release date, card count) via CM-d "Create a new set…" (set + mapping in one transaction) or Admin → Sets; step 9 requires `placeholder_sets: []` (section 6.2) |
| Q3 | Follows Q1: **`rbcm_expansions` rows kept, mapping cleared** | SPECIAL: the reset sets `rbexp_rbset_id` to NULL (RESET-b S13); step 8 maps them again from SQL B |
| Q2 | **Keep `rbcardbans`** (2026-11-12). 2026-11-15: **kept — decided by the agent, owner to confirm.** The owner's 2026-11-15 rule would wipe it, but dev holds exactly the 25 rows migration `0009` seeded (12 in 1v1, 13 in 2v2): reference data identical to a fresh install, not test data; wiping it would only force 25 `flask bans add` by hand, since the seed never runs again | KEEP; `flask bans list` shows the 25 rows after step 5 and at the end (steps 5, 13, 16). If the owner overrules: one-line change in `TABLE_POLICY` (`rbcardbans` → WIPE), and the runbook records `flask bans list` before the reset and re-adds the wanted bans with `flask bans add` after step 9 |
| Q4 | **WIPE `rbcm_ignored`** (owner 2026-11-15; was Keep on 2026-11-12) | WIPE; the list was erroneous test data, so it is not recorded in the worksheet; the owner ignores products again in step 14 |
| Q5 | **WIPE `rbproducts`** (owner 2026-11-15; was Keep on 2026-11-12) | WIPE (after `rbuserproducts`, RESTRICT); `products_refresh` rebuilds the catalog from the first load (step 14); kinds, locks, hidden flags and uploaded images are not preserved (redo in Admin → Products); `PRODUCT_IMAGES_DIR` is moved aside in step 7 like the card images and avatars (section 5) |
| Q6 | **Keep the finished `daily_prices` job rows** | SPECIAL `rbjobs` (RESET-b S12) |
| Q7 | Wipe the audit trail (+ one `data.reset` row) | WIPE `rbadminaudit` (RESET-b S16) |
| Q8 | Wipe the 2FA of the kept accounts | WIPE `rbusermfa`, `rbrecoverycodes`; re-enrol after step 7 |
| Q9 | **Move the card images folder aside and re-download everything** | Section 5, step 7. 2026-11-15: `PRODUCT_IMAGES_DIR` is moved aside too (follows Q5), like `AVATAR_DIR` |
| Q10 | Full re-download of the catalog; read the rehearsal diff first. 2026-11-15: **the 132 cards Riot does not publish (OGNX, SFDX, OGSX, the SFD runes, PROK) are accepted as lost**; they can be recreated by hand later (Admin → Cards or the CM-c form) | Section 4, 11.3 step 7; no step of the runbook restores them |
| Q11 | Wipe the legacy `rbcardmarket` rows | WIPE |
| Q12 | **No export step**: the `pg_dump` is the only safety net | No collection or deck export before the reset |
| Q13 | Timing: after F9-j, before F9-f/F9-g | Section 2 |

Open questions: Q2 as revised on 2026-11-15 (`rbcardbans` kept by the agent; the owner confirms or
overrules before the reset).

Notes the owner should know: the Cardmarket links are regenerated (owner decision; manual links on the
current dev data are moot); `rbqa` keeps its account but loses its data; `racmos` is demoted to a normal user
in step 6.

## 14. Rehearsal results (2026-11-15, scratch database `riftbound_reset_test`)

Run by the agent on a copy of the dev data (a `pg_dump` of the dev database taken at head `0032_api_keys`,
restored with `--no-owner`), never on the dev database. Dev counts were checked unchanged afterwards.

| Step | Result | Time |
|---|---|---|
| Restore the dump into the empty scratch database | 35 tables in schema `riftbound`, head `0032_api_keys` | 3 s |
| Dry run (kept users `rbqa`, `racmos`) | Backup accepted (`pg_restore -l`, 490 TOC entries); counts as in section 3 (KEEP: bans 25, ignored 2, products 122, prices 54,901, Cardmarket products 54,766, load history 141; WIPE: sets 14, cards 1,511, card changes 1,308, collection 322, decks 7+7, audit 108 ...; users keep 2 / delete 6; jobs keep 24 / delete 87; expansions keep 18, mapping cleared 9) | instant |
| Execute (`--execute --confirm "RESET riftbound_reset_test"`) | `Reset done: 4928 rows deleted in 20 tables, 9 expansion mappings cleared; kept tables unchanged` | 4.5 s |
| Dry run again | Users delete 0, jobs delete 0, `rbadminaudit 1` (the `data.reset` row), nothing else to delete | - |
| Sequences | Restarted at max + 1 (`rbusers` next id 12 after max 11, `rbjobs` 107 after 106) | - |
| Soft links | `rbproducts.rbpdt_id_set` codes all valid again once sets with the same codes exist (P1 empty) | - |
| Step 8 (shortcut, sets + mapping restored from CSV) | 14 sets, 9 expansions mapped | - |
| Step 9 Riot sync on the empty catalog | `riot_sync` success, **1,379 cards inserted directly, 0 rows in `rbcardchanges` (nothing to approve), no placeholder sets**, 1.3 GB of images downloaded (OGN, OGS, RAD, SFD, UNL, VEN) | 3 min 17 s |
| Step 14: Auto-match before a load | 751 clear cases linked in 4 rounds of 200; 1,126 left (1,098 ambiguous, 28 no candidates) | 16 s |
| Step 14: "Load now" (`daily_prices` + `value_snapshot`, `products_refresh`, `price_alerts`) | all four jobs success; the exact-name pass linked about 300 more | 16 s |
| Step 14: Auto-match after the load | 0 clear cases left; **827 products still to link by hand** (799 ambiguous, 28 no candidates); 1,052 links total | 16 s |

### What the re-download loses (decision needed before the real reset)

The dev database has **1,511 cards; the sync recreates 1,379**. The 132 missing cards are not in the Riot
gallery and do not come back by themselves:

| Set | Cards lost | Examples |
|---|---|---|
| OGNX | 60 | Blazing Scorcher, Ravenbloom Student, Heimerdinger ... |
| SFDX | 36 | Fae Dragon, Yone Blademaster ... |
| OGSX | 17 | Annie Fiery, Flash ... |
| SFD | 14 | the runes `R01`, `R01a`, `R02` ... |
| PROK | 5 | `FND196` Teemo Scout, `FND249`, `FND251` ... |

Three collection lines of the owner point at them. Options: (a) accept the loss and add them later through
the admin card editor; (b) change RESET-b so that it keeps the cards of the sets the gallery does not list
(a small, test-covered change: the policy would become per set); (c) export them before the reset and
re-create them after. Section 13 Q10 said to read this diff first: this is that diff.

### Manual work after the reset (measured)

- Today (dev data) 415 Cardmarket products are unmatched; after the reset **827** (about 410 more links to
  make by hand, because the current manual links are lost on purpose).
- 9 Cardmarket expansions stay unmapped, as today.
- No Riot change approvals are needed (the sync inserts on an empty catalog).
