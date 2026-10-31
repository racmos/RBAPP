import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { ReactElement } from 'react';
import { createI18n } from '@/i18n';
import { contrast } from '@/lib/contrast';
import { DOMAIN_COLORS } from '@/lib/domains';
import { DomainPips } from './DomainPips';

async function renderPips(ui: ReactElement) {
  const i18n = await createI18n();
  const { I18nextProvider } = await import('react-i18next');
  return render(<I18nextProvider i18n={i18n}>{ui}</I18nextProvider>);
}

describe('DomainPips', () => {
  it('renders nothing for an empty list', () => {
    const { container } = render(<DomainPips domains={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it('labels the group with the names of three domains as an English list', async () => {
    await renderPips(<DomainPips domains={['Fury', 'Chaos', 'Calm']} />);
    expect(screen.getByRole('img', { name: 'Fury, Chaos, and Calm' })).toBeVisible();
  });

  it('labels the group with the names of two domains', async () => {
    await renderPips(<DomainPips domains={['Fury', 'Chaos']} />);
    expect(screen.getByRole('img', { name: 'Fury and Chaos' })).toBeVisible();
  });

  it('falls back to a circle for an unknown domain', async () => {
    await renderPips(<DomainPips domains={['Void']} />);
    const group = screen.getByRole('img');
    expect(group.querySelector('svg')).toBeVisible();
  });

  it('has at least 3:1 contrast for the glyph ink on every domain', () => {
    const inks = ['#ffffff', '#06222c'];
    for (const [domain, color] of Object.entries(DOMAIN_COLORS)) {
      const best = Math.max(...inks.map((ink) => contrast(ink, color)));
      expect(best, `glyph contrast on ${domain}`).toBeGreaterThanOrEqual(3);
    }
  });
});
