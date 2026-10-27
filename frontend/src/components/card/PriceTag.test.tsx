import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { ReactElement } from 'react';
import { createI18n } from '@/i18n';
import { champion } from '@/test/fixtures/cards';
import { PriceTag } from './PriceTag';

async function renderPrice(
  ui: ReactElement,
  { lang = 'es' as const }: { lang?: 'es' | 'en' } = {},
) {
  const i18n = await createI18n(lang);
  const { I18nextProvider } = await import('react-i18next');
  return render(<I18nextProvider i18n={i18n}>{ui}</I18nextProvider>);
}

describe('PriceTag', () => {
  it('formats the market price and 7-day trend in Spanish', async () => {
    await renderPrice(<PriceTag price={champion.price} />, { lang: 'es' });
    expect(screen.getByText('1,21 €')).toBeVisible();
    expect(screen.getByText('+10,0 %')).toBeVisible();
  });

  it('shows the 30-day trend when requested', async () => {
    await renderPrice(<PriceTag price={champion.price} trend="30d" />, { lang: 'en' });
    expect(screen.getByText('+5.0%')).toBeVisible();
  });

  it('shows foil price when requested', async () => {
    const price = { ...champion.price!, market_foil: 2.5 };
    await renderPrice(<PriceTag price={price} foil />, { lang: 'en' });
    expect(screen.getByText('€2.50')).toBeVisible();
  });

  it('shows "no price" when the price is null', async () => {
    await renderPrice(<PriceTag price={null} />, { lang: 'es' });
    expect(screen.getByText('Sin precio')).toBeVisible();
  });

  it('announces the trend with screen-reader text', async () => {
    await renderPrice(<PriceTag price={champion.price} />, { lang: 'es' });
    expect(screen.getByText('Sube un 10,0 % en 7 días')).toBeInTheDocument();
  });
});
