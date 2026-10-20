import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { Switch } from './Switch';

function Demo({ onCheckedChange }: { onCheckedChange?: (value: boolean) => void }) {
  const [checked, setChecked] = useState(false);
  return (
    <Switch
      label="Notificaciones"
      checked={checked}
      onCheckedChange={(value) => {
        setChecked(value);
        onCheckedChange?.(value);
      }}
    />
  );
}

describe('Switch (DS-8)', () => {
  it('has the switch role, its label as name and reflects the state', () => {
    render(<Demo />);
    const toggle = screen.getByRole('switch', { name: 'Notificaciones' });
    expect(toggle).toHaveAttribute('aria-checked', 'false');
  });

  it('toggles with the mouse', async () => {
    const spy = vi.fn();
    render(<Demo onCheckedChange={spy} />);
    const toggle = screen.getByRole('switch', { name: 'Notificaciones' });
    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-checked', 'true');
    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-checked', 'false');
    expect(spy.mock.calls).toEqual([[true], [false]]);
  });

  it.each([['{Enter}'], [' ']])('toggles with the keyboard key %j', async (key) => {
    render(<Demo />);
    await userEvent.tab();
    expect(screen.getByRole('switch')).toHaveFocus();
    await userEvent.keyboard(key);
    expect(screen.getByRole('switch')).toHaveAttribute('aria-checked', 'true');
  });

  it('does nothing while disabled', async () => {
    const spy = vi.fn();
    render(<Switch label="X" checked={false} disabled onCheckedChange={spy} />);
    await userEvent.click(screen.getByRole('switch', { name: 'X' }));
    expect(spy).not.toHaveBeenCalled();
  });
});
