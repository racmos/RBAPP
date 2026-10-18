# Delta for landing-feeds

> Tags: `[a]`..`[e]` = delivery unit. The proposal assigns no unit to this capability; it is tagged `[d]` because the exploration ties it to the rate-limiting work (open point, see report). All scenarios are pytest-testable (scraper functions mocked, clock injected).

## ADDED Requirements

### Requirement: LAND-1 Cached feed items [d]

The six public partials `/api/noticias`, `/api/discord`, `/api/torneos-online`, `/api/torneos-fisicos`, `/api/videos`, `/api/decks` MUST cache the items returned by their feed function, per feed, for `LANDING_CACHE_TTL` seconds (default 300). Within the TTL, repeated requests MUST NOT call the feed function again. After the TTL the next request MUST call it once and refresh the cache. A fallback (placeholder) result is cached like any other, so a failing upstream is contacted at most once per TTL. Rendered output MUST be identical to the uncached output for the same items, and the endpoints stay public.

#### Scenario: Hit within TTL
- GIVEN `fetch_noticias` mocked to count calls and an empty cache
- WHEN `GET /api/noticias` is requested 5 times within the TTL
- THEN the mock was called once and all 5 responses have status 200 and the same body

#### Scenario: Expiry
- GIVEN a cached entry and the clock advanced past the TTL
- WHEN `GET /api/noticias` is requested twice
- THEN the mock was called exactly once more

#### Scenario: Feeds are independent
- GIVEN `/api/decks` cached
- WHEN `/api/noticias` is requested for the first time
- THEN `fetch_noticias` is called (a hit on one feed does not serve another)

#### Scenario: Still public
- GIVEN no session
- WHEN any of the six partials is requested
- THEN status 200 (not redirected to login)

#### Scenario: Configurable TTL
- GIVEN `LANDING_CACHE_TTL=0`
- WHEN a partial is requested twice
- THEN the feed function is called twice
