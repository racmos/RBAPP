# Delta for price-resolution

> Tags: `[a]`..`[e]` = delivery unit. All scenarios are pytest-testable (pure function plus SQLite seeding). Prices are Cardmarket EUR floats from `rbcm_price`; a column that is NULL (or 0, as today) counts as missing.

## ADDED Requirements

### Requirement: PRC-1 Fallback chain [a]

Given a price row, the card rarity and the foil flag, the unit price MUST be the first available value of:
- premium (rarity `rare`, `epic` or `showcase`, case-insensitive) OR foil `S`: `avg7_foil -> avg7 -> low_foil -> low`
- otherwise (common, uncommon, unknown or empty rarity, foil `N`): `avg7 -> avg7_foil -> low -> low_foil`

If there is no price row, or all four values are missing, the result MUST be `None`. This behavior comes from `1ae1f6e` and MUST be pinned by table-driven tests against the current implementation first.

#### Scenario: Premium prefers foil average
- GIVEN rarity `Rare`, foil `N`, `avg7_foil=5.0`, `avg7=3.0`
- WHEN the price is resolved
- THEN 5.0

#### Scenario: Premium cascade
- GIVEN rarity `epic`, `avg7_foil` and `avg7` NULL, `low_foil=1.2`, `low=1.0`
- WHEN resolved
- THEN 1.2; and with `low_foil` also NULL the result is 1.0

#### Scenario: Showcase is premium
- GIVEN rarity `SHOWCASE`, only `low=0.5`
- WHEN resolved
- THEN 0.5

#### Scenario: Common non-foil prefers avg7
- GIVEN rarity `common`, foil `N`, `avg7=0.1`, `avg7_foil=0.9`
- WHEN resolved
- THEN 0.1

#### Scenario: Common non-foil cascade
- GIVEN rarity `uncommon`, foil `N`, avg7 and avg7_foil NULL, `low=0.2`, `low_foil=0.8`
- WHEN resolved
- THEN 0.2

#### Scenario: Common foil
- GIVEN rarity `common`, foil `S`, `avg7_foil=0.9`, `avg7=0.1`
- WHEN resolved
- THEN 0.9

#### Scenario: Nothing available
- GIVEN no price row, or a row with all four columns NULL
- WHEN resolved
- THEN `None`

### Requirement: PRC-2 One shared implementation [c]

The chain MUST live in one module (`app/services/pricing.py`) used by the collection list/export and by deck viewing. No other code path may pick a price column by its own rule. Deck viewing prices a card as foil `N` using its latest-dated price row.

#### Scenario: Deck matches collection
- GIVEN a mapped `rare` card whose latest price row has only `rbprc_low=0.5`
- WHEN a deck containing it is viewed, and the same card is listed in a collection
- THEN both show 0.5

#### Scenario: Deck showcase and low fallback
- GIVEN a `showcase` card with only `rbprc_low_foil=2.0` in its latest row
- WHEN a deck containing it is viewed
- THEN the card price is 2.0 (deck previously returned `None`)

#### Scenario: Latest row wins
- GIVEN price rows dated `2026-10-01` (avg7=1.0) and `2026-10-02` (avg7=2.0) for the mapped product, rarity `common`
- WHEN a deck is viewed
- THEN the card price is 2.0

#### Scenario: Unmapped card
- GIVEN a deck card with no product mapping
- WHEN viewed
- THEN the price is `None`
