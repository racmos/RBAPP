# M-d: Card images out of git, into a data directory

| Field | Value |
|---|---|
| Phase / unit | M (maintenance) / d — batch 1, unit 1 (`docs/requirements/BATCH-1.md`) |
| Branch | `chore/m-d-card-images` (from `origin/main`) |
| Depends on | F2-a merged (#34) |
| Size forecast | ~350 authored lines (tests and docs included); the deletion of 376 tracked images is not counted |
| Risk | `Risk: item 1 (the deploy would delete the images from the deployed checkout if the copy step is skipped) + item 5 (new setting and route on the server)` |
| TDD | ON (strict). Runner: `venv/bin/pytest` |
| Decisions | `docs/knowledge/decisions-2026-10-25.md` → D-Md-1 … D-Md-3 |

## Objective

Card images stop living in git and in the code tree. They are read and written in a data directory set by
`CARD_IMAGES_DIR` and served at `/riftbound/media/cards/<folder>/<file>`. Every reader and writer (catalog,
Jinja pages, admin upload, Riot scraper) goes through one module, so F13 and F14 only use that module.

## Read first

- `app/services/card_images.py`, `app/models/card.py` (`card_image_folder`, `image_src`)
- `app/services/riot_scraper.py` (image download, around `card_image_path`), `app/routes/domains/cards.py`
  (`upload_card_image`), `app/templates/deck.html` (line with `/riftbound/static/images/cards/placeholder.png`)
- `config.py` (`FRONTEND_DIST` pattern: env value or a default path), `.gitignore`, `.env.example`
- `app/routes/spa.py` (`safe_join` use), `tests/test_authz_matrix.py`
- `docs/knowledge/ops-runbook.md` (deploy section), `docs/frontend.md` (precache rules: nothing under
  `/riftbound/static` or `/riftbound/api`)

## Scope

In: setting, media route, path module, every reader/writer moved to it, legacy copy command, untracking the
images, docs and runbook. Out: thumbnails (F2-l, batch 2), any change to image names or folders, CDN/Nginx
serving.

## Specs

S1. Setting `CARD_IMAGES_DIR` in `config.py`: the env value stripped, or the default
    `str(Path(__file__).resolve().parent / 'data' / 'card-images')`. It must be an absolute path after
    resolution; a relative value → `ConfigError('CARD_IMAGES_DIR must be an absolute path')`. The directory is
    created on first write, not at startup. `.env.example` documents it next to `FRONTEND_DIST`:
    `# CARD_IMAGES_DIR=/srv/riftbound/card-images   # absolute; default <project>/data/card-images`.
S2. `.gitignore` adds `/data/`. `app/static/images/cards/` keeps only `.gitkeep`; the 376 tracked images are
    removed from the index with `git rm --cached` (the files stay on disk in the worktree; the deployed
    server copies them first, see "After merge").
S3. `app/services/card_images.py` becomes the only place that knows the directory:
    - `images_root() -> str`: `current_app.config['CARD_IMAGES_DIR']`.
    - `card_image_path(image, set_id=None) -> str`: same validation and messages as today, rooted at
      `images_root()` instead of `<static>/images/cards` (signature loses `static_folder`; update every caller).
    - `card_image_url(image, set_id=None) -> str | None`: `/riftbound/media/cards/<folder>/<image>` or `None`
      when there is no image or no safe folder.
    - `RbCard.image_src` returns `card_image_url(self.image, self.rbcar_rbset_id)`.
S4. Route `GET /riftbound/media/cards/<folder>/<filename>` on a new blueprint `media` (`app/routes/media.py`),
    endpoint `media.card_image`, class `P` in the authz matrix:
    - `folder` must be letters and digits only and `filename` a plain file name (same rule as
      `card_image_path`); otherwise 404.
    - Served with `send_from_directory(images_root(), f'{folder}/{filename}')`; missing file → 404;
      `Cache-Control: public, max-age=604800` (7 days).
    - Never touches the session (no `Set-Cookie`), like the SPA blueprint.
S5. Writers: the Riot scraper image download and the Jinja admin `upload_card_image` write through the new
    `card_image_path` (create the folder with `os.makedirs(..., exist_ok=True)`). Behaviour otherwise unchanged.
S6. `app/templates/deck.html`: the hard-coded placeholder URL becomes an inline neutral SVG data URI (the old
    file does not exist in the repo); verify with `git ls-files app/static/images/cards/placeholder.png` —
    if the file exists, keep it in git as an app asset under `app/static/images/placeholder-card.png` and point
    the template there instead.
S7. CLI `flask images import-legacy [--source PATH]` (`app/cli/images.py`, registered like the other groups):
    copies every file under `--source` (default `<app static>/images/cards`) into `CARD_IMAGES_DIR`,
    keeping `<folder>/<file>`, never overwriting an existing file, skipping anything that is not a plain file in
    a letters-and-digits folder; prints `Copied <n>, skipped <m> existing, ignored <k>.` and exits 0. Running it
    twice copies 0 the second time.
S8. Docs: `AGENTS.md` (setting, media route, "card images live in CARD_IMAGES_DIR, never in git"; CRLF kept),
    `docs/knowledge/architecture.md` (images), `docs/knowledge/ops-runbook.md` new section "Card images"
    with the deploy procedure of "After merge", `docs/knowledge/state.md` (remove the "376 card images tracked
    in git" known issue; M-d row; pending check for the server copy).

## API / data contract

`GET /riftbound/media/cards/<folder>/<filename>` → 200 image (type from the extension), 404 otherwise. No
JSON. `image_src` in every existing payload (Jinja templates, `GET /bans` is unaffected) changes prefix.

## UI

none (images keep showing in the Jinja pages through `image_src`).

## Acceptance criteria

- [ ] AC1 `tests/test_card_images.py`: `card_image_path` rooted at a temp `CARD_IMAGES_DIR` (fixture), every refusal case (`..`, slash, backslash, NUL, unsafe folder, symlink escape); `card_image_url` and `image_src` values (S3).
- [ ] AC2 `tests/test_media_route.py`: 200 with the right type and `Cache-Control`, 404 missing, 404 bad folder, 404 traversal attempts, anonymous access, no `Set-Cookie` (S4); authz matrix classifies `media.card_image` as P.
- [ ] AC3 `tests/test_config.py` (create): default path, absolute env path, relative value → `ConfigError` (S1).
- [ ] AC4 `tests/test_images_cli.py`: copy, skip existing, ignore unsafe names, idempotent second run, message text (S7).
- [ ] AC5 `git ls-files app/static/images/cards` prints only `app/static/images/cards/.gitkeep` (S2).
- [ ] AC6 Full lanes green; docs and `state.md` updated (S8).

## Delivery

PR title: `chore(images): card images in CARD_IMAGES_DIR, served at /riftbound/media (M-d)`. The PR body
starts with the server step of "After merge" in bold.

## After merge (server, before or together with the deploy that pulls this commit)

1. **Before pulling**: create the directory (outside the checkout), owned by the service user, and copy the
   images: `cp -a <checkout>/app/static/images/cards/. <CARD_IMAGES_DIR>/` (or, after the pull, the files are
   gone from the checkout: restore them from the previous commit with `git -C <checkout> archive <old sha>
   app/static/images/cards | tar -x -C /tmp/cards-restore` and run `flask images import-legacy --source …`).
2. Set `CARD_IMAGES_DIR` in `.env`, deploy, restart, run `flask images import-legacy` (copies 0 if step 1 was
   done).
3. Live check: open a Jinja catalog page; images load from `/riftbound/media/cards/…`; `curl -sI` one image →
   200 with `Cache-Control: public, max-age=604800`.

## Open questions

none
