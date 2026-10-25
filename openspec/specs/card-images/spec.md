# card-images Specification

Source: change f0-foundation (archived 2026-10-19)

> Tags: `[a]`..`[e]` = delivery unit of change f0-foundation. Untagged scenarios are pytest-testable (tmp static folder, mocked HTTP, SQLite).

## Requirements

### Requirement: IMG-1 Folder derives from the filename prefix [a]

`RbCard.image_src` MUST be `/riftbound/media/cards/<folder>/<image>` (amended 2026-10-25, M-d: was `/riftbound/static/images/cards/<folder>/<image>`; the file is served from `CARD_IMAGES_DIR` by `media.card_image`) where `<folder>` is the lowercase text before the last `_` of `image` (not the set id). With no `image`, `image_src` MUST be `None`. This is the behavior introduced by `1ae1f6e`, now covered by characterization tests.

#### Scenario: Promo set
- GIVEN a card with `rbcar_rbset_id='OGNX'`, `image='ogn_257.png'`
- WHEN `image_src` is read
- THEN it is `/riftbound/media/cards/ogn/ogn_257.png`

#### Scenario: Regular set and PROK
- GIVEN `OGN`/`ogn_1.png` and `PROK`/`ogn_265.png`
- WHEN `image_src` is read
- THEN both folders are `ogn`

#### Scenario: No image
- GIVEN `image` is `None` or `''`
- WHEN `image_src` is read
- THEN it is `None`; and `_image_folder('')`, `_image_folder(None)` and `_image_folder('noprefix.png')` return `''`

### Requirement: IMG-2 Upload cannot escape its folder [c]

`POST /riftbound/card/upload_image` (admin only) MUST write only under `<CARD_IMAGES_DIR>/<folder>/` (amended 2026-10-25, M-d: was `<static_folder>/images/cards/<folder>/`; `CARD_IMAGES_DIR` is an absolute data directory outside git, default `<project>/data/card-images`), independent of the process working directory. `<folder>` is the filename-prefix folder (IMG-1), falling back to `set_id.lower()` when the filename has no `_`. Both `set_id` (lowercased) and the derived folder MUST match `^[a-z0-9]+$`; otherwise the request MUST fail with 400 `{success:false,message}` and write nothing. The existing filename sanitization, extension allow-list (jpg, jpeg, png, webp) and 2 MB limit MUST be kept.

#### Scenario: Traversal rejected
- GIVEN an admin and a tmp `CARD_IMAGES_DIR`
- WHEN `set_id` is `../../evil`, `..`, `/tmp/x`, `a/b`, `a\b` or empty, with filename `x.png` (no `_`)
- THEN each response is 400 and no new file exists anywhere under or outside the tmp tree

#### Scenario: Traversal via filename
- GIVEN an admin, `set_id='ogn'`, tmp `CARD_IMAGES_DIR`
- WHEN the filename is `../../evil.png`
- THEN the response is 200 `{success:true,filename:'evil.png'}` and the file is at `<CARD_IMAGES_DIR>/ogn/evil.png`; nothing is written outside `<CARD_IMAGES_DIR>`

#### Scenario: Valid upload lands where image_src reads
- GIVEN an admin, `set_id='ognx'`, filename `ogn_257.png`
- WHEN the upload is posted
- THEN the response is 200 `{success:true,filename:'ogn_257.png'}` and the file is at `<CARD_IMAGES_DIR>/ogn/ogn_257.png`

#### Scenario: Fallback folder
- GIVEN `set_id='PROK'`, filename `promo.png`
- WHEN uploaded
- THEN the file is at `<CARD_IMAGES_DIR>/prok/promo.png`

#### Scenario: Limits kept
- GIVEN an admin
- WHEN a 3 MB file or a `.exe` file is uploaded
- THEN the status is 400 and no file is written

### Requirement: IMG-3 Scraper writes where the UI reads [c]

The Riot scraper MUST save each card image into the folder given by IMG-1 for that card's image filename (fallback `rbcar_rbset_id.lower()` when the name has no `_`), under `CARD_IMAGES_DIR` (amended 2026-10-25, M-d: was the app static folder).

#### Scenario: Promo card from scraper
- GIVEN a scraped card `rbcar_rbset_id='OGNX'`, `image='ogn_257.png'`, HTTP mocked
- WHEN the scraper stores the image
- THEN the file is under `<CARD_IMAGES_DIR>/ogn/` and `RbCard.image_src` points at that file

#### Scenario: Fallback
- GIVEN a scraped card with `image='plain.png'` in set `PROK`
- WHEN stored
- THEN the file is under `<CARD_IMAGES_DIR>/prok/`
