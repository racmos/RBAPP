import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { renderWithI18n } from '@/test/i18n';
import { ErrorState } from './ErrorState';
import { Icon } from './Icon';
import { Skeleton } from './Skeleton';

describe('Skeleton', () => {
  it('is a busy region with a hidden label for assistive technology', () => {
    render(<Skeleton label="Cargando mazos" />);
    const region = screen.getByText('Cargando mazos').closest('[aria-busy]');
    expect(region).toHaveAttribute('aria-busy', 'true');
    expect(screen.getByText('Cargando mazos')).toHaveClass('sr-only');
  });

  it('draws the requested number of lines', () => {
    const { container } = render(<Skeleton label="x" lines={4} />);
    expect(container.querySelectorAll('[data-skeleton-line]')).toHaveLength(4);
  });
});

describe('ErrorState', () => {
  it('announces the message and offers a retry action', async () => {
    const onRetry = vi.fn();
    await renderWithI18n(<ErrorState message="Sin conexión" onRetry={onRetry} />);
    expect(screen.getByRole('alert')).toHaveTextContent('Sin conexión');
    await userEvent.click(screen.getByRole('button', { name: 'Reintentar' }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('has no retry button without a handler', async () => {
    await renderWithI18n(<ErrorState message="Falló" />);
    expect(screen.getByRole('alert')).toHaveTextContent('Falló');
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it('retries in the active language', async () => {
    await renderWithI18n(<ErrorState message="Failed" onRetry={() => {}} />, 'en');
    expect(screen.getByRole('button', { name: 'Retry' })).toBeVisible();
  });
});

describe('Icon', () => {
  it.each(['eye', 'eye-off', 'warning', 'check-circle'] as const)(
    'draws %s, hidden from assistive technology',
    (name) => {
      const { container } = render(<Icon name={name} />);
      const svg = container.querySelector('svg');
      expect(svg).toHaveAttribute('aria-hidden', 'true');
      expect(svg?.querySelectorAll('path, circle').length).toBeGreaterThan(0);
    },
  );

  it('exposes an image role and name when given a title', () => {
    render(<Icon name="warning" title="Atención" />);
    expect(screen.getByRole('img', { name: 'Atención' })).toBeInTheDocument();
  });

  it('draws different shapes for different icons', () => {
    const shape = (name: 'eye' | 'warning') => render(<Icon name={name} />).container.innerHTML;
    expect(shape('eye')).not.toBe(shape('warning'));
  });
});
