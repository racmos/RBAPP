import { ApiError } from '@/api/errors';

/** The ways the re-authentication dialog can confirm the user (F9-j S3; OAuth comes in F9-g). */
export type ReauthMethod = 'password' | 'totp';
const KNOWN: readonly ReauthMethod[] = ['password', 'totp'];

/** The user closed the re-authentication dialog: callers ignore it (no toast, no alert). */
export class ReauthCancelled extends Error {
  constructor() {
    super('reauth_cancelled');
    this.name = 'ReauthCancelled';
  }
}

export const isReauthCancelled = (error: unknown): error is ReauthCancelled =>
  error instanceof ReauthCancelled;

export const isReauthRequired = (error: unknown): error is ApiError =>
  error instanceof ApiError && error.code === 'reauth_required';

/** The methods of a `reauth_required` answer (`params.methods`) the dialog can offer, in order. */
export function reauthMethods(error: ApiError): ReauthMethod[] {
  const raw: unknown = (error.params as Record<string, unknown> | null)?.methods;
  const listed = Array.isArray(raw) ? raw : [];
  return KNOWN.filter((method) => listed.includes(method));
}

/** Opens the dialog; resolves after a successful `POST /me/reauth`, rejects on cancel. */
export type AskReauth = (methods: ReauthMethod[]) => Promise<void>;

/**
 * Run `action`; when it answers `reauth_required`, ask the user to confirm it's them and run it
 * **once more** (F9-j S2). A second `reauth_required` goes to `onRepeat` (an error toast) and
 * rejects with `ReauthCancelled`, so there is no loop. Any other failure reaches the caller.
 */
export async function withReauth<T>(
  action: () => Promise<T>,
  ask: AskReauth,
  onRepeat: (error: ApiError) => void,
): Promise<T> {
  try {
    return await action();
  } catch (error) {
    if (!isReauthRequired(error)) throw error;
    const methods = reauthMethods(error);
    // No method this screen can offer (an OAuth-only account before F9-g): say so, no dialog.
    if (methods.length === 0) {
      onRepeat(error);
      throw new ReauthCancelled();
    }
    await ask(methods);
  }
  try {
    return await action();
  } catch (error) {
    if (!isReauthRequired(error)) throw error;
    onRepeat(error);
    throw new ReauthCancelled();
  }
}
