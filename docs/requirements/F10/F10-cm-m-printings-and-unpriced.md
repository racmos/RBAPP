# F10-CM-m: Auto-match — legends with more Cardmarket printings than cards, and unpriced pairs

| Field | Value |
|---|---|
| Phase / unit | F10 / CM-m (Cardmarket admin, owner feedback 2026-11-24) |
| Branch | `feat/cm-extra-printings` (from up-to-date `origin/main`) |
| Depends on | CM-h (promo cards), CM-k/k2 (plated cards), #161–#163 (auto-match rules) |
| Size forecast | ~600 authored lines |
| Risk | `Risk: none` (matcher rules only add decisions; creating cards is explicit, audited) |
| TDD | ON (strict). Backend `pytest`, frontend `npx vitest run` |
| Sources | Owner message 2026-11-24: Radiance legends are not matched ("para Cardmarket es Ziggs, Hexplosives Expert y para nosotros es de nombre Hexplosives Expert y de tag Ziggs") |

## Objective

Auto-match leaves 151 ambiguous, 34 conflict and 17 no-candidate products. The Radiance legends are the
visible case. **It is not a name problem**: `Ziggs, Hexplosives Expert` already finds `RAD-141` and `RAD-169`
by the tag forms and `RAD-141` is linked. The cause (real data, 2026-11-24): Cardmarket lists **three**
printings per Radiance legend (Rare 0.02 €, Showcase 45 €, a third at 450 €) while the catalog has **two**
(`RAD-141`, `RAD-169`; the signed `RAD-169s` is not in the Riot gallery). Two products for one free slot is
ambiguous by design. The same shape explains most of the 75 ambiguous groups. Add a way to create the missing
printings and make the matcher decide the remaining unambiguous pairs.

## Read first

- `app/services/cardmarket_matcher.py` (`_build_card_index`, `_expand_slots`, `card_rank_key`,
  `_paired_by_rank`, `_get_partition_candidates`), `app/services/daily_prices.py::classify_unmapped`,
  `app/services/promo_cards.py` (the plan/create pattern, `_plated_items`).
- `docs/knowledge/ops-runbook.md` ("Missing promo cards", "Plated cards") and the `Auto-match` panel.
- Real data example: product 917343 (0.02 €, linked `RAD-141`), 917370 (45 €), 917487 (450 €), all
  `Ziggs, Hexplosives Expert`; cards `RAD-141` Rare, `RAD-169` Showcase. Other cases: `OGN-255` / `303` /
  `303s`, `RAD-151` / `174` with 4 products, `RAD-86` / `86a` / `178` with 6.

## Scope

In: a report of products that have more Cardmarket printings than catalog slots (per set, with the card
that would be copied), creation of the missing signed printing from the highest-rank printing, the
unpriced-pair rule in the matcher, the Auto-match review text, tests, docs.
Out: changing what a clear case is for common/uncommon foil pairs (owner decision A of CM-h stays), any
migration, linking by hand, images.

## Specs

- **S1 Diagnosis in the review.** In the Auto-match review, an `ambiguous` product whose own-set cards are
  all taken or fewer than the products of its Cardmarket card group says so: reason detail
  `more_printings_than_cards` with counts (`3 Cardmarket printings, 2 cards`) and the candidate cards. A new
  reason code, additive; `errors.json` / catalog tests updated; nothing else in the review changes.
- **S2 Missing printings list.** `GET /admin/cardmarket/missing-printings` (A) lists, per set, the card
  groups (same Cardmarket card group, same normalised name) with more products than free slots, each with
  the products by price, the cards they take and the **proposed new card**: id = the highest-rank printing's
  id + `s` when that card has no letter variant (`169` → `169s`), copy of the highest-rank printing (all
  card fields but the image), rarity `Showcase`. Groups where the proposal is unclear (a letter variant
  already exists, the number of extra products is not exactly one) are listed as `manual` with the reason.
- **S3 Create.** `POST /admin/cardmarket/missing-printings` `{items: [{set_id, card_id}]}` (1–200) creates the
  proposed cards in one transaction through `catalog_admin.create_cards`, one audit row, an existing card is
  skipped; refuses ids that are not in the current list (400 like CM-h). The create step does not link;
  Auto-match afterwards does.
- **S4 Panel.** `Prepare → Missing cards` (see CM-l) gets a second list `Extra printings` under the promo
  list (or a segmented control if CM-l is not built yet), with the same selection / Create / confirm pattern
  as the promo list, and the proposed id and rarity per row.
- **S5 Unpriced pair (not built until the owner decides).** Auto-match refuses to pair two products of one
  card group when one of them has no price in the latest load (the rank pairing needs prices above 0), e.g.
  the two PLAT products of a legend where one is unpriced. CM-k2's plan gives the unpriced product the
  lower rank. If the owner confirms that rule (see Open questions), the matcher applies the same rule in
  `_paired_by_rank` and the pair becomes a clear case. Until then these pairs stay `ambiguous` and are
  linked by hand.
- **S6 Radiance acceptance.** After creating `RAD-169s` (and the equivalents of the list) Auto-match Preview
  decides `917370 → RAD-169` and `917487 → RAD-169s` as clear cases, with `917343 → RAD-141` untouched.
- **S7 No regressions.** The CM-h promo and CM-k PLAT tests, the foil-pair ambiguity of commons and the
  slot-owner rule (#162) are unchanged and stay green; statement bounds are asserted for the new GET.

## API / data contract

- `GET /admin/cardmarket/missing-printings` → `{date, sets: [{set_id, groups: [{name, products: [{id, price}],
  cards: [{set_id, card_id, rarity}], proposed: {set_id, card_id, rarity} | null, status, reason}]}], summary}`.
- `POST /admin/cardmarket/missing-printings` → `{created: [...], skipped: [...]}`; errors as CM-h.
- Review item: `reason: ambiguous` plus optional `detail: {products, cards}`; contract additive only.
- No migration. Authz matrix entries for the two routes (A).

## UI

Auto-match review rows for S1 show the text "3 printings on Cardmarket, 2 cards here: create the missing
printing" with a link to the Missing cards panel filtered to that set. Extra printings rows: set, card name,
products with prices, "will create RAD-169s (Showcase)", checkbox, **Create N cards**.

## Acceptance criteria

1. The real RAD legends appear in the list with the proposed `…s` ids; none of the proposals collides with an
   existing card.
2. Creating them and re-running Preview moves the matching ambiguous products to clear cases.
3. Strings, error codes, authz, audit, statement bounds and the CM-h / CM-k suites green; whole lanes green.

## Delivery

One PR (backend + frontend, no migration). Deploy = pull + restart + frontend build.
Docs: `docs/api.md`, `docs/frontend.md`, `docs/knowledge/state.md`, `docs/knowledge/ops-runbook.md`
("Extra printings"), `AGENTS.md` structure lines.

## Open questions

- Owner: is the third Cardmarket printing of a legend the **signed** card (`<id>s`, as `OGN-303s`,
  `SFD-230s`)? If a set uses another id for it, the proposal changes (S2).
- Owner: for a PLAT pair where one product has no price (e.g. `922511`), which printing gets the
  unpriced product? (CM-k2 gives it the lower rank; Auto-match refuses it today.) Decide S5.

## Log

- 2026-11-24 — written after the live check of the Radiance legends (917343 / 917370 / 917487 vs `RAD-141`,
  `RAD-169`); the cause is a missing printing, not the tag name.
