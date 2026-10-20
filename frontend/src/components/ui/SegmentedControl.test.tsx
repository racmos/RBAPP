import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { SegmentedControl } from './SegmentedControl';

const OPTIONS = [
  { value: 'auto', label: 'Auto' },
  { value: 'compact', label: 'Compacta' },
  { value: 'comfy', label: 'Cómoda' },
] as const;

function Demo({ onChange }: { onChange?: (value: string) => void }) {
  const [value, setValue] = useState<string>('auto');
  return (
    <SegmentedControl
      label="Densidad"
      options={OPTIONS}
      value={value}
      onChange={(next) => {
        setValue(next);
        onChange?.(next);
      }}
    />
  );
}

describe('SegmentedControl (DS-8)', () => {
  it('is a labelled radiogroup with exactly one option checked', () => {
    render(<Demo />);
    expect(screen.getByRole('radiogroup', { name: 'Densidad' })).toBeVisible();
    const radios = screen.getAllByRole('radio');
    expect(radios).toHaveLength(3);
    expect(radios.filter((radio) => (radio as HTMLInputElement).checked)).toHaveLength(1);
    expect(screen.getByRole('radio', { name: 'Auto' })).toBeChecked();
  });

  it('selecting the second option with the arrow key fires onChange with its value', async () => {
    const spy = vi.fn();
    render(<Demo onChange={spy} />);
    await userEvent.tab();
    expect(screen.getByRole('radio', { name: 'Auto' })).toHaveFocus();
    await userEvent.keyboard('{ArrowRight}');
    expect(spy).toHaveBeenCalledTimes(1);
    expect(spy).toHaveBeenCalledWith('compact');
    const checked = screen
      .getAllByRole('radio')
      .filter((radio) => (radio as HTMLInputElement).checked);
    expect(checked).toHaveLength(1);
    expect(checked[0]).toBe(screen.getByRole('radio', { name: 'Compacta' }));
  });

  it('a click selects an option', async () => {
    const spy = vi.fn();
    render(<Demo onChange={spy} />);
    await userEvent.click(screen.getByText('Cómoda'));
    expect(spy).toHaveBeenCalledWith('comfy');
    expect(screen.getByRole('radio', { name: 'Cómoda' })).toBeChecked();
  });

  it('can be labelled by a visible element instead of a string', () => {
    render(
      <>
        <span id="lbl">Acento visible</span>
        <SegmentedControl labelledBy="lbl" options={OPTIONS} value="auto" onChange={() => {}} />
      </>,
    );
    expect(screen.getByRole('radiogroup', { name: 'Acento visible' })).toBeVisible();
  });

  it('disables an option', async () => {
    const spy = vi.fn();
    render(
      <SegmentedControl
        label="G"
        options={[
          { value: 'a', label: 'A' },
          { value: 'b', label: 'B', disabled: true },
        ]}
        value="a"
        onChange={spy}
      />,
    );
    expect(screen.getByRole('radio', { name: 'B' })).toBeDisabled();
    await userEvent.click(screen.getByText('B'));
    expect(spy).not.toHaveBeenCalled();
  });
});
