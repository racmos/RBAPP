import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Brand } from './Brand';

describe('Brand (DS-9)', () => {
  it('exposes the wordmark as an image named "Rift Manager"', () => {
    render(<Brand variant="wordmark" />);
    const image = screen.getByRole('img', { name: 'Rift Manager' });
    expect(image).toHaveAttribute('src', expect.stringContaining('wordmark'));
  });

  it('exposes the mark alone with the same name', () => {
    render(<Brand variant="mark" />);
    const image = screen.getByRole('img', { name: 'Rift Manager' });
    expect(image).toHaveAttribute('src', expect.stringMatching(/mark(?!.*word)/));
    expect(image.getAttribute('src')).not.toContain('wordmark');
  });

  it('keeps the image from being dragged or shrunk by layout', () => {
    render(<Brand variant="mark" />);
    expect(screen.getByRole('img', { name: 'Rift Manager' })).toHaveAttribute('draggable', 'false');
  });

  it('forwards a class name for sizing by the caller', () => {
    render(<Brand variant="wordmark" className="topbar-brand" />);
    expect(screen.getByRole('img', { name: 'Rift Manager' })).toHaveClass('topbar-brand');
  });
});
