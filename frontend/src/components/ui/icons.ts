/** Stroke icons on a 24x24 grid, as path data. Unit e extends this to the full set (DS-8). */
export const ICONS = {
  eye: ['M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z', 'M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6Z'],
  'eye-off': [
    'M9.9 5.2A10 10 0 0 1 12 5c6.4 0 10 7 10 7a17 17 0 0 1-3.2 4.1',
    'M6.1 6.6C3.4 8.4 2 12 2 12s3.6 7 10 7c1.5 0 2.9-.4 4.1-.9',
    'M9.9 9.9a3 3 0 0 0 4.2 4.2',
    'M3 3l18 18',
  ],
  warning: ['M12 3.5 2.5 20h19L12 3.5Z', 'M12 10v4.5', 'M12 17.4v.1'],
  'check-circle': ['M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Z', 'M8 12.4l2.8 2.8L16.2 9.8'],
} as const satisfies Record<string, readonly string[]>;

export type IconName = keyof typeof ICONS;
