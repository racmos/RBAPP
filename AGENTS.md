# Riftbound - Agent Instructions

## Workflow (read first)

This file is the single source of instructions for every AI agent on this repository (Claude Code, gentle-shell, Codex, Gemini, Copilot and others). `CLAUDE.md` only imports it; never put rules in an agent-specific file.

Work arrives as a unit requirement in `docs/requirements/F<n>/F<n>-<x>-<slug>.md` (format: `docs/requirements/TEMPLATE.md`), written by the planner (a Claude Project) from the phase spec `docs/requirements/F<n>/README.md`. The full cycle, roles and rules are in `docs/knowledge/workflow.md`.

- Before changing anything read `docs/knowledge/state.md` (status), `docs/knowledge/conventions.md` (rules) and the requirement's "Read first" list. `docs/knowledge/product.md` holds the owner's binding decisions.
- One phase, or a group of related requirements, = one branch from up-to-date `origin/main` = one PR, with one commit per requirement so a single unit can be reverted. A migration or any change to stored data goes in its own PR (it is deployed with a backup first). Work in a git worktree, never in the deployed checkout (it serves the dev app; see `docs/knowledge/ops-runbook.md`).
- Strict TDD: observe the failing test before the code. Finish with every lane green (`pytest`; `cd frontend && npm run lint && npm run typecheck && npx vitest run && npm run build && npm run check:dist`).
- Update `docs/knowledge/state.md` in the same PR, plus this file and `docs/*.md` when structure, commands, endpoints or conventions change.
- Push, PR creation and merge are the owner's decisions; the owner merges. Deploy to dev only when asked, following `docs/knowledge/ops-runbook.md` and the local `ops.local.md` (git-ignored, never committed).
- A requirement that contradicts the code, `openspec/specs/` or `product.md`: stop and report instead of guessing.

## Project Overview

**Rift Manager** is a web application to manage the Riftbound trading card game:
- Authentication, profiles and roles (user / admin)
- Card sets and individual cards
- Personal collection tracking (quantities, foil, playsets, selling)
- Deck building and deck viewing
- Cardmarket prices (admin tools) and price resolution
- A React single-page app at `/riftbound/app/` (the old Jinja web was retired; `/` redirects to the app until the new landing page of F8)
- A JSON API (`/riftbound/api/v1`) for the React app

## Technology Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.12 |
| Backend | Flask 3.1.0 |
| Database | PostgreSQL (schema `riftbound`); SQLite in memory for the tests |
| ORM | SQLAlchemy 2.0.36 + Flask-SQLAlchemy 3.1.1 (driver: psycopg 3.2.13) |
| Migrations | Alembic 1.20.0 through Flask-Migrate 4.1.0 |
| Auth | Flask-Login 0.6.3 |
| CSRF | Flask-WTF 1.3.0 |
| Rate limits | Flask-Limiter 4.1.1 (in-memory, per worker) |
| Captcha | altcha 2.3.0 (proof of work, vendored widget) |
| Validation | Pydantic 2.10.5 |
| Testing | pytest 8.3.4, pytest-cov 6.0.0 |
| Server | Gunicorn 23.0.0 behind Nginx |
| Frontend | React 19.3.0 + TypeScript 6.0.3 + Vite 8.3.2 in `frontend/` (Node 24, exact pins in `frontend/package.json`); tests with Vitest 5.0.3 |

The exact pins live in `requirements.txt`; if you change one, update this table (a unit that touches the pins re-creates the pin check, see Testing).

## Project Structure

```
riftbound/
├── app/
│   ├── __init__.py          # App factory, extensions (db, migrate, login, csrf, limiter), blueprints
│   ├── errors.py            # Error handlers + wants_json() (JSON or HTML negotiation) + html_error_page() (minimal inline page)
│   ├── security.py          # require_admin (before_request hook of api_admin)
│   ├── db_schema.py         # Schema name + Alembic options shared by the app and migrations/env.py
│   ├── api/                 # JSON API
│   │   ├── error_codes.py   # ErrorCode / DetailCode: machine-readable error `code`s
│   │   ├── responses.py     # ok() / fail() envelopes
│   │   └── v1/              # Blueprint api_v1 at /riftbound/api/v1
│   │       ├── __init__.py
│   │       ├── auth.py      # session, captcha, login, logout, register
│   │       ├── bans.py      # GET /bans (card bans per game mode)
│   │       ├── cards.py       # GET /cards (list; F2-c), GET /cards/<set>/<id> + /prices (detail; F2-d)
│   │       ├── me_products.py # GET/POST /me/products, PATCH/DELETE /me/products/<id> (F14-c)
│   │       ├── locations.py   # /locations CRUD, order, next-code; /collection/<id>/locations assign and move (F16-b)
│   │       ├── decks.py       # /decks CRUD, PUT content (autosave, hard limits), versions, restore, diff (F5-d); text import preview/import, export (F5-e); share link + public deck (F5-g)
│   │       ├── products.py    # GET /products, /products/<id>, /products/<id>/prices (F14-b)
│   │       ├── collection.py  # GET /collection (F3-b) and its writes: POST, PATCH/DELETE /<id>, split, bulk, keep-playset (F3-c)
│   │       ├── me.py        # GET/PATCH /me/prefs (interface preferences), PATCH /me/account (email, password)
│   │       └── meta.py      # health, meta/config
│   ├── schemas/             # Pydantic request models
│   │   ├── admin.py         # AdminSetCreate/Patch, AdminCardCreate/Patch/Query
│   ├── cli/                 # Flask CLI groups
│   │   ├── bans.py          # flask bans list|add|remove (card bans per game mode)
│   │   ├── images.py        # flask images import-legacy (copy the old card images into CARD_IMAGES_DIR)
│   │   ├── jobs.py          # flask jobs enqueue|run-pending|list
│   │   ├── riot.py          # flask riot recheck-pending [--dry-run] (marks stale pending card changes obsolete)
│   │   ├── decks.py         # flask decks migrate [--dry-run] [--strict] (copies rbdecks into decks v2, F5-c)
│   │   ├── schema.py        # flask schema snapshot
│   │   └── users.py         # flask users promote|demote|block|unblock|set-password|list|unlock
│   ├── api/
│   │   └── admin/           # api_admin blueprint: /riftbound/api/v1/admin/*, admin-only
│   │       ├── overview.py  # GET /admin/overview (catalog counters, riot, cardmarket health: CM-e)
│   │       ├── audit.py     # GET /admin/audit (filters, paged, newest first), GET /admin/audit/facets (CM-e)
│   │       ├── cardmarket.py # GET /admin/cardmarket/loads, /loads/<date>, /status, POST /load (CM-a: load log, "Load now")
│   │       ├── cardmarket_matching.py # /admin/cardmarket/unmatched (+ candidates), /links CRUD (link, relink, unlink, conflicts), /ignored, /auto-match/preview|apply, /review (CM-b)
│   │       ├── cardmarket_expansions.py # /admin/cardmarket/expansions list, PUT map (optionally creating the set like POST /admin/sets), DELETE .../mapping (CM-d)
│   │       ├── sets.py      # GET/POST /admin/sets, PATCH/DELETE /admin/sets/<id>
│   │       ├── products.py  # GET /admin/products, PATCH /admin/products/<id> (kind/set locks, hidden), POST .../image (F14-d)
│   │       └── cards.py     # GET/POST /admin/cards, PATCH/DELETE + image per card│   ├── jobs/                # Background job kinds; the package is the single import point (create_app)
│   │   ├── registry.py      # JobKind(name, handler, timeout_seconds), register / get / names, JobFailed
│   │   ├── riot_sync.py     # riot_sync: gallery diff, auto-apply vs approval (1800 s)
│   │   ├── products_refresh.py # products_refresh: product catalog from the non-singles of a load, queued after daily_prices (600 s, F14-a)
│   │   ├── value_snapshot.py # value_snapshot: daily collection value per user, queued after daily_prices (900 s, F4-c)
│   │   ├── daily_prices.py  # daily_prices: Cardmarket load, validation, clear auto-match, review list (1800 s)
│   │   └── heartbeat.py     # heartbeat: diagnostic kind (60 s)
│   ├── models/              # SQLAlchemy models (Rb prefix)
│   │   ├── ban.py           # RbCardBan (rbcardbans): bans by card name and game mode
│   │   ├── card_change.py   # RbCardChange (rbcardchanges): proposed card changes (pending, approved, rejected, obsolete)
│   │   ├── user.py          # User (rbusers)
│   │   ├── set.py           # RbSet (rbset)
│   │   ├── card.py          # RbCard (rbcards)
│   │   ├── collection.py    # RbCollection (rbcollection)
│   │   ├── deck.py          # RbDeck (rbdecks): legacy decks, no longer written (copied to v2 by `flask decks migrate`; F11 drops it)
│   │   ├── deck_v2.py       # RbDeckHead (rbdeckheads), RbDeckVersion (rbdeckversions): decks v2 (F5-c)
│   │   ├── market.py        # RbCardMarket (rbcardmarket)
│   │   ├── cardmarket.py    # Rbcm* models (rbcm_* tables, Cardmarket loader) and RbProducts (rbproducts)
│   │   ├── captcha.py       # RbCaptchaUsed (rbcaptcha_used)
│   │   ├── audit.py         # RbAdminAudit (rbadminaudit): audit trail of admin writes
│   │   ├── job.py           # RbJob (rbjobs): job queue and results, one active job per kind
│   │   ├── user_product.py  # RbUserProduct (rbuserproducts): sealed products a user owns (F14-c)
│   │   ├── playset.py       # RbKeepPlayset (rbkeepplayset): card names a user keeps a playset of (F3-a)
│   │   ├── location.py      # RbLocation (rblocations), RbCollectionLocation (rbcollection_locations): storage locations and copies per location (F16-a)
│   │   ├── wishlist.py      # RbWishlist (rbwishlists), RbWishlistLine (rbwishlistlines), RbWishlistAlert (rbwishlistalerts): wishlists, wanted cards, daily price alerts (F3-f-1)
│   │   ├── import_preview.py # RbImportPreview (rbimportpreviews): parsed import rows for 30 minutes (F3-e)
│   │   ├── snapshot.py      # RbValueSnapshot (rbvaluesnaps): daily collection value per user (F4-c)
│   │   └── prefs.py         # RbUserPrefs (rbuserprefs): interface preferences, NULL = Auto; playset size (F3-a)
│   ├── routes/
│   │   ├── media.py         # media_bp: card images from CARD_IMAGES_DIR at /riftbound/media/cards/
│   │   ├── redirects.py     # legacy_redirects: `/`, `/riftbound/` and the old Jinja URLs -> 302 to the app
│   │   └── spa.py           # spa_bp: serves the React build from FRONTEND_DIST at /riftbound/app/
│   ├── services/            # Business logic, no Flask request objects
│   │   ├── account.py       # update_account: email and/or password of the signed-in user (PATCH /me/account)
│   │   ├── auth.py          # authenticate (lockout), register_user, unlock_user
│   │   ├── audit.py         # record() adds an audit row in the caller's transaction
│   │   ├── audit_log.py     # read-only audit log (CM-e): list_audit (filters, paging), facets; details passed through
│   │   ├── bans.py          # name_key, ban_map, card_bans, ban_info, list_bans, add_ban, remove_ban
│   │   ├── captcha.py       # none / altcha providers, replay store
│   │   ├── cardmarket_log.py # Cardmarket load log computed on read (CM-a): list_loads, load_day, health (status without prices_as_of; the admin overview, CM-e), status, derive_status, unmatched_clauses (the one definition of unmatched), unmatched_count, unmapped_expansions_count (the one definition of unmapped expansions)
│   │   ├── cardmarket_matching.py # matching workbench (CM-b): list_unmatched (suggestions), candidates, link/unlink/relink, list_links (conflicts), ignore list, preview/apply/review over daily_prices.classify_unmapped
│   │   ├── cardmarket_expansions.py # Cardmarket expansions (CM-d): list_expansions (counts of the latest load, mapped set), map_to, unmap
│   │   ├── catalog.py       # card parsing, natural sort, foil eligibility, base printings, card_summary (F2-b)
│   │   ├── card_detail.py   # card detail + price history: printings, related, user lines/decks (F2-d)
│   │   ├── card_list.py     # cards list query: filters, disjunctive facets, sort, pagination (F2-c)
│   │   ├── deck_rules.py    # pure deck rules engine (F5-a): validate (issues + completeness), can_add/can_move, hard_limit_violations, apply_legend/champion, auto_runes, deck_domains, sort_names; shared cases tests/fixtures/deck_rules_cases.json
│   │   ├── deck_migration.py # route_deck (legacy cards -> content v2 by type), plan_migration / report_lines / apply_plan for `flask decks migrate` (F5-c)
│   │   ├── decks.py         # decks v2 of one user (F5-d): list/detail with legality per mode and value, create/update/delete, save_content (hard limits), snapshot, restore, diff; import_preview, import_deck, export_text (F5-e)
│   │   ├── deck_text.py     # common deck text format (F5-e), pure: parse_text, Resolver (id, name_key, legend `Tag, Name`), build_content (warnings), format_text
│   │   ├── deck_share.py    # share / unshare (22-char slug, unique, idempotent), public_deck (read-only, no workbench, owner only when public) (F5-g)
│   ├── catalog_admin.py # set/card lists, create/update/delete, image upload helpers (F13-b)
│   │   ├── collection_import.py # CSV import: preview rows with reason codes, commit add/replace (F3-e)
│   │   ├── collection_export.py # CSV export rows and stream: RBAPP and Cardmarket formats (F3-d)
│   │   ├── collection_read.py # list_collection: groups, lines, prices, P/L, totals, facets (F3-b)
│   │   ├── collection_write.py # add (merge), edit (stale guard), delete, split, bulk, keep playset (F3-c)
│   │   ├── collection_rules.py # kept_copies, playset_size (F3-a)
│   │   ├── locations.py     # locations CRUD, order, lock, suggest_next_code, assign/move/remove copies, take_copies in order, release (F16-a)
│   │   ├── daily_prices.py  # validate_load, classify_unmapped (read-only clear/doubtful decision, CM-b), add_links, match_clear_cases (daily_prices job, F4-b)
│   │   ├── jobs.py          # enqueue, claim_next, expire_stale, run_pending, list_jobs, last_success_today (job runner)
│   │   ├── prefs.py         # get_prefs / update_prefs (interface preferences)
│   │   ├── product_list.py  # products list, detail, price history (F14-b)
│   │   ├── product_prices.py # product_price chain avg7 > trend > low, product_price_summaries (F14-b)
│   │   ├── product_images.py # images_root, product_image_path, product_image_url (PRODUCT_IMAGES_DIR, F14-d)
│   │   ├── product_images.py # images_root, product_image_path, product_image_url (PRODUCT_IMAGES_DIR, F14-d)
│   │   ├── products.py      # kind_for(category), refresh_products(date): rbproducts catalog (F14-a)
│   │   ├── user_products.py # owned products: list with total, add (merge in SQL), edit, delete, products_values (F14-c)
│   │   ├── snapshots.py     # take_snapshots(today): one rbvaluesnaps row per user with a collection (F4-c)
│   │   ├── pricing.py       # resolve_price (+_with_source), batched price_summaries (F2-b)
│   │   ├── card_images.py   # images_root, card_image_path, card_image_url, import_legacy (CARD_IMAGES_DIR)
│   │   ├── cardmarket_loader.py
│   │   ├── cardmarket_matcher.py
│   │   ├── riot_scraper.py    # gallery fetch + parse only; writes go through riot_sync.py
│   │   └── riot_sync.py     # fetch_gallery, window_for, sync (per-set savepoints)
│   ├── schemas/             # Pydantic
│   │   ├── deck_content.py  # DeckContentV2: shape of a v2 deck version (F5-R6), VISIBILITIES (F5-c)
│   │   ├── game_domain.py   # Game enumerations (modes, domains, types, supertypes, rarities) and DECK_RULES (F5-a), the single source for schemas and CHECKs (F2-b; see docs/api.md)
│   │   ├── prefs_domain.py  # Value domains of the interface preferences (schema + model CHECKs)
│   │   ├── validators.py    # Request schemas
│   │   └── validation.py    # @validate_json decorator
│   ├── utils/
│   │   └── clock.py         # utcnow() (patched in tests)
│   └── static/images/cards/ # `.gitkeep` only: default source of `flask images import-legacy` (never served)
├── migrations/              # Alembic
│   ├── env.py
│   ├── versions/            # 0001_baseline ... one file per revision
│   └── legacy_sql/          # Frozen pre-Alembic SQL (reference only)
├── frontend/                # React app (F1); see "Frontend" below
│   ├── package.json         # Exact pins, scripts (dev, build, lint, typecheck, test, check:dist)
│   ├── assets-src/          # Brand and background sources (never shipped)
│   ├── public/              # Committed icons and favicons (generated by `npm run icons`)
│   ├── pwa-options.ts       # vite-plugin-pwa options (manifest, Workbox, self-destroying switch)
│   ├── pwa-assets.config.ts # Icon presets for `npm run icons`
│   ├── scripts/             # brand-trace.mjs, make-bg.mjs, icons.mjs, check-dist.mjs
│   └── src/
│       ├── app/             # Router, route table, providers, bootstrap (wires everything)
│       ├── api/             # Typed fetch client, CSRF token, ApiError, endpoints
│       ├── auth/            # Session query, guards, safeNext, login and register screens
│       ├── i18n/            # English catalog (only language), translateError, catalog check
│       ├── prefs/           # Preferences: bootstrap, resolve, apply, mirror, optimistic sync, provider
│       ├── pwa/             # Update toast, install prompt and iOS dialog (the service worker comes from vite-plugin-pwa)
│       ├── account/         # Interface settings page and its live preview; ProfilePage (/account/profile: username read-only, Email and Password forms over PATCH /me/account)
│       ├── shell/           # AppShell, Topbar, BottomNav, MoreSheet, HomeHub, nav registry, NotFound
│       ├── admin/           # Admin area: AdminLayout + adminNav (one entry per screen), Overview (with the Cardmarket band, CM-e), Sets, Cards, Products, Riot, Changes; admin/audit/ (CM-e): AuditPage (/admin/audit: filters in the URL, table / cards on phones, readable actions, target links, Details JSON) over pure format.ts; admin/cardmarket/ (CM-a): CardmarketPage (/admin/cardmarket: status header from /admin/cardmarket/status with "Load now" + 3 s job polling, load days table from md / cards on phones with "Show more" to 120, recent daily_prices jobs), DayDetail (files of every run, new products, job and result summary), queries, pure format helpers; admin/cardmarket/matching/ (CM-b): MatchingPage (/admin/cardmarket/matching: status counters, tabs To link | Linked | Conflicts | Ignored | Auto-match | Expansions in the URL; the unmapped expansions counter links to Expansions), ToLinkPanel (unmatched + suggestion buttons, Ignore), LinkDialog (candidates with images, slot None/N/S, 409 who-holds-it / relink instead), LinkedPanel (links table, Relink/Unlink; conflicts grouped by slot), IgnoredPanel (Restore), AutoMatchPanel (preview/apply clear cases, review by reason), ExpansionsPanel (CM-d: expansions with counts, "Not mapped only", Map to a set / Change with a set select or "Create a new set…" through `SetEditor`, Unmap, Undo toasts), CreateCardForm (CM-c: create the missing card from a Cardmarket item with the cards-admin fields `CardEditor.tsx::CardFields`, then link it; Undo unlinks only), queries (Undo toasts, refresh of every cardmarket query), pure format helpers
│       ├── products/        # ProductsPage (mobile F14-e, desktop rail/tables/panel F14-f), ProductDetail, line sheet, tiles, params ⇄ URL, queries
│       ├── locations/       # LocationsPage (list F16-c, table/drag/panel F16-d), new and edit sheets with suggested codes, queries (also the line locations the collection uses)
│       ├── decks/           # Decks UI (F5-h): DecksPage (/decks: grid of deck cards from 860 px, one column below; DeckListToolbar over pure deckListParams.ts: search, mode, legality, sort in the URL; DeckCardActions: Open, Duplicate, copy text, share link, delete; New deck, Import), DeckView (/decks/:id: legality, completeness, sections, editing with the rules, autosave; two panes from 960 px with CardBrowser, F5-i), CardBrowser (zone tabs, search, Filter popover with FilterPanel + browserFilters.ts, tile grid that adds through the editor; below 960 px AddCardsSheet opens it per section in a bottom sheet, one zone, filters inline), workspace tabs List | Stats with DeckStats.tsx (tiles, energy curve, power & runes by domain, unit might, keywords) over pure deckStats.ts (F5-i step 4), DeckActions (rename/mode, Save as version, Versions, Export menu to the clipboard: Copy decklist with a read-only fallback, Share deck; delete), DeckVersions (Versions modal: newest first, Current badge, per-version diff against the previous one, Restore with confirmation through `editor.reset`), CardZoom (thumb/magnifier button that opens the full card in a modal), ArtSwitch ("N alt arts" → choose the printing of each copy, `editor.changeArt` over pure `setPrinting`), Guarded (control disabled with its reason), editor.ts + useDeckEditor, issues.ts (issue/limit messages, `decks` namespace), queries
│       ├── decks/rules/     # Deck rules library (F5-b): pure TS port of app/services/deck_rules.py (validate, canAdd/canMove, hard limits, applyLegend/Champion, autoRunes, deckDomains, sortNames); RulesContext from /meta/game; cases.test.ts runs tests/fixtures/deck_rules_cases.json
│       ├── collection/      # CollectionPage (mobile F3-g, desktop table/bulk/panel F3-h), items, LineSheet, AddSheet, filters, params ⇄ URL, queries
│       ├── catalog/         # CardsLayout, card detail route/view, queries, outlet context (F2-f); CatalogPage, params, price history (F2-g/h); CardCombobox + topbar card search (F2-k)
│       ├── components/ui/   # Primitives (Brand, Button, Field, Input, Toast, ...)
│       ├── components/card/ # CardImage, placeholder, pips, rarity, ban badge, price (F2-e)
│       ├── lib/             # breakpoints, contrast, format, background, storage
│       ├── styles/          # Layered tokens, base, background, fonts
│       └── test/            # Vitest setup, MSW server, renderApp, viewport mock, CSS helpers
├── tests/
│   ├── conftest.py          # Fixtures (see Testing)
│   └── test_*.py
├── docs/
│   ├── knowledge/           # Product, architecture, conventions, state, roadmap, workflow, ops runbook
│   ├── requirements/        # Phase specs (F<n>/README.md) and unit requirements for gentle-shell
│   ├── migrations.md        # Migration runbook
│   ├── nginx_config         # Nginx template
│   ├── systemd/             # systemd templates: job runner timer (F4-a), daily load timers (F4-b)
│   └── riftbound.service    # systemd unit
├── openspec/                # Spec-driven development artifacts (SDD)
├── .github/
│   └── workflows/           # ci.yml, security.yml, release.yml
├── config.py                # Settings from environment variables
├── run.py                   # Local entry point (python run.py)
├── wsgi.py                  # WSGI entry point
├── pytest.ini
├── requirements.txt
├── .env.example
└── README.md
```

## Configuration

Settings come only from environment variables (`config.py`). A git-ignored `.env` is read **only** when `RB_ENV=development`.

| Variable | Meaning |
|----------|---------|
| `RB_ENV` | `development`, `testing` or `production` (unset = production) |
| `SECRET_KEY` | 32+ random characters; the app refuses weak or default keys outside development |
| `DATABASE_URL` | `postgresql+psycopg://user:password@host:5432/riftbound` |
| `PRODUCT_IMAGES_DIR` | Absolute path of the product images directory; unset = `<project>/data/product-images` (git-ignored); a relative path stops the app with `ConfigError`. Served at `/riftbound/media/products/<file>` (F14-d) |
| `CARD_IMAGES_DIR` | Absolute path of the card images data directory (`ogn/`, `ogs/`, ...); unset = `<project>/data/card-images` (git-ignored); a relative path stops the app with `ConfigError`. Card images live in `CARD_IMAGES_DIR`, never in git (M-d) |

The rest (cookies, kill switches, lockout, captcha, proxy hops) is documented in `.env.example`. Never commit real values and never write a credential, IP address or hostname into code or docs.

## Conventions

### Database Naming
- Tables: `rbusers`, `rbset`, `rbcards`, `rbcollection`, `rbdecks`, `rbdeckheads`, `rbdeckversions`, `rbcardmarket`, `rbproducts`, `rbcaptcha_used`, `rbuserprefs`, `rbjobs`, `rbcardbans`, `rbadminaudit`, `rbcardchanges`, `rbkeepplayset`, `rbvaluesnaps`, `rbimportpreviews`, `rbuserproducts`, `rblocations`, `rbcollection_locations`, `rbwishlists`, `rbwishlistlines`, `rbwishlistalerts`, and the Cardmarket loader tables `rbcm_categories`, `rbcm_expansions`, `rbcm_ignored`, `rbcm_load_history`, `rbcm_price`, `rbcm_product_card_map`, `rbcm_products`
- Schema: `riftbound`
- Model classes use the `Rb` prefix (the user model is `User`, table `rbusers`)
- `rbproducts` (F14-a): keyed by `rbpdt_id_product` (`rbpdt_id_set` nullable), with `rbpdt_category`, `rbpdt_kind` (CHECK `rbproducts_kind_chk`), `rbpdt_kind_locked`, `rbpdt_set_locked`, `rbpdt_hidden`, `rbpdt_listed`, `rbpdt_updated_at`; only `rbpdt_type = 'nonsingle'` rows are products; `products_refresh` never deletes (a product that leaves the file gets `rbpdt_listed = false`)
- `rbcollection` (F3-a): `rbcol_sell_qty` (0..quantity) is the number of copies for sale and `rbcol_purchase_price` the optional unit purchase price; `rbcol_selling` is only `Y` or `N`; **`rbcol_playset` is deprecated** (no longer read since the Jinja web was retired; dropped in F11). Playset size per user is `rbuserprefs.rbprf_playset_size` (NULL = 3) and the "keep a playset" marks are `rbkeepplayset` (one row per user and `name_key`)
- `rbwishlists` / `rbwishlistlines` / `rbwishlistalerts` (F3-f-1, migration `0026_wishlists`): wishlists of a user (`rbwls_user_id` → `rbusers.id`, name unique per user ignoring case, position, one default per user through a partial unique index), their wanted cards (`name_key` + optional printing, foil `any`/`N`/`S`, qty 1..99, optional max price; one line per target and list through an expression unique index over `coalesce(set, '*')`, `coalesce(card, '*')`) and the daily price alerts (one per user, target and price date; kept when a list is deleted). Design: `docs/requirements/F3/F3-f-wishlists-design.md`
- `rbdeckheads` / `rbdeckversions` (F5-c, migration `0025_decks_v2`): decks v2. A head (`rbdkh_user_id` → `rbusers.id`, name unique per user, mode, visibility, share slug, current version, `rbdkh_legacy_name`) has versions (`rbdkv_seq` unique per deck, `rbdkv_content` = content v2 validated by `app/schemas/deck_content.py`, `rbdkv_legacy_id` = the `rbdecks.id` it was copied from). `flask decks migrate [--dry-run] [--strict]` copies the legacy decks (dry run first, see `docs/knowledge/ops-runbook.md` → "Decks v2 migration"); `rbdecks` is no longer written since the Jinja deck pages were retired (F11 drops it)

### Column Naming
- snake_case with the table prefix: `rbcar_name`, `rbcol_quantity`, `rbdck_snapshot`
- `rbusers` is the exception: `username`, `email`, `is_admin`, `is_blocked`, ...
- `rbcol_quantity` is an integer (1..9999); never store numbers as text.

### URL Routes
- Every route uses the `/riftbound` prefix (Nginx reverse proxy); `/` only redirects to the app (the F8 landing page will live there).
- The API v1 uses the envelope below.

### Blueprints
`media_bp`, `legacy_redirects`, `spa_bp`, `api_v1` (JSON API) and `api_admin` (admin JSON API). The Jinja web (landing, dashboard, auth forms, sets, cards, collection, decks, price tools, profile, templates, static assets) was retired in PR 3/3 of its retirement.

### Old URLs (`legacy_redirects`)
`app/routes/redirects.py`, public, GET/HEAD only (POST is a 405), never touches the session. 302 (not 301: the landing returns at `/` in F8): `/`, `/riftbound`, `/riftbound/` and `/riftbound/set` → `/riftbound/app/`; `/riftbound/login` → `/riftbound/app/login` (keeps `next` when it is a safe `/riftbound/` path, same checks as `auth/safeNext.ts`); `/riftbound/register` → `/riftbound/app/register`; `/riftbound/card` → `/riftbound/app/cards`; `/riftbound/collection` → `/riftbound/app/collection`; `/riftbound/deck` and `/riftbound/deck/view/<any>` → `/riftbound/app/decks`; `/riftbound/profile` → `/riftbound/app/account/profile`; `/riftbound/price` → `/riftbound/app/admin/cardmarket`. Registered before `spa_bp`.

### SPA hosting (`spa_bp`)
`app/routes/spa.py` serves the frontend build (`FRONTEND_DIST`, default `frontend/dist`, read per request) at `/riftbound/app/`. Public, never touches the session, so no `Set-Cookie`. `assets/*` are immutable; everything else is `no-cache`. A path without a file extension gets `index.html`; a missing file with an extension is a real 404; no build is a 503 (JSON for JSON clients, a minimal inline page otherwise). The `index.html` responses carry `Content-Security-Policy-Report-Only` (`SPA_CSP=report-only`, the default, or `off`; any other value stops the app with `ConfigError`); no other response gets a CSP. It is registered after `legacy_redirects`; Tests get a temporary dist from the `spa_dist` / `spa_app` fixtures, no Node needed. See `docs/frontend.md`.

### Card images (`media_bp`)
Card images live in `CARD_IMAGES_DIR`, never in git (`/data/` is git-ignored; `app/static/images/cards/` keeps only `.gitkeep`). `app/services/card_images.py` is the only module that knows the directory: `images_root()`, `card_image_path(image, set_id=None)` (every write: admin upload, Riot scraper) and `card_image_url(image, set_id=None)`, which `RbCard.image_src` returns: `/riftbound/media/cards/<folder>/<image>`. `app/routes/media.py` serves it (endpoint `media.card_image`, public): the folder must be letters and digits and the file a plain name, otherwise 404, as are missing files, folders and symlinks resolving outside the root; `Cache-Control: public, max-age=604800`; it never touches the session (no `Set-Cookie`; its 404 is a minimal answer of its own). The app has no static route: `/riftbound/static/...` is a 404. `flask images import-legacy [--source PATH]` copies `<folder>/<file>` images (default source `app/static/images/cards`) into `CARD_IMAGES_DIR`, never overwriting (`docs/knowledge/ops-runbook.md` → "Card images"). Tests use the `card_images_dir` fixture (a temporary `CARD_IMAGES_DIR`) and never touch the real images.

## Roles and Authorization

Every URL rule is **public (P)**, **authenticated (U)** or **admin (A)**. `tests/test_authz_matrix.py` lists them all and fails, naming the rule, when a new route is not classified: add it there.

- Admin routes live in the `api_admin` blueprint, guarded as a whole by `before_request(require_admin)` (`app/security.py`). Anonymous callers get a JSON 401, plain users 403.
- `is_admin` and `is_blocked` are changed only by the CLI (`flask users promote|demote|block|unblock <username>`), never by request input. A blocked user is rejected exactly like a wrong password.
- Card bans (`rbcardbans`) are changed only by the CLI (`flask bans add|remove`) until the F10 admin UI; signed-in users read them with `GET /bans`.
- Admin writes record one `rbadminaudit` row in the same transaction (`app/services/audit.py`); admins read the catalog counters with `GET /admin/overview`.
- Never trust ids from the client: deck and collection queries are scoped to the logged-in user.
- Public (P) API endpoints: `GET /health`, `/meta/config`, `/meta/game`, `/auth/session`, `/auth/captcha`, `POST /auth/login`, `/auth/register` and `GET /public/decks/<slug>` (F5-g: the read-only deck behind a share link; never touches the session, `Cache-Control: no-store`, 60/minute per IP, owner username only when the deck is public, no workbench). Everything else under `/riftbound/api/v1` is U or A.

## CSRF, Sessions and Login Protection

- Every `POST`/`PUT`/`PATCH`/`DELETE` needs a valid token in the `X-CSRFToken` header or the `csrf_token` form field. There are no exemptions, API included. `GET /riftbound/api/v1/auth/session` returns a token for API clients.
- Logout is `POST /auth/logout` only.
- Session cookies are HttpOnly, SameSite=Lax and Secure in production.
- Login: 5th consecutive failure locks the account 15 minutes, doubling up to 24 hours; a locked login answers 429 with `Retry-After`. Unlock with `flask users unlock <username>`. Login is limited to 10/minute and 50/hour per IP, register to 5/hour.
- Registration uses an ALTCHA proof of work (`CAPTCHA_PROVIDER`); solved challenges are stored in `rbcaptcha_used` so they cannot be replayed.
- Kill switches (rollback only): `WTF_CSRF_ENABLED`, `RATELIMIT_ENABLED`, `CAPTCHA_PROVIDER=none`, `SPA_CSP=off`.

## JSON vs HTML

`wants_json()` in `app/errors.py` decides: JSON when the path is under `/riftbound/api/`, or the body is JSON, or `Accept` prefers `application/json` over `text/html` (a bare `*/*` counts as JSON). A request with no `Accept` header is HTML. Errors, 401 (Flask-Login) and CSRF failures follow it. Since the Jinja web was retired the only HTML the backend writes is the redirects and one inline error page (`html_error_page`: status, message, a "Back to the app" link; escaped, no assets, no script, no session cookie; the 429 keeps `Retry-After`). An anonymous HTML request to a protected non-API page is redirected to `/riftbound/app/login?next=<path and query>`.

## API v1

Prefix `/riftbound/api/v1`: `GET /health`, `GET /meta/config`, `GET /auth/session`, `GET /auth/captcha`, `POST /auth/login`, `POST /auth/logout`, `POST /auth/register`, `GET /me/prefs`, `PATCH /me/prefs`, `PATCH /me/account`, `GET /bans`, `GET /meta/game`, `GET /cards`, `GET /collection`, `POST /collection`, `PATCH`/`DELETE /collection/<id>`, `POST /collection/<id>/split`, `POST /collection/bulk`, `POST /collection/keep-playset`, `GET /products`, `GET /products/<id>`, `GET /products/<id>/prices`, `GET`/`POST /me/products`, `PATCH`/`DELETE /me/products/<id>`, `GET /collection/export`, `POST /collection/import/preview`, `POST /collection/import/commit`. Decks (F5-d): `GET`/`POST /decks`, `GET`/`PATCH`/`DELETE /decks/<id>`, `PUT /decks/<id>/content`, `GET`/`POST /decks/<id>/versions`, `GET /decks/<id>/versions/<seq>`, `POST /decks/<id>/versions/<seq>/restore`, `GET /decks/<id>/diff?a=&b=`, `POST /decks/<id>/duplicate` (copy of the current content into a new private deck, `(copy)` name); text import/export (F5-e): `POST /decks/import/preview`, `POST /decks/import`, `GET /decks/<id>/export?format=text`; sharing (F5-g): `POST`/`DELETE /decks/<id>/share` (U), `GET /public/decks/<slug>` (P). Locations (F16-b): `GET`/`POST /locations`, `GET /locations/next-code`, `PATCH`/`DELETE /locations/<id>`, `PUT /locations/order`, `GET`/`PUT /collection/<id>/locations`, `POST /collection/<id>/locations/move`. Admin prefix `/riftbound/api/v1/admin` (A): `GET /admin/overview`, `GET/POST /admin/sets`, `PATCH/DELETE /admin/sets/<id>`, `GET/POST /admin/cards`, `PATCH/DELETE /admin/cards/<set>/<id>` and `POST .../image`, `POST /admin/riot/sync`, `GET /admin/jobs`, `GET /admin/jobs/<id>`, `GET /admin/products`, `PATCH /admin/products/<id>`, `POST /admin/products/<id>/image`, `GET /admin/riot/changes`, `POST .../changes/<id>/approve|reject`, `POST .../changes/bulk`, and the Cardmarket load log (CM-a): `GET /admin/cardmarket/loads`, `GET /admin/cardmarket/loads/<date>`, `GET /admin/cardmarket/status`, `POST /admin/cardmarket/load` (queues `daily_prices`; 409 `job_running`), and the Cardmarket matching workbench (CM-b): `GET /admin/cardmarket/unmatched`, `GET /admin/cardmarket/unmatched/<id>/candidates`, `GET`/`POST /admin/cardmarket/links`, `PUT`/`DELETE /admin/cardmarket/links/<id>` (relink in one transaction / unlink; 409 `already_exists` when linked or the slot is taken; products are linked by Cardmarket id), `GET`/`POST /admin/cardmarket/ignored`, `DELETE /admin/cardmarket/ignored/<id>`, `POST /admin/cardmarket/auto-match/preview|apply`, `GET /admin/cardmarket/review`, and the Cardmarket expansions (CM-d): `GET /admin/cardmarket/expansions` (`?unmapped=true`), `PUT /admin/cardmarket/expansions/<id>` (`{set_id}` or `{set_id, create_set}`: creates the set as `POST /admin/sets` does, in the same transaction; returns `previous`), `DELETE /admin/cardmarket/expansions/<id>/mapping`, and the audit log (CM-e): `GET /admin/audit` (`actor`, `action`, `target_type`, `target_id`, `from`, `to`, `page`, `per_page` 50/100/200; newest first) and `GET /admin/audit/facets`; `GET /admin/overview` also carries `cardmarket {last_load, loaded_today, job_status, unmatched, unmapped_expansions}` (see `docs/api.md`).

- `GET /auth/session` returns `{authenticated, csrf_token}` for anonymous callers and `{authenticated, user, prefs, csrf_token}` when signed in. `prefs` always has the six keys `lang`, `density`, `accent`, `bg_intensity`, `collection_view`, `playset_size` (F3-c; `null` = 3 copies); `null` means Auto; the SPA is English-only and ignores `lang` (S21) (a user without a row gets five `null`s and no row is created).
- `POST /auth/login` takes `{username, password, remember?}`. `remember` is a strict boolean (default `false`); `true` also issues a 30-day `remember_token` cookie (`REMEMBER_COOKIE_DURATION`, absolute expiry). Logout expires it, and a blocked user stays anonymous.
- `GET`/`PATCH /me/prefs` (`app/api/v1/me.py`): a key that is absent stays unchanged, `null` resets it to Auto, an invalid value is a 400 and nothing is stored (all-or-nothing), unknown keys are ignored. Domains live in `app/schemas/prefs_domain.py` (shared by the schema and the model CHECKs). Logic is in `app/services/prefs.py`.
- `PATCH /me/account` (`app/api/v1/me.py`, U, logic `app/services/account.py`, `docs/api.md` → "PATCH /me/account"): `{email?, password?, current_password?}` (at least one of email/password); a new password needs `current_password` (400 `current_password_incorrect` when wrong, nothing written), an email-only change does not; 409 `email_taken` (ignoring case); 10 calls/hour per IP (429 `rate_limited`); returns `{user}` and keeps the session. The React profile page `/account/profile` uses it (nav `profile` is `spa`).
- `GET /bans` (`app/api/v1/bans.py`, U) returns `{items: [{name, mode, since, reason, printings: [{set_id, card_id}]}]}` ordered by mode, then name; optional `?mode=1v1|2v2` (any other value is a 400 `validation_error`). A ban covers every printing of a card name (`name_key` in `app/services/bans.py`); modes come from `app/schemas/game_domain.py`. Bans are managed with `flask bans list [--mode M]`, `flask bans add NAME --mode 1v1|2v2|all [--since YYYY-MM-DD] [--reason TEXT] [--force]` and `flask bans remove NAME --mode 1v1|2v2|all`. The legacy `rbcar_banned` column is not a source (F11 drops it).
- `GET /cards/<set_id>/<card_id>` (`api_v1.get_card`, U) returns `CardDetail` (summary + ability, set, price_detail, printings/related `CardMini`, ban_info, my_lines, in_decks); `GET …/prices` (`api_v1.get_card_prices`, U) returns `{range, currency: EUR, foilable, product_id, points}` (`docs/api.md` → "GET /cards/<set>/<id>"). At most 10/4 SQL statements; detail p95 123 ms on dev (6 printings).
- `GET /cards` (`app/api/v1/cards.py`, U) returns `{data: {items: [CardSummary]}, meta: {page, per_page, total, pages, facets, price_as_of}}` (`docs/api.md` → "GET /cards"): free-text `q`/`text`, 7 repeated facet params, numeric/price ranges, `owned`, `banned_in`, `base_only`, 9 sort keys with nulls-last and natural tiebreak; disjunctive facets in canonical order; at most 12 SQL statements; prices for all matches only with price sort/bounds, else the page only. Query validation via `@validate_query` (`CardListQuery`); same 400 body as `validate_json` with message "Invalid query parameters".
- Collection import (F3-e, `docs/api.md` → "Collection import"): `POST /collection/import/preview` parses an RBAPP CSV (2 MB, 10 000 rows) into rows with `status` and `reason_codes` and stores them 30 minutes; `POST /collection/import/commit` adds them or replaces the printings in the file, all or nothing. New codes `import_expired` (410) and `import_format_unknown` (400).
- Decks v2 (F5-d, `app/api/v1/decks.py`, U, `docs/api.md` → "Decks (F5-d)"): only the owner sees a deck (another user's id or an unknown id/seq is a 404 on every route). `GET /decks` lists `{legend, champion, domains, counts, value, legal, issues}` per deck (value excludes the workbench; 9 SQL statements whatever the number of decks); `PUT /decks/<id>/content` autosaves the current version, refuses hard limits with 400 `deck_limit_exceeded` `params {rule, max, name?}` and unknown cards with `validation_error`; soft rules come back as `legality` (both modes, bans read on every request). `POST …/versions` and `…/restore` always add a new current version; `diff` compares two versions per zone and printing.
- Deck sharing (F5-g, `app/services/deck_share.py`, `docs/api.md` → "Deck sharing (F5-g)"): `POST /decks/<id>/share` (U) → `{slug, url}` (22 url-safe random chars, unique, idempotent; `url` from the request host + `/riftbound/app/d/<slug>`), `DELETE …/share` (U) → `{share: null}`, the old URL 404s at once and re-sharing draws a new slug; every `DeckHead` carries `share: {slug, url} | null`. `GET /public/decks/<slug>` (`api_v1.public_deck`, **P**, `@limiter.limit('60 per minute')`, `Cache-Control: no-store`, no `Set-Cookie`): `{name, mode, visibility, owner: {username} | null (only when public), updated_at, content, cards, unknown_cards, domains, counts, value, value_unpriced, legality}` without the workbench, `owned_total` null, never ids, email, versions, notes or slugs; unknown, revoked and malformed slugs give the same 404; 7 SQL statements.
- Deck text import/export (F5-e, `app/services/deck_text.py`, U, `docs/api.md` → "Deck import/export (F5-e)"): one format, the common text every deck site exports (`Legend:`, `Champion:`, `MainDeck:`, `Battlefields:`, `Rune Pool:`, `Sideboard:`, `N Name` lines); `format` `auto|text`, else 400 `import_format_unknown`; text ≤ 64 KB and 2000 lines. The import always loads: unknown or ambiguous names are left out with a warning, wrong-block cards stay in their block (`wrong_zone`), hard limits are stored as is (`hard_limit` warnings; `PUT …/content` refuses them until fixed). The preview writes nothing; the export keeps the content order and excludes the workbench.
- Products admin (F14-d, `app/api/admin/products.py`, A, `docs/api.md` → "Products (F14-d)"): `PATCH` of `kind` or `set_id` locks the value so `products_refresh` leaves it alone (`kind: null` / `set_id: "auto"` unlock and recompute); `hidden` removes the product from users (owners still see it); `POST .../image` (2 MB, magic bytes) stores `<id>.<ext>` in `PRODUCT_IMAGES_DIR`, served by the public `media.product_image` route. Every write is audited (`product.update`, `product.image`).
- Owned products (F14-c, `app/api/v1/me_products.py`, U, `docs/api.md` → "Owned products"): `GET /me/products` returns the caller's product lines with a `total {value, lines, qty, unpriced}`; POST merges the same product and purchase price in SQL; PATCH/DELETE of an id that is not the caller's is a 404. **The products total is never part of the collection value**: no collection endpoint or F3 field changed, and `rbvaluesnaps.rbvsn_products_value` is a separate column (users who own only products get a snapshot row with the cards at 0).
- Products (F14-b, `app/api/v1/products.py`, U, `docs/api.md` → "GET /products"): `GET /products` lists `ProductSummary` (`{id, name, kind, category, set_id, image_src, listed, price {value, source, change_7d_pct, change_30d_pct, as_of} | null, owned_qty}`; contract, additive only) with `q`, `kind[]`, `set[]`, `listed`, 4 sorts (nulls last), disjunctive facets `{kind, set}`, `per_page` 24-96; `GET /products/<id>` adds `description`, latest price `columns` and `lines`; `GET /products/<id>/prices?range=` gives the history. The price is the first non-zero of `avg7`, `trend`, `low` (never foil). Only non-single, non-hidden products; `owned_qty` is 0 until F14-c.
- `GET /collection/export` (`app/api/v1/collection.py`, U, F3-d, `docs/api.md` → "GET /collection/export"): CSV download, `format=rbapp|cardmarket` (default rbapp) plus the list filters and `only_selling`; UTF-8 BOM, streamed, `X-Rows-Exported`; the Cardmarket file is byte-identical to the old Jinja export (golden bytes frozen in `tests/fixtures/collection_export_cardmarket_golden.csv`), text cells starting with `=+-@` get a leading `'`.
- Collection writes (F3-c, `app/api/v1/collection.py`, U, `docs/api.md` → "Collection writes"): `POST /collection` merges identical lines, `PATCH /collection/<id>` guards with `if_updated_at` (409 `stale_line`), `DELETE` returns the line so it can be posted back, `split`, `bulk` (all or nothing) and `keep-playset`; quantities that add up change in SQL; ids that are not the user's are a 404. New codes `foil_not_allowed`, `insufficient_quantity`, `stale_line`. Bulk `set.location_id` (F16-x): absent keeps every line's locations, an id puts all the copies of each line there, `null` unassigns them; a locked location that would change is a 409 `location_locked` with `params.codes` and nothing changes.
- `GET /collection` (`app/api/v1/collection.py`, U, F3-b) returns `{data: {items: [CollectionGroup]}, meta: {page, per_page, total_groups, pages, totals, facets, price_as_of, playset_size}}` (`docs/api.md` → "GET /collection"): groups per printing and foil with their lines, market value and profit/loss, the playset flag, 9 sort keys, line and card filters, disjunctive facets; at most 10 SQL statements. `CollectionLine` and `CollectionGroup` are contracts (additive changes only).
- `GET /meta/game` (`app/api/v1/meta.py`, P) returns a `GameMeta` (`docs/api.md` → "Data shapes"): modes, domains/types/supertypes/rarities (S1 tuples plus unknown data values), every set with `card_count`, price freshness (`updated_on` from `rbcm_price`, null when empty), `rules: {deck: DECK_RULES}` (F5-a; other keys reserved for F15). Anonymous 200, `Cache-Control: no-cache`. Card objects use `CardSummary` from `app/services/catalog.py::card_summary` (batched prices via `price_summaries`, at most two SQL statements).

```json
{"success": true, "data": {}, "meta": {}}
{"success": false, "error": "Validation Error", "message": "Invalid request data", "details": [{"field": "password", "message": "...", "type": "..."}]}
```

Errors may also carry a machine-readable `code` and `params` (`{"code": "locked", "params": {"retry_after": 30}}`); `message` is always the fallback and codeless errors keep the F0 shape. The codes are the `ErrorCode` values of `app/api/error_codes.py`: `invalid_credentials`, `locked`, `rate_limited`, `username_taken`, `email_taken`, `current_password_incorrect`, `captcha_failed`, `csrf_invalid`, `unauthenticated`, `validation_error`, `bad_request` (unreadable body on a `@validate_json` endpoint), `internal_error` (unexpected failure; no endpoint has used it since the Jinja web was retired). Each item of `details` keeps `field`, `message`, `type` and adds `code` (`required`, `too_short`, `too_long`, `invalid_format`, `invalid_value`, `out_of_range`) and, when it applies, `params` (`{"min": 8}`). The codes are additive and also appear on the CSRF and 429 handlers and the 401 handler. A new code needs the enum value, the English frontend catalog and the catalog test (`tests/test_error_catalogs.py`). Unreadable `@validate_json` bodies go through `unexpected_failure()` (`app/errors.py`): a clear `message` and `code`, the traceback in the server log, and the exception text only under `detail` for a signed-in admin.

Use `ok()` / `fail()` from `app/api/responses.py`. Error names: `Validation Error`, `Unauthorized`, `Forbidden`, `Not Found`, `Method Not Allowed`, `Conflict`, `Captcha Error`, `CSRF Error`, `Too Many Requests`, `Service Unavailable`, `Internal Server Error`. 500 responses never include exception text.

## Development Guidelines

### Before Writing Code
1. Read the existing patterns in `app/api/` and `app/services/`
2. Check the schemas in `app/schemas/validators.py`
3. Check the models in `app/models/` for the data structure
4. Check `openspec/` for the spec of the change you are working on

### Code Style
- PEP 8, type hints where useful
- Keep routes thin: put logic in `app/services/`
- Use `db.session.commit()` after database operations
- Preserve each file's line endings (some files are CRLF)

### Request Validation
Every endpoint that receives JSON uses `@validate_json`:
```python
from app.schemas.validators import LocationCreate
from app.schemas.validation import validate_json

@api_v1.post('/locations')
@login_required
@validate_json(LocationCreate)
def create_location():
    data = request.validated_data  # Validated Pydantic model
    ...
```

### Database Changes (Alembic)
The database is built only by migrations (`db.create_all()` is used by the tests alone).
```bash
flask db migrate -m "describe the change"   # autogenerate, then READ the file
flask db upgrade                             # apply
flask db check                               # must report no drift
flask db downgrade -1                        # every revision must be reversible
```
Revisions live in `migrations/versions/`. Change the model and the revision together; the unit adds a round-trip and drift test for its revision (see Testing). Back up before upgrading a real database; see `docs/migrations.md`.

### Testing
**Test policy (since 2026-10-22, unit M-a).** The pre-existing suites were removed. Only
`tests/test_authz_matrix.py` (every URL rule classified P/U/A) and the startup smoke tests
(`tests/test_smoke.py`, `frontend/src/app/smoke.test.tsx`) remain. Strict TDD still applies: every
unit writes the tests for the behaviour it adds or changes. When a unit touches an area whose old
guard was removed, it re-creates that guard in its smallest form: a migration → a round-trip and
model/schema drift test for that revision (`tests/migration_helpers.py`); new UI strings → the English
catalog test (`frontend/src/i18n/catalogCheck.test.ts`); a new error code → the backend/frontend catalog test; a new pinned
version → the pin check. The SPA never links to a Jinja page (`frontend/src/test/no-legacy-links.test.ts`). The last
commit with the old suites is `902047c6579e5ee670e1fb4b103a941159b85c00`; recover any file with `git show 902047c6579e5ee670e1fb4b103a941159b85c00:<path>`.

Strict TDD: write the failing test first, then the code.
```bash
pip install -r requirements.txt
pytest                                    # SQLite, no setup
pytest --cov=app --cov-report=term
TEST_POSTGRES_URL=postgresql+psycopg://user:password@localhost:5432/riftbound_test pytest -m postgres
```
- `tests/conftest.py` sets `RB_ENV=testing`; the default `app` has CSRF, rate limits and captcha **off**.
- Fixtures: `make_user`, `login_as`, `authenticated_client`, `admin_client`, `other_user_client`, `csrf_app`, `limited_app`, `altcha_app`, `frozen_clock`, `migration_app`, `pg_url`, `spa_dist`, `spa_app`, `card_images_dir`.
- `login_as` and the logged-in client fixtures sign in through `POST /auth/login` with the token of `GET /auth/session`, so they work with `csrf_app` in any order.
- The login protections (lockout, blocked user, rate limits, remember cookie, captcha replay, CSRF on every unsafe rule) are guarded through the JSON API by `tests/test_api_auth_guards.py`; the old URLs by `tests/test_legacy_redirects.py`.
- PostgreSQL-marked tests (none today) need a database whose name contains `test`; a unit that adds them re-adds the `pytest -m postgres` CI step (PostgreSQL 18).
- Nothing in the tests may reach the internet.

### Security
- Passwords are hashed with Werkzeug's `generate_password_hash`; minimum 8 characters.
- All routes except the old-URL redirects, the SPA shell, the media files and the public API endpoints require login.
- Secrets only through environment variables.
- File uploads and image paths go through `app/services/card_images.py`: `card_image_path(image, set_id)` (rooted at `CARD_IMAGES_DIR`), never the static folder or the working directory.
- Cardmarket URLs must be on the allow-list (`CARDMARKET_ALLOWED_HOSTS`).

## Database Operations

```python
# Query with filters
cards = RbCard.query.filter(RbCard.rbcar_name.ilike(f'%{search}%')).all()

# Pagination
pagination = query.paginate(page=page, per_page=per_page, error_out=False)

# Join query
query = db.session.query(RbCollection, RbCard).join(
    RbCard,
    (RbCollection.rbcol_rbset_id == RbCard.rbcar_rbset_id) &
    (RbCollection.rbcol_rbcar_id == RbCard.rbcar_id)
)
```

## Running

```bash
python run.py                    # http://127.0.0.1:5000/riftbound (loopback, debug off)
```

Production (systemd unit in `docs/riftbound.service`, Nginx template in `docs/nginx_config`):
```bash
gunicorn --workers 3 --bind 0.0.0.0:8000 run:app
```
Firewall port 8000 so only the Nginx host reaches it. ProxyFix trusts exactly one proxy hop (`PROXY_FIX_X_*=1`); the proxy must send `Host`, `X-Forwarded-For` and `X-Forwarded-Proto`, and must not strip `Referer` (the CSRF check needs it over HTTPS).

Background jobs (table `rbjobs`): `riftbound-jobs.timer` starts `flask jobs run-pending` every minute under `flock -n`; kinds: `heartbeat` (diagnostic), `daily_prices` (daily Cardmarket load at 06:30 Europe/Madrid, retried at 08:00 with `--unless-succeeded-today` when it did not succeed), `value_snapshot` (daily collection value per user in `rbvaluesnaps`) and `products_refresh` (product catalog in `rbproducts`; both queued by `daily_prices` as its last steps on success) and `riot_sync` (gallery sync: `riftbound-riot-sync-am.timer` at 08:00 and `-pm.timer` at 14:00 Europe/Madrid queue `trigger=schedule` + `slot`; exit 1 when a sync is active is the normal skip via `SuccessExitStatus=1`) (templates in `docs/systemd/`, install and rollback in `docs/knowledge/ops-runbook.md` → "Scheduled jobs").
```bash
flask jobs enqueue <kind> [--param key=value]...   # one queued or running job per kind
flask jobs enqueue <kind> --unless-succeeded-today  # skip (exit 0) when a <kind> job succeeded today (UTC)
flask jobs run-pending                             # expire stale jobs, run the queued ones (exit 0)
flask jobs list [--limit N]                        # newest first, default 20
```

## Error Handling

HTTP errors are handled in `app/errors.py`: 400, 401, 403, 404, 405, 429, 500 and CSRF failures. Browsers get an HTML page, JSON clients get:
```json
{
  "success": false,
  "error": "Error Type",
  "message": "Description"
}
```

## Common Tasks

### Adding a New Model
1. Create a file in `app/models/` with `__tablename__` and `{"schema": "riftbound"}`
2. Import it in `app/models/__init__.py`
3. `flask db migrate`, review, `flask db upgrade`, `flask db check`
4. Add a route or service and its tests

### Adding a New Route
1. Add it to the domain file in `app/api/v1/` (or `app/api/admin/` when it is admin-only); logic goes in `app/services/`
2. Use `@login_required` (the admin blueprint is guarded as a whole) and `@validate_json(schema)`
3. Classify it in `tests/test_authz_matrix.py`
4. Document it in `docs/api.md`; screens live in the React app (`frontend/`)

### Adding Request Validation
1. Define the schema in `app/schemas/validators.py`
2. Use `@validate_json(SchemaClass)`
3. Read `request.validated_data`

### Adding a Job Kind
1. A module in `app/jobs/` with `handler(params: dict) -> dict` that calls `register(JobKind(name, handler, timeout_seconds))`; import it in `app/jobs/__init__.py`; raise `JobFailed(message)` for an expected failure (the message is stored without the class name)
2. A migration that extends the `ck_rbjobs_kind` CHECK, and `JOB_KINDS` in `app/models/job.py`
3. Tests through `app.services.jobs` (`run_pending()`) and the runbook entry in `docs/knowledge/ops-runbook.md` → "Scheduled jobs"

## Troubleshooting

- **App does not start**: the error names the missing or weak variable (`SECRET_KEY`, `DATABASE_URL`); check `.env.example`.
- **`flask db check` reports drift**: the model and the migrations disagree; fix one of them.
- **POST returns 400 "CSRF"**: the request has no token, or Nginx strips `Referer` / does not send `X-Forwarded-Proto`.
- **Locked out**: `flask users unlock <username>`.

## Frontend

The React app lives in `frontend/` (Node 24, see `.nvmrc`). Work there with `npm`:

| Command | What it does |
|---------|--------------|
| `npm ci` | Install the exact versions of `package-lock.json` |
| `npm run dev` | Vite dev server; proxies `/riftbound/api` to Flask |
| `npm run lint` / `typecheck` | ESLint (folder boundaries, a11y) plus Prettier check / `tsc -b` |
| `npx vitest run` | Unit and component tests (strict TDD: test first) |
| `npm run build` then `npm run check:dist` | Production build in `frontend/dist` and its checks (manifest, icons, service worker, altcha chunking) |
| `npm run icons` | Regenerate the committed icons in `frontend/public/` from the brand mark |

Conventions: dependencies are pinned without `^` or `~` (`frontend/.npmrc`); CSS is layered (`@layer reset, tokens, base, layout, components, utilities`) and every `*.module.css` wraps its rules in `@layer components`; `@media` widths come only from `src/lib/breakpoints.ts`; the background never brightens the map and body text keeps at least 4.5:1 contrast over it (`src/lib/background.ts`).

App shell and preferences (unit e): signed-in pages render inside `frontend/src/shell/AppShell.tsx`; `shell/navRegistry.ts` is the single list behind the topbar, the bottom navigation, the "More" sheet and the home hub (each entry is `spa` or `planned`; nothing in the app links to a Jinja page, guarded by `src/test/no-legacy-links.test.ts`). Interface preferences live in `frontend/src/prefs/` (`rb_prefs_v1` mirror applied before the first render, Auto resolved below 860 px, optimistic PATCH with revert) and are edited at `/riftbound/app/account/interface`. Admin screens live in `frontend/src/admin/` (`AdminLayout` + nav registry, one folder per screen, `admin` i18n namespace). See `docs/frontend.md`.

PWA (unit f): the app installs as "Rift Manager" (`pwa-options.ts`, vite-plugin-pwa `generateSW`, prompt mode). The worker is `/riftbound/app/sw.js` with scope `/riftbound/app/`; it precaches the app shell only and never touches `/riftbound/api/*`, `/riftbound/static/*` or Jinja pages. `frontend/src/pwa/` holds the "New version available." update toast (`useUpdatePrompt`), the install item (`installPrompt.ts` is started in `app/bootstrap.tsx`; iOS Safari gets `IosInstallDialog`) and the offline behaviour lives in `auth/offline.ts` plus `components/ui/OfflineBanner.tsx` (the shell opens offline when a signed-in hint exists; settings and logout are read-only offline). A plain revert is not a rollback of the PWA: build with `VITE_PWA_SELF_DESTROY=true` first (see `docs/frontend.md`, "Rolling back the PWA"). Icons are committed; `npm run icons` regenerates them and `npm run check:dist` verifies them.

Authentication and API access (unit d): `frontend/src/api/client.ts` is the only code that calls `fetch`. It unwraps `{success, data}`, throws `ApiError` (`kind` http, network, timeout or parse; `code` normalised from `body.code` or derived from the F0 body), keeps the CSRF token in memory only (`api/csrf.ts`, never in web storage), sends `X-CSRFToken` on POST, PATCH, PUT and DELETE, retries once after `csrf_invalid`, and calls the registered unauthorized handler on a 401 from any path except `/auth/login` and `/auth/logout`. The session is the TanStack Query entry `['session']` (`auth/session.ts`); route loaders `requireAuth`, `requireAnon` and `requireAdmin` (`auth/guards.ts`) run before anything renders. `next` is always an absolute `/riftbound/...` path and `auth/safeNext.ts` decides between a router navigation and a full page load. `altcha` is imported only by `auth/AltchaWidget.tsx` (lazy register route) and must keep the version pinned in `requirements.txt`. The app is English-only (owner feedback S21): text lives in `src/i18n/locales/en/*.json`, the only and typed catalog; there is no Spanish catalog, no language toggle, no language preference or detection, and `<html lang>` is `en`. Numbers, money and dates use one English locale in `src/lib/format.ts` (`1,061.52 €`, `5 Oct 2026`, `+10.0%`). The backend still stores the `lang` preference; the app ignores it. A unit that adds strings keeps `src/i18n/catalogCheck.test.ts` green (no empty strings, English plural forms only, no Spanish characters) and writes its tests in English. A backend error code needs `code.<value>` in `locales/en/errors.json`; the unit that adds a code adds a test for it. See `docs/frontend.md`.
