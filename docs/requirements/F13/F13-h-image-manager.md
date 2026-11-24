# F13-h: Image manager — find cards and products without an image and upload one from the computer

| Field | Value |
|---|---|
| Phase / unit | F13 / h (owner feedback 2026-11-24) |
| Branch | `feat/f13h-image-manager` (from up-to-date `origin/main`) |
| Depends on | F13-b (card image upload), F14-d (product image upload), F9-c (Pillow, avatar pipeline) |
| Size forecast | ~900 authored lines (backend + frontend) |
| Risk | item 6 candidate: image bytes are re-encoded and written to disk; no data migration. `Risk: none` for stored data (only `rbcar_image` / `rbpdt_image` names change) |
| TDD | ON (strict). Backend `pytest`, frontend `npx vitest run`; nothing reaches the internet |
| Sources | Owner message 2026-11-24: "falta un apartado donde las cartas o productos sin imagen se pueda seleccionar una desde local para subirla. Al subirla debe crearse una nueva y redimensionarse a un formato óptimo y se guardará en el directorio con la nomenclatura." |

## Objective

After the production reset the cards created by hand (runes, promos, plated cards) and many products have no
image. Today an image can only be uploaded one card at a time from the edit form, as the raw file, with no
resize. Give the admin one screen that lists what lacks an image, lets them pick a file from their computer,
and stores a resized, optimised copy under the standard file name.

## Read first

- `app/services/card_images.py` (`images_root`, `card_image_path`, `card_image_url`), `app/models/card.py`
  (`card_image_folder`), `app/api/admin/cards.py` (`POST …/image`, `MAX_IMAGE_BYTES`),
  `app/services/catalog_admin.py` (`detect_image_ext`, `image_stem`).
- `app/services/product_images.py`, `app/api/admin/products.py` (`POST …/image`, `_remove_previous`).
- `app/services/avatars.py` (Pillow pipeline: bomb limits, `exif_transpose`, LANCZOS, WebP re-encode,
  temp file + `os.replace`) — the model to follow.
- `frontend/src/admin/CardsAdminPage.tsx` (`missing_image`), `ProductsAdminPage.tsx` (`no_image`),
  `CardEditor.tsx` / `ProductEditor.tsx` upload controls, `account/AvatarUpload.tsx`.

## Scope

In: a new admin screen, the image processing service, both existing upload routes using it, the
"image missing" filter that also finds a missing file, bulk upload by file name, tests, docs.
Out: changing the images already stored (no mass conversion), image CDN, cropping UI, Riot image download,
user avatars.

## Specs

- **S1 Screen.** Admin → **Images** (nav entry next to Cards and Products), tabs `Cards | Products`, URL
  `?tab=cards|products`. Each tab lists the items **without a usable image** with a thumbnail placeholder,
  name, code (`SET-id`, product kind), set, and a **Choose file** button; filters: search `q`, set (cards) or
  kind (products), and a switch `Include files missing on disk` (default on). Counters per tab. Paged
  50/100/200 like the other admin lists. Desktop table; phone cards.
- **S2 "Without a usable image"** = the image column is empty **or** the file named by it does not exist
  under `CARD_IMAGES_DIR` / `PRODUCT_IMAGES_DIR` (today only the column is checked, so a card whose file was
  lost is never found). New list parameter `image=missing|present|any` (default `any`) on `GET /admin/cards`
  and `GET /admin/products` (the older `missing_image` / `no_image` stay and map to `missing`); the existence
  check is batched per folder (no per-row filesystem call storm; at most one directory scan per folder).
- **S3 Pick and upload.** **Choose file** opens the computer's file picker (`accept` PNG, JPEG, WebP);
  drag-and-drop onto a row works too. A preview and the file's size show before sending. One upload per
  click; the row updates in place (thumbnail appears, row leaves the "missing" list after a refetch) with an
  Undo toast that restores the previous state (previous file kept until the toast expires, see S7).
- **S4 Processing (server, one shared service `app/services/image_upload.py`).** Accept PNG, JPEG, WebP by
  magic bytes only (never the client name or type); input limit **10 MB** and **25 megapixels**, minimum
  short side 200 px (card) / 120 px (product); decode with decompression-bomb warnings as errors;
  `exif_transpose`; drop all metadata; convert to RGB(A) as needed; **fit inside** a maximum size without
  upscaling and without cropping, keeping the aspect ratio: **cards 744 × 1039 px**, **products 800 × 800 px**
  (proposal: the card ratio is 5:7; 744 px wide is about 2× the largest on-screen tile);
  resize with LANCZOS; encode **WebP, quality 85** (lossless fallback never; `method=6`); the output is
  written to a temp file in the target folder and moved with `os.replace` (atomic). A failure leaves the
  previous image untouched and returns a 400 with the same `validation_error` shape as today
  (`invalid_format`, `out_of_range` with `params.max`, new `too_small`).
- **S5 Naming (`nomenclatura`).** A new file is always created, never overwritten in place:
  cards `CARD_IMAGES_DIR/<folder>/<set lower>_<card id lower>.webp` (e.g. `ogn/ogn_66.webp`,
  `ognx/ognx_66.webp`, `plat/plat_sfd189.webp`); the folder is the part of the stem before the last `_`
  (`card_image_folder`), the folder must match `[a-z0-9]+` and is created when missing. Products
  `PRODUCT_IMAGES_DIR/<id>.webp`. `rbcar_image` / `rbpdt_image` store the new file name; `image_url`
  (legacy text column) is not written. If the name already exists (a re-upload) the new file is written as
  `<stem>-<n>.webp` (n = next free integer) so the browser cache of the old URL is never reused.
- **S6 Bulk upload.** A **Upload several images** button accepts many files at once; each file is matched by
  its **file name stem** to a card (`ogn_66`, `OGN-66`, `ognx_66`, `plat_sfd189`; case-insensitive,
  `-`/`_` equivalent) or product (`<id>`); a preview table shows `file → target` with a status
  (`ready`, `no match`, `several matches`, `too large`, `not an image`), nothing is sent until the admin
  confirms, unmatched files can be assigned by hand from a search select, and the confirm sends the ready
  files one by one (concurrency 2) with a progress bar and a final summary; a failure of one file does not
  stop the others. Limit 50 files per batch.
- **S7 Previous files.** The previous file of a card/product is **not deleted at upload**; it is deleted when
  the Undo toast expires or on the next upload to the same item, only if it is inside the images root and no
  other row uses that file name. A daily `flask images prune-orphans [--dry-run]` CLI lists/removes files no
  row references (never run by a timer; documented in the runbook).
- **S8 Audit.** One `rbadminaudit` row per image written (`card.image` / `product.image`, details
  `{image, bytes_in, bytes_out, width, height}`), the batch writes one row per file.
- **S9 Authorization.** All new routes are admin (A) and classified in `tests/test_authz_matrix.py`; CSRF as
  every write; the media routes stay public and never touch the session.
- **S10 Errors in the UI** use the existing error catalog (`code.<value>` in `errors.json`) plus `too_small`;
  strings in the `admin` namespace.
- **S11 The two edit forms** (`CardEditor`, `ProductEditor`) keep their upload control but call the same
  route, so they also resize and rename. Existing tests are adapted, not deleted.

## API / data contract

- `POST /admin/cards/<set>/<id>/image` and `POST /admin/products/<id>/image`: multipart `file` (unchanged),
  limit raised to 10 MB, response adds `{image, width, height, bytes}`. Backwards compatible (additive).
- `GET /admin/cards` and `GET /admin/products`: `image=missing|present|any`; the response rows carry
  `has_image` (true only when the file exists) next to the existing fields.
- `GET /admin/images/summary` → `{cards: {missing, total}, products: {missing, total}}` for the counters.
- No migration: no table or column changes.

## UI

The Images screen is a list-first admin screen like Cards/Products (toolbar with search, filters and the
bulk button; rows with a 48 px thumbnail, a "No image" badge and **Choose file**). The drop target and the
focusable **Choose file** button have a visible focus ring; success and failure are announced
(`role="status"` / `role="alert"`).

## Acceptance criteria

1. A card with an empty image and a card whose file is gone both appear under `Cards` (switch on); turning
   the switch off hides the second kind.
2. Uploading a 3000 × 4200 PNG gives `<set>_<id>.webp`, at most 744 × 1039, without metadata; the row shows
   the new thumbnail; the old file stays until the Undo toast expires.
3. A text file renamed `.png`, a 30 Mpx image, a 12 MB file and a 100 × 100 image are refused with the
   right code and nothing is written; a failed upload leaves the old image.
4. Uploading to a card whose target name exists writes `<stem>-2.webp` and updates the column.
5. The bulk dialog matches `ogn_66.png` and `OGN-66.jpg` to OGN-66, flags `ogn_66.png` + `ogn-66.jpg` as
   `several matches`, and a failing file does not stop the batch.
6. Authz matrix, CSRF and audit rows as S8/S9; whole backend and frontend lanes green; no real card image
   directory is touched by the tests (`card_images_dir` fixture).

## Delivery

Two commits in one PR: (1) service + routes + tests (backend), (2) screen + bulk dialog + tests (frontend).
Docs: `docs/api.md`, `docs/frontend.md`, `docs/knowledge/state.md`, `docs/knowledge/ops-runbook.md`
("Card images": the new screen, the naming and `flask images prune-orphans`), `AGENTS.md` structure lines.
Deploy: pull + restart + frontend build; no migration, no backup needed. After the deploy the owner uploads
the images of the runes and promo/plated cards from the new screen.

## After merge

State the new maximum sizes in `docs/knowledge/product.md`; consider re-encoding the existing 973 MB card
image folder with a one-off CLI (separate unit, owner decision).

## Open questions

- Owner: are **744 × 1039 WebP q85** (cards) and **800 × 800** (products) acceptable, or do you prefer
  a smaller size or keeping PNG?
- Owner: should the previous file be deleted at once (S7 keeps it until the Undo expires)?

## Log

- 2026-11-24 — requirement written from the owner's feedback; sizes and WebP are proposals.
