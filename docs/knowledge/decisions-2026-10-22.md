# Owner decisions of 2026-10-21/22 and the agreed plan

Recorded by the planner after the owner answered the open questions of the milestones review (Spanish
working document "Rift Manager — Hitos y prioridades"). These decisions are binding. Folded into the plan
documents by M-b (#<PR>); kept as the record of the owner's answers.

## Agreed order

1. **M-a** Test reset (`docs/requirements/M/M-a-test-reset.md`) — next unit.
2. **M-b** Plan update: fold this file into `product.md`, `roadmap.md`, `open-decisions.md`, the phase specs
   and `state.md`; add the new phase specs (Riot sync + catalog admin, Products, Rules app).
3. **M-c** Hygiene: remove private IPs and the dev domain from tracked files (no history rewrite); legacy
   endpoints stop returning exception text (clear message + error code to the user, full detail logged and
   visible to the admin); replace `datetime.utcnow()` with `app/utils/clock.utcnow()`.
4. **F4-a + F4-b** Job runner + timers, daily Cardmarket load.
5. **F2-a** Per-mode card bans, initial data from the official ban list (owner provides it).
6. **M-d** Card images out of git, into a data directory outside the code tree (copy first: removing them
   from the index would delete them from the deployed checkout on the next pull).
7. **Riot sync + catalog admin** (pulled forward from F10, without waiting for F9): admin foundation, sets
   with release date, cards, Riot sync schedule, change-approval table.
8. **F2** rest (catalog).
9. **F3** Collection + **F4-c** daily value snapshots.
10. **Products** (new phase).
11. Medium priority: rest of F4, F5 without the hand simulator, F6, F7, rest of F10, F9 (Google/Discord
    login just before production), F11 (without the new landing), F12 production.
12. After production: **Rules app** (new phase) → mulligan / opening hands (F5-k, split out) → F8 events
    (upcoming-events calendar from the official site first) + new landing (F11-a/b).

## Decisions

| Topic | Decision |
|---|---|
| Tests | Remove every existing suite except `tests/test_authz_matrix.py`; add startup smoke tests (backend + frontend). Strict TDD continues: each unit writes its own tests and re-creates a removed guard when it touches its area. First unit (M-a). |
| Daily prices | Cardmarket load every day at 06:30 Europe/Madrid; retry at 08:00 if it failed (replaces D-F4-1's 09:30). The job validates the load (files, rows, new products) and records the result. Planned right after M-b/M-c. |
| Auto-match (D-F4-2) | Yes after every load, clear cases only. Doubtful cases go to a review list; the planner analyses them to add matching criteria and automate as much as possible. |
| "Scraping" scope | Three sources: the official Riot card gallery; collection CSV import/export (F3); Cardmarket products, both singles and sealed (boxes, cases, sleeves, …). |
| Riot sync | The admin creates the set and enters its release date by hand (the set's name/code may change until the first card is revealed). From 21 days before the release date: card extraction at 08:00 and 14:00 Europe/Madrid. From the release date for 14 days: once a day. Afterwards: once a month. New cards are always inserted. Changes to existing cards are applied automatically inside the active windows (pre-release and 14 days after); in the monthly run they go to an admin approval table (field, old value, new value; approve/reject). The gallery provides no release date. |
| Catalog admin | Built together with the Riot sync, before the rest of the catalog (pulls F10-a, F10-e, F10-f forward; F10 user admin still waits for F9). |
| Bans (D-F2-2) | Per card name (all printings), two modes 1v1 and 2v2. The legacy `rbcar_banned` flag is not used as a source (the scraper resets it); the initial data comes from the official ban list provided by the owner. |
| Playset (D-F3-1) | Replaces the legacy `rbcol_playset`. User profile setting "playset size", default 3, editable. A per-card check "keep a playset" on each collection card. When a checked card's kept copies (counted per card name, all printings) fall below the profile value, the UI warns and highlights the line/tile in red. No blocking. The legacy `rbcol_selling = 'S'` value is evaluated and removed in F3. |
| Products (new phase) | New section for sealed Cardmarket products (boxes, cases, sleeves, …): price and history, and quantity owned. Their value is a separate "products" total, not added to the cards' collection value. After F3. |
| Legacy price CSV (D-F10-6) | Drop it (it only listed `set;name;id;N` for every card, without prices). The Cardmarket sales export of F7 is a different feature and stays. |
| Rules app (new phase) | After production, before events. Select cards that interact; the answer comes only from the official rule documents (Core Rules, Tournament Rules, FAQ). Previous queries are stored and returned when repeated. Needs an AI service (paid per query) and semantic (vector) search, Obsidian-like linking. Specified when the phase starts. |
| Mulligan / opening hands (D-F5-6) | Separate section, after production (F5-k split out of F5). Needs the official rules from the owner. |
| Events (D-F8-1) | After production and after the Rules app. Start with an upcoming-events calendar scraped from the official site; past events when a source exists. |
| Landing | The current landing is a draft with placeholder content; rebuilt with the events work. |
| Google/Discord login | Kept in F9, done just before production (owner creates the OAuth apps with a step-by-step guide). |
| Repo history | Private IPs/domain are removed from files only; history is not rewritten (no secret was committed that is still valid). |
| Spanish enum names (D-F2-12) | Taken from the official Spanish card gallery (`es-es`) by the implementer; the owner is asked only if they are not there. The dev DB holds English values (the scraper reads `en-us`). |
| Real enum values (D-F2-1) | The implementer queries the dev PostgreSQL database read-only (data there is real). |
| Job runner | Built once in F4-a (`rbjobs` + `flask jobs run-pending`); F10-d and every later phase only register job kinds. |

## Owner inputs still pending

| Input | Needed for |
|---|---|
| Official ban list (cards and mode) | F2-a |
| Collection CSV samples (Cardmarket, piltoverarchive, own spreadsheets, …) | F3-e, at the start of F3 |
| Deck export samples (riftdecks, piltover) | F5-e, at the start of F5 |
| Official opening hand and mulligan rules | Mulligan section |
| Google and Discord OAuth apps (guided) | F9-f, before production |
| Past events source | F8 |
