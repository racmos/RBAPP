import { act, renderHook } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { setViewport } from '@/test/viewport';
import { BREAKPOINTS, down, up } from './breakpoints';
import { useMediaQuery } from './useMediaQuery';

describe('breakpoints (DS-4)', () => {
  it('exports the five-step scale', () => {
    expect(BREAKPOINTS).toEqual({ sm: 680, md: 860, lg: 960, xl: 1240, '2xl': 1600 });
  });

  it('builds mobile-first up() queries', () => {
    expect(up('md')).toBe('(min-width: 860px)');
    expect(up('2xl')).toBe('(min-width: 1600px)');
  });

  it('builds down() queries 0.02 px below the breakpoint (R1)', () => {
    expect(down('md')).toBe('(max-width: 859.98px)');
    expect(down('xl')).toBe('(max-width: 1239.98px)');
    expect(down('sm')).toBe('(max-width: 679.98px)');
  });
});

describe('useMediaQuery', () => {
  it('is true at 859 and false at 860 for down(md)', () => {
    setViewport(859);
    const phone = renderHook(() => useMediaQuery(down('md')));
    expect(phone.result.current).toBe(true);
    phone.unmount();

    setViewport(860);
    const desktop = renderHook(() => useMediaQuery(down('md')));
    expect(desktop.result.current).toBe(false);
  });

  it('re-renders when the viewport crosses the breakpoint', () => {
    setViewport(1280);
    const { result } = renderHook(() => useMediaQuery(down('md')));
    expect(result.current).toBe(false);
    act(() => setViewport(390));
    expect(result.current).toBe(true);
    act(() => setViewport(1000));
    expect(result.current).toBe(false);
  });

  it('follows a changed query between renders', () => {
    setViewport(1000);
    const { result, rerender } = renderHook(({ query }) => useMediaQuery(query), {
      initialProps: { query: up('md') },
    });
    expect(result.current).toBe(true);
    rerender({ query: up('xl') });
    expect(result.current).toBe(false);
  });
});
