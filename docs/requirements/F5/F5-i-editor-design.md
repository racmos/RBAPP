# F5-i: Deck editor redesign (desktop two panes) — design notes

Status: **design, owner reference screenshots described**. Source: nine screenshots the owner left in
`/home/racmos/ejemplosdecks/editordeck1.png … editordeck9.png` on the dev host (2026-11-05), taken from a
deck editor the owner likes. They are not committed (4.9 MB); this document is the record. Owner instruction:
build the editor like this **without losing what the app already shows (prices, workbench, legality
reasons, completeness per section)**. After the editor: the deck list screen.

This note replaces the "desktop" half of F5-i in `README.md` (list | editor | analysis) with the owner's
layout. Mobile keeps the F5-h screens.

## What each image shows

| Image | What it shows |
|---|---|
| 1 | **Two panes.** Left = card browser: tabs `Legend · Champion · Main Deck · Battlefields · Sideboard · Runes`, counter "298 of 298 cards for Main Deck", search box ("Search Main Deck cards…"), `View` button, `Filter` button, `Fit` checkbox, a grid of card images with energy badge (top left) and might badge (top right). Right = **Deck workspace**: header "DECK WORKSPACE · Saved", deck name field, icon buttons (history, download, upload/export, lock, trash, fullscreen), `Suggestions`, `Guide`, `Play in Simulator`, tabs `List · Full Art · Stats`. In List: `LEGEND 1/1` and `CHAMPION 1/1` side by side, then `MAIN DECK 39/39` with "By Type" and "Name ↑" selectors, sub-headed `UNIT 17 cards`, `SPELL 16 cards`, `GEAR 6 cards`; each card is a small row: thumb (badge "3 alt arts" when the printing has variants), `−` / `+` stepper, name, quantity `3x`, energy pip and power/might pips, a swap icon (move zone) and an expand icon. |
| 2 | Same screen scrolled to the bottom of the workspace: `GEAR`, `BATTLEFIELDS 3/3`, `SIDEBOARD 10/10`, `RUNES 12/12` (the two rune cards with "11 alt arts"). The **Filter popover** of the browser is open: *Card* (Domain icons, Type with counts Gear/Spell/Unit, Rarity Common…Showcase with counts), *Cost & Might* (Energy 0…7+, Power 0…3+, Might 0…7+, each value with its count), *Advanced* (Set with counts: Origins, Spiritforged, Unleashed, Vendetta, Radiance; Keywords select; Tags select; Abilities select), *Status* (Legal only, Available to add, Bookmarked only: switches with counts). |
| 3 | Workspace tab **Full Art**, mode `Stacked`: the cards as images, grouped like the list (MAIN DECK by type, then SIDEBOARD, RUNES with stacks `x6`), copies stacked with a `x3` badge; `All copies` is the alternative; a size slider `S … 1/6`. |
| 4 | Full Art with `All copies`: Legend and Champion as large cards, Battlefields (landscape), Sideboard and Runes with every copy shown. |
| 5 | Workspace tab **Stats**: summary (Main Deck 39, Avg Energy 2.9, Avg Might 3.8, Power Cards 14), **Energy curve** (bars 0…10 stacked by Unit/Spell/Gear/Champion), **Power & Runes** by domain (percent bars, per domain: cards, power, runes), **Unit might** histogram 0…12, **Keywords** with counts (Reaction, Hidden, Action, Equip…). |
| 6 | **Versions** modal: list by date ("Current", older ones), each row shows `+1 −1` and expands to the changes (`+1 Rakelstake — Battlefields`, `−1 Hunters' Circle — Battlefields`) with a **Restore** button; a version that did not change shows "66 cards". |
| 7 | **Export** menu (upload icon): Copy decklist, Copy deck code (compact share code), Share deck, Download wallpaper (16:9 PNG, 1080p to 4K). |
| 8 | **Import deck** dialog: big textarea with the common text format, lines ending in `[RAD-149]`; right panel **Import validation** (`1/1 legend`, `1/1 champion`, `39/39 main deck`, `3/3 battlefields`, `12/12 runes`, `10/10 sideboard cards`); a green "READY TO IMPORT" chip; buttons Cancel / Import Deck; a "Use deck code" alternative. (Already built in #98 except the live panel.) |
| 9 | **Publish to Community Decks** dialog (show-as name, description, up to 3 highlight cards). |

## What we build, and what we do not

**In scope (the owner asked for the editor to look like this):**
1. Two panes on desktop (browser left, workspace right), resizable divider; tabs of the browser select the
   zone being filled and filter the grid (Legend: Legend cards; Champion: Champion Units sharing a tag with the
   legend; Main: everything allowed in main; Battlefields; Sideboard; Runes of the legend's domains).
2. Card browser: search, `View` (grid size), `Fit`, **Filter popover** with the groups of image 2
   (domain, type, rarity, energy, power, might, set, keywords, tags, abilities, legal only, available to add).
   Counts next to each value come from the same query (disjunctive facets, like the catalog).
3. Workspace **List** tab with the rows of image 1, **keeping**: price per card and total value, workbench
   section ("not counted"), completeness per section (`8/10 · 2 missing`), legality chips for 1v1/2v2 with
   reasons, the disabled-with-reason controls of F5-h.
4. **Full Art** tab (Stacked / All copies, size slider) and **Stats** tab (image 5).
5. **Versions** modal with diff and Restore (backend exists: versions, diff, restore).
6. **Export** menu: Copy decklist (the existing text export), Share deck (existing share link). Import
   dialog gets the live validation panel.

**Out of scope for now (say so, do not fake):** `Suggestions`, `Guide`, `Play in Simulator` (hand
simulator, F5-k after production), `Copy deck code` (needs a format decision), `Download wallpaper`,
`Publish to Community Decks` (no community feature), `Bookmarked only`, `Available to add` until a
definition is agreed (probably "copies in my collection not used by another deck": needs F16 deck
locations/F5-f; ask the owner).

## Backend gaps this needs (no migration expected)

> **Step 1 done (backend):** every deck card now carries `energy`, `power`, `might`, `variants` (printings of the same name) and `keywords` (derived from the ability text, approximate); `rarity`, `domains` and `tags` were already there. Still open below: `GET /cards` filters for the browser, `legal_for_deck`, and the `available` flag.

- Deck card payload (`GET /decks/<id>`, public deck) must carry **energy, power and might** (and rarity,
  domains, tags) so the rows and the stats can be drawn.
- **Keywords** (Reaction, Hidden…): not stored as a column; either derive from the ability text or leave the
  Keywords block and filter out until a source exists. Decide with the owner.
- `GET /cards` already supports most filters (domain, type, rarity, set, energy, might, text); check
  `power` and `keywords` ranges, `legal_for_deck` (cards allowed in a zone for this deck) and an
  `owned_qty`/available flag.
- The card catalog shows **alt arts count** per name (badge "3 alt arts"): `variants` per card name.

## Steps (one worker at a time, ask the owner between steps)

1. Backend: energy/power/might/rarity/domains/tags on deck cards, `variants` count, tests. (small)
2. Desktop two-pane shell: workspace List tab restyled to the rows of image 1 (keeps prices/workbench) +
   browser pane with tabs, search, grid; add/remove from the grid and the rows through the existing editor
   hook and rules. (largest)
   **Done (frontend, `feat/f5i-editor-two-pane`):** rows with energy/power/might, alt arts and Main/Sideboard
   grouped by type; `CardBrowser` left of the workspace from 960 px while editing is possible (tabs, search,
   48-tile grid with energy/might/copies badges, refusals with the rules' reason, paging). Not yet: the
   resizable divider, `View`, `Fit` and the workspace tabs (List / Full Art / Stats); the filter popover is
   step 3.
   **Legend identity (owner rule, `fix/f5i-browser-identity`):** once a legend is chosen the editor offers
   only legal choices: the browser and the section searches list main, sideboard and champion cards of the
   legend's domains (`domain_match=subset`, colourless included), and adding refuses an off-domain card or a
   Signature card that shares no tag with the legend, with the reason. The rules engine stays soft on
   purpose (`validate` reports colour and Signature tag) so imports and versions keep loading.
3. Filter popover + facets. 
4. Stats tab.
5. Full Art tab.
6. Versions modal (diff, Restore) and export menu; import validation panel live.
7. Deck list screen (next menu the owner asked for).

## Decisions (owner, 2026-11-05)

1. **Keywords**: derived from the ability text (approximate; documented as such in the UI help).
2. **"Available to add"**: copies of the card (by name, any printing) that the owner has in the collection
   and can use for this deck, **whether or not they sit in a storage location** (a location, locked or not,
   is only where they are kept). Copies only leave the collection when the owner **confirms mounting the
   deck** (F16-e: a locked location is created for the deck), not while editing. So available = owned
   copies of the name minus the copies this deck already uses; copies inside a **locked deck location**
   (another mounted deck) are not available. To confirm with the owner when F16-e is built.
3. **Power Cards** = cards with a power cost greater than 0.
4. **Mobile**: the card browser and its filters open as a **bottom sheet** from each section.

