# Cardmarket admin and retiring the old web — design notes

Status: **design, owner decisions of 2026-11-06**. Builds on F10-d/g/h of `README.md` (this note orders and
sharpens them) and on F11-e (retire Jinja).

## Owner request (2026-11-06)

1. The old (Jinja) web has no reason to stay: remove it from the project.
2. The admin area is not clear on the Cardmarket side. Missing:
   - a **log** of the daily price load: that it ran, what was loaded, whether **new products** appeared;
   - a **tool to link** our cards and products with Cardmarket's when matching fails, so they stay linked;
   - **unlink** a wrongly linked one, to link it to the right one or, when ours does not exist, **create it**
     (a card in `cards` or a product in `products`) and link it to the Cardmarket item.

## What the admin has today (so the names are clear)

- **Riot** (`/admin/riot`): the sync of the official gallery (cards and sets): run now, schedule (08:00 and
  14:00), history of runs.
- **Changes** (`/admin/riot/changes`): the queue of **differences the sync found** (new or changed cards). Each
  one is approved or rejected; it is a review queue, not a manual editor. Hand corrections of a card are in
  **Cards**.
- **Cardmarket prices have no screen**: the daily job `daily_prices` (06:30, retry 08:00; validates, loads,
  auto-links the clear cases, lists the doubtful ones) is only visible with `flask jobs list`. The only UI to
  link products is the old Jinja page `/riftbound/price/*` (unmatched, map/unmap, mappings browser,
  auto-match, ignored, unmapped expansions, create card/product). **That is why the old web goes last.**

## Decisions

- **Order**: build the React Cardmarket admin first, then delete the old web entirely.
- **Landing**: when the old web goes, `/riftbound/` redirects to the new app (`/riftbound/app/`). The new
  public landing comes later with events (F8).

## Units (one worker, one PR per unit; migrations in their own PR)

| Unit | Content | Notes |
|---|---|---|
| CM-a | **Load log** (API + screen `/admin/cardmarket`): one row per load day with files, rows, status, message, duration, **new products** (set difference of `rbcm_products` between that date and the previous one, computed on read: no migration), unmatched count; "Load now" job and its status (reuses the existing `daily_prices` job kind: no migration; URL overrides would need a new kind and a migration, later if wanted) | F10-d + first part of F10-h. As built (CM-a API): failed loads leave no history row, so a failed day shows only in the status header (job error). **Done**: API (#113) and screen (`feat/cm-a-screen`: header, Load now, days, day detail, recent `daily_prices` jobs so failed runs are listed too) |
| CM-b | **Matching workbench**: unmatched products (search, category, price), suggestions from the auto-match dry run, **link** (with foil N/S), **unlink**, relink in one step, conflicts, ignored add/restore, mappings browser with filters | F10-g/h; port of the legacy endpoints with characterization tests first. **Done**: API (#115) and screen (`feat/cm-b-workbench`: `/admin/cardmarket/matching`, tabs To link, Linked, Conflicts, Ignored, Auto-match with review; link dialog with candidate images and slots; Undo on every write) |
| CM-c | **Create what is missing from a Cardmarket item**: prefilled form to create the card (`rbcards`) or the product (`rbproducts`) and link it in the same action | uses the catalog admin writes of F13. **Done** (`feat/cm-c-create-card`, frontend only): "Create card" on a To link single, on review items with no candidates and in the link dialog; prefilled cards-admin form, `POST /admin/cards` then the link, Undo removes the link only. Products need no creation: `products_refresh` creates every Cardmarket non-single in `rbproducts` with the same id (linked by identity; edits in `/admin/products`) |
| CM-d | **Unmapped expansions**: map a Cardmarket expansion to a set, or create the set | **Done** (`feat/cm-d-expansions-api`): `GET/PUT /admin/cardmarket/expansions[/<id>]`, `DELETE …/<id>/mapping` (create the set as `POST /admin/sets` does, in the same transaction; audited) and the workbench tab Expansions (Map, Change, Unmap with Undo; the unmapped counters link to it) |
| CM-e | Overview counters (last load, unmatched, unmapped expansions) and audit rows for every link/unlink | audit exists (`rbadminaudit`) |

## Retiring the old web (after CM-b/c are in use)

Delete the Jinja routes and templates (`app/routes/domains/*`, auth forms, landing, `app/templates`, legacy
static), keep the JSON API, the SPA host, media and the CLI; `/riftbound/` redirects to the app; classify the
remaining routes in `tests/test_authz_matrix.py`; update `AGENTS.md`, `docs/`; run a last `flask decks
migrate` first (R13 becomes moot: there are no old deck pages to switch off). The legacy price-CSV
generator is already dropped (owner, 2026-10-22).
