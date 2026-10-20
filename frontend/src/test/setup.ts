import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterAll, afterEach, beforeAll, expect } from 'vitest';
import * as axeMatchers from 'vitest-axe/matchers';
import { installDialogPolyfill } from './dialog';
import { installRelativeFetch } from './fetch';
import { installPopoverPolyfill } from './popover';
import { server } from './msw/server';
import { installMatchMedia, resetViewport } from './viewport';

// Files that opt into `@vitest-environment node` (file-system tests) have no window.
if (typeof window !== 'undefined') {
  expect.extend(axeMatchers);
  installMatchMedia();
  installDialogPolyfill();
  installPopoverPolyfill();
  installRelativeFetch();

  // An unhandled request is a bug in the test, not something to let through to the network.
  beforeAll(() => server.listen({ onUnhandledFrame: 'error' }));
  afterAll(() => server.close());
  afterEach(() => {
    cleanup();
    resetViewport();
    server.resetHandlers();
    localStorage.clear();
    sessionStorage.clear();
    // What applyPrefs writes to <html> must not leak from one test into the next.
    const root = document.documentElement;
    for (const name of ['data-accent', 'data-density', 'data-bg', 'style']) {
      root.removeAttribute(name);
    }
  });
}
