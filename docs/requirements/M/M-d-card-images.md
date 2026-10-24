# M-d: Card images out of git, into a data directory

| Field | Value |
|---|---|
| Phase / unit | M (maintenance) / d |
| Branch | `chore/m-d-card-images` (from up-to-date `main`) |
| Depends on | F2-a merged and deployed (#34) — done |
| Size forecast | ~250 authored lines (config, one route, call sites, tests, docs). The removal of the tracked images is not counted. |
| Risk | `Risk: item 1 (the deployed checkout loses the tracked images on the next pull), item 5 (deploy order and a new setting on the server), item 2 (a public file-serving route: path traversal)` |
| TDD | ON (strict). Runner: `venv/bin/pytest`; image tests use a temporary directory, never the repo's images |
| Written by | gentle-shell on the owner's instruction (2026-10-25, "si adelante"), from `docs/knowledge/decisions-2026-10-22.md` item 6 |

## Objective

Decision of 2026-10-22: "M-d Card images out of git, into a data directory outside the code tree (copy
first: removing them from the index would delete them from the deployed checkout on the next pull)."
Card images stay at the same public URLs (`/riftbound/static/images/cards/<folder>/<file>`), so no page,
API payload or PWA rule changes; only where the files live on disk changes.

## Specs

S1. Setting `CARD_IMAGES_DIR` (`config.py`, environment variable of the same name): absolute path of the
    card images root (the folder that holds `ogn/`, `ogs/`, `sfd/`, `unl/`, …). Unset or empty → the
    current location `<app static folder>/images/cards`. A relative path stops the app at startup with a
    `ConfigError` whose message names `CARD_IMAGES_DIR` and says it must be absolute. `.env.example` and
    `README.md` document it.
S2. `app/services/card_images.py`: `card_image_path(images_root, image, set_id=None)` takes the images root
    directly (no `images/cards` suffix added); every rule of today stays (plain file name, derived folder,
    resolved path must stay inside the root, symlinks followed). The admin upload
    (`cards.upload_card_image`) and the Riot scraper (step 4) pass `current_app.config['CARD_IMAGES_DIR']`.
S3. Route `GET /riftbound/static/images/cards/<path:filename>` (endpoint `card_images.serve`, its own small
    blueprint) serves files from `CARD_IMAGES_DIR` with `send_from_directory` (no traversal: `..`, absolute
    paths and symlinks outside the root → 404). Missing file → 404. Same caching as Flask's static files
    (conditional requests, `SEND_FILE_MAX_AGE_DEFAULT`). It wins over the generic static rule for that prefix;
    every other `/riftbound/static/...` URL is unchanged. Public (P) in `tests/test_authz_matrix.py`.
    `RbCard.image_src` is unchanged.
S4. Remove the tracked images from git (`git rm -r --cached` of `app/static/images/cards/ogn` and `.../ogs`;
    keep `app/static/images/cards/.gitkeep`). `.gitignore` already ignores the folder; add the data directory
    pattern only if a default inside the repo is introduced (it is not).
S5. Tests (temporary `CARD_IMAGES_DIR`): config default/override/relative-path error; `card_image_path`
    rules with the new root; upload writes into `CARD_IMAGES_DIR/<folder>/<file>` and the file is then served
    at its `image_src` URL with 200 and the same bytes; traversal attempts (`../`, encoded `%2e%2e`,
    absolute, a symlink pointing outside) → 404; missing → 404; an unrelated static file
    (`/riftbound/static/js/csrf.js`) still served; scraper step 4 resolves its destination under
    `CARD_IMAGES_DIR` (no network: mock the download); authz matrix classifies the new rule as P.
S6. Docs: `AGENTS.md` (structure, the setting, the route, "File uploads and image paths go through
    `app/services/card_images.py`"), `docs/knowledge/ops-runbook.md` (data directory: location, backup of the
    images, deploy order of S7, rollback), `docs/knowledge/state.md` (M-d row, the "376 card images tracked"
    known issue removed, next unit), `docs/requirements/README.md`, `docs/requirements/F12/README.md` only
    if it still says images move in F12-g. Line endings preserved (AGENTS.md, README.md, config.py,
    `.env.example`, `app/__init__.py`, `cards.py` are CRLF).
S7. Deploy order (gentle-shell, on the server, after merge), in the runbook:
    1. Copy every image (tracked and untracked) to the data directory
       (`cp -a app/static/images/cards/. <data dir>/`), compare file counts and total size.
    2. Add `CARD_IMAGES_DIR=<data dir>` to `.env`; restart; check an image URL answers 200 from the data
       directory (temporarily rename one source file to prove it is not served from the old place).
    3. `git pull` (removes the tracked images from the checkout), restart, check the same URLs again.
    4. Leave the untracked leftovers in `app/static/images/cards/` until the owner confirms; then delete.
S8. Lanes green: `pytest`; frontend untouched.

## Open questions

none

## Log

- L1 (owner, 2026-10-25): "si adelante" (to the plan: copy first, app reads a configurable data
  directory, remove the images from git, deploy in that order).
- L2 (gentle-shell): the data directory on the dev server is chosen (`<data dir>` here; the host
  value lives only in `.env` and `ops.local.md`, never in tracked files).
