import { afterEach, describe, expect, it, vi } from 'vitest';
import { CHUNK_RELOAD_KEY, installChunkReload, isChunkLoadError } from './chunkReload';

afterEach(() => vi.useRealTimers());

const preloadError = () => {
  const event = new Event('vite:preloadError', { cancelable: true });
  window.dispatchEvent(event);
  return event;
};

describe('vite:preloadError (D24)', () => {
  it('reloads once and prevents the default error', () => {
    const reload = vi.fn();
    const uninstall = installChunkReload({ reload });
    const event = preloadError();
    expect(reload).toHaveBeenCalledTimes(1);
    expect(event.defaultPrevented).toBe(true);
    expect(sessionStorage.getItem(CHUNK_RELOAD_KEY)).not.toBeNull();
    uninstall();
  });

  it('does not reload a second time while the guard is set', () => {
    const reload = vi.fn();
    const uninstall = installChunkReload({ reload });
    preloadError();
    preloadError();
    expect(reload).toHaveBeenCalledTimes(1);
    uninstall();
  });

  it('does not reload when the guard was set by the previous page load', () => {
    sessionStorage.setItem(CHUNK_RELOAD_KEY, '1');
    const reload = vi.fn();
    const uninstall = installChunkReload({ reload });
    preloadError();
    expect(reload).not.toHaveBeenCalled();
    uninstall();
  });

  it('forgets the guard after the page has been healthy for a while', () => {
    vi.useFakeTimers();
    sessionStorage.setItem(CHUNK_RELOAD_KEY, '1');
    const reload = vi.fn();
    const uninstall = installChunkReload({ reload });
    vi.advanceTimersByTime(10_001);
    expect(sessionStorage.getItem(CHUNK_RELOAD_KEY)).toBeNull();
    preloadError();
    expect(reload).toHaveBeenCalledTimes(1);
    uninstall();
  });

  it('stops listening once uninstalled', () => {
    const reload = vi.fn();
    installChunkReload({ reload })();
    preloadError();
    expect(reload).not.toHaveBeenCalled();
  });
});

describe('isChunkLoadError', () => {
  it.each([
    'Failed to fetch dynamically imported module: https://x/assets/a.js',
    'error loading dynamically imported module',
    'Importing a module script failed.',
    'Unable to preload CSS for /assets/a.css',
  ])('recognises "%s"', (message) => {
    expect(isChunkLoadError(new Error(message))).toBe(true);
  });

  it('rejects other errors and non-errors', () => {
    expect(isChunkLoadError(new Error('Cannot read properties of undefined'))).toBe(false);
    expect(isChunkLoadError('Failed to fetch dynamically imported module')).toBe(false);
    expect(isChunkLoadError(null)).toBe(false);
  });
});
