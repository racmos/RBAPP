import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { Slider } from './Slider';

function Demo({
  onChange,
  onCommit,
  initial = 100,
}: {
  onChange?: (value: number) => void;
  onCommit?: (value: number) => void;
  initial?: number;
}) {
  const [value, setValue] = useState(initial);
  return (
    <Slider
      label="Intensidad del fondo"
      value={value}
      min={0}
      max={100}
      step={5}
      unit="%"
      onChange={(next) => {
        setValue(next);
        onChange?.(next);
      }}
      onCommit={onCommit}
    />
  );
}

describe('Slider (DS-8)', () => {
  it('is a labelled slider with its range and a visible value', () => {
    render(<Demo initial={40} />);
    const slider = screen.getByRole('slider', { name: 'Intensidad del fondo' });
    expect(slider).toHaveValue('40');
    expect(slider).toHaveAttribute('min', '0');
    expect(slider).toHaveAttribute('max', '100');
    expect(slider).toHaveAttribute('step', '5');
    expect(screen.getByText('40%')).toBeVisible();
    expect(slider).toHaveAttribute('aria-valuetext', '40%');
  });

  it('reports every value while dragging and shows the new one', () => {
    const spy = vi.fn();
    render(<Demo onChange={spy} />);
    const slider = screen.getByRole('slider');
    fireEvent.change(slider, { target: { value: '70' } });
    fireEvent.change(slider, { target: { value: '35' } });
    expect(spy.mock.calls).toEqual([[70], [35]]);
    expect(screen.getByText('35%')).toBeVisible();
  });

  it('commits the final value on pointerup', () => {
    const onCommit = vi.fn();
    render(<Demo onCommit={onCommit} />);
    const slider = screen.getByRole('slider');
    fireEvent.change(slider, { target: { value: '20' } });
    expect(onCommit).not.toHaveBeenCalled();
    fireEvent.pointerUp(slider);
    expect(onCommit).toHaveBeenCalledTimes(1);
    expect(onCommit).toHaveBeenCalledWith(20);
  });

  it('commits on blur and after a key press', async () => {
    const onCommit = vi.fn();
    render(<Demo onCommit={onCommit} initial={50} />);
    await userEvent.tab();
    fireEvent.change(screen.getByRole('slider'), { target: { value: '55' } });
    fireEvent.keyUp(screen.getByRole('slider'), { key: 'ArrowRight' });
    expect(onCommit).toHaveBeenLastCalledWith(55);
    fireEvent.change(screen.getByRole('slider'), { target: { value: '60' } });
    await userEvent.tab(); // leaves the slider
    expect(onCommit).toHaveBeenLastCalledWith(60);
  });
});
