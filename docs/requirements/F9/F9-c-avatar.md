# F9-c: Avatar upload and serving

| Field | Value |
|---|---|
| Phase / unit | F9 / c |
| Branch | `feat/f9c-avatar` (from up-to-date `main`, F9-b merged) |
| Depends on | F9-b (`rbuserprofile.rbupf_avatar_file`, `rbupf_avatar_version`, `avatar_url` in the payloads) |
| Size forecast | ~400 authored lines (tests and docs included) |
| Risk | `Risk: item 5 (new pinned dependency Pillow) + item 2 (untrusted image parsing of user uploads)` |
| TDD | ON (strict). Runner: `venv/bin/pytest` (backend only) |
| Save as | `docs/requirements/F9/F9-c-avatar.md` |

## Objective

A user can upload a profile photo from any common image file, and remove it. The server checks the file
is really an image, fixes its orientation, strips every metadata (location included), crops it to a
square and stores two small WebP versions. Signed-in users see each other's photos; anonymous visitors
never do. No screen here (F9-i).

## Read first

- `AGENTS.md` (Card images section: the pattern to copy; Configuration; Security), `docs/knowledge/conventions.md`
- `docs/requirements/F9/README.md` (D-F9-10, D-F9-12), `F9-b-profile-reauth.md` (S6, S7)
- `config.py` (`_images_dir_setting`, `CARD_IMAGES_DIR`, `PRODUCT_IMAGES_DIR`), `app/services/card_images.py`,
  `app/services/product_images.py`, `app/api/admin/cards.py` (`MAX_IMAGE_BYTES`, upload pattern),
  `app/routes/media.py`, `app/errors.py`
- `requirements.txt`, the technology table of `AGENTS.md`, `.env.example` (CRLF), `README.md` (CRLF)
- `tests/conftest.py` (`card_images_dir` fixture pattern)

## Scope

In:
- Pillow pinned in `requirements.txt` and the `AGENTS.md` technology table
- `AVATAR_DIR` setting, `app/services/avatars.py` (the only module that knows the directory)
- `POST /me/avatar`, `DELETE /me/avatar`, `GET /users/<id>/avatar`
- `avatar_url` filled in `user_payload` and `GET /me`
- Error codes `image_invalid`, `file_too_large`; a JSON 413 handler
- Re-created guards: dependency pin check, `.env.example` ↔ `README.md` check (each created only if absent)

Out (do not do, even if tempting):
- Any UI (F9-i: upload with preview, topbar avatar)
- Client-side cropping, animated avatars, avatars for anonymous viewers, a public profile page
- Changing card or product image handling

## Specs

S1. Dependency: `Pillow==<version>` in `requirements.txt` (newest release published at least two weeks
    before the install day, `docs/knowledge/conventions.md` section 5 practice; record version and
    publish date in the PR) and a `Pillow` row in the `AGENTS.md` technology table with the same
    version. No other new package.
S2. `AVATAR_DIR` (config, `.env.example`, `README.md`): absolute path; unset or blank =
    `<project>/data/avatars` (git-ignored `/data/`); a relative path stops the app with `ConfigError`
    naming `AVATAR_DIR` (same helper as `CARD_IMAGES_DIR`). The directory is created on first write.
    `app/services/avatars.py` is the only module that reads it (`avatars_root()`, `avatar_path(stem,
    size)`, `avatar_url(user_id, version)`). Tests use a new `avatar_dir` fixture (temporary directory)
    and never touch a real path.
S3. `POST /me/avatar` (U, `multipart/form-data`, field `file`): a request body over 5 MB + 64 KB is
    refused before it is read (per-request `request.max_content_length`) and a file over 5 MB
    (5,242,880 bytes) is refused → 413 `{error: "Payload Too Large", message: "The file is too large",
    code: "file_too_large", params: {max_mb: 5}}`; no `file` part → 400 `validation_error` (field
    `file`, `required`). Limited to `20/hour` per IP (`scope='avatar'`, 21st → 429 `rate_limited`).
S4. The format is decided by Pillow only (never the file name or the `Content-Type`): `Image.open` +
    full decode inside a guard; accepted formats `JPEG`, `PNG`, `WEBP`, `GIF` (first frame only). Every
    other format, a truncated or corrupt file, an image over 25 megapixels (decompression-bomb guard:
    the warning is treated as an error) or smaller than 64 px on either side → 400 `{error:
    "Validation Error", message: "The file is not a supported image", code: "image_invalid"}`. Nothing
    is written on any refusal.
S5. Processing: `ImageOps.exif_transpose` (orientation), convert to RGB (RGBA when the source has
    alpha), centre square crop to the shorter side, resize with LANCZOS to 256×256 and 64×64, save each
    as WebP quality 85 **without** EXIF, XMP or ICC data. The stored files carry no metadata of the
    upload (a test uploads a JPEG with an EXIF GPS block and an orientation tag and checks the output
    has no EXIF and the right orientation).
S6. Storage: new version `n = rbupf_avatar_version + 1`; stem `<user_id>-<n>`; files
    `<stem>-256.webp` and `<stem>-64.webp` written to a temporary name in `AVATAR_DIR` and moved into
    place with `os.replace`; then the profile row (created if missing) gets `rbupf_avatar_file = stem`,
    `rbupf_avatar_version = n`, `rbupf_updated_at = now`, committed; then the previous version's files
    are deleted (a failure to delete is logged, never an error). Response 200 `{avatar_url}`.
S7. `DELETE /me/avatar` (U) → 200 `{avatar_url: null}`: clears `rbupf_avatar_file`, increments the
    version (so cached URLs change), deletes the files. Without an avatar it answers the same and
    changes nothing.
S8. `avatar_url` (in `user_payload` and `GET /me` `profile`) = `/riftbound/api/v1/users/<id>/avatar?v=<n>`
    when the user has an avatar, else `null`.
S9. `GET /users/<int:id>/avatar?size=256|64&v=<n>` (U, endpoint `api_v1.user_avatar`): any signed-in
    user may read any user's avatar (D-F9-12); anonymous → 401 `unauthenticated` (never the image).
    `size` absent = 256; any other value → 400 `validation_error`. Unknown user or no avatar → the 404
    envelope. 200: `image/webp`, `X-Content-Type-Options: nosniff`, `Cache-Control: private,
    max-age=31536000, immutable` when `v` equals the current version, otherwise `private, no-cache`;
    never `public`. The file path is built only from the stored stem and the size (no client text
    reaches the file system).
S10. JSON 413: `app/errors.py` handles `RequestEntityTooLarge` with the `wants_json()` rule (JSON:
    S3 body; HTML: the inline error page). Error name `Payload Too Large` is added to the list in
    `AGENTS.md`.
S11. Error codes (enum, `errors.json`, catalog test): `image_invalid` (400) → "That file is not a
    supported image. Use a JPEG, PNG, WebP or GIF of at least 64 by 64 pixels."; `file_too_large`
    (413) → "The file is too large (maximum {{max_mb}} MB)."
S12. Guards re-created (each only if absent; extend when present): `tests/test_dependency_pins.py`
    (every requirement line is `name==version`; each package named in the `AGENTS.md` technology table
    shows the pinned version, Pillow included); `tests/test_env_docs.py` (every variable of
    `.env.example` appears in `README.md`). Edits to `.env.example` and `README.md` keep their CRLF
    endings (conventions section 8).

## API / data contract

| Method | Path (prefix `/riftbound/api/v1`) | Auth | Endpoint name | Response |
|---|---|---|---|---|
| POST | `/me/avatar` | U | `api_v1.upload_my_avatar` | `{avatar_url}` / 400 `image_invalid` / 413 `file_too_large` |
| DELETE | `/me/avatar` | U | `api_v1.delete_my_avatar` | `{avatar_url: null}` |
| GET | `/users/<int:id>/avatar` | U | `api_v1.user_avatar` | WebP bytes |

No migration (columns from `0030_user_profile`). `docs/api.md`: "Avatar (F9-c)".

## UI

none (F9-i).

## Acceptance criteria

- [ ] AC1 `tests/test_avatars.py` (service): every accepted format; refused formats (BMP, TIFF, SVG
      text, plain text), truncated JPEG, 63-px side, over-25-megapixel header; square crop of a
      landscape and a portrait; EXIF orientation applied; no EXIF/ICC in the output; both sizes; temp
      files never left behind (S4-S6)
- [ ] AC2 `tests/test_api_avatar.py`: upload → `avatar_url` with the new version in `/auth/session` and
      `GET /me`; previous files deleted; 5 MB boundary (exactly 5,242,880 bytes accepted, one more
      refused) and the oversized body refused before reading; missing part; delete (twice);
      rate limit with `limited_app`; nothing written on refusal (S3, S6-S8)
- [ ] AC3 `tests/test_api_avatar.py::TestServe`: another signed-in user reads it; anonymous 401; size
      64/256/other; unknown user and no avatar 404; cache headers for current and stale `v`; no `public`
      (S9)
- [ ] AC4 `tests/test_config.py` extended: `AVATAR_DIR` default, absolute, relative → `ConfigError`
      naming the variable only (S2); `tests/test_error_responses.py` (or new) for the JSON/HTML 413 (S10)
- [ ] AC5 Error catalog test green with both codes; authz matrix: the three endpoints → `U`;
      `tests/test_dependency_pins.py` and `tests/test_env_docs.py` green (S11, S12)
- [ ] AC6 `bandit -r app/ -ll` clean
- [ ] AC7 Full lanes green: `venv/bin/pytest`; `cd frontend && npm run lint && npm run typecheck &&
      npx vitest run && npm run build && npm run check:dist`
- [ ] AC8 Docs: `docs/api.md` "Avatar (F9-c)"; `AGENTS.md` (technology table, Configuration table
      `AVATAR_DIR`, tree `app/services/avatars.py`, API list, error names); `.env.example`, `README.md`;
      `docs/knowledge/ops-runbook.md` (where avatars live, included in the backup scope note);
      `docs/knowledge/state.md`

## Delivery

- Conventional Commits; commit messages end with the attribution lines the session supplies.
- PR title: `feat(account): avatar upload, metadata strip and serving (F9 unit c)`. PR body: S# → tests,
  Pillow version and publish date, rollback (revert; uploaded files stay in `AVATAR_DIR`, harmless).
- Never merge. The owner merges.

## After merge

- Deploy to dev: `venv/bin/pip install -r requirements.txt` (Pillow), optionally set `AVATAR_DIR`
  (absolute) in the service environment, restart. No migration.
- Live checks: `POST /riftbound/api/v1/me/avatar` with a phone photo → 200; the returned URL answers
  `image/webp` 256×256; a second account reads it; a private window gets 401.
- Manual checks for the owner: none (no screen yet).

## Open questions

none
