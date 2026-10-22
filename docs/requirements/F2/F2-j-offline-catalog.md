# F2-j: Offline catalog — service-worker read cache for the catalog and card images

| Field | Value |
|---|---|
| Phase / unit | F2 / j |
| Branch | `feat/f2j-offline-catalog` (from up-to-date `main`) |
| Depends on | F2-i merged (catalog, detail, chart in place). F2-l recommended first (thumbnails), not required |
| Size forecast | ~350 authored lines (tests and docs included) |
| Risk | `Risk: items 5 and 6 (changes the service worker and the check:dist delivery gate; real offline behaviour is only fully observable on a device)` |
| TDD | ON (strict). Runners: `venv/bin/pytest` (backend, untouched), `cd frontend && npx vitest run` (frontend) |
| Save as | `docs/requirements/F2/F2-j-offline-catalog.md` (commit this document verbatim in the first commit if it is not in the repo yet) |

## Objective

With no network (plane, basement shop, bad signal), the installed app still shows the catalog pages and
cards the user already viewed, with their images, read-only. Online behaviour does not change: the app
always asks the network first and only falls back to the saved copy when the network fails or is too
slow. Nothing of one account is shown to another account on the same device.

## Read first

- `AGENTS.md`, `docs/knowledge/conventions.md`, `docs/frontend.md` ("Service worker and install", "Rolling back the PWA")
- `docs/requirements/F2/README.md` (F2-R22, R23, R24; D-F2-7, D-F2-8, D-F2-9) and the cross-phase contract
  "Offline read cache" in `docs/knowledge/roadmap.md`
- `openspec/specs/pwa/spec.md` (PWA-1 "no runtime caching" — this unit amends it; PWA-7 offline boot)
- `frontend/pwa-options.ts` (+ `pwa-options.test.ts`), `frontend/scripts/check-dist.mjs` (+ `check-dist.test.ts`),
  `frontend/src/app/queryClient.ts`, `src/auth/signOut.ts`, `src/auth/session.ts`, `src/auth/offline.ts`,
  `src/catalog/queries.ts`, `src/components/ui/{EmptyState,OfflineBanner}.tsx`

## Scope

In:
- Workbox `runtimeCaching` for the catalog API GETs and card images; cache names and limits.
- `check:dist` rules allowing exactly these routes.
- `networkMode: 'offlineFirst'` for catalog queries; offline-not-cached states.
- Purge of the API cache on logout and on a change of signed-in user.
- Docs (amendment of PWA-1).

Out (do not do, even if tempting):
- Full catalog snapshot / IndexedDB / client-side search offline (D-F2-8 option b).
- Caching `/auth/*`, `/me/*`, Jinja pages or any non-GET request. Background sync of edits.
- Collection and decks (F3, F5 extend the same allow-list).

## Specs

S1. `buildPwaOptions` adds exactly three `workbox.runtimeCaching` entries (same-origin, `GET` only):
    | Name (`cacheName`) | `urlPattern` (pathname) | Handler | Options |
    |---|---|---|---|
    | `rb-api-catalog` | `^/riftbound/api/v1/(cards(/.*)?\|meta/game\|bans)$` | `NetworkFirst` | `networkTimeoutSeconds: 4`; `expiration {maxEntries: 300, maxAgeSeconds: 14 days}`; `cacheableResponse {statuses: [200]}` |
    | `rb-card-thumbs` | `^/riftbound/static/images/card-thumbs/` | `CacheFirst` | `expiration {maxEntries: 2500, maxAgeSeconds: 60 days, purgeOnQuotaError: true}`; statuses `[200]` |
    | `rb-card-images` | `^/riftbound/static/images/cards/` | `CacheFirst` | `expiration {maxEntries: 300, maxAgeSeconds: 60 days, purgeOnQuotaError: true}`; statuses `[200]` |
    Matching uses `url.pathname` and `url.origin === self.location.origin`; query strings are part of the
    API cache key (different filters = different entries). The precache and navigation fallback are unchanged.

S2. `check-dist.mjs`: the rule "no `registerRoute` other than the navigation route" becomes "the registered
    runtime routes are exactly the three of S1 (by cache name) and no route matches `/riftbound/api/v1/auth`
    or `/riftbound/api/v1/me`"; the precache rule (no URL under `/riftbound/api`) stays. `check-dist.test.ts`
    gets: valid build with the three routes passes; an extra route fails naming it; a route whose pattern
    matches `/riftbound/api/v1/auth/session` fails. The self-destroying build check is unchanged.

S3. Catalog queries (`useGameMeta`, `useCardList`, `useCardDetail`, `useCardPrices`) use
    `networkMode: 'offlineFirst'` (they fire once even when `navigator.onLine` is false, so the worker can
    answer from its cache); other queries keep the default. Retries on network errors stay as configured.

S4. Offline states (when the request fails with `ApiError.kind === 'network'` and `useOffline()` is true):
    catalog, detail and chart show `EmptyState` with icon `offline`, title `cards:offline.title`, body
    `cards:offline.body` (no retry button while offline; when connectivity returns the query refetches by
    itself). Data served from the cache renders normally under the existing offline banner. A card image
    missing from the cache falls back to `CardArtPlaceholder` (F2-e behaviour).

S5. User isolation: `purgeUserCaches()` (exported from `@/pwa`) deletes the Cache Storage cache
    `rb-api-catalog` (never the image caches) and is a no-op when `caches` is unavailable. It is called:
    (a) by `resetToAnonymous` (logout and expired session); (b) when a session arrives whose `user.id`
    differs from the last one seen on this device (`localStorage` key `rb_last_user_id`, written after every
    successful signed-in session; storage errors ignored). Example: user A signs in, browses, signs out;
    user B signs in on the same phone and goes offline → B never sees A's `owned` counts.

S6. Docs: `docs/frontend.md` "Service worker and install": the precache row stays; a new row "Runtime caches"
    lists S1 (names, strategy, limits), states that edits are never cached and that F3/F5 add their GET
    endpoints to the same `NetworkFirst` pattern, and documents the purge; the device checklist gains
    "offline catalog" steps (After merge). `AGENTS.md` (CRLF) frontend paragraph: one sentence on the read
    cache. The PR body records that this amends F1 PWA-1.

## API / data contract

none (client side only). Cache names in S1 are a contract for F3/F5 (they add `rb-api-collection` and
`rb-api-decks` with the same options and purge rule).

## UI

Strings — `cards.json`:

| Key | es | en |
|---|---|---|
| `offline.title` | No disponible sin conexión | Not available offline |
| `offline.body` | Esta vista no se ha guardado en este dispositivo. Conéctate para verla; las cartas que ya abriste siguen disponibles. | This view is not saved on this device. Connect to see it; the cards you already opened are still available. |

Applies to every width; no layout change.

## Acceptance criteria

- [ ] AC1 `frontend/pwa-options.test.ts`: the three entries, patterns match/don't match a table of URLs (cards list with query, card detail, prices, meta/game, bans → API cache; `/auth/session`, `/me/prefs`, `/riftbound/card` Jinja → none; thumb and full image paths → their caches), handlers and limits (S1).
- [ ] AC2 `frontend/scripts/check-dist.test.ts` new cases and a real `npm run build && npm run check:dist` green (S2).
- [ ] AC3 `src/catalog/offline.test.tsx`: with `navigator.onLine=false` the list query still calls fetch (MSW answers) and renders; with a network error offline → S4 empty state without retry; going online refetches (S3, S4).
- [ ] AC4 `src/pwa/purgeUserCaches.test.ts` and `src/auth/logout.test.tsx` / `session.test.ts`: purge on logout, on 401 reset, on user id change, not on the same user; image caches untouched; no `caches` → no throw (S5).
- [ ] AC5 Full lanes green: `venv/bin/pytest`; `cd frontend && npm run lint && npm run typecheck && npx vitest run && npm run build && npm run check:dist`
- [ ] AC6 `docs/knowledge/state.md` updated (what changed, PR number placeholder, follow-up: "F3/F5 extend the read cache")
- [ ] AC7 `docs/frontend.md` / `AGENTS.md` updated (S6).

## Delivery

- Conventional Commits; commit messages end with the attribution lines the session supplies.
- Push and PR only when the user says so. PR title: `feat(pwa): offline read cache for the catalog (F2 unit j)`.
  PR body: summary, specs → tests map (S# → test file::name), PWA-1 amendment, manual checks, rollback
  (self-destroying build if the worker misbehaves, then revert — `docs/frontend.md`).
- Never merge. The user merges.

## After merge (user asks gentle-shell, or does it)

- Deploy to dev with `docs/knowledge/ops-runbook.md` (frontend build only). The update toast appears on
  installed apps; accept it.
- Live checks: DevTools → Application → Cache Storage shows `rb-api-catalog`, `rb-card-images` (and
  `rb-card-thumbs` if F2-l is live) after browsing; the PWA live check still passes except the
  "nothing under /riftbound/api" precache item, which stays true (runtime caches are not precache).
- Manual checks for the user: on the installed app browse two catalog pages and three cards, switch on
  airplane mode, reopen the app: those pages and cards (with images) open; an unvisited filter shows
  "No disponible sin conexión"; sign out and sign in with another account → its catalog shows its own copies.

## Open questions

- CONFIRM D-F2-7: `NetworkFirst` with a 4 s timeout instead of the stale-while-revalidate named in the
  cross-phase contract (SWR would show stale data right after edits in F3/F5).
- CONFIRM D-F2-8: offline = what was viewed; no full catalog snapshot.
- CONFIRM D-F2-9: limits 300 API entries / 14 days, 2 500 thumbnails and 300 full images / 60 days.
