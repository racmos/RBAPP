import { readStorage, removeStorage, writeStorage } from '@/lib/storage';

/** A non-sensitive flag: "this browser had a signed-in session" (offline boot, PWA-7). */
const HINT_KEY = 'rb_was_signed_in';

export const hasSignedInHint = (): boolean => readStorage(HINT_KEY) === '1';
export const setSignedInHint = (): void => writeStorage(HINT_KEY, '1');
export const clearSignedInHint = (): void => removeStorage(HINT_KEY);
