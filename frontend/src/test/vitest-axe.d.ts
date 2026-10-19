import 'vitest';

// vitest-axe 0.1.0 ships matcher types for an older vitest; declare the one matcher we use.
declare module 'vitest' {
  interface Assertion {
    toHaveNoViolations(): void;
  }
  interface AsymmetricMatchersContaining {
    toHaveNoViolations(): void;
  }
}
