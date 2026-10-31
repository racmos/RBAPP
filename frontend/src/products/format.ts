import type { CardPrice, ProductPrice, ProductPricePoint, PricePoint } from '@/api/types';

/** `PriceTag` reads a card price: the product value is its market price, never a foil one. */
export const asCardPrice = (price: ProductPrice): CardPrice => ({
  market: price.value,
  market_source: price.source,
  market_foil: null,
  market_foil_source: null,
  trend_7d_pct: price.change_7d_pct,
  trend_30d_pct: price.change_30d_pct,
  as_of: price.as_of,
});

/** `PriceChart` draws card points: the product `value` becomes the market series. */
export const asChartPoints = (points: ProductPricePoint[]): PricePoint[] =>
  points.map((point) => ({
    date: point.date,
    market: point.value,
    low: null,
    avg7: null,
    avg30: null,
    market_foil: null,
  }));
