import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Sparkline } from './Sparkline';
import styles from './Sparkline.module.css';

describe('Sparkline (F2-g S7)', () => {
  it('renders nothing when there are no values', () => {
    const { container } = render(<Sparkline values={[]} label="empty" />);
    expect(container.firstChild).toBeNull();
  });

  it('renders nothing when every value is null', () => {
    const { container } = render(<Sparkline values={[null, null, null]} label="all null" />);
    expect(container.firstChild).toBeNull();
  });

  it('renders a flat line and a dot for a single value', () => {
    render(<Sparkline values={[5]} label="single" />);
    expect(screen.getByRole('img', { name: 'single' })).toBeVisible();
    expect(document.querySelector('line')).toBeInTheDocument();
    expect(document.querySelector('circle')).toBeInTheDocument();
  });

  it('uses the green colour when the last value is higher than the first', () => {
    render(<Sparkline values={[1, 2, 3]} label="up" />);
    const svg = screen.getByRole('img', { name: 'up' });
    expect(svg).toHaveClass(styles.up);
    expect(svg).not.toHaveClass(styles.down);
  });

  it('uses the red colour when the last value is lower than the first', () => {
    render(<Sparkline values={[3, 2, 1]} label="down" />);
    const svg = screen.getByRole('img', { name: 'down' });
    expect(svg).toHaveClass(styles.down);
    expect(svg).not.toHaveClass(styles.up);
  });

  it('ignores nulls when comparing first and last non-null values', () => {
    render(<Sparkline values={[null, 1, null, 3, null]} label="skip nulls" />);
    const svg = screen.getByRole('img', { name: 'skip nulls' });
    expect(svg).toHaveClass(styles.up);
  });

  it('draws a polyline for multiple values', () => {
    render(<Sparkline values={[1, 2, 3]} label="line" />);
    const polyline = document.querySelector('polyline');
    expect(polyline).toBeInTheDocument();
    expect(polyline?.getAttribute('points')).toMatch(/^\d/);
  });
});
