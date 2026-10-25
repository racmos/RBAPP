# F14-d: Products admin — curation API, images, admin screen

| Field | Value |
|---|---|
| Phase / unit | F14 / d — batch 1, unit 30 |
| Branch | `feat/f14d-products-admin` (from the F14-c branch) |
| Depends on | F14-a…c, F13-a, F13-f (stack) |
| Size forecast | ~550 authored lines |
| Risk | `Risk: item 2 (file upload, admin writes)` |
| TDD | ON (strict). Runners: `venv/bin/pytest`, `cd frontend && npx vitest run` |
| Sources | F14 phase spec (F14-R2, "API", "UI", D-F14-3, D-F14-8) |

## Objective

The admin tidies the product catalog: hides what does not belong, corrects the kind or the set (and the daily
refresh then respects it), and uploads a picture per product.

## Read first

- `app/api/admin/` (F13), `app/services/audit.py`, `app/services/card_images.py` and `app/routes/media.py` (M-d),
  F13-b image upload (magic bytes), `frontend/src/admin/` (layout, `CardsAdminPage` patterns)

## Specs

S1. Setting `PRODUCT_IMAGES_DIR` (same rules as `CARD_IMAGES_DIR`, default `<project>/data/product-images`);
    `product_image_path(filename)` (plain file name only) and route `GET /riftbound/media/products/<filename>`
    (`media.product_image`, P, same headers as the card image route). `.env.example` documents it.
S2. `GET /admin/products` (A): filters `q`, `kind[]`, `hidden=any|yes|no`, `listed=any|yes|no`,
    `no_set=true`, `no_image=true`; sort `name` | `updated`; pagination 50/100/200. Item = `ProductSummary` +
    `{hidden, kind_locked, set_locked, rbpdt_type}`; only non-singles.
S3. `PATCH /admin/products/<id>` (A) any of `{hidden, kind, set_id}`: `kind` in the F14-a list → sets
    `kind_locked = true` (`kind: null` → unlock and recompute from the category); `set_id` existing set or null →
    `set_locked = true` (`"set_id": "auto"` → unlock and recompute from the expansion). Audit `product.update`
    with the changed fields.
S4. `POST /admin/products/<id>/image` (A, multipart `file`): same validation as F13-b S9 (2 MB, magic bytes);
    file name `<id>.<ext>`; updates `rbpdt_image`; audit `product.image`. `ProductSummary.image_src` becomes
    `/riftbound/media/products/<rbpdt_image>` when set.
S5. Admin UI `/admin/products` (`ProductsAdminPage`, admin nav entry `products`): filters bar; desktop table
    (image 40 px or kind placeholder icon `gift`, name, kind, set, price, listed, hidden, updated) + editor drawer
    (≥ 1600 persistent panel): kind `Select` (`products:kind.<kind>` + `admin:products.kindAuto`), set `Select`
    (`admin:products.setAuto` + sets), hidden `Switch`, image upload (same component as `CardEditor`), lock badges
    `admin:products.locked`. Mobile: cards + bottom sheet editor. States as G6; axe clean.
S6. Docs: `AGENTS.md`, `docs/api.md`, `docs/frontend.md`, runbook (product images directory, same copy rules),
    `state.md` (pending check: create `PRODUCT_IMAGES_DIR` on the server).

## UI strings

| Key | ES | EN |
|---|---|---|
| `admin:nav.products` | Productos | Products |
| `admin:products.title` | Productos | Products |
| `admin:products.subtitle` | Catálogo de producto sellado de Cardmarket. | Cardmarket sealed product catalog. |
| `admin:products.caption` | Productos del catálogo | Catalog products |
| `admin:products.filters.hidden` | Ocultos | Hidden |
| `admin:products.filters.listed` | En Cardmarket | On Cardmarket |
| `admin:products.filters.noSet` | Sin set | Without set |
| `admin:products.filters.noImage` | Sin imagen | Without image |
| `admin:products.columns.image` | Imagen | Image |
| `admin:products.columns.name` | Nombre | Name |
| `admin:products.columns.kind` | Tipo | Kind |
| `admin:products.columns.set` | Set | Set |
| `admin:products.columns.price` | Precio | Price |
| `admin:products.columns.listed` | En Cardmarket | On Cardmarket |
| `admin:products.columns.hidden` | Oculto | Hidden |
| `admin:products.columns.updated` | Actualizado | Updated |
| `admin:products.fields.kind` | Tipo | Kind |
| `admin:products.fields.set` | Set | Set |
| `admin:products.fields.hidden` | Ocultar a los usuarios | Hide from users |
| `admin:products.kindAuto` | Automático (según la categoría) | Automatic (from the category) |
| `admin:products.setAuto` | Automático (según la expansión) | Automatic (from the expansion) |
| `admin:products.locked` | Fijado a mano | Set by hand |
| `admin:products.saved` | Producto guardado. | Product saved. |
| `admin:products.empty` | Ningún producto coincide con los filtros. | No product matches the filters. |
| `admin:products.pickOne` | Elige un producto para editarlo. | Pick a product to edit it. |
| `products:kind.booster` | Sobre | Booster |
| `products:kind.box` | Caja de sobres | Booster box |
| `products:kind.case` | Case | Case |
| `products:kind.bundle` | Pack | Bundle |
| `products:kind.starter` | Mazo de inicio | Starter deck |
| `products:kind.sleeves` | Fundas | Sleeves |
| `products:kind.accessory` | Accesorio | Accessory |
| `products:kind.other` | Otro | Other |

(`products` namespace is created here with the `kind` keys; F14-e adds the rest.)

## Acceptance criteria

- [ ] AC1 `tests/test_media_route.py` (extend) and config tests for `PRODUCT_IMAGES_DIR` (S1).
- [ ] AC2 `tests/test_admin_products_api.py`: filters, lock/unlock of kind and set (refresh respects locks — call `refresh_products` after a patch), audit, image upload rules (S2-S4).
- [ ] AC3 `ProductsAdminPage.test.tsx`: table at 1280, cards at 390, panel at 1700, edit kind/set/hidden, upload (S5).
- [ ] AC4 Authz matrix; axe; parity; full lanes green; docs (S6).

## Delivery

PR title: `feat(products): products admin with kind/set locks and images (F14 unit d)`.

## After merge

Deploy; create `PRODUCT_IMAGES_DIR` on the server and set it in `.env`.

## Open questions

none
