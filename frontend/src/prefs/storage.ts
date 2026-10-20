import { readStorage, writeStorage } from '@/lib/storage';
import { EMPTY_PREFS, sanitizePrefs } from './domain';
import type { Prefs } from './types';

/** localStorage key of the copy of the account preferences (PREF-7, R4). */
export const MIRROR_KEY = 'rb_prefs_v1';

/** The last known preferences, `null` (Auto) kept; a missing or damaged mirror is the empty one. */
export function readMirror(): Prefs {
  const stored = readStorage(MIRROR_KEY);
  if (stored === null) return { ...EMPTY_PREFS };
  try {
    return sanitizePrefs(JSON.parse(stored));
  } catch {
    return { ...EMPTY_PREFS };
  }
}

/** Store exactly the five fields (the argument may carry more, for example from a payload). */
export function writeMirror(prefs: Prefs): void {
  writeStorage(MIRROR_KEY, JSON.stringify(sanitizePrefs(prefs)));
}
