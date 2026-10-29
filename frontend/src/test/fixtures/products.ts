import type { AdminProduct, AdminProductList } from '@/api/endpoints';
import type {
  MyProducts,
  OwnedProductLine,
  OwnedProductLineBase,
  ProductDetail,
  ProductListMeta,
  ProductPricePoint,
  ProductSummary,
} from '@/api/types';

/** An unlocked product with an image and a price (F14-d). */
export const boosterBox: AdminProduct = {
  id: 501,
  name: 'Origins Booster Box',
  kind: 'box',
  category: 'Riftbound Booster Boxes',
  set_id: 'OGN',
  image_src: '/riftbound/media/products/501.png',
  listed: true,
  price: {
    value: 99.5,
    source: 'avg7',
    change_7d_pct: null,
    change_30d_pct: null,
    as_of: '2026-10-28',
  },
  owned_qty: 0,
  hidden: false,
  kind_locked: false,
  set_locked: false,
  rbpdt_type: 'nonsingle',
  updated_at: '2026-10-28T06:30:00Z',
};

/** A hidden product with both locks, no set, no image and no price. */
export const sleeves: AdminProduct = {
  id: 502,
  name: 'Riftbound Sleeves',
  kind: 'sleeves',
  category: 'Riftbound Accessories',
  set_id: null,
  image_src: null,
  listed: false,
  price: null,
  owned_qty: 0,
  hidden: true,
  kind_locked: true,
  set_locked: true,
  rbpdt_type: 'nonsingle',
  updated_at: null,
};

export const adminProductList: AdminProductList = {
  items: [boosterBox, sleeves],
  meta: { page: 1, per_page: 50, total: 2, pages: 1 },
};

// --- User screens (F14-e) ---

/** The booster box as users see it: priced, with changes, two copies owned. */
export const boxSummary: ProductSummary = {
  id: 501,
  name: 'Origins Booster Box',
  kind: 'box',
  category: 'Riftbound Booster Boxes',
  set_id: 'OGN',
  image_src: '/riftbound/media/products/501.png',
  listed: true,
  price: {
    value: 99.5,
    source: 'avg7',
    change_7d_pct: 2.5,
    change_30d_pct: -4.1,
    as_of: '2026-10-28',
  },
  owned_qty: 2,
};

export const boosterSummary: ProductSummary = {
  id: 503,
  name: 'Origins Booster',
  kind: 'booster',
  category: 'Riftbound Boosters',
  set_id: 'OGN',
  image_src: null,
  listed: true,
  price: {
    value: 4.2,
    source: 'trend',
    change_7d_pct: -1.2,
    change_30d_pct: null,
    as_of: '2026-10-28',
  },
  owned_qty: 0,
};

/** No set, no image, no price; owned once. */
export const sleevesSummary: ProductSummary = {
  id: 502,
  name: 'Riftbound Sleeves',
  kind: 'sleeves',
  category: 'Riftbound Accessories',
  set_id: null,
  image_src: null,
  listed: true,
  price: null,
  owned_qty: 1,
};

export const productSummaries: ProductSummary[] = [boosterSummary, boxSummary, sleevesSummary];

export const productListMeta: ProductListMeta = {
  page: 1,
  per_page: 48,
  total: 3,
  pages: 1,
  facets: { kind: { booster: 1, box: 1, sleeves: 1 }, set: { OGN: 2 } },
  price_as_of: '2026-10-28',
};

export const boxLine: OwnedProductLine = {
  id: 801,
  product: boxSummary,
  quantity: 2,
  purchase_price: 90,
  note: 'Sealed',
  value: 199,
  pl_abs: 19,
  pl_pct: 10.6,
  updated_at: '2026-10-27T10:00:00Z',
};

export const sleevesLine: OwnedProductLine = {
  id: 802,
  product: sleevesSummary,
  quantity: 1,
  purchase_price: null,
  note: null,
  value: null,
  pl_abs: null,
  pl_pct: null,
  updated_at: '2026-10-27T10:05:00Z',
};

export const myProducts: MyProducts = {
  items: [boxLine, sleevesLine],
  total: { value: 199, lines: 2, qty: 3, unpriced: 1 },
};

export const noProducts: MyProducts = {
  items: [],
  total: { value: 0, lines: 0, qty: 0, unpriced: 0 },
};

function withoutProduct(line: OwnedProductLine): OwnedProductLineBase {
  const rest: Partial<OwnedProductLine> = { ...line };
  delete rest.product;
  return rest as OwnedProductLineBase;
}

export const productDetails: Record<number, ProductDetail> = {
  501: {
    ...boxSummary,
    description: 'A sealed box of 24 boosters.',
    columns: { avg7: 99.5, trend: 101, low: 95, avg30: 103.7 },
    lines: [withoutProduct(boxLine)],
  },
  502: {
    ...sleevesSummary,
    description: null,
    columns: null,
    lines: [withoutProduct(sleevesLine)],
  },
  503: { ...boosterSummary, description: null, columns: null, lines: [] },
};

export const productPricePoints: ProductPricePoint[] = [
  { date: '2026-10-26', value: 98, avg7: 98, trend: 100, low: 94 },
  { date: '2026-10-27', value: 99, avg7: 99, trend: 100.5, low: 94.5 },
  { date: '2026-10-28', value: 99.5, avg7: 99.5, trend: 101, low: 95 },
];
