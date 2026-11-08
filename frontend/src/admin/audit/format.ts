/** Pure helpers of the admin audit screen (CM-e). */

/** Every action the admin area records (`audit.record`), with its readable label. */
const ACTION_LABELS = {
  'cardmarket.load': 'audit.actions.cardmarketLoad',
  'cardmarket.link': 'audit.actions.cardmarketLink',
  'cardmarket.relink': 'audit.actions.cardmarketRelink',
  'cardmarket.unlink': 'audit.actions.cardmarketUnlink',
  'cardmarket.ignore': 'audit.actions.cardmarketIgnore',
  'cardmarket.unignore': 'audit.actions.cardmarketUnignore',
  'cardmarket.auto_match': 'audit.actions.cardmarketAutoMatch',
  'cardmarket.expansion.map': 'audit.actions.cardmarketExpansionMap',
  'cardmarket.expansion.unmap': 'audit.actions.cardmarketExpansionUnmap',
  'set.create': 'audit.actions.setCreate',
  'set.update': 'audit.actions.setUpdate',
  'set.delete': 'audit.actions.setDelete',
  'card.create': 'audit.actions.cardCreate',
  'card.update': 'audit.actions.cardUpdate',
  'card.image': 'audit.actions.cardImage',
  'card.delete': 'audit.actions.cardDelete',
  'product.update': 'audit.actions.productUpdate',
  'product.image': 'audit.actions.productImage',
  'riot.sync_requested': 'audit.actions.riotSyncRequested',
  'riot.insert': 'audit.actions.riotInsert',
  'riot.apply': 'audit.actions.riotApply',
  'riot.recheck': 'audit.actions.riotRecheck',
  'riot.change_approve': 'audit.actions.riotChangeApprove',
  'riot.change_reject': 'audit.actions.riotChangeReject',
} as const;

export type ActionLabelKey = (typeof ACTION_LABELS)[keyof typeof ACTION_LABELS];

/** The label key of an action, or null for one this client does not know (shown as sent). */
export const actionLabelKey = (action: string): ActionLabelKey | null =>
  Object.hasOwn(ACTION_LABELS, action) ? ACTION_LABELS[action as keyof typeof ACTION_LABELS] : null;

const TARGET_LABELS = {
  cardmarket_product: 'audit.targets.cardmarketProduct',
  cardmarket_expansion: 'audit.targets.cardmarketExpansion',
  cardmarket: 'audit.targets.cardmarket',
  card: 'audit.targets.card',
  card_change: 'audit.targets.cardChange',
  set: 'audit.targets.set',
  product: 'audit.targets.product',
  job: 'audit.targets.job',
} as const;

export type TargetLabelKey = (typeof TARGET_LABELS)[keyof typeof TARGET_LABELS];

export const targetLabelKey = (targetType: string): TargetLabelKey | null =>
  Object.hasOwn(TARGET_LABELS, targetType)
    ? TARGET_LABELS[targetType as keyof typeof TARGET_LABELS]
    : null;

const withQ = (path: string, id: string) => `${path}?${new URLSearchParams({ q: id }).toString()}`;

/**
 * The admin screen that shows the target of a row, or null when there is no safe route: a
 * Cardmarket product opens the workbench tab that holds it after the action (a link in Linked,
 * an ignored one in Ignored, an unlinked or restored one in To link), searched by its id.
 */
export function targetLink(row: {
  action: string;
  target_type: string;
  target_id: string | null;
}): string | null {
  const id = row.target_id;
  if (!id) return null;
  switch (row.target_type) {
    case 'cardmarket_product':
      if (!/^\d+$/.test(id)) return null;
      if (row.action === 'cardmarket.link' || row.action === 'cardmarket.relink')
        return `/admin/cardmarket/matching?tab=linked&q=${id}`;
      if (row.action === 'cardmarket.ignore') return '/admin/cardmarket/matching?tab=ignored';
      return `/admin/cardmarket/matching?q=${id}`;
    case 'cardmarket_expansion':
      return '/admin/cardmarket/matching?tab=expansions&show=all';
    case 'cardmarket':
      return '/admin/cardmarket';
    case 'card':
      return withQ('/admin/cards', id);
    case 'product':
      return /^\d+$/.test(id) ? withQ('/admin/products', id) : null;
    case 'set':
      return '/admin/sets';
    default:
      return null;
  }
}

/** The filters of the screen URL that the API takes, in a fixed order. */
export const FILTER_KEYS = [
  'action',
  'actor',
  'target_type',
  'target_id',
  'from',
  'to',
  'page',
  'per_page',
] as const;
export const PAGE_SIZES = ['50', '100', '200'] as const;
export const DEFAULT_PAGE_SIZE = '50';

/** The `GET /admin/audit` query of the screen URL (empty values dropped). */
export function auditApiQuery(params: URLSearchParams): string {
  const query = new URLSearchParams();
  for (const key of FILTER_KEYS) {
    const value = params.get(key);
    if (value) query.set(key, value);
  }
  if (!query.get('per_page')) query.set('per_page', DEFAULT_PAGE_SIZE);
  return query.toString();
}
