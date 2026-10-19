type Area = 'local' | 'session';

/** `window.localStorage`/`sessionStorage` can throw (blocked, private mode): callers never see it. */
const area = (kind: Area): Storage =>
  kind === 'local' ? window.localStorage : window.sessionStorage;

export function readStorage(key: string, kind: Area = 'local'): string | null {
  try {
    return area(kind).getItem(key);
  } catch {
    return null;
  }
}

export function writeStorage(key: string, value: string, kind: Area = 'local'): void {
  try {
    area(kind).setItem(key, value);
  } catch {
    // Storage is a convenience (language, hint); losing a write is not an error.
  }
}

export function removeStorage(key: string, kind: Area = 'local'): void {
  try {
    area(kind).removeItem(key);
  } catch {
    // See writeStorage.
  }
}
