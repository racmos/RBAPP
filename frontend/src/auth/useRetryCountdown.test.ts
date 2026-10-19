import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useRetryCountdown } from './useRetryCountdown';

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe('useRetryCountdown (FAUTH-7)', () => {
  it('is idle until started', () => {
    const { result } = renderHook(() => useRetryCountdown());
    expect(result.current.remaining).toBe(0);
    expect(result.current.active).toBe(false);
  });

  it('counts down in whole seconds from the given value', () => {
    const { result } = renderHook(() => useRetryCountdown());
    act(() => result.current.start(30));
    expect(result.current.remaining).toBe(30);
    expect(result.current.active).toBe(true);
    act(() => void vi.advanceTimersByTime(10_000));
    expect(result.current.remaining).toBe(20);
    act(() => void vi.advanceTimersByTime(19_000));
    expect(result.current.remaining).toBe(1);
  });

  it('ends at zero, calling onEnd once', () => {
    const onEnd = vi.fn();
    const { result } = renderHook(() => useRetryCountdown({ onEnd }));
    act(() => result.current.start(3));
    act(() => void vi.advanceTimersByTime(2_999));
    expect(result.current.active).toBe(true);
    expect(onEnd).not.toHaveBeenCalled();
    act(() => void vi.advanceTimersByTime(1));
    expect(result.current.remaining).toBe(0);
    expect(result.current.active).toBe(false);
    act(() => void vi.advanceTimersByTime(10_000));
    expect(onEnd).toHaveBeenCalledTimes(1);
  });

  it('restarts from a new value', () => {
    const { result } = renderHook(() => useRetryCountdown());
    act(() => result.current.start(30));
    act(() => void vi.advanceTimersByTime(5_000));
    act(() => result.current.start(60));
    expect(result.current.remaining).toBe(60);
  });

  it.each([0, -5, Number.NaN])('ignores %s', (seconds) => {
    const { result } = renderHook(() => useRetryCountdown());
    act(() => result.current.start(seconds));
    expect(result.current.active).toBe(false);
  });

  it('stops its timer on unmount', () => {
    const onEnd = vi.fn();
    const { result, unmount } = renderHook(() => useRetryCountdown({ onEnd }));
    act(() => result.current.start(2));
    unmount();
    act(() => void vi.advanceTimersByTime(5_000));
    expect(onEnd).not.toHaveBeenCalled();
  });
});
