# Planner decisions of 2026-10-25 (delegated by the owner) — batch 1, functional sketch

On 2026-10-25 the owner asked for "todos los requisitos más acotados para que invente o improvise lo menos
posible, menos pausas; mergeas varias PRs seguidas y poder presentar un boceto funcional lo antes posible.
Debe ser totalmente autónomo y después ya iremos revisando módulo a módulo". The planner therefore closed
every open decision that affects batch 1 (`docs/requirements/BATCH-1.md`) with the recommendation of its
phase spec, unless this file says otherwise. These decisions are binding for the implementer and are
reviewed by the owner module by module after the batch. Where this file and a phase spec's "Open
decisions" table disagree, **this file wins**; `decisions-2026-10-22.md` and `product.md` still win over
both.

## Scope of batch 1 (the functional sketch)

In, in this order: M-d → F13-a…g → F2-b, c, d, e, f, g, h, i, k → F3-a, F3-b, F4-c, F3-c, F3-d, F3-e,
F3-g, F3-h, F3-i → F14-a…f. The order and the files are in `docs/requirements/BATCH-1.md`.

Deferred to batch 2 (polish, after the owner's review): F2-j (offline catalog), F2-l (WebP thumbnails),
F3-f + F3-j (wishlist), F3-k (offline collection), offline for products (D-F14-12), import formats other
than RBAPP (Cardmarket, riftdecks, Piltover Archive, own spreadsheets: they need the owner's sample files,
D-F3-2), the audit purge job (D-F13-13), the rest of F4 (movers, dashboard, push, watchlist) and every
later phase.

## M-d — card images out of git

| ID | Decision |
|---|---|
| D-Md-1 | Images live in a directory set by the env variable `CARD_IMAGES_DIR` (absolute path). When unset, the default is `<project root>/data/card-images` (git-ignored; dev and tests). The deployed server sets it in `.env` to a path outside the checkout (host value in `ops.local.md`). |
| D-Md-2 | New public URL `/riftbound/media/cards/<folder>/<file>` served by Flask from that directory (`P`, like static files); `RbCard.image_src` returns it. The old `/riftbound/static/images/cards/...` URLs stop working after the deploy (nothing outside the app links to them). |
| D-Md-3 | Files are copied, never moved, by `flask images import-legacy` (idempotent) and by the runbook step that runs **before** the deploy pulls the commit that removes them from git. |

## F2 — catalog

| ID | Decision |
|---|---|
| D-F2-1 | The implementer runs the three read-only `SELECT … GROUP BY` queries of the F2 phase spec on the dev database at the start of F2-b and adapts the S1 tuples to the real values (known values keep the draft order; extra real values are appended); the query output goes in the PR body. |
| D-F2-3 | Catalog API for signed-in users (`U`); `GET /meta/game` public (`P`). |
| D-F2-4 | Recommendation accepted (base printing rule; tokens shown and filterable, `exclude_supertype=Token`). |
| D-F2-5 | Recommendation accepted: Mercado (with source), Mín., Media 30 d, Mercado foil when foilable; trends 7 d and 30 d; no "High". |
| D-F2-6 | `30d`, `90d` (default), `1y`, `all`. |
| D-F2-7, 8, 9, 10 | Accepted as recommended, implemented in batch 2 (F2-j, F2-l). |
| D-F2-11 | `sets` nav entry stays `legacy` (the admin edits sets in `/admin/sets` from F13-f). |
| D-F2-12 | Spanish enum names from the official `es-es` card gallery when the implementer can read it; otherwise the names proposed in the F2-e draft. Either way the PR lists every name used for the owner's review. |
| D-F2-13 | Grid by default, last view remembered per device; 48 per page below 1240 px, 48/96/192 from 1240 px; sort `number` ascending. |
| D-F2-14 | Topbar search from 1240 px, `/` shortcut (F2-k). |

## F13 — Riot sync + catalog admin

Every recommendation of the F13 phase spec is accepted (D-F13-1 … D-F13-18), with these precisions:

| ID | Decision |
|---|---|
| D-F13-1 | Post-release daily run at 08:00 Europe/Madrid. |
| D-F13-2 | Monthly run on the 1st of each month at 08:00 Europe/Madrid, every set in `monthly` in one run. |
| D-F13-3 | Release date required when creating a set through the admin API; existing sets without a date behave as `monthly` and are listed on the overview. |
| D-F13-4 | Gallery set codes without an `rbset` row are auto-created as placeholder sets (name = code, no release date) and flagged on the overview. |
| D-F13-5 | A manual run applies the same per-set window rules, processing every requested set at once (all sets when none is given). |
| D-F13-11 | The legacy Jinja button "extract Riot cards" **queues** a manual `riot_sync` job (no second writer, no 30 s request); "refresh Riot sets" stays read only. |
| D-F13-13 | Audit retention one year; the purge job is deferred to batch 2 (follow-up in `state.md`). |
| D-F13-16 | Pending-changes counter on the overview and in the admin navigation; push later (F4-f). |
| D-F13-19 (new) | The pure window calculator lives in F13-c (the engine needs it to decide auto-apply vs approval); F13-d adds the due-set selection, the two timers and the runbook. |
| D-F13-20 (new) | Two timers instead of one: `riftbound-riot-sync-am` (08:00) and `riftbound-riot-sync-pm` (14:00), each passing `--param slot=am|pm`. |
| D-F13-21 (new) | Card keys (`set_id`, `card_id`) are immutable through the admin API; a wrong key is fixed by creating the right card and deleting the wrong one while it is unused. |
| D-F13-22 (new) | The per-set "last sync job" of F13-R4 is replaced by the global last run on the overview and the runs list in `/admin/riot` (finding the last job per set would scan job results). |

## F3 — collection

| ID | Decision |
|---|---|
| D-F3-2 | Batch 1 imports and exports the **RBAPP** format (header `set_id,card_id,name,foil,qty,condition,language,purchase_price,selling,sell_qty,sell_price`) and exports the **Cardmarket** format byte-compatible with today's Jinja export. Other import formats wait for the owner's samples (batch 2). |
| D-F3-3 | Import previews in a table `rbimportpreviews`, kept 30 minutes. |
| D-F3-4 | Cardmarket language list (11 languages); existing free-text values are kept and shown as they are. |
| D-F3-5 | Merge identical lines on add, with `purchase_price` in the key. |
| D-F3-6 | `rbcol_user` stays a username. |
| D-F3-7 | Wishlist and watchlist are separate concepts (both outside batch 1). |
| D-F3-8 | Undo toast 8 s; bulk ≤ 1 000 ids; "select all filtered" beyond 1 000 is a follow-up. |
| D-F3-9 | Playset size in `rbuserprefs.rbprf_playset_size` (`NULL` = 3), range 1-9, through `GET`/`PATCH /me/prefs` (`playset_size`). |
| D-F3-10 | "Keep a playset" stored per user and card name (`rbkeepplayset`); kept copies = Σ (`qty` − `sell_qty`) over every line of that name (all printings, foil and non-foil). |
| D-F3-11 | Legacy `rbcol_selling = 'S'` rows become `'Y'`; the F3-a migration reports how many rows it changed and the PR records the number. |
| D-F3-12 | Yes: every user and card name with a legacy `rbcol_playset` gets "keep a playset" once in the F3-a migration. |

## F4-c — value snapshots

| ID | Decision |
|---|---|
| D-F4-4 | Users without a collection get no row. |
| D-F4-5 | Value = PRC-1 market price of each line (same as the collection screen); lines without a price are counted in `unpriced` and add 0. |
| D-F4-11 (new) | `value_snapshot` runs as its own job kind, queued by a successful `daily_prices` run (F4-R4), and can be queued by hand. The snapshot date is the UTC date of the run (same convention as F4-b). |

## F14 — products

Every recommendation of the F14 phase spec is accepted (D-F14-1 … D-F14-11, D-F14-13), with these
precisions:

| ID | Decision |
|---|---|
| D-F14-6 | Accepted: nullable `rbvsn_products_value` in the F4-c snapshot, written by `value_snapshot` from F14-c on. |
| D-F14-7 | Deferred: there is no dashboard in batch 1. |
| D-F14-12 | Deferred: products are online-only in batch 1 (product.md's offline list is unchanged). |
| D-F14-14 (new) | Nav entry `products`, icon `gift`, placements `top`, `hub`, `more`; labels "Productos" / "Products". |
