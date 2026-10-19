import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';
import { installMatchMedia, resetViewport } from './viewport';

// Files that opt into `@vitest-environment node` (file-system tests) have no window.
if (typeof window !== 'undefined') {
  installMatchMedia();
  afterEach(() => {
    cleanup();
    resetViewport();
  });
}
