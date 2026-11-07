import { describe, expect, it } from 'vitest';
import { auditApiQuery, actionLabelKey, targetLink } from './format';

const item = (action: string, target_type: string, target_id: string | null) => ({
  action,
  target_type,
  target_id,
});

describe('targetLink (CM-e)', () => {
  it('links a Cardmarket product to the workbench tab that holds it', () => {
    expect(targetLink(item('cardmarket.link', 'cardmarket_product', '501'))).toBe(
      '/admin/cardmarket/matching?tab=linked&q=501',
    );
    expect(targetLink(item('cardmarket.relink', 'cardmarket_product', '501'))).toBe(
      '/admin/cardmarket/matching?tab=linked&q=501',
    );
    expect(targetLink(item('cardmarket.unlink', 'cardmarket_product', '501'))).toBe(
      '/admin/cardmarket/matching?q=501',
    );
    expect(targetLink(item('cardmarket.unignore', 'cardmarket_product', '501'))).toBe(
      '/admin/cardmarket/matching?q=501',
    );
    expect(targetLink(item('cardmarket.ignore', 'cardmarket_product', '501'))).toBe(
      '/admin/cardmarket/matching?tab=ignored',
    );
  });

  it('links expansions, cards, products, sets and the auto-match', () => {
    expect(targetLink(item('cardmarket.expansion.map', 'cardmarket_expansion', '6567'))).toBe(
      '/admin/cardmarket/matching?tab=expansions&show=all',
    );
    expect(targetLink(item('card.update', 'card', 'OGN-001'))).toBe('/admin/cards?q=OGN-001');
    expect(targetLink(item('product.update', 'product', '7001'))).toBe('/admin/products?q=7001');
    expect(targetLink(item('set.create', 'set', 'UNL'))).toBe('/admin/sets');
    expect(targetLink(item('cardmarket.auto_match', 'cardmarket', '20300103'))).toBe(
      '/admin/cardmarket',
    );
  });

  it('encodes the id and has no link without a safe route or an id', () => {
    expect(targetLink(item('card.update', 'card', 'A&B C'))).toBe('/admin/cards?q=A%26B+C');
    expect(targetLink(item('cardmarket.load', 'job', '12'))).toBeNull();
    expect(targetLink(item('riot.recheck', 'card_change', null))).toBeNull();
    expect(targetLink(item('card.delete', 'card', null))).toBeNull();
    expect(targetLink(item('user.promote', 'user', '3'))).toBeNull();
    expect(targetLink(item('cardmarket.link', 'cardmarket_product', 'abc'))).toBeNull();
  });
});

describe('actionLabelKey (CM-e)', () => {
  it('knows every action the admin writes and nothing else', () => {
    expect(actionLabelKey('cardmarket.expansion.map')).toBe('audit.actions.cardmarketExpansionMap');
    expect(actionLabelKey('riot.change_approve')).toBe('audit.actions.riotChangeApprove');
    expect(actionLabelKey('set.create')).toBe('audit.actions.setCreate');
    expect(actionLabelKey('something.new')).toBeNull();
    expect(actionLabelKey('constructor')).toBeNull();
  });
});

describe('auditApiQuery (CM-e)', () => {
  it('keeps only the API filters, with the default page size', () => {
    const params = new URLSearchParams(
      'action=cardmarket.link&actor=ad&target_type=card&target_id=OGN-001&from=2030-01-01' +
        '&to=2030-01-31&page=2&per_page=100&tab=x&q=',
    );
    expect(auditApiQuery(params)).toBe(
      'action=cardmarket.link&actor=ad&target_type=card&target_id=OGN-001&from=2030-01-01' +
        '&to=2030-01-31&page=2&per_page=100',
    );
    expect(auditApiQuery(new URLSearchParams())).toBe('per_page=50');
  });
});
