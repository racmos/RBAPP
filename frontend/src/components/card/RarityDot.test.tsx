import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { ReactElement } from 'react';
import { createI18n } from '@/i18n';
import { RarityDot } from './RarityDot';

async function renderDot(ui: ReactElement) {
  const i18n = await createI18n();
  const { I18nextProvider } = await import('react-i18next');
  return render(<I18nextProvider i18n={i18n}>{ui}</I18nextProvider>);
}

describe('RarityDot', () => {
  it('shows the dot with an aria-label when there is no label', async () => {
    await renderDot(<RarityDot rarity="Rare" />);
    expect(screen.getByRole('img', { name: 'Rarity: Rare' })).toBeVisible();
  });

  it('shows the label of a rare card', async () => {
    await renderDot(<RarityDot rarity="Rare" showLabel />);
    expect(screen.getByText('Rare')).toBeVisible();
  });

  it('shows the label of a common card', async () => {
    await renderDot(<RarityDot rarity="Common" showLabel />);
    expect(screen.getByText('Common')).toBeVisible();
  });
});
