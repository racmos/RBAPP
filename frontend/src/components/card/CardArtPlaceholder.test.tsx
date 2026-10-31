import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { ReactElement } from 'react';
import { createI18n } from '@/i18n';
import { basicRune, champion, foilCommon, noImage, token } from '@/test/fixtures/cards';
import { CardArtPlaceholder } from './CardArtPlaceholder';

async function renderPlaceholder(ui: ReactElement) {
  const i18n = await createI18n();
  const { I18nextProvider } = await import('react-i18next');
  return render(<I18nextProvider i18n={i18n}>{ui}</I18nextProvider>);
}

describe('CardArtPlaceholder', () => {
  it('uses a radial gradient for a single domain', async () => {
    await renderPlaceholder(<CardArtPlaceholder card={foilCommon} />);
    const placeholder = screen.getByRole('img', { name: foilCommon.name });
    expect(placeholder).toHaveStyle({
      backgroundImage: expect.stringContaining('radial-gradient'),
    });
  });

  it('uses a linear gradient for two domains', async () => {
    await renderPlaceholder(<CardArtPlaceholder card={champion} />);
    const placeholder = screen.getByRole('img', { name: champion.name });
    expect(placeholder).toHaveStyle({
      backgroundImage: expect.stringContaining('linear-gradient'),
    });
  });

  it('shows the translated type in upper case', async () => {
    await renderPlaceholder(<CardArtPlaceholder card={champion} />);
    expect(screen.getByText('CHAMPION UNIT')).toBeVisible();
  });

  it('shows the energy circle when energy is present', async () => {
    await renderPlaceholder(<CardArtPlaceholder card={champion} />);
    expect(screen.getByText(String(champion.energy))).toBeVisible();
  });

  it('shows the might square when might is present', async () => {
    await renderPlaceholder(<CardArtPlaceholder card={champion} />);
    expect(screen.getByLabelText(/might/i)).toBeVisible();
  });

  it('is aria-hidden when decorative', async () => {
    await renderPlaceholder(<CardArtPlaceholder card={noImage} decorative />);
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
  });

  it('renders a fallback for a token without domains', async () => {
    await renderPlaceholder(<CardArtPlaceholder card={token} />);
    expect(screen.getByRole('img', { name: token.name })).toBeVisible();
  });

  it('renders a fallback for a basic rune', async () => {
    await renderPlaceholder(<CardArtPlaceholder card={basicRune} />);
    expect(screen.getByRole('img', { name: basicRune.name })).toBeVisible();
  });
});
