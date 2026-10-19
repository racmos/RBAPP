import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { Checkbox } from './Checkbox';

describe('Checkbox', () => {
  it('is a checkbox reachable by its label, and the label toggles it', async () => {
    const onChange = vi.fn();
    render(<Checkbox label="Recordarme" checked={false} onChange={onChange} />);
    await userEvent.click(screen.getByText('Recordarme'));
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('checkbox', { name: 'Recordarme' })).not.toBeChecked();
  });

  it('reflects a checked state', () => {
    render(<Checkbox label="Recordarme" checked onChange={() => {}} />);
    expect(screen.getByRole('checkbox', { name: 'Recordarme' })).toBeChecked();
  });

  it('can be toggled with the keyboard', async () => {
    const onChange = vi.fn();
    render(<Checkbox label="Recordarme" checked={false} onChange={onChange} />);
    await userEvent.tab();
    expect(screen.getByRole('checkbox')).toHaveFocus();
    await userEvent.keyboard(' ');
    expect(onChange).toHaveBeenCalledTimes(1);
  });
});
