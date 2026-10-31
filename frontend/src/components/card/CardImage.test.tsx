import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { ReactElement } from 'react';
import { createI18n } from '@/i18n';
import { champion, noImage } from '@/test/fixtures/cards';
import { CardImage } from './CardImage';

async function renderCardImage(ui: ReactElement) {
  const i18n = await createI18n();
  const { I18nextProvider } = await import('react-i18next');
  return render(<I18nextProvider i18n={i18n}>{ui}</I18nextProvider>);
}

describe('CardImage', () => {
  it('uses thumb source for thumb size when available', async () => {
    await renderCardImage(<CardImage card={champion} size="thumb" />);
    const img = screen.getByRole('img', { name: champion.name }) as HTMLImageElement;
    expect(img.src).toContain(champion.image_thumb_src!);
  });

  it('falls back to full source when thumb is missing', async () => {
    const card = { ...champion, image_thumb_src: null };
    await renderCardImage(<CardImage card={card} size="thumb" />);
    const img = screen.getByRole('img', { name: card.name }) as HTMLImageElement;
    expect(img.src).toContain(card.image_src!);
  });

  it('always uses full source for full size', async () => {
    await renderCardImage(<CardImage card={champion} size="full" />);
    const img = screen.getByRole('img', { name: champion.name }) as HTMLImageElement;
    expect(img.src).toContain(champion.image_src!);
    expect(img.src).not.toContain(champion.image_thumb_src!);
  });

  it('sets width, height, decoding and lazy loading by default', async () => {
    await renderCardImage(<CardImage card={champion} size="tile" />);
    const img = screen.getByRole('img') as HTMLImageElement;
    expect(img).toHaveAttribute('width', '352');
    expect(img).toHaveAttribute('height', '492');
    expect(img).toHaveAttribute('decoding', 'async');
    expect(img).toHaveAttribute('loading', 'lazy');
  });

  it('uses eager loading when priority is set', async () => {
    await renderCardImage(<CardImage card={champion} size="tile" priority />);
    const img = screen.getByRole('img') as HTMLImageElement;
    expect(img).toHaveAttribute('loading', 'eager');
  });

  it('is decorative when requested', async () => {
    await renderCardImage(<CardImage card={champion} size="thumb" decorative />);
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
    expect(document.querySelector('img')).toHaveAttribute('alt', '');
  });

  it('renders the placeholder when image_src is null', async () => {
    await renderCardImage(<CardImage card={noImage} size="thumb" />);
    expect(screen.getByRole('img', { name: noImage.name })).toBeVisible();
    expect(document.querySelector('img')).toBeNull();
  });

  it('retries with image_src after a thumb error then falls back to placeholder', async () => {
    const card = { ...champion, image_thumb_src: '/bad-thumb.png', image_src: '/bad-full.png' };
    await renderCardImage(<CardImage card={card} size="thumb" />);
    const img = screen.getByRole('img') as HTMLImageElement;
    expect(img.src).toContain('/bad-thumb.png');

    fireEvent.error(img);
    const retried = screen.getByRole('img') as HTMLImageElement;
    expect(retried.src).toContain('/bad-full.png');

    fireEvent.error(retried);
    expect(screen.getByRole('img', { name: card.name })).toBeVisible();
    expect(document.querySelector('img')).toBeNull();
  });
});
