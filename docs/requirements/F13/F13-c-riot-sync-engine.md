# F13-c: Riot sync engine — diff, auto-apply vs approval, `riot_sync` job

| Field | Value |
|---|---|
| Phase / unit | F13 / c — batch 1, unit 4 |
| Branch | `feat/f13c-riot-sync-engine` (from the F13-b branch) |
| Depends on | F13-a, F13-b, F4-a (stack / main) |
| Size forecast | ~600 authored lines |
| Risk | `Risk: item 1 (writes the card catalog from an external page) + item 6 (diff rules; the gallery format can change)` |
| TDD | ON (strict). Runner: `venv/bin/pytest`. No network: gallery HTML and images come from fixtures / mocks |
| Sources | F13 phase spec (F13-R2, R3, R12-R18, R24, R26, data model), `decisions-2026-10-25.md` (D-F13-3…11, 18, 19) |

## Objective

One sync engine keeps the catalog in line with the official Riot gallery: it always inserts new cards, and
for existing cards it applies changes by itself around a release (pre-release and the 14 days after) while
every change found in the monthly run waits in an approval table. It runs as the `riot_sync` job; the legacy
Jinja button only queues it.

## Read first

- `app/services/riot_scraper.py` (fetch, `__NEXT_DATA__`, `_parse_card`, `_download_image`, `extract_riot_cards`)
- `app/routes/domains/price.py` (`refresh_riot_sets`, `extract_riot_cards` routes) and the Riot section of
  `app/templates/price.html` (what its JS reads from the response)
- `app/jobs/` (registry, `daily_prices.py`), `app/services/jobs.py` (`enqueue`, `JobAlreadyActive`),
  `app/models/job.py` (`JOB_KINDS`), `migrations/versions/0008_jobs_daily_prices.py` (how a kind is added)
- `app/services/audit.py` (F13-a), `app/services/card_images.py` (M-d), `app/models/set.py`, `app/models/card.py`

## Scope

In: fetch/parse split, `app/services/riot_sync.py`, window calculator, `rbcardchanges`, kind `riot_sync`,
legacy button → queue. Out: schedule and timers (F13-d), HTTP API and UI (F13-e…g), deleting cards.

## Specs

S1. Split the scraper: `fetch_gallery() -> GalleryData` returns `{cards: [parsed dicts as today from
    `_parse_card`], set_codes: [sorted codes], unparsed: int}`; one GET of the `en-us` gallery; network or
    page-format errors raise `GalleryError(message)` (message without URLs or stack). The old
    `extract_riot_cards` write path is removed; `refresh_riot_sets` stays as it is.
S2. Window calculator `window_for(release_date: date | None, today: date) -> str` (pure, in
    `app/services/riot_sync.py`): `None` date → `monthly`; `today < R−21` → `none`; `R−21 ≤ today ≤ R−1` →
    `pre_release`; `R ≤ today ≤ R+13` → `post_release`; `today ≥ R+14` → `monthly`. `today` is the
    Europe/Madrid local date of the run (`zoneinfo`). Active windows = `pre_release`, `post_release`.
S3. `sync(set_codes: list[str] | None, trigger: str, now: datetime) -> dict` (one DB transaction per set; a
    failure in one set rolls back that set only and is reported):
    - Fetch once (S1). A `GalleryError` → raise `JobFailed(message)`; nothing written.
    - Sets to process: `set_codes` (validated against `rbset` ∪ gallery codes) or every gallery code.
    - Missing set (gallery code without `rbset` row, D-F13-4): create it (name = code, `rbset_outdat` NULL,
      `rbset_ncard` = gallery count) and list it in `result.placeholder_sets`; audit `set.create` with the
      system actor.
    - `rbset_ncard` is written only when it is NULL (D-F13-18).
S4. New card (key not in `rbcards`): insert with every synced field and `rbcar_banned = 'N'` (column default
    semantics; the sync never writes it afterwards, D-F13-10); download its image when missing on disk
    (`card_image_path`); audit one `riot.insert` row per set with `details: {"cards": [ids…]}` (system actor).
S5. Existing card — synced fields: `rbcar_name`, `rbcar_domain`, `rbcar_type`, `rbcar_tags`, `rbcar_energy`,
    `rbcar_power`, `rbcar_might`, `rbcar_ability`, `rbcar_rarity`, `rbcar_artist`, `image_url`, `image`.
    Values are compared as stored (numbers as ints, texts exact, NULL vs empty text treated as equal).
    - Window active (S2) for the card's set: apply every difference at once; audit one `riot.apply` row per card,
      `details: {"fields": {"rbcar_name": [old, new], …}}` (system actor). When `image_url` changes, download
      the new image over the card's file name (D-F13-8).
    - Window `monthly` or `none`: do not apply. For each different field create or update one `pending` row in
      `rbcardchanges` (update `new_value`, `detected_at` and `job_id` when a pending row exists for that card
      and field); skip it when the latest `rejected` row of that card and field has the same `new_value`
      (D-F13-7).
S6. Cards in `rbcards` of a processed set that are not in the gallery: never touched; counted (D-F13-9).
S7. Result (returned by `sync`, stored as the job result):
    ```json
    {"trigger": "manual", "today": "2026-11-02", "gallery": {"cards": 812, "unparsed": 0, "set_codes": ["OGN", "OGS"]},
     "placeholder_sets": [], "sets": [{"set_id": "OGN", "window": "monthly", "inserted": 0, "applied": 0,
     "proposed": 3, "unchanged": 295, "missing_from_gallery": 1, "images": {"downloaded": 0, "existing": 298, "failed": 0},
     "error": null}]}
    ```
    `error` is a sanitised message (F13-R3) when that set's transaction failed.
S8. Table `rbcardchanges` (migration `00NN_card_changes`), model `RbCardChange` in `app/models/card_change.py`,
    exactly as the phase spec "Data model changes" (`rbchg_` prefix; FK to `rbcards` ON UPDATE CASCADE
    ON DELETE CASCADE; `field` CHECK IN the S5 list; `status` CHECK IN (`pending`, `approved`, `rejected`);
    `job_id` FK `rbjobs` ON DELETE SET NULL; `decided_by` FK `rbusers.id` ON DELETE SET NULL; partial unique
    index `uq_rbcardchanges_pending` on (`rbchg_rbset_id`, `rbchg_rbcar_id`, `rbchg_field`) WHERE status =
    'pending'). Values stored as text (numbers as decimal strings, NULL as NULL).
S9. Kind `riot_sync` (`app/jobs/riot_sync.py`, timeout 1800 s): params `trigger` (`schedule`|`manual`,
    default `manual`), `sets` (comma-separated codes, optional), `slot` (`am`|`pm`, used by F13-d; ignored
    here). Unknown params or values → `JobFailed('riot_sync: invalid params')`. Migration
    `00NN_jobs_riot_sync` extends `ck_rbjobs_kind` and `JOB_KINDS` (same pattern as 0008).
S10. Legacy Jinja (D-F13-11): `POST /riftbound/price/extract-riot-cards` queues `riot_sync` with
     `trigger=manual` and the requested sets, and answers `{"success": true, "job_id": n, "message":
     "Sincronización encolada (trabajo n). Revisa el resultado en la nueva administración."}`; when one is
     active → `{"success": false, "message": "Ya hay una sincronización en curso."}` (HTTP 409). Adapt the JS
     of `price.html` minimally to show the message (it no longer receives `steps`/`stats`).
S11. Docs: `AGENTS.md` (kind list, `rbcardchanges`, "only the Riot sync writes cards from the gallery"),
     `docs/knowledge/ops-runbook.md` → "Scheduled jobs" (run by hand: `flask jobs enqueue riot_sync --param
     trigger=manual [--param sets=OGN,OGS]`), `state.md` (remove the "scraper resets rbcar_banned" known issue).

## API / data contract

Job result as S7. No HTTP endpoint (F13-e).

## UI

Legacy Jinja message of S10 only (ES text as written; the Jinja page is Spanish-only).

## Acceptance criteria

- [ ] AC1 `tests/test_riot_window.py`: `R−22`, `R−21`, `R−1`, `R`, `R+13`, `R+14`, `None`, and both DST changes of Europe/Madrid for `today` (S2).
- [ ] AC2 `tests/test_riot_sync.py` with a fixture gallery (`tests/fixtures/riot/gallery.html`, a small `__NEXT_DATA__` with two sets): insert new cards; placeholder set; `rbset_ncard` only when NULL; auto-apply in an active window with audit; proposals in `monthly`; existing pending row updated; rejected value not proposed again; NULL vs empty equal; cards missing from the gallery untouched; one set failing does not roll back the other; `rbcar_banned` never written; `GalleryError` → nothing written (S3-S7).
- [ ] AC3 `tests/test_riot_sync_job.py`: kind registered, params validation, result stored, one active job at a time (S9); migrations round trip + drift for both revisions (S8, S9).
- [ ] AC4 `tests/test_legacy_riot_button.py`: queues the job, 409 when active, admin only (S10).
- [ ] AC5 Full lanes green; docs and `state.md` (S11).

## Delivery

PR title: `feat(riot): sync engine with auto-apply windows, change table and riot_sync job (F13 unit c)`.

## After merge

Deploy (backup first: `card_changes`, `jobs_riot_sync`). Live: `flask jobs enqueue riot_sync --param
trigger=manual` and, a minute later, read the result (runbook one-liner); expect 0 inserted and proposals
only for sets in `monthly`.

## Open questions

none

## Log

- L1 (implementer): `sync` takes an optional `job_id` keyword (default `None`) so the
  handler can stamp the job on the rows it proposes; the positional contract
  `(set_codes, trigger, now)` is unchanged.
- L2 (implementer): an unknown code in `set_codes` fails the whole job
  (`riot_sync: unknown set(s): …`) instead of being skipped; the retry then shows the cause.
- L3 (implementer): `window_for` takes plain dates; the Madrid conversion lives in
  `today_madrid` (D-F13-19 window calculator stays pure and DST is tested at the boundary).
- L4 (implementer): the old `extract_riot_cards` write path is removed (S1); the M-d scraper
  image tests now drive the new engine and `test_error_responses.py` lost its extract entry
  (the route answers 200/409, never 500).
