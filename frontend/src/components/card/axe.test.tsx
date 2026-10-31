import { describe, expect, it } from 'vitest';
import { axe } from 'vitest-axe';
import type { ReactElement } from 'react';
import { createI18n } from '@/i18n';
import { basicRune, champion, foilCommon, noImage, noPrice, token } from '@/test/fixtures/cards';
import { render } from '@testing-library/react';
import { BanBadge, CardArtPlaceholder, CardImage, DomainPips, PriceTag, RarityDot } from '.';

async function renderWithI18n(ui: ReactElement) {
  const i18n = await createI18n();
  const { I18nextProvider } = await import('react-i18next');
  return render(<I18nextProvider i18n={i18n}>{ui}</I18nextProvider>);
}

const fixtures = [
  { name: 'champion', card: champion },
  { name: 'foilCommon', card: foilCommon },
  { name: 'basicRune', card: basicRune },
  { name: 'token', card: token },
  { name: 'noImage', card: noImage },
  { name: 'noPrice', card: noPrice },
];

describe('card atoms accessibility', () => {
  it('has no axe violations for every fixture rendered with every atom', async () => {
    for (const { card } of fixtures) {
      const { container } = await renderWithI18n(
        <div style={{ display: 'grid', gap: 16 }}>
          <CardImage card={card} size="tile" />
          <CardArtPlaceholder card={card} />
          <DomainPips domains={card.domains} />
          <RarityDot rarity={card.rarity} showLabel />
          <BanBadge bans={card.bans} />
          <PriceTag price={card.price} />
        </div>,
      );
      expect(await axe(container)).toHaveNoViolations();
    }
  });
});
