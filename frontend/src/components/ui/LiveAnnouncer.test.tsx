import { act, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { LiveAnnouncer, announce } from './LiveAnnouncer';

describe('LiveAnnouncer', () => {
  it('is always mounted as a polite, visually hidden live region', () => {
    render(<LiveAnnouncer />);
    const region = screen.getByRole('status');
    expect(region).toHaveAttribute('aria-live', 'polite');
    expect(region).toBeEmptyDOMElement();
    expect(region).toHaveClass('sr-only');
  });

  it('shows the announced text', () => {
    render(<LiveAnnouncer />);
    act(() => announce('Cuenta creada'));
    expect(screen.getByRole('status')).toHaveTextContent('Cuenta creada');
    act(() => announce('Otro mensaje'));
    expect(screen.getByRole('status')).toHaveTextContent('Otro mensaje');
  });

  it('re-announces the same message by changing the node content', () => {
    render(<LiveAnnouncer />);
    act(() => announce('Error'));
    const first = screen.getByRole('status').textContent;
    act(() => announce('Error'));
    const second = screen.getByRole('status').textContent;
    expect(first).not.toBe(second);
    expect(second).toContain('Error');
  });
});
