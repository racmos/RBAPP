import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { Placeholder } from './Placeholder';

afterEach(() => {
  document.documentElement.removeAttribute('data-bg');
  document.documentElement.removeAttribute('style');
});

describe('Placeholder (screenshot harness, replaced in units d/e)', () => {
  it('shows the brand wordmark', () => {
    render(<Placeholder showBackgroundSlider={false} />);
    expect(screen.getByRole('img', { name: 'Rift Manager' })).toBeInTheDocument();
  });

  it('has no slider unless asked for', () => {
    render(<Placeholder showBackgroundSlider={false} />);
    expect(screen.queryByRole('slider')).not.toBeInTheDocument();
  });

  it('offers a labelled 0..100 slider that drives the background live', () => {
    render(<Placeholder showBackgroundSlider />);
    const slider = screen.getByRole('slider', { name: 'Intensidad del fondo' });
    expect(slider).toHaveAttribute('min', '0');
    expect(slider).toHaveAttribute('max', '100');
    expect(slider).toHaveValue('100');

    fireEvent.change(slider, { target: { value: '40' } });
    const root = document.documentElement;
    expect(root.dataset.bg).toBe('on');
    expect(root.style.getPropertyValue('--bg-image-opacity')).toBe('0.4');
    expect(screen.getByText('40 %')).toBeInTheDocument();

    fireEvent.change(slider, { target: { value: '0' } });
    expect(root.dataset.bg).toBe('off');
    expect(root.style.getPropertyValue('--bg-image-opacity')).toBe('0');
  });
});
