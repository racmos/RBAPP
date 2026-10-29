import type { AdminProduct, AdminProductList } from '@/api/endpoints';

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
