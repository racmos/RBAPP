# F5-g: Deck share link and public read-only deck

| Field | Value |
|---|---|
| Phase / unit | F5 / g |
| Branch | `feat/f5g-deck-share` (from `main` `ef7cbb5`, F5-a..e merged) |
| Depends on | F5-c (`rbdkh_share_slug`, `rbdkh_visibility`, deployed), F5-d (decks API, `_Catalog`, detail shape) |
| Size forecast | ~600 authored lines (tests and docs included) |
| Risk | `Risk: item 2 (the first API endpoint that shows user content to anonymous callers: slug entropy, revocation, owner anonymity, rate limit, no cookie, no cache), item 3 (`share` on DeckHead and the PublicDeck shape are what F5-h and F5-m consume)` |
| TDD | ON (strict). Runner: `venv/bin/pytest` (backend only) |
| Save as | `docs/requirements/F5/F5-g-deck-share.md` |

## Objective

The owner of a deck gets a read-only link to it, can revoke it at any time (the old link stops
working at once) and can share again with a new link. Anyone with the link reads the deck (name,
content, legality, value) without signing in; the owner's username is shown only when the deck is
public (D-F5-4). No migration, no screen (the public page is F5-m).

## Read first

- `AGENTS.md`, `docs/knowledge/conventions.md`
- `docs/requirements/F5/README.md` (F5-R12, F5-R20, D-F5-4), `F5-d-decks-api.md`, `F5-e-decks-import-export.md`
- `app/models/deck_v2.py`, `app/services/decks.py`, `app/api/v1/decks.py`, `app/api/v1/auth.py`
  (`limiter`), `app/api/v1/meta.py` (public endpoint pattern), `tests/test_authz_matrix.py`

## Scope

In:
- `POST`/`DELETE /decks/<id>/share` (U), `GET /public/decks/<slug>` (P), `app/services/deck_share.py`
- `share: {slug, url} | null` on `DeckHead` (so on `GET /decks` items and every `DeckDetail`)
- Authz matrix entries, `docs/api.md` "Deck sharing (F5-g)"

Out (do not do, even if tempting):
- Any migration or model change (the columns exist since `0025_decks_v2`)
- The public SPA page `/riftbound/app/d/:slug` (F5-m), any UI (F5-h..j)
- A public index or search of decks

## Specs

S1. `POST /decks/<id>/share` (U, no body) -> 200 `{slug, url}`: `slug` is 22 url-safe random
  characters (`secrets.token_urlsafe(16)`, `[A-Za-z0-9_-]{22}`), unique among decks (a taken slug
  is drawn again, at most 5 draws); `url` = `<request scheme and host>/riftbound/app/d/<slug>`
  (`url_for('spa.asset', ..., _external=True)`, never a fixed host). A deck that already has a slug
  answers the same `{slug, url}`. The deck's `updated_at` does not change.
S2. `DELETE /decks/<id>/share` (U) -> 200 `{share: null}`; the slug is cleared and
  `GET /public/decks/<old slug>` answers 404 from the next request on. A deck without a link
  answers the same. Sharing again gives a new slug; the old one stays 404. Deleting the deck
  kills its link.
S3. Both share routes: another user's deck or an unknown id -> the 404 envelope and nothing
  changes; anonymous -> 401 `unauthenticated`.
S4. `DeckHead` gains `share: {slug, url} | null` after `updated_at` (additive): `GET /decks`
  items, `GET`/`POST`/`PATCH /decks…` details, the import detail and `DELETE /decks/<id>`'s
  `deleted`. `GET /decks` stays at 9 SQL statements.
S5. `GET /public/decks/<slug>` (P): no login, no `Set-Cookie`, `Cache-Control: no-store` on every
  answer, 60 requests per minute per IP (`@limiter.limit('60 per minute')`; the 61st -> 429
  `rate_limited` with `Retry-After`; unknown slugs count too).
S6. An unknown, revoked or malformed slug -> the same 404 envelope `{success: false, error:
  "Not Found", message: "The requested resource was not found"}`; a malformed slug never reaches
  the database.
S7. 200 -> `{name, mode, visibility, owner, updated_at, content, cards, unknown_cards, domains,
  counts, value, value_unpriced, legality}` (exactly these keys, in this order). `owner` =
  `{username}` only when `visibility` is `public`, else `null`.
S8. The workbench is left out: `content` has no `workbench` key, `cards`, `counts` (`{main, runes,
  battlefields, sideboard}`), `value` and `legality` are those of the deck without it. Legality
  is computed on read in both modes with the bans of the moment.
S9. Never returned: deck id, user id, email, `created_at`, `current_seq`, versions, notes, the
  slug or other decks' slugs; `DeckCard.owned_total` is `null` (no collection is read).
S10. The public read runs 7 SQL statements (head + owner username, current version, cards, sets,
  bans, prices ×2).

## API / data contract

Routes in `app/api/v1/decks.py`: `api_v1.share_deck` (POST, U), `api_v1.unshare_deck` (DELETE, U),
`api_v1.public_deck` (GET, P). Shapes in `docs/api.md` → "Deck sharing (F5-g)". No new error code,
no migration.

## UI

none

## Acceptance criteria

- [x] AC1 S1-S3: `tests/test_api_deck_share.py::TestShare`, `TestRevoke`
- [x] AC2 S4: `TestShare::test_the_deck_detail_and_list_carry_the_share`; key lists in
  `tests/test_api_decks.py`, `tests/test_api_deck_import_export.py`; `TestList::test_sql_statements_do_not_grow_with_the_decks` (9)
- [x] AC3 S5-S10: `tests/test_api_deck_share.py::TestPublicDeck`, `TestRateLimit`
- [x] AC4 Authz: `tests/test_authz_matrix.py` (`api_v1.public_deck` P, `share_deck` / `unshare_deck` U)
- [x] AC5 Full backend lane green: `venv/bin/pytest`
- [x] AC6 `docs/api.md`, `docs/knowledge/state.md`, `AGENTS.md`, F5 `README.md` updated

## Deviations and decisions (L)

- L1 (agent): the public payload leaves the workbench out entirely (content, cards, counts, value,
  legality). Product: the workbench is excluded from export, value and legality, and it is the
  owner's scratch space. Legality is computed on the shown content, so a `copies_over` or
  `workbench_over` that only the workbench causes does not appear publicly (the owner's view
  still shows it); such a deck cannot be saved anyway (hard limit) except right after an import.
- L2 (agent): `DeckCard.owned_total` is `null` in the public payload: the owner's copies would leak
  their collection and the viewer's would need the session (which the route never touches).
  F5-m may read the viewer's own collection through the U endpoints.
- L3 (agent): the public payload adds `unknown_cards`, `domains` and `counts` to the fields the
  phase spec lists (same meaning as in `DeckDetail`; no private data) so F5-m needs no second call.
- L4 (agent): `DELETE /decks/<id>/share` answers 200 `{share: null}` (the repo's deletes answer
  200 with a body, never 204) and is a no-op on a deck without a link.
- L5 (agent): sharing and revoking do not refresh `updated_at` (the deck list is ordered by
  content changes).
- L6 (agent): the 404 of the public route carries `Cache-Control: no-store` too, built with the
  same handler as any other 404 so its body cannot be told apart.

## Delivery

- Conventional Commits. PR title: `feat(decks): share link and public read-only deck (F5 unit g)`.
  Never merge.

## After merge

- Deploy to dev with `docs/knowledge/ops-runbook.md` (no migration).
- Live checks: share a deck (`POST /riftbound/api/v1/decks/<id>/share`), open
  `GET /riftbound/api/v1/public/decks/<slug>` in a private window (200, `owner: null`, no
  cookie), mark the deck public (owner shown), revoke (404 at once).
- Manual checks for the owner: none (no screen).

## Open questions

none
