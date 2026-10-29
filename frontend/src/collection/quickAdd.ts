import { readStorage, writeStorage } from '@/lib/storage';

/** The add sheet's last choices, for this browser session only (never in the URL). */
export const QUICK_ADD_KEY = 'rb_quick_add_v1';

export type QuickAddChoices = {
  set: string | null;
  foil: boolean;
  qty: number;
  condition: string | null;
  language: string | null;
  purchase_price: number | null;
  selling: boolean;
};

export const DEFAULT_CHOICES: QuickAddChoices = {
  set: null,
  foil: false,
  qty: 1,
  condition: null,
  language: null,
  purchase_price: null,
  selling: false,
};

const text = (value: unknown): string | null =>
  typeof value === 'string' && value !== '' ? value : null;

/** Reads the stored choices; anything unreadable or out of range falls back to its default. */
export function readChoices(): QuickAddChoices {
  const raw = readStorage(QUICK_ADD_KEY, 'session');
  if (!raw) return DEFAULT_CHOICES;
  let stored: unknown;
  try {
    stored = JSON.parse(raw);
  } catch {
    return DEFAULT_CHOICES;
  }
  if (typeof stored !== 'object' || stored === null) return DEFAULT_CHOICES;
  const value = stored as Record<string, unknown>;
  const { qty, purchase_price: price } = value;
  return {
    set: text(value.set),
    foil: value.foil === true,
    qty: typeof qty === 'number' && Number.isInteger(qty) && qty >= 1 && qty <= 9999 ? qty : 1,
    condition: text(value.condition),
    language: text(value.language),
    purchase_price:
      typeof price === 'number' && Number.isFinite(price) && price >= 0 ? price : null,
    selling: value.selling === true,
  };
}

export function writeChoices(choices: QuickAddChoices): void {
  writeStorage(QUICK_ADD_KEY, JSON.stringify(choices), 'session');
}
