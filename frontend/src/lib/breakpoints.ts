/** Single source of the breakpoint scale (DS-4); CSS `@media` widths must use these values. */
export const BREAKPOINTS = { sm: 680, md: 860, lg: 960, xl: 1240, '2xl': 1600 } as const;

export type Breakpoint = keyof typeof BREAKPOINTS;

/** Width just below a breakpoint: max-width ranges stop 0.02 px short of the next one. */
export const below = (px: number) => Number((px - 0.02).toFixed(2));

/** Mobile-first: viewport is at least the breakpoint. */
export const up = (breakpoint: Breakpoint) => `(min-width: ${BREAKPOINTS[breakpoint]}px)`;

/** Viewport is narrower than the breakpoint (the phone range for `md`, R1). */
export const down = (breakpoint: Breakpoint) => `(max-width: ${below(BREAKPOINTS[breakpoint])}px)`;
