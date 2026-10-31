import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { ReactElement } from 'react';
import { createI18n } from '@/i18n';
import { champion } from '@/test/fixtures/cards';
import { BanBadge } from './BanBadge';

async function renderBadge(ui: ReactElement) {
  const i18n = await createI18n();
  const { I18nextProvider } = await import('react-i18next');
  return render(<I18nextProvider i18n={i18n}>{ui}</I18nextProvider>);
}

describe('BanBadge', () => {
  it('renders nothing when there are no bans', () => {
    const { container } = render(<BanBadge bans={{ '1v1': false, '2v2': false }} />);
    expect(container.firstChild).toBeNull();
  });

  it('shows the full badge for one mode', async () => {
    await renderBadge(<BanBadge bans={champion.bans} />);
    expect(screen.getByText('Banned in 1v1')).toBeVisible();
  });

  it('shows the full badge for both modes', async () => {
    await renderBadge(<BanBadge bans={{ '1v1': true, '2v2': true }} />);
    expect(screen.getByText('Banned in 1v1 and 2v2')).toBeVisible();
  });

  it('shows the compact variant with joined modes', async () => {
    await renderBadge(<BanBadge bans={{ '1v1': true, '2v2': true }} variant="compact" />);
    expect(screen.getByText('1v1 · 2v2')).toBeVisible();
    expect(screen.getByText('Banned in 1v1 and 2v2').className).toMatch(/srOnly|sr-only/);
  });
});
