import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { Button } from './Button';

describe('Button', () => {
  it('is a type=button by default so it never submits a form by accident', () => {
    render(<Button>Guardar</Button>);
    expect(screen.getByRole('button', { name: 'Guardar' })).toHaveAttribute('type', 'button');
  });

  it('can be a submit button', () => {
    render(<Button type="submit">Entrar</Button>);
    expect(screen.getByRole('button', { name: 'Entrar' })).toHaveAttribute('type', 'submit');
  });

  it('calls onClick when idle', async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Ir</Button>);
    await userEvent.click(screen.getByRole('button', { name: 'Ir' }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it('pending disables the button, sets aria-busy and swallows clicks', async () => {
    const onClick = vi.fn();
    render(
      <Button pending onClick={onClick}>
        Entrar
      </Button>,
    );
    const button = screen.getByRole('button', { name: 'Entrar' });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute('aria-busy', 'true');
    await userEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });

  it('is not busy when idle, and disabled still disables', () => {
    render(<Button disabled>Nada</Button>);
    const button = screen.getByRole('button', { name: 'Nada' });
    expect(button).toBeDisabled();
    expect(button).not.toHaveAttribute('aria-busy');
  });

  it.each(['primary', 'ghost', 'danger'] as const)(
    'renders the %s variant as a button',
    (variant) => {
      render(<Button variant={variant}>{variant}</Button>);
      expect(screen.getByRole('button', { name: variant })).toBeEnabled();
    },
  );
});
