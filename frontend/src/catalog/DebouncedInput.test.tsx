import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { startTransition, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { DebouncedInput } from './DebouncedInput';

function Harness({ initial, onCommit }: { initial: string; onCommit: (next: string) => void }) {
  const [value, setValue] = useState(initial);
  return (
    <>
      <DebouncedInput
        aria-label="Size"
        value={value}
        delay={50}
        onCommit={(next) => {
          onCommit(next);
          setValue(next);
        }}
      />
      <button type="button" onClick={() => setValue('8')}>
        External
      </button>
    </>
  );
}

describe('DebouncedInput', () => {
  const actEnvironment = (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean })
    .IS_REACT_ACT_ENVIRONMENT;
  afterEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT =
      actEnvironment;
  });

  it('a value typed before the mount effects run is kept', async () => {
    // A transition render (what the router does) commits the input and runs its passive effects
    // later. An input event in between must not be undone by the mount run of those effects.
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = false;
    const container = document.createElement('div');
    document.body.append(container);
    const onCommit = vi.fn();
    let typedEarly = false;
    const observer = new MutationObserver(() => {
      const input = container.querySelector('input');
      if (!input || typedEarly) return;
      typedEarly = true;
      fireEvent.change(input, { target: { value: '6' } });
    });
    observer.observe(container, { childList: true, subtree: true });
    const root = createRoot(container);
    try {
      startTransition(() => root.render(<Harness initial="4" onCommit={onCommit} />));
      await waitFor(() => expect(onCommit).toHaveBeenCalledWith('6'));
      expect(typedEarly).toBe(true);
      expect(container.querySelector('input')).toHaveValue('6');
    } finally {
      observer.disconnect();
      root.unmount();
      container.remove();
    }
  });

  it('commits the typed text after the delay and keeps it when the value echoes it', async () => {
    const onCommit = vi.fn();
    render(<Harness initial="4" onCommit={onCommit} />);
    const input = screen.getByRole('textbox', { name: 'Size' });
    fireEvent.change(input, { target: { value: '6' } });
    expect(onCommit).not.toHaveBeenCalled();
    await waitFor(() => expect(onCommit).toHaveBeenCalledWith('6'));
    expect(onCommit).toHaveBeenCalledTimes(1);
    expect(input).toHaveValue('6');
  });

  it('commits at once on Enter', () => {
    const onCommit = vi.fn();
    render(<Harness initial="4" onCommit={onCommit} />);
    const input = screen.getByRole('textbox', { name: 'Size' });
    fireEvent.change(input, { target: { value: '7' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onCommit).toHaveBeenCalledWith('7');
  });

  it('takes over a value that changes from outside', () => {
    const onCommit = vi.fn();
    render(<Harness initial="4" onCommit={onCommit} />);
    const input = screen.getByRole('textbox', { name: 'Size' });
    act(() => screen.getByRole('button', { name: 'External' }).click());
    expect(input).toHaveValue('8');
    expect(onCommit).not.toHaveBeenCalled();
  });
});
