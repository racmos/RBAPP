/**
 * Stroke icons on a 24x24 grid, as path data (DS-8): the 47 icons of the prototype plus the
 * ones the shell needs. Shapes of the prototype (`rect`, `circle`) are written as paths by the
 * two helpers so every icon is just a list of `d` strings.
 */
const round = (value: number) => +value.toFixed(2);

/** A rectangle, with rounded corners when `r` is given. */
const rect = (x: number, y: number, w: number, h: number, r = 0): string => {
  if (!r) return `M${x} ${y}h${w}v${h}h${-w}z`;
  const side = (length: number) => round(length - 2 * r);
  return [
    `M${round(x + r)} ${y}`,
    `h${side(w)}`,
    `a${r} ${r} 0 0 1 ${r} ${r}`,
    `v${side(h)}`,
    `a${r} ${r} 0 0 1 ${-r} ${r}`,
    `h${-side(w)}`,
    `a${r} ${r} 0 0 1 ${-r} ${-r}`,
    `v${-side(h)}`,
    `a${r} ${r} 0 0 1 ${r} ${-r}z`,
  ].join('');
};

const circle = (cx: number, cy: number, r: number): string =>
  `M${round(cx - r)} ${cy}a${r} ${r} 0 1 0 ${round(2 * r)} 0a${r} ${r} 0 1 0 ${round(-2 * r)} 0`;

export const ICONS = {
  // navigation and modules
  dashboard: [
    rect(3, 3, 7, 9, 1.3),
    rect(14, 3, 7, 5, 1.3),
    rect(14, 12, 7, 9, 1.3),
    rect(3, 16, 7, 5, 1.3),
  ],
  cards: [rect(3, 5, 13, 16, 2), 'M8 2.5l11 3a2 2 0 0 1 1.4 2.4L18 18'],
  collection: [rect(3, 4, 18, 16, 2), 'M3 9h18M8 4v16'],
  decks: ['M4 7l8-4 8 4-8 4-8-4z', 'M4 12l8 4 8-4M4 17l8 4 8-4'],
  sales: ['M3 3v18h18', 'M7 14l3-4 3 3 4-6'],
  stats: ['M4 20V10M10 20V4M16 20v-7M22 20H2'],
  calendar: [rect(3, 4.5, 18, 16.5, 2), 'M3 9.5h18M8 2.5v4M16 2.5v4'],
  // actions
  search: [circle(11, 11, 7), 'M21 21l-4-4'],
  filter: ['M3 5h18l-7 8v6l-4-2v-4z'],
  image: [rect(3, 3, 18, 18, 2), circle(8.5, 8.5, 1.5), 'M21 16l-5-5-7 7'],
  export: ['M12 3v12M8 7l4-4 4 4', 'M4 15v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4'],
  trash: ['M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13'],
  plus: ['M12 5v14M5 12h14'],
  minus: ['M5 12h14'],
  edit: ['M4 20h4l11-11a2 2 0 0 0-3-3L5 17z'],
  check: ['M5 12l4 4 10-10'],
  close: ['M6 6l12 12M18 6L6 18'],
  menu: ['M3 6h18M3 12h18M3 18h18'],
  arrow: ['M5 12h14M13 6l6 6-6 6'],
  refresh: ['M20 12a8 8 0 1 1-2.4-5.7M20 4v4h-4'],
  copy: [rect(9, 9, 11, 11, 2), 'M5 15V5a2 2 0 0 1 2-2h8'],
  link: ['M9.5 14.5l5-5M10.5 6.5l1-1a4 4 0 0 1 5.7 5.7l-1 1M13.5 17.5l-1 1a4 4 0 0 1-5.7-5.7l1-1'],
  logout: ['M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3', 'M10 12H3M6 8l-3 4 3 4'],
  // things
  tag: ['M3 11l8-8 9 9-8 8z', circle(8, 8, 1.4)],
  star: ['M12 3l2.5 5.5L20 9l-4 4 1 6-5-3-5 3 1-6-4-4 5.5-.5z'],
  grid: [
    rect(3, 3, 7, 7, 1.3),
    rect(14, 3, 7, 7, 1.3),
    rect(3, 14, 7, 7, 1.3),
    rect(14, 14, 7, 7, 1.3),
  ],
  list: ['M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01'],
  coin: [circle(12, 12, 9), 'M12 7v10M9.5 9.5h3a1.5 1.5 0 0 1 0 3h-1a1.5 1.5 0 0 0 0 3h3'],
  gift: [
    'M4 9h16v3H4zM5 12v8h14v-8M12 9v11M12 9c-1-2.5-2.6-4-4.2-4a2 2 0 0 0 0 4zM12 9c1-2.5 2.6-4 4.2-4a2 2 0 0 1 0 4z',
  ],
  card: [rect(2.5, 5, 19, 14, 2), 'M2.5 10h19M6 15h4'],
  mail: [rect(3, 5, 18, 14, 2), 'M3.5 7l8.5 6 8.5-6'],
  lock: [rect(4.5, 11, 15, 9, 2), 'M8 11V8a4 4 0 0 1 8 0v3'],
  key: [circle(8, 15, 4), 'M11 12l8.5-8.5M16.5 6l2.5 2.5'],
  camera: [rect(3, 7, 18, 13, 2.5), 'M8.5 7l1.6-2.6h3.8L15.5 7', circle(12, 13.5, 3.4)],
  device: [rect(3, 4, 18, 12, 2), 'M8.5 20h7M12 16v4'],
  globe: [circle(12, 12, 9), 'M3 12h18M12 3a14 14 0 0 1 0 18 14 14 0 0 1 0-18z'],
  pin: ['M12 21s7-6.3 7-11a7 7 0 1 0-14 0c0 4.7 7 11 7 11z', circle(12, 10, 2.6)],
  clock: [circle(12, 12, 9), 'M12 7v5l3.5 2'],
  ticket: [
    'M3 8a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2 2 2 0 0 0 0 4 2 2 0 0 1-2 2H5a2 2 0 0 1-2-2 2 2 0 0 0 0-4z',
    'M15 6v12',
  ],
  bookmark: ['M6 4h12v16l-6-4-6 4z'],
  trophy: [
    'M7 4h10v4a5 5 0 0 1-10 0z',
    'M7 5H4v1.5A3.5 3.5 0 0 0 7 10M17 5h3v1.5A3.5 3.5 0 0 1 17 10M9 13.5h6M12 13.5V18M8.5 21h7',
  ],
  // people and account
  account: [circle(12, 8, 4), 'M4.5 20c0-4 3.5-6.2 7.5-6.2S19.5 16 19.5 20'],
  users: [
    circle(9, 8, 3.4),
    'M3.5 20c0-3.3 2.6-5.2 5.5-5.2s5.5 1.9 5.5 5.2',
    'M16 5.2a3.4 3.4 0 0 1 0 6.5M17.5 14.8c2.4.5 4 2.3 4 5.2',
  ],
  shield: ['M12 3l8 3v5.5c0 4.6-3.3 7.9-8 9.2-4.7-1.3-8-4.6-8-9.2V6z'],
  sliders: ['M4 7h16M4 12h16M4 17h16', circle(9, 7, 2.3), circle(15, 12, 2.3), circle(7, 17, 2.3)],
  // visibility
  eye: ['M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z', 'M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6Z'],
  'eye-off': [
    'M9.9 5.2A10 10 0 0 1 12 5c6.4 0 10 7 10 7a17 17 0 0 1-3.2 4.1',
    'M6.1 6.6C3.4 8.4 2 12 2 12s3.6 7 10 7c1.5 0 2.9-.4 4.1-.9',
    'M9.9 9.9a3 3 0 0 0 4.2 4.2',
    'M3 3l18 18',
  ],
  // the shell's own
  more: ['M5 12h.01M12 12h.01M19 12h.01'],
  install: ['M12 4v11M8 11l4 4 4-4', 'M5 19h14'],
  warning: ['M12 3.5 2.5 20h19L12 3.5Z', 'M12 10v4.5', 'M12 17.4v.1'],
  offline: [
    'M3 3l18 18',
    'M8.5 16.5a5 5 0 0 1 7 0',
    'M5 12.9a10 10 0 0 1 5-2.6M19 12.9a10 10 0 0 0-4.5-2.5',
    'M12 20h.01',
  ],
  settings: [
    circle(12, 12, 3),
    'M12 2.5l1.6 2.2 2.7-.5.9 2.6 2.6.9-.5 2.7 2.2 1.6-2.2 1.6.5 2.7-2.6.9-.9 2.6-2.7-.5L12 21.5l-1.6-2.2-2.7.5-.9-2.6-2.6-.9.5-2.7L2.5 12l2.2-1.6-.5-2.7 2.6-.9.9-2.6 2.7.5z',
  ],
  info: [circle(12, 12, 9), 'M12 11v5', 'M12 8h.01'],
  'external-link': [
    'M14 4h6v6',
    'M20 4l-9 9',
    'M18 14v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4',
  ],
  'check-circle': [circle(12, 12, 9), 'M8 12.4l2.8 2.8L16.2 9.8'],
} as const satisfies Record<string, readonly string[]>;

export type IconName = keyof typeof ICONS;
