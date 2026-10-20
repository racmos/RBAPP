import { describe, expect, it, vi } from 'vitest';
import { resetViewport, setDisplayMode, setViewport } from './viewport';

describe('setViewport / matchMedia mock', () => {
  it('matches max-width queries below the breakpoint and not above', () => {
    setViewport(390);
    expect(window.matchMedia('(max-width: 859.98px)').matches).toBe(true);
    expect(window.matchMedia('(min-width: 860px)').matches).toBe(false);
    setViewport(1280);
    expect(window.matchMedia('(max-width: 859.98px)').matches).toBe(false);
    expect(window.matchMedia('(min-width: 860px)').matches).toBe(true);
  });

  it('treats the exact breakpoint as desktop and 859 as phone (R1)', () => {
    setViewport(859);
    expect(window.matchMedia('(max-width: 859.98px)').matches).toBe(true);
    setViewport(860);
    expect(window.matchMedia('(max-width: 859.98px)').matches).toBe(false);
    expect(window.matchMedia('(min-width: 860px)').matches).toBe(true);
  });

  it('evaluates ranges joined with "and"', () => {
    setViewport(1000);
    expect(window.matchMedia('(min-width: 960px) and (max-width: 1239.98px)').matches).toBe(true);
    setViewport(1300);
    expect(window.matchMedia('(min-width: 960px) and (max-width: 1239.98px)').matches).toBe(false);
  });

  it('does not match features it does not model', () => {
    setViewport(1000);
    expect(window.matchMedia('(prefers-reduced-motion: reduce)').matches).toBe(false);
  });

  it('exposes innerWidth', () => {
    setViewport(412);
    expect(window.innerWidth).toBe(412);
  });

  it('fires change listeners only when a result flips', () => {
    setViewport(1280);
    const query = window.matchMedia('(max-width: 859.98px)');
    const listener = vi.fn();
    query.addEventListener('change', listener);
    setViewport(390);
    expect(listener).toHaveBeenCalledTimes(1);
    expect(listener.mock.calls[0][0]).toMatchObject({
      matches: true,
      media: '(max-width: 859.98px)',
    });
    setViewport(400);
    expect(listener).toHaveBeenCalledTimes(1);
    query.removeEventListener('change', listener);
    setViewport(1280);
    expect(listener).toHaveBeenCalledTimes(1);
  });

  it('supports the legacy addListener API', () => {
    setViewport(1280);
    const query = window.matchMedia('(min-width: 860px)');
    const listener = vi.fn();
    query.addListener(listener);
    setViewport(500);
    expect(listener).toHaveBeenCalledTimes(1);
    query.removeListener(listener);
    setViewport(1280);
    expect(listener).toHaveBeenCalledTimes(1);
  });

  it('is installed by the global test setup', () => {
    expect(typeof window.matchMedia).toBe('function');
  });
});

describe('setDisplayMode / matchMedia mock (PWA-6)', () => {
  it('is a browser tab by default and models (display-mode: standalone)', () => {
    expect(window.matchMedia('(display-mode: standalone)').matches).toBe(false);
    expect(window.matchMedia('(display-mode: browser)').matches).toBe(true);
    setDisplayMode('standalone');
    expect(window.matchMedia('(display-mode: standalone)').matches).toBe(true);
    expect(window.matchMedia('(display-mode: browser)').matches).toBe(false);
  });

  it('notifies listeners when the mode changes and is reset with the viewport', () => {
    const listener = vi.fn();
    window.matchMedia('(display-mode: standalone)').addEventListener('change', listener);
    setDisplayMode('standalone');
    expect(listener).toHaveBeenCalledTimes(1);
    resetViewport();
    expect(window.matchMedia('(display-mode: standalone)').matches).toBe(false);
  });
});
