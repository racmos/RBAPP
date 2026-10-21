# F2-l: Card thumbnails (optional)

| Field | Value |
|---|---|
| Phase / unit | F2 / l |
| Branch | `feat/f2l-card-thumbnails` (from up-to-date `main`) |
| Depends on | F2-b merged (`card_summary`, `image_thumb_src` always null today) |
| Size forecast | ~350 authored lines (tests and docs included) |
| Risk | `Risk: item 5 (new Python dependency Pillow, pinned; deploy needs pip install and a one-off generation run)` |
| TDD | ON (strict). Runners: `venv/bin/pytest` (backend), `cd frontend && npx vitest run` (frontend, untouched) |
| Save as | `docs/requirements/F2/F2-l-card-thumbnails.md` (commit this document verbatim in the first commit if it is not in the repo yet) |

## Objective

Catalog grids, lists and pickers load small WebP thumbnails (about 15-25 KB) instead of the 200 KB card PNGs,
so a page of 48 cards weighs under 1 MB on a phone and many more cards fit in the offline image cache. The
full image is still used in the card detail.

## Read first

- `AGENTS.md` (stack table is checked by `tests/test_docs.py`), `docs/knowledge/conventions.md`, `docs/knowledge/ops-runbook.md`
- `docs/requirements/F2/README.md` (F2-R15; D-F2-10)
- `openspec/specs/card-images/spec.md` (IMG-1..3), `app/models/card.py` (`card_image_folder`, `image_src`),
  `app/services/card_images.py`, `app/services/riot_scraper.py` (image download step), `app/cli/__init__.py`,
  `app/services/catalog.py::card_summary`, `requirements.txt`, `.gitignore`

## Scope

In:
- Pillow pinned in `requirements.txt`.
- `app/services/card_thumbs.py` (paths, generation, existence index).
- `flask images thumbs` CLI; scraper generates the thumb after each downloaded image.
- `image_thumb_src` filled in `card_summary` / `CardMini`.

Out (do not do, even if tempting):
- AVIF, multiple sizes, `srcset` density variants, changing the full images, serving through Nginx.

## Specs

S1. Dependency: `Pillow==<latest release at implementation time that is at least two weeks old>` (exact
    pin, with WebP support) in `requirements.txt`; CI installs it; nothing else is added.

S2. Paths (`app/services/card_thumbs.py`): thumbnail of image `<prefix>_<id>.png` lives at
    `<static>/images/card-thumbs/<folder>/<stem>.webp`, where `<folder>` is `card_image_folder(image, set_id)`
    (IMG-1) and `<stem>` the file name without extension; public URL
    `/riftbound/static/images/card-thumbs/<folder>/<stem>.webp`. `thumb_path` refuses anything that resolves
    outside `<static>/images/card-thumbs/` (same rules as `card_image_path`, ValueError). `.gitignore` adds
    `app/static/images/card-thumbs/`.

S3. `make_thumb(src_path, dest_path)`: width 240 px, height proportional (352×492 → 240×335), Lanczos,
    WebP quality 80, method 6, metadata stripped; writes to a temp file in the same folder and renames
    (atomic). Returns the size in bytes.

S4. CLI `flask images thumbs [--set SET] [--force]`: for every `rbcards` row with an `image` (optionally one
    set), generate the thumb when it is missing or older than the source (`--force` regenerates). Output one
    final line `Thumbnails: <created> created, <skipped> up to date, <missing> source missing, <failed> failed.`
    and, for each failure, `Failed <set>/<id>: <reason>` (never a stack trace). Exit 0 unless every attempted
    image failed (exit 1). Idempotent.

S5. Scraper: after an image is downloaded (or already exists) the thumb is generated if missing; a thumb
    failure is logged and counted in the step message (`…, N thumbnails`), never aborts the run.

S6. `image_thumb_src` in `card_summary` and `CardMini` = the thumb URL when the file exists, else `null`.
    Existence uses a per-folder index (`os.scandir` of the thumbs folder) cached in memory and refreshed when
    the folder's mtime changes; at most one `scandir` per folder per request (test with a counter).

S7. Docs: `AGENTS.md` (CRLF) lists `card_thumbs.py`, the CLI and the thumbs folder; `docs/knowledge/ops-runbook.md`
    "Service operations": `venv/bin/flask images thumbs` and that it must run once after this deploy; `docs/api.md`
    notes `image_thumb_src`.

## API / data contract

`CardSummary.image_thumb_src` / `CardMini.image_thumb_src` become non-null when the thumbnail exists. No migration.

## UI

none (F2-e `CardImage` already prefers `image_thumb_src` for `thumb`/`tile`).

## Acceptance criteria

- [ ] AC1 `tests/test_card_thumbs.py`: path rules incl. promo prefix folder and traversal refusal; `make_thumb` output size 240×335 WebP from a generated 352×492 PNG fixture (made with Pillow in the test, no binary in the repo); atomic write (S2, S3).
- [ ] AC2 `tests/test_images_cli.py`: created/skipped/missing/failed counts and lines, `--set`, `--force`, exit codes (S4).
- [ ] AC3 `tests/test_riot_scraper_thumbs.py` (new; the HTTP session and the gallery JSON are mocked, no internet): thumb generated after download, failure counted in the step message, run continues (S5).
- [ ] AC4 `tests/test_catalog_service.py`: `image_thumb_src` null/non-null and one scandir per folder (S6).
- [ ] AC5 Full lanes green: `venv/bin/pytest`; `cd frontend && npm run lint && npm run typecheck && npx vitest run && npm run build && npm run check:dist`
- [ ] AC6 `docs/knowledge/state.md` updated (what changed, PR number placeholder, follow-up: run `flask images thumbs` on deploy)
- [ ] AC7 Docs updated (S7); `tests/test_docs.py` green.

## Delivery

- Conventional Commits; commit messages end with the attribution lines the session supplies.
- Push and PR only when the user says so. PR title: `feat(images): WebP card thumbnails (F2 unit l)`.
  PR body: summary, specs → tests map (S# → test file::name), average thumb size measured on the dev images,
  manual checks, rollback (revert; delete `app/static/images/card-thumbs/`).
- Never merge. The user merges.

## After merge (user asks gentle-shell, or does it)

- Deploy to dev with `docs/knowledge/ops-runbook.md`: `pip install -r requirements.txt`, restart, then
  `venv/bin/flask images thumbs` (report the summary line).
- Live checks: `GET <URL>/riftbound/static/images/card-thumbs/ogn/ogn_1.webp` → 200 `image/webp`;
  `GET /riftbound/api/v1/cards?per_page=1` → `image_thumb_src` not null.
- Manual checks for the user: the catalog on the phone loads visibly faster; thumbnails look sharp at tile size.

## Open questions

- CONFIRM D-F2-10: generate WebP thumbnails with Pillow (new dependency).
